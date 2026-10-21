#!/usr/bin/env python3
"""dispatch 记账与通用兜底顺位的门禁（2026-10-21）。

两条锁：

1. `summarize_dispatch` 的尾等待口径。历史上前两版 wasted 口径都失去了行动
   意义（一版必然大于墙钟，一版恒为 0），本次拆成 tail / abandoned 两个量，
   这里锁死它们的定义边界：早停时 tail≈0、no_early 时 tail 以首条结果为锚、
   全失败时 tail=0（没有可交付的东西，等待不可省）。
2. 通用兜底顺位：octen 领队是 A/B 结论（5/6 胜、p90 1643→716ms），
   `ARGO_GENERAL_FALLBACK_LEAD` 必须能把它换回去，否则 A/B 臂与线上回退
   都没有逃生口。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from dispatch_result import summarize_dispatch  # noqa: E402
from route_combo import _general_fallback  # noqa: E402


class TestSummarizeDispatch:
    def _sum(self, **kw):
        base = {"wall_ms": 1500, "contributed_ms": [900.0],
                "first_result_at": None, "first_sufficient_at": None,
                "base": 100.0, "abandoned_ms": []}
        base.update(kw)
        return summarize_dispatch(**base)

    def test_early_stop_tail_is_near_zero(self):
        """判据在 500ms 成立、1500ms 返回：尾等待只该报 1000ms 而不是 0 或墙钟。"""
        acc = self._sum(first_sufficient_at=100.5,
                        contributed_ms=[1490.0])
        assert acc["first_sufficient_ms"] == 500
        assert acc["tail_wait_ms"] == 1000
        assert acc["useful_ms"] == 1490

    def test_no_early_uses_first_result_anchor(self):
        """no_early 域没有够用时刻：尾等待必须从首条结果算，这才是白等。"""
        acc = self._sum(first_result_at=100.7, contributed_ms=[1490.0])
        assert acc["first_sufficient_ms"] == 0
        assert acc["tail_wait_ms"] == 800

    def test_all_failed_has_no_tail(self):
        acc = self._sum(contributed_ms=[], first_result_at=None)
        assert acc["tail_wait_ms"] == 0
        assert acc["useful_ms"] == 0

    def test_abandoned_is_sum_not_wall(self):
        """弃置是并行资源浪费，可以等于墙钟，但不能被当成「用户多等」。"""
        acc = self._sum(first_sufficient_at=100.2, abandoned_ms=[400.0, 300.0])
        assert acc["abandoned_engine_ms"] == 700
        assert acc["tail_wait_ms"] == 1300


class TestGeneralFallbackLead:
    ENABLED = {"octen", "anysearch", "local_bing", "local_search"}

    def test_octen_leads_by_default(self, monkeypatch):
        monkeypatch.delenv("ARGO_GENERAL_FALLBACK_LEAD", raising=False)
        monkeypatch.delenv("ARGO_GENERAL_FALLBACK_LEGACY", raising=False)
        assert _general_fallback(self.ENABLED)[:2] == ["octen", "anysearch"]

    def test_lead_override_moves_named_engine_first(self, monkeypatch):
        monkeypatch.setenv("ARGO_GENERAL_FALLBACK_LEAD", "anysearch")
        monkeypatch.delenv("ARGO_GENERAL_FALLBACK_LEGACY", raising=False)
        assert _general_fallback(self.ENABLED)[:2] == ["anysearch", "octen"]

    def test_unknown_override_is_ignored(self, monkeypatch):
        monkeypatch.setenv("ARGO_GENERAL_FALLBACK_LEAD", "not_an_engine")
        monkeypatch.delenv("ARGO_GENERAL_FALLBACK_LEGACY", raising=False)
        assert _general_fallback(self.ENABLED)[:2] == ["octen", "anysearch"]
