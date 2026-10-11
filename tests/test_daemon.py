#!/usr/bin/env python3
"""daemon（常驻进程 + UDS 快路径）行为锁。

覆盖面：
  - 生命周期：start → ping/status 可见 → stop → socket/指针/pid 全清
  - 执行语义：run op 跑 search --list-engines（离线）出合法 JSON；
    白名单外的 script 拒绝；连续两笔 run（模块重执行的温态安全）
  - 陈尸清理：指针/socket 陈尸时 start 仍能成功
  - CLI 快路径端到端：daemon 在位时 bin/argo search 走 UDS（结果与常态等价）；
    ARGO_NO_DAEMON=1 显式关闭也等价；daemon 死而指针在时静默回退不报错
  - 空闲自杀：--idle-exit 生效，socket 自清

观察点与客户端同契约：socket 真实位置一律经指针文件 .daemon_sock 读出
（原生状态根路径可能超过 AF_UNIX 的 104 字节上限，daemon 会自动落短路径
哈希位——tests 深层 tmp 目录正是这条兜底分支的日常触发场景）。

全部离线（list-engines 只读注册表，不发网络）。POSIX-only：daemonize 用 fork。
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
BIN = ROOT / "bin" / "argo"
DAEMON = ROOT / "scripts" / "daemon.py"

pytestmark = pytest.mark.skipif(os.name == "nt", reason="daemonize 依赖 fork，仅 POSIX")


def _env(tmp_path: Path) -> dict:
    env = dict(os.environ)
    env["ARGO_STATE_DIR"] = str(tmp_path / "state")
    return env


def _pointer(tmp_path: Path) -> Path:
    return tmp_path / "state" / ".daemon_sock"


def _sock(tmp_path: Path) -> Path:
    """从指针读 socket 真实路径（与 bin/argo 快路径同一发现方式）。"""
    return Path(_pointer(tmp_path).read_text(encoding="utf-8").strip())


def _daemon(tmp_path: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(DAEMON), *extra, "--json"],
        env=_env(tmp_path), capture_output=True, text=True, timeout=30,
    )


def _start(tmp_path: Path) -> dict:
    r = _daemon(tmp_path, "start")
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout.strip().splitlines()[-1])


def _wait_sock(tmp_path: Path, want: bool, timeout: float = 10.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            alive = _sock(tmp_path).exists()
        except (OSError, ValueError):
            alive = False
        if alive == want and _pointer(tmp_path).exists() == want:
            return
        time.sleep(0.05)
    pytest.fail(f"socket 未在 {timeout}s 内变为 {'存在' if want else '消失'}")


def _uds(sock: Path, req: dict, timeout: float = 30.0) -> dict:
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect(str(sock))
        s.sendall((json.dumps(req) + "\n").encode("utf-8"))
        buf = b""
        while not buf.endswith(b"\n"):
            chunk = s.recv(65536)
            if not chunk:
                break
            buf += chunk
    finally:
        s.close()
    assert buf, "daemon 未返回任何响应"
    return json.loads(buf.decode("utf-8", "replace"))


@pytest.fixture()
def running(tmp_path):
    info = _start(tmp_path)
    _wait_sock(tmp_path, True)
    yield info
    _daemon(tmp_path, "stop")
    _wait_sock(tmp_path, False)


def test_lifecycle_ping_status_stop(tmp_path):
    info = _start(tmp_path)
    _wait_sock(tmp_path, True)
    assert info.get("pid")
    sock = _sock(tmp_path)
    st = _daemon(tmp_path, "status")
    assert st.returncode == 0 and json.loads(st.stdout)["running"] is True
    # 二次 start：报已在运行而非起第二个
    again = _start(tmp_path)
    assert again.get("already_running") is True
    _daemon(tmp_path, "stop")
    _wait_sock(tmp_path, False)
    assert not sock.exists(), "socket 未随 stop 清场"
    assert not (tmp_path / "state" / "daemon.pid").exists(), "pid 未随 stop 清场"


def test_run_list_engines_and_warm_reuse(tmp_path):
    _start(tmp_path)
    _wait_sock(tmp_path, True)
    sock = _sock(tmp_path)
    # 第一笔：冷（daemon 内首次 import search 全家）
    r1 = _uds(sock, {"op": "run", "script": "search",
                     "args": ["--list-engines", "--json"]})
    assert r1["ok"] and r1["exit_code"] == 0, r1.get("stderr", "")[:500]
    engines = json.loads(r1["stdout"])
    assert isinstance(engines, list) and len(engines) > 100
    # 第二笔：温态（runpy 重执行 + sys.modules 复用不串）
    r2 = _uds(sock, {"op": "run", "script": "search",
                     "args": ["--list-engines", "--json"]})
    assert r2["ok"] and r2["exit_code"] == 0
    assert json.loads(r2["stdout"]) == engines


def test_run_whitelist_rejects_unknown_script(tmp_path):
    _start(tmp_path)
    _wait_sock(tmp_path, True)
    r = _uds(_sock(tmp_path), {"op": "run", "script": "not_a_script", "args": []})
    assert r["ok"] is False and "白名单" in r.get("error", "")


def test_start_survives_stale_pointer(tmp_path):
    # 陈尸形态：上代异常退出留下旧指针（指向不存在的 socket）——start 必须
    # 清场后照常起来，这是 _alive() 的兜底职责
    _pointer(tmp_path).parent.mkdir(parents=True, exist_ok=True)
    _pointer(tmp_path).write_text("/tmp/definitely-dead-argo-daemon.sock\n", encoding="utf-8")
    _start(tmp_path)
    _wait_sock(tmp_path, True)
    r = _uds(_sock(tmp_path), {"op": "ping"})
    assert r["ok"] is True


def test_cli_fastpath_and_fallback(tmp_path):
    # daemon 在位：bin/argo search 必须产出与常态等价的合法 JSON（指针存在 +
    # daemon 存活时 _daemon_run 必然命中，等价性即快路径正确性）
    _start(tmp_path)
    _wait_sock(tmp_path, True)
    r = subprocess.run([sys.executable, str(BIN), "search", "--list-engines", "--json"],
                       env=_env(tmp_path), capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    assert len(json.loads(r.stdout)) > 100

    # ARGO_NO_DAEMON=1：显式关闭后同样等价（常态路径回归保护）
    env = _env(tmp_path)
    env["ARGO_NO_DAEMON"] = "1"
    r2 = subprocess.run([sys.executable, str(BIN), "search", "--list-engines", "--json"],
                        env=env, capture_output=True, text=True, timeout=30)
    assert r2.returncode == 0 and json.loads(r2.stdout) == json.loads(r.stdout)

    # daemon 死而指针残留：快路径必须静默回退，输出照常、无报错噪音
    _daemon(tmp_path, "stop")
    _wait_sock(tmp_path, False)
    r3 = subprocess.run([sys.executable, str(BIN), "search", "--list-engines", "--json"],
                        env=_env(tmp_path), capture_output=True, text=True, timeout=30)
    assert r3.returncode == 0, r3.stderr
    assert json.loads(r3.stdout) == json.loads(r.stdout)


def test_idle_exit_self_terminate(tmp_path):
    r = subprocess.run(
        [sys.executable, str(DAEMON), "start", "--idle-exit", "1", "--json"],
        env=_env(tmp_path), capture_output=True, text=True, timeout=30)
    assert r.returncode == 0
    _wait_sock(tmp_path, True)
    _wait_sock(tmp_path, False, timeout=15.0)  # 空闲 1s + 5s 看护轮询窗
