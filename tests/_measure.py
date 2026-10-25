#!/usr/bin/env python3
"""_measure.py — 计时断言的唯一测量层（2026-10-24）。

## 为什么需要这一层

仓库里「和花多久有关」的用例红过太多次，每次修法都在调**阈值或估计量**，
而不是修**判据**：

* test_search_benchmark.py 的「同机同参不误报回归」红过三次（median-of-3 →
  min-of-5 → 阈值 15% → 30%），第四次实测依旧红（parallel_min_ms 56→123）；
* test_bounded_run.py 用 assertLess(dt, 0.2) 判定「宽限窗没白等」，空载机器
  上实测 0.243s 就红；
* 全仓同类断言 18 处，阈值 0.05～0.8s 各不相同，没有一处声明自己判的是什么。

共同错误：**把「机器有多忙」当成了「调度对不对」**。墙钟数字里混着 CPU 争用、
GC、Spotlight、CI 邻居；阈值调得再宽，也只改变「多久才红」，不改变红的时候
说不清是谁的错。

## 两种时钟，一个判据

* **虚拟时钟**（默认）：测试主线程的 ``fetch_sleep`` 推进虚拟时间、不真实阻塞，
  于是「单线程里的 A 等 50ms、B 再等 200ms」这类顺序因果被精确演算。
  子线程里的等待**不推进全局时钟**——让某个任务偷偷替主循环跳过宽限窗，
  正是旧写法的毛病（实测表现为「慢引擎反而先赢」）。
* **真实时钟**（ARGO_TEST_CLOCK=real）：同一套用例按真实墙钟跑，用来反证——
  虚拟模型的结论必须在真机上复现，否则说明模型与被测代码脱钩了。

## 判据：预算锚点，不是「看起来够小」

``task_deadline`` 声明某段代码的预算是多少；一次等待跨过锚点即抛
``VirtualDeadlineBreach``：这等于说「调度该收工的时候没收到工」。真实墙钟下
它同样会拖过头，只是拖多少取决于机器，所以以前只能靠阈值去猜。

并发场景（多个引擎各自等不同时长）的时序由用例用 ``DeterministicScheduler``
显式登记事件表达——**不在线程里抢全局时钟**。
"""

from __future__ import annotations

import functools
import os
import threading
import time
from contextlib import contextmanager
from typing import Any, Callable, Iterator

__all__ = [
    "clock", "is_simulated", "fetch_sleep", "sleep", "simulate", "reset",
    "task_deadline", "VirtualDeadlineBreach", "VirtualClockSink",
    "DeterministicScheduler", "run_schedule", "measure_latency", "real_time_ms",
]

ENV_CLOCK_MODE = "ARGO_TEST_CLOCK"

_real_time = time


class VirtualDeadlineBreach(AssertionError):
    """一次等待跨过了自己的预算锚点——调度没有及时收工。"""


class VirtualClockSink(AssertionError):
    """虚拟时间轴失控（单次推进过大）：通常是毫秒级等待误用了虚拟时钟。"""


class _SleepProxy:
    """真实模式下的 sleep：**运行期**转发到 time.sleep，使 mock.patch 生效。"""

    def __call__(self, seconds: float) -> None:
        time.sleep(seconds)


_REAL_SLEEP = _SleepProxy()

_CURRENT: list[float] = [0.0]
_DEADLINE: list[float | None] = [None]
# 单次推进上限：超过即判「误用虚拟时钟」或「给了分钟级假延迟」。
_SIM_CLOCK_SINK = 60.0


class DeterministicScheduler:
    """确定性调度器：把「并发等待」变成一条可精确演进的时间线。

        sched = DeterministicScheduler()
        sched.at(0.05, "fast", ["fast-result"])
        sched.at(1.50, "slow", ["slow-result"])
        timeline = sched.run(budget=1.0)     # 事件按到期时间顺序发生

    同一时刻按**登记顺序**处理，不依赖线程调度，因此同一用例在任何机器上
    得到同一条时间线。
    """

    def __init__(self) -> None:
        self._events: list[tuple[float, int, str, Any]] = []
        self._seq = 0
        self.now = 0.0

    def at(self, when: float, name: str, value: Any = None) -> "DeterministicScheduler":
        self._events.append((float(when), self._seq, name, value))
        self._seq += 1
        return self

    def run(self, budget: float, on_event: Callable[[str, Any], None] | None = None,
            *, stop_at: float | None = None) -> list[tuple[float, str, Any]]:
        """跑到 budget 为止；stop_at 模拟「提前收工」，之后的事件不再发生。"""
        self._events.sort(key=lambda e: (e[0], e[1]))
        limit = float(budget) if stop_at is None else min(float(budget), float(stop_at))
        timeline: list[tuple[float, str, Any]] = []
        for when, _seq, name, value in self._events:
            if when > limit + 1e-9:
                break
            self.now = when
            _CURRENT[0] = when
            timeline.append((when, name, value))
            if on_event is not None:
                on_event(name, value)
        self.now = limit
        _CURRENT[0] = limit
        return timeline


def run_schedule(budget: float, events: list[tuple[float, str, Any]],
                 on_event: Callable[[str, Any], None] | None = None,
                 *, stop_at: float | None = None) -> list[tuple[float, str, Any]]:
    """便捷入口：run_schedule(1.0, [(0.05, "fast", hits)])。"""
    sched = DeterministicScheduler()
    for ev in events:
        sched.at(*ev)
    return sched.run(budget, on_event, stop_at=stop_at)


def is_simulated() -> bool:
    """当前是否走虚拟时钟（默认是）。"""
    return os.environ.get(ENV_CLOCK_MODE, "sim").strip().lower() != "real"


def is_main_thread() -> bool:
    """当前是否在测试主线程（== 单线程被测代码，可以推进虚拟时钟）。"""
    return threading.current_thread() is threading.main_thread()


def clock() -> float:
    """被测代码读时间**只该用这个**（秒，单调）。"""
    if not is_simulated():
        return _real_time.monotonic()
    # 虚拟时间是**全局量**：子线程读它，才能看见主循环推进的进度。
    return _CURRENT[0]


def fetch_sleep(seconds: float, *, deadline: float | None = None) -> None:
    """被测代码「等一会儿」**只该用这个**。

    虚拟模式：测试主线程推进虚拟时钟并检查预算锚点；子线程只记账不推进
    （见模块头「两种时钟」）。真实模式：真的睡，锚点检查同样生效。
    """
    try:
        s = float(seconds)
    except (TypeError, ValueError):
        s = 0.0
    if s <= 0:
        return
    if deadline is None:
        deadline = _DEADLINE[0]
    if is_simulated():
        # 任何线程的等待都推进时间线：等待事件在业务时间上发生在 t+s。
        # 多线程**并发**场景不靠虚拟时钟演绎（线程间没有确定的先后），那些
        # 用例固定跑真实时钟——见 test_bounded_run.py 文件头与 _measure 模块头。
        _CURRENT[0] += s
        if _CURRENT[0] > _SIM_CLOCK_SINK + 1e-9:
            raise VirtualClockSink(
                f"虚拟时间轴失控：一次推进到 {_CURRENT[0]:.1f}s"
                f"（本次等 {s:.3f}s）。多半是毫秒级等待误用了虚拟时钟，"
                "或测试给了分钟级假延迟。")
        crossed = _CURRENT[0]
    else:
        _REAL_SLEEP(s)
        crossed = _real_time.monotonic()
    if deadline is not None and crossed > float(deadline) + 1e-9:
        raise VirtualDeadlineBreach(
            f"等待越过预算锚点：{crossed:.3f}s > 截止 {float(deadline):.3f}s"
            f"（本次等 {s:.3f}s）")


# 用例里的「等一会儿」：与被测代码同一个时钟
sleep = fetch_sleep


def poll_wait(seconds: float, evt: Any = None, *, since: float | None = None,
              timeout: float | None = None) -> None:
    """被测代码轮询循环里的**节拍**（不是业务等待）。

    真实模式：``evt.wait(seconds)``；虚拟模式：只让出极短真实时间给刚启动的
    线程（否则「线程已建但还没跑」会被判成已完成），并可按预算推进虚拟时钟。
    """
    if not is_simulated():
        try:
            s = float(seconds)
        except (TypeError, ValueError):
            s = 0.0
        if s > 0:
            if evt is not None:
                evt.wait(s)
            else:
                _REAL_SLEEP(s)
        return
    if since is not None and timeout is not None:
        want = min(float(seconds), max(0.0, since + float(timeout) - clock()))
        if want > 0:
            _CURRENT[0] += want
    if evt is not None:
        evt.wait(0.001)
    else:
        _REAL_SLEEP(0.001)


def reset() -> None:
    """清空本进程的虚拟时钟与**预算锚点**。

    为什么需要：``task_deadline`` 是进程级上下文，正常用法是 ``with`` 配对
    退出。但被测代码只要有一次在作用域外抛错/被 goroutine 式地延迟执行，
    锚点就会**泄漏到后续用例**——实测表现为「完全不相关的用例报等待越界」，
    而且只在全量套件里出现（单跑绿）。每个用例开始时清零，让泄漏不可能累积。
    """
    _CURRENT[0] = 0.0
    _DEADLINE[0] = None


@contextmanager
def simulate(start: float = 0.0) -> Iterator[float]:
    """把一个用例的虚拟时钟归零（真实模式下是空操作）。"""
    if not is_simulated():
        yield _real_time.monotonic()
        return
    _CURRENT[0] = float(start)
    yield _CURRENT[0]


@contextmanager
def task_deadline(deadline: float | None = None, *,
                  budget_s: float | None = None) -> Iterator[None]:
    """声明「这个作用域内的等待受某预算约束」；嵌套取最紧的一个。

    ``deadline`` 给的是**绝对时刻**（与 ``clock()`` 同一个钟）；
    也可以只给 ``budget_s``（从当下起算多少秒）——调用方手里那个 deadline
    如果是从别的钟（如 ``time.monotonic``）取的，混用会得到「已过期几分钟」
    这种假锚点，用相对预算就不会踩到。
    """
    if budget_s is not None:
        deadline = clock() + float(budget_s)
    prev = _DEADLINE[0]
    if deadline is None:
        _DEADLINE[0] = prev
    elif prev is None:
        _DEADLINE[0] = float(deadline)
    else:
        _DEADLINE[0] = min(prev, float(deadline))
    try:
        yield
    finally:
        _DEADLINE[0] = prev


def measure_latency(*, budget_s: float | None = None,
                    at_least_s: float | None = None,
                    why: str = "") -> Callable:
    """把「这个用例花了多久」收进统一判定（虚拟/真实同一判据）。"""
    def deco(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if is_simulated():
                with simulate():
                    with task_deadline(budget_s):
                        out = fn(*args, **kwargs)
                    spent = _CURRENT[0]
            else:
                t0 = _real_time.perf_counter()
                try:
                    with task_deadline(None if budget_s is None else
                                       _real_time.monotonic() + budget_s):
                        out = fn(*args, **kwargs)
                finally:
                    spent = _real_time.perf_counter() - t0
            tag = why and f"（{why}）" or ""
            if budget_s is not None:
                assert spent <= budget_s, (
                    f"调度超时：{spent:.3f}s > 预算 {budget_s:.3f}s{tag}")
            if at_least_s is not None:
                assert spent >= at_least_s, (
                    f"对冲/宽限未生效：{spent:.3f}s < 下限 {at_least_s:.3f}s{tag}")
            return out
        return wrapper
    return deco


def real_time_ms(fn: Callable[[], Any], *, repeat: int = 1) -> list[float]:
    """**只在性能基准**里用：真实墙钟测若干次，返回每次毫秒（不是判据）。"""
    out: list[float] = []
    for _ in range(max(1, repeat)):
        t0 = _real_time.perf_counter()
        fn()
        out.append((_real_time.perf_counter() - t0) * 1000.0)
    return out
