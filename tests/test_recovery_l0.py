#!/usr/bin/env python3
"""test_recovery_l0 — 恢复链 L0 的三个契约（全 mock，不联网）。

1. **误判恢复**：early_stopped 且 combo 有 skipped 引擎时，补跑交付
   真结果者按恢复流并入（记回 raw_results、发恢复使用日志）。
2. **壳不算「交付」**：被跳过引擎若只交 SERP/跳转壳（2026-10-11 热榜
   实测的事故类），不算恢复成功——返回空让调用方落 L3。壳若经 L0
   回流，会绕过主链壳过滤（过滤跑在恢复链之前）直送最终输出。
3. **死线**：deadline（monotonic 秒）之后不再点火；剩余不足
   _MIN_USEFUL_SLICE_S（P50 口径）也不点火。串行补跑无此约束时
   最坏 |skipped| × 单引擎超时，把已失败的查询再拖几十秒。

死线用假时钟驱动（run_one 推钟），不靠真实 sleep——墙钟断言在并行
跑全量时是 flaky 工厂。
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from recovery_l0 import maybe_retry_skipped  # noqa: E402


def _real(tag: str, n: int = 3) -> list[dict]:
    return [{"title": f"{tag} 结果 {i}", "snippet": f"{tag} 摘要 {i}",
             "url": f"https://example.com/{tag}/{i}"} for i in range(n)]


def _shells(n: int = 5) -> list[dict]:
    # baidu /s?wd= 是 is_serp_or_jump_url 的判定正面样例（热榜壳链同款）
    return [{"title": f"壳 {i}", "snippet": "热搜榜",
             "url": f"https://www.baidu.com/s?wd=壳{i}"} for i in range(n)]


class _FakeClock:
    """可推进程的单调钟：替代 recovery_l0.time，sleep 零成本。"""

    def __init__(self):
        self.t = 1000.0

    def monotonic(self) -> float:
        return self.t


def _ingest_spy(sink: list) -> callable:
    return lambda *a: sink.append(a)


# ── 契约 1：误判恢复 ──────────────────────────────────────────────────────────

def test_recovers_skipped_engine():
    calls, ingested = [], []
    raw = {"engine_a": _real("a")}

    def run_one(eng):
        calls.append(eng)
        return eng, _real(eng), {"engine": eng}, 123

    merged, info = maybe_retry_skipped(
        True, ["engine_a", "engine_b"], raw, lambda: ["engine_a", "engine_b"],
        "测试查询", run_one, _ingest_spy(ingested), 5, None)

    assert calls == ["engine_b"], f"只应补跑 skipped 引擎：{calls}"
    assert merged and info is not None, "真结果应恢复成功"
    assert info["level_used"] == "L0" and info["recovered"] is True
    assert ingested, "补跑调用必须过 ingest（provenance 与自适应学习可见）"
    assert "engine_b" in raw, "补跑结果必须记回 raw_results"


def test_not_early_stopped_is_noop():
    calls = []

    def run_one(eng):
        calls.append(eng)
        return eng, _real(eng), {}, 10

    merged, info = maybe_retry_skipped(
        False, ["engine_a"], {}, lambda: ["engine_a"], "查询",
        run_one, _ingest_spy([]), 5, None)
    assert calls == [] and merged == [] and info is None


def test_no_skipped_engines_is_noop():
    calls = []
    merged, info = maybe_retry_skipped(
        True, ["engine_a"], {"engine_a": _real("a")}, lambda: ["engine_a"],
        "查询", lambda e: calls.append(e), _ingest_spy([]), 5, None)
    assert calls == [] and merged == [] and info is None


def test_unavailable_engine_not_called():
    calls = []

    def run_one(eng):
        calls.append(eng)
        return eng, _real(eng), {}, 10

    maybe_retry_skipped(
        True, ["engine_a", "engine_gone"], {"engine_a": _real("a")},
        lambda: ["engine_a"], "查询", run_one, _ingest_spy([]), 5, None)
    assert calls == [], "不在可用集的引擎不得点火"


def test_emit_usage_receives_recovery_record():
    emitted = []

    def _emit(stream, payload):
        emitted.append((stream, payload))
        return True

    maybe_retry_skipped(
        True, ["engine_a", "engine_b"], {"engine_a": _real("a")},
        lambda: ["engine_a", "engine_b"], "测试查询",
        lambda e: (e, _real(e), {}, 10), _ingest_spy([]), 5, _emit)
    assert emitted and emitted[0][0] == "recovery"
    assert emitted[0][1]["recovered"] is True


# ── 契约 2：壳不算「交付」 ────────────────────────────────────────────────────

def test_shell_only_results_fall_through_to_l3():
    """被跳过引擎只交壳 → 不算恢复成功，落 L3。"""
    calls = []

    def run_one(eng):
        calls.append(eng)
        return eng, _shells(), {"engine": eng}, 100

    merged, info = maybe_retry_skipped(
        True, ["engine_a", "engine_b"], {"engine_a": _real("a")},
        lambda: ["engine_a", "engine_b"], "测试查询",
        run_one, _ingest_spy([]), 5, None)
    assert calls == ["engine_b"]
    assert merged == [] and info is None, (
        "壳链接不得经 L0 判为恢复成功——那是早停误判的同一类垃圾")


def test_mixed_results_keep_only_real_ones():
    """壳+真结果混合：壳被滤掉，真结果照常恢复。"""
    mixed = _shells(3) + _real("b", 3)

    def run_one(eng):
        return eng, mixed, {}, 100

    merged, info = maybe_retry_skipped(
        True, ["engine_a", "engine_b"], {"engine_a": _real("a")},
        lambda: ["engine_a", "engine_b"], "测试查询",
        run_one, _ingest_spy([]), 5, None)
    assert info is not None and merged
    assert all(not (u := r.get("url", "")).startswith("https://www.baidu.com/s")
               for r in merged), "壳不得混进恢复结果"


# ── 契约 3：死线 ─────────────────────────────────────────────────────────────

def test_expired_deadline_starts_nothing():
    clock = _FakeClock()
    calls = []

    def run_one(eng):
        calls.append(eng)
        clock.t += 0.3
        return eng, _real(eng), {}, 10

    with patch("recovery_l0.time", clock):
        merged, info = maybe_retry_skipped(
            True, ["engine_a", "engine_b"], {}, lambda: ["engine_a", "engine_b"],
            "查询", run_one, _ingest_spy([]), 5, None,
            deadline=clock.t - 1.0)
    assert calls == [] and merged == [] and info is None, "死线已过不得点火"


def test_deadline_below_min_slice_starts_nothing():
    """剩余不足一次有效尝试（P50 口径 1.5s）时，起跑大概率白烧——不起。"""
    clock = _FakeClock()
    calls = []

    def run_one(eng):
        calls.append(eng)
        clock.t += 0.3
        return eng, _real(eng), {}, 10

    with patch("recovery_l0.time", clock):
        maybe_retry_skipped(
            True, ["engine_a", "engine_b"], {}, lambda: ["engine_a", "engine_b"],
            "查询", run_one, _ingest_spy([]), 5, None,
            deadline=clock.t + 1.4)
    assert calls == [], f"剩余 {1.4}s < 下限 1.5s，不得点火：{calls}"


def test_deadline_stops_between_engines():
    """窗内先跑，窗收窄到下限之下即停——串行补跑有界。"""
    clock = _FakeClock()
    calls = []

    def run_one(eng):
        calls.append(eng)
        clock.t += 0.8
        return eng, _real(eng), {}, 10

    with patch("recovery_l0.time", clock):
        merged, info = maybe_retry_skipped(
            True, ["engine_a", "engine_b", "engine_c"], {},
            lambda: ["engine_a", "engine_b", "engine_c"],
            "查询", run_one, _ingest_spy([]), 5, None,
            deadline=clock.t + 2.0)
    # 首引擎前 remain=2.0 ≥ 1.5 → 点火；跑完推钟 0.8，remain=1.2 < 1.5 → 停
    assert calls == ["engine_a"], f"死线应在下限之下停火：{calls}"
    assert merged and info is not None


def test_no_deadline_runs_all_skipped():
    """deadline=None（仅测试契约）：全部补跑，恢复行为不回归。"""
    calls = []

    def run_one(eng):
        calls.append(eng)
        return eng, _real(eng), {}, 10

    merged, info = maybe_retry_skipped(
        True, ["engine_a", "engine_b"], {}, lambda: ["engine_a", "engine_b"],
        "查询", run_one, _ingest_spy([]), 5, None)
    assert calls == ["engine_a", "engine_b"]
    assert info is not None


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
