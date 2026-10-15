#!/usr/bin/env python3
"""tests/test_engine_call_key.py — 引擎单飞 key 的完整性契约。

背景（2026-10-15 复核）：`engines.search()` 的进程内单飞把「同 query+engine+参数」
的并发调用合并成一次上游执行，但 `_call_key` 只吃 (query, engine, n, kwargs)，
而真正决定结果的 depth / mode / timeout 是通过闭包进入 `_execute` 的——
它们没进 key，于是**不同档位的并发调用被错误合并**：deep 请求可能拿到
fast 的结果集（反向亦然，且 follower 继承 leader 的 timeout）。

触发面：MCP 常驻进程的并发 tool call、research/verify 的并行子查询、
任何同进程内嵌调用方。docstring 早已写明「影响结果的参数必须进 key」，
depth/mode/timeout 恰是被漏掉的三个。
"""

from __future__ import annotations

import sys
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

SCRIPT_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import engines  # noqa: E402


class TestCallKeyContract(unittest.TestCase):
    """纯函数面：影响结果的参数必须在 key 里区分开。"""

    def test_same_params_same_key(self):
        k1 = engines._call_key("q", "e", 5, {"a": 1})
        k2 = engines._call_key("q", "e", 5, {"a": 1})
        self.assertEqual(k1, k2)

    def test_depth_differentiated(self):
        fast = engines._call_key("q", "e", 5, {}, timeout=8, depth="fast", mode="fast")
        deep = engines._call_key("q", "e", 5, {}, timeout=8, depth="deep", mode="deep")
        self.assertNotEqual(fast, deep, "不同 depth 不得共用单飞 key")

    def test_mode_differentiated(self):
        a = engines._call_key("q", "e", 5, {}, timeout=8, depth="fast", mode="fast")
        b = engines._call_key("q", "e", 5, {}, timeout=8, depth="fast", mode="deep")
        self.assertNotEqual(a, b, "不同 mode 不得共用单飞 key")

    def test_timeout_differentiated(self):
        a = engines._call_key("q", "e", 5, {}, timeout=8, depth="fast", mode="fast")
        b = engines._call_key("q", "e", 5, {}, timeout=20, depth="fast", mode="fast")
        self.assertNotEqual(a, b, "不同 timeout 不得共用单飞 key")

    def test_kwargs_still_differentiated(self):
        a = engines._call_key("q", "e", 5, {"since": "7d"}, timeout=8,
                              depth="fast", mode="fast")
        b = engines._call_key("q", "e", 5, {"until": "1d"}, timeout=8,
                              depth="fast", mode="fast")
        self.assertNotEqual(a, b)


class TestNoCrossTierCoalescing(unittest.TestCase):
    """集成面：并发跨档位调用不得被合并成一次。"""

    def _run_pair(self, **overrides):
        """并发跑两个档位不同的 search，返回 (上游调用次数, leader 实际档位)。"""
        calls: list[tuple] = []
        entered = threading.Barrier(2, timeout=5)

        def fake_engine(query, n, timeout, depth="fast", mode="fast", **kw):
            calls.append((depth, mode, timeout))
            time.sleep(0.12)  # 保证两次调用时间窗重叠
            return [{"title": f"hit-{depth}", "url": "https://x.example/1"}]

        registry = {"b1_fake_engine": fake_engine}
        results: list[list] = []
        errors: list[BaseException] = []

        def call(depth, mode, timeout):
            try:
                entered.wait()
                results.append(engines.search("b1 probe", "b1_fake_engine", n=5,
                                              timeout=timeout, depth=depth,
                                              mode=mode))
            except BaseException as exc:  # noqa: BLE001 - 测试收集用
                errors.append(exc)

        base = dict(depth="fast", mode="fast", timeout=8)
        base.update(overrides)
        t1 = threading.Thread(target=call, kwargs=base)
        t2 = threading.Thread(target=call, kwargs=dict(depth="deep", mode="deep",
                                                       timeout=20))
        with mock.patch.object(engines, "get_registry", return_value=registry):
            t1.start(); t2.start(); t1.join(10); t2.join(10)
        return calls, results, errors

    def test_cross_tier_calls_are_not_merged(self):
        calls, results, errors = self._run_pair()
        self.assertFalse(errors, f"调用抛异常：{errors}")
        self.assertEqual(len(calls), 2,
                         f"跨档位调用被错误合并（上游只跑了 {len(calls)} 次）：{calls}")
        self.assertEqual({c[0] for c in calls}, {"fast", "deep"},
                         f"两个档位都应真的执行：{calls}")
        # 最坏形态的证据：fast 调用者不得拿到 deep 的产物，反之亦然
        got = {r[0]["title"] for r in results if r}
        self.assertEqual(got, {"hit-fast", "hit-deep"},
                         f"结果被串档：{got}")


if __name__ == "__main__":
    unittest.main()
