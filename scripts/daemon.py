#!/usr/bin/env python3
"""daemon.py — argo 常驻进程：把每次 CLI 调用的固定成本变成本次 UDS 往返。

背景（2026-10-11 实测，见仓库外分析底稿）：一次 web 搜索 ~800ms 里，
dispatch（引擎网络等待）占 97%；真正的 Python 计算只有几十毫秒。但**每次
CLI 调用都要重付一遍「解释器启动 + 重模块 import」约 85–100ms**——engines
全家（builders/urllib/http）26ms、search_entry 9.9ms、recovery 2.8ms……
agent 循环里一次研究任务调 15–20 次 argo，这笔固定成本就放大成 1.5–2s。

对照 OpenAI Habitat（Python→Rust）案例的结论是：argo 的可省成本来自
「每次调用的固定开销」，不是 Python 语言本身——所以正解是常驻进程把
import 付一次，而不是重写语言。收益相同，成本差两个数量级。

设计：
  - 协议：UDS 上逐连接一行 JSON 请求 / 一行 JSON 响应（stdlib socket，无新依赖）
  - 执行：runpy.run_module 复刻 bin/argo 的原地执行语义（sys.argv 置换 +
    stdout/stderr 重定向捕获），daemon 与 CLI 的行为严格同源
  - 串行：请求执行持全局锁。原因：redirect_stdout 是进程级全局态，并发
    会串流；且 argo 内部本就高并发（并行效率 >1），CLI 层串行不损吞吐。
    连接接受与响应发送仍在多线程——排队不阻塞心跳/停止。
  - 快路径：bin/argo 侧零 import 直连（socket 指针文件 `.daemon_sock` 落在
    bin/argo 可预测的缓存根下，解耦 argo_paths 的深层解析）
  - 生命周期：`argo daemon start|status|stop|restart`；空闲 --idle-exit 秒
    自杀（默认 1800），不留僵尸；SIGTERM 同样清场
  - 安全：socket chmod 0600（UDS 连接权限跟随文件权限，默认 umask 会放出
    0755 让同机其他用户连上）；只放行白名单脚本

第一笔 run 请求会多付 ~100ms（search 全家首次 import），此后全部热路径。
daemon 自身启动刻意轻：只 import argo_paths/engine_env，不预热引擎栈。

运行：
  python3 scripts/daemon.py start [--foreground] [--idle-exit 1800] [--json]
  python3 scripts/daemon.py status [--json]
  python3 scripts/daemon.py stop [--json]
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import runpy
import signal
import socket
import sys
import threading
import time

SCRIPTS_DIR = os.path.dirname(os.path.realpath(__file__))
ARGO_HOME = os.path.dirname(SCRIPTS_DIR)
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from argo_paths import state_path, state_root  # noqa: E402

SOCK_NAME = "daemon.sock"
PID_NAME = "daemon.pid"
LOG_NAME = "daemon.log"
POINTER_NAME = ".daemon_sock"  # 指针文件：落 bin/argo 可预测的缓存根，内容=真实 socket 路径
MAX_REQ_BYTES = 1 << 20  # 单请求上限 1MB（args 很小，此值纯防失控）

# 可执行脚本白名单（键=客户端传的 script 名，值=runpy 模块名）。
# 与 bin/argo.scripts 同源收窄：daemon 只收 CLI 映射表里真实存在的目标，
# 客户端 v1 只路由 search；表先备全，后续放行只需在此加行 + bin/argo 改路由。
RUNNABLE = {
    "search": "search",
}


def _cache_root() -> str:
    """bin/argo 可预测的缓存根（与 bin/argo._default_cache_root 同一逻辑）。

    指针文件必须落在客户端**不 import 任何模块**就能算出的位置——entrypoint
    的零 import 纪律不可破，所以这里反向迁就它的简化解析（env → XDG → 历史
    目录），而不是客户端迁就 argo_paths 的完整解析（config.yaml db_path 分支
    客户端不读 yaml 就算不出来）。两边不一致时快路径静默失效退回常态执行，
    不会错。
    """
    # ARGO_STATE_DIR 与 bin/argo 的 _PY_CACHE 同一优先级：env 覆盖是测试隔离
    # 的硬开关，指针文件必须跟 socket 一起落进被隔离的根，两端才对得上。
    env_dir = os.environ.get("ARGO_STATE_DIR", "").strip()
    if env_dir:
        return env_dir
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        return os.path.join(base, "unified-search")
    xdg = os.environ.get("XDG_CACHE_HOME", "").strip()
    if xdg:
        return os.path.join(xdg, "unified-search")
    return os.path.expanduser("~/.cache/unified-search")


def _sock_path() -> str:
    """socket 路径：默认与状态根同目录；超长时落短路径哈希位。

    macOS/Linux 的 AF_UNIX 路径上限是 104 字节（sun_path），pytest 的深层
    临时目录、或用户把 ARGO_STATE_DIR 挪进深嵌套目录时，原生路径会超——
    实测 bind 直接 OSError「AF_UNIX path too long」。此时退到
    /tmp/argo-daemon-<uid>/<state_root 哈希>.sock：目录 0700 保用户隔离，
    哈希保不同状态根互不冲突；可预测性由指针文件承担（客户端只读指针，
    不算 socket 路径），所以这里怎么挪都不影响两端契约。
    """
    native = str(state_path(SOCK_NAME))
    if os.name == "nt" or len(native.encode("utf-8")) <= 100:
        return native
    import hashlib
    h = hashlib.sha1(str(state_root()).encode("utf-8")).hexdigest()[:10]
    d = f"/tmp/argo-daemon-{os.getuid()}"
    return os.path.join(d, f"{h}.sock")


def _pointer_path() -> str:
    return os.path.join(_cache_root(), POINTER_NAME)


def _pid_path() -> str:
    return str(state_path(PID_NAME))


def _pid_is_daemon(pid: int) -> bool:
    """核实 pid 的命令行确实是本 daemon（macOS/Linux ps，Windows 视为不是）。

    误杀的代价不对称：漏杀只是留一个下次 start 时 ping 不到、自己会空闲退出的
    进程；错杀是 SIGTERM 一个无关进程。所以判据从紧——ps 拿不到或不像就放弃。
    """
    if os.name == "nt":
        return False
    import subprocess
    try:
        r = subprocess.run(["ps", "-p", str(pid), "-o", "command="],
                           capture_output=True, text=True, timeout=5,
                           encoding="utf-8", errors="replace")
        return "daemon.py" in (r.stdout or "")
    except Exception:
        return False


def _log_path() -> str:
    return str(state_path(LOG_NAME))


def _atomic_write(path: str, text: str) -> None:
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    tmp = f"{path}.tmp.{os.getpid()}"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


# ── 状态查询 ────────────────────────────────────────────────────────────────


def ping(sock_path: str, timeout: float = 1.0) -> dict:
    """对 socket 发 ping；活着返回响应 dict，死了抛 OSError。"""
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect(sock_path)
        s.sendall(b'{"op":"ping"}\n')
        buf = b""
        while not buf.endswith(b"\n"):
            chunk = s.recv(65536)
            if not chunk:
                break
            buf += chunk
        return json.loads(buf.decode("utf-8", "replace"))
    finally:
        s.close()


def _alive() -> dict | None:
    """daemon 存活则返回 ping 响应，否则 None（顺带清陈尸 socket/指针）。"""
    sp = _sock_path()
    if not os.path.exists(sp):
        return None
    try:
        return ping(sp)
    except Exception:
        with contextlib.suppress(OSError):
            os.unlink(sp)
        with contextlib.suppress(OSError):
            os.unlink(_pointer_path())
        return None


# ── 请求执行 ────────────────────────────────────────────────────────────────

_EXEC_LOCK = threading.Lock()


def _run_request(req: dict) -> dict:
    """执行一笔 run 请求：与 bin/argo 原地路径严格同语义。

    run_module 而非直接调 main()：与 bin/argo 的 runpy 路径一字不差，脚本
    的 `if __name__ == "__main__"` / argparse / sys.exit 语义原样生效。代价
    是每次重执行脚本顶层（__pycache__ 命中下 ~几 ms）——相对引擎 RTT 可忽略，
    换来的是零特判的「和 CLI 完全一样」。
    """
    script = req.get("script")
    module = RUNNABLE.get(script or "")
    args = req.get("args") or []
    if module is None:
        return {"ok": False, "error": f"script 不在白名单: {script!r}"}
    if not isinstance(args, list) or not all(isinstance(a, str) for a in args):
        return {"ok": False, "error": "args 必须是字符串列表"}

    script_path = os.path.join(SCRIPTS_DIR, f"{script}.py")
    t0 = time.perf_counter()
    out, err = io.StringIO(), io.StringIO()
    code = 0
    old_argv, old_cwd = sys.argv, os.getcwd()
    with _EXEC_LOCK:
        try:
            cwd = req.get("cwd")
            if cwd and os.path.isdir(cwd):
                os.chdir(cwd)
            sys.argv = [script_path] + args
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                try:
                    runpy.run_module(module, run_name="__main__")
                except SystemExit as e:
                    # 与 CLI 退出码契约一致：None/0 → 0，整数原样，其余 → 1
                    code = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
        except BaseException as e:  # 引擎栈漏出的非 SystemExit：按 CLI 语义退出码 1
            code = 1
            err.write(f"\n[daemon] {type(e).__name__}: {e}\n")
        finally:
            sys.argv = old_argv
            with contextlib.suppress(OSError):
                os.chdir(old_cwd)
    return {
        "ok": True,
        "exit_code": code,
        "stdout": out.getvalue(),
        "stderr": err.getvalue(),
        "took_ms": round((time.perf_counter() - t0) * 1000, 1),
    }


# ── 服务循环 ────────────────────────────────────────────────────────────────


class _Server:
    def __init__(self, idle_exit_s: float) -> None:
        self.idle_exit_s = idle_exit_s
        self.stop_evt = threading.Event()
        self.active = 0
        self.active_lock = threading.Lock()
        self.last_activity = time.monotonic()

    def handle(self, conn: socket.socket) -> None:
        with self.active_lock:
            self.active += 1
        try:
            conn.settimeout(300)
            buf = b""
            while not buf.endswith(b"\n") and len(buf) < MAX_REQ_BYTES:
                chunk = conn.recv(65536)
                if not chunk:
                    break
                buf += chunk
            resp: dict = {"ok": False, "error": "空请求"}
            if buf.strip():
                try:
                    req = json.loads(buf.decode("utf-8", "replace"))
                    op = req.get("op")
                    if op == "ping":
                        resp = {"ok": True, "pid": os.getpid(),
                                "uptime_s": round(time.monotonic() - self.last_activity, 1)}
                    elif op == "stop":
                        resp = {"ok": True, "stopping": True}
                        self.stop_evt.set()
                    elif op == "run":
                        self.last_activity = time.monotonic()
                        resp = _run_request(req)
                        self.last_activity = time.monotonic()
                    else:
                        resp = {"ok": False, "error": f"未知 op: {op!r}"}
                except Exception as e:
                    resp = {"ok": False, "error": f"{type(e).__name__}: {e}"}
            conn.sendall((json.dumps(resp, ensure_ascii=False) + "\n").encode("utf-8"))
        except OSError:
            pass  # 客户端超时先走：响应丢弃即可，引擎侧照常完成
        finally:
            with contextlib.suppress(OSError):
                conn.close()
            with self.active_lock:
                self.active -= 1

    def serve_forever(self) -> None:
        sp = _sock_path()
        # bind 前建目录：UDS bind 会在 socket 路径上落文件，目录不存在即
        # FileNotFoundError（测试隔离/新机器首次启动必踩——上一版就栽在这）
        d = os.path.dirname(sp)
        if d:
            os.makedirs(d, exist_ok=True)
        if d.startswith("/tmp/argo-daemon-"):
            os.chmod(d, 0o700)  # 短路径位落在共享 /tmp：目录必须锁回本用户
        listen_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            listen_sock.bind(sp)
        except OSError as e:
            # 父进程只能看到「启动超时」，死因必须自己写进日志
            print(f"[daemon] bind 失败 {sp}: {e}", flush=True)
            raise
        os.chmod(sp, 0o600)  # UDS 连接权限=文件权限；默认 umask 会放出组/其他可连
        listen_sock.listen(16)
        _atomic_write(_pid_path(), f"{os.getpid()}\n")
        _atomic_write(_pointer_path(), sp + "\n")

        def _cleanup() -> None:
            with contextlib.suppress(OSError):
                listen_sock.close()
            for p in (_sock_path(), _pointer_path(), _pid_path()):
                with contextlib.suppress(OSError):
                    os.unlink(p)

        def _on_term(_sig, _frm) -> None:
            self.stop_evt.set()

        signal.signal(signal.SIGTERM, _on_term)
        signal.signal(signal.SIGINT, _on_term)

        def _watchdog() -> None:
            while not self.stop_evt.wait(5.0):
                if self.idle_exit_s > 0 and self.active == 0 \
                        and time.monotonic() - self.last_activity > self.idle_exit_s:
                    print(f"[daemon] 空闲 {self.idle_exit_s:.0f}s，自杀退出", flush=True)
                    self.stop_evt.set()

        threading.Thread(target=_watchdog, daemon=True).start()
        print(f"[daemon] pid={os.getpid()} socket={sp} 就绪", flush=True)
        try:
            listen_sock.settimeout(2.0)
            while not self.stop_evt.is_set():
                try:
                    conn, _ = listen_sock.accept()
                except socket.timeout:
                    continue
                threading.Thread(target=self.handle, args=(conn,), daemon=True).start()
            # stop 请求的响应要送达：等在途 handler 收尾（上限 1s）
            deadline = time.monotonic() + 1.0
            while time.monotonic() < deadline:
                with self.active_lock:
                    if self.active == 0:
                        break
                time.sleep(0.02)
        finally:
            _cleanup()
            print("[daemon] 已退出", flush=True)


# ── 子命令 ──────────────────────────────────────────────────────────────────


def _start(args: argparse.Namespace) -> int:
    alive = _alive()
    if alive:
        print(json.dumps({"ok": True, "already_running": True, **alive},
                         ensure_ascii=False) if args.json
              else f"argo daemon 已在运行 pid={alive.get('pid')}")
        return 0

    if args.foreground or os.name == "nt":  # Windows 无 fork：只支持前台
        _serve_child(args)
        return 0

    pid = os.fork()
    if pid > 0:
        # 父进程：等 socket 就绪后报告（子进程 bind 完成即视为成功）
        deadline = time.time() + 10
        while time.time() < deadline:
            try:
                info = ping(_sock_path(), 0.5)
                msg = {"ok": True, "pid": info.get("pid")}
                print(json.dumps(msg, ensure_ascii=False) if args.json
                      else f"argo daemon 已启动 pid={info.get('pid')} socket={_sock_path()}")
                return 0
            except Exception:
                time.sleep(0.05)
        print(json.dumps({"ok": False, "error": "启动超时", "log": _log_path()},
                         ensure_ascii=False) if args.json
              else f"argo daemon 启动超时，看日志：{_log_path()}", file=sys.stderr)
        return 1
    os.setsid()
    # 重定向 stdio 到日志：daemon 不再依赖终端（日志目录同样可能还不存在）
    log_dir = os.path.dirname(_log_path())
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
    log = open(_log_path(), "ab", buffering=0)
    os.dup2(log.fileno(), 0)
    os.dup2(log.fileno(), 1)
    os.dup2(log.fileno(), 2)
    with contextlib.suppress(OSError):
        log.close()
    _serve_child(args)
    return 0


def _serve_child(args: argparse.Namespace) -> None:
    try:
        from engine_env import sync_envfile_to_environ
        sync_envfile_to_environ()
    except Exception:
        pass  # env 文件读不到不拦 daemon：引擎侧按各自缺 key 的既有口径失败
    _Server(args.idle_exit).serve_forever()


def _stop(args: argparse.Namespace) -> int:
    sp = _sock_path()
    try:
        ping(sp, 1.0)
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(2.0)
        s.connect(sp)
        s.sendall(b'{"op":"stop"}\n')
        buf = b""
        while not buf.endswith(b"\n"):
            chunk = s.recv(65536)
            if not chunk:
                break
            buf += chunk
        s.close()
        deadline = time.time() + 5
        while time.time() < deadline and os.path.exists(sp):
            time.sleep(0.05)
        print(json.dumps({"ok": True, "stopped": True}, ensure_ascii=False) if args.json
              else "argo daemon 已停止")
        return 0
    except Exception:
        # socket 已死：靠 pid 文件兜底补刀，避免进程活着却没有入口的孤儿态。
        # kill 前先核实命令行确实是本 daemon——pid 文件可能陈旧，而 OS 的 pid
        # 会复用：裸 SIGTERM 一个恰好复用 pid 的无关进程是真实伤害。
        killed = None
        try:
            with open(_pid_path(), encoding="utf-8") as f:
                pid = int(f.read().strip())
            if _pid_is_daemon(pid):
                os.kill(pid, signal.SIGTERM)
                killed = pid
        except (OSError, ValueError):
            pass
        for p in (sp, _pointer_path(), _pid_path()):
            with contextlib.suppress(OSError):
                os.unlink(p)
        print(json.dumps({"ok": True, "stopped": True, "killed": killed},
                         ensure_ascii=False) if args.json else "argo daemon 已清理")
        return 0


def _status(args: argparse.Namespace) -> int:
    alive = _alive()
    payload = {"ok": True, "running": bool(alive), "socket": _sock_path(),
               "pid": (alive or {}).get("pid")}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        if alive:
            print(f"argo daemon 运行中 pid={alive.get('pid')} socket={_sock_path()}")
        else:
            print(f"argo daemon 未运行（socket={_sock_path()}）")
    return 0


def _cli() -> int:
    ap = argparse.ArgumentParser(description="argo 常驻 daemon（消 CLI 每次调用的启动+import 固定成本）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_start = sub.add_parser("start", help="启动 daemon（默认后台化）")
    p_start.add_argument("--foreground", action="store_true", help="前台运行（调试用）")
    p_start.add_argument("--idle-exit", type=float, default=1800.0,
                         help="空闲 N 秒后自杀退出；0=常驻不退（默认 1800）")
    for p in (p_start, sub.add_parser("status"), sub.add_parser("stop")):
        p.add_argument("--json", action="store_true", help="机器可读输出")
    args = ap.parse_args()
    if args.cmd == "start":
        return _start(args)
    if args.cmd == "stop":
        return _stop(args)
    return _status(args)


if __name__ == "__main__":
    raise SystemExit(_cli())
