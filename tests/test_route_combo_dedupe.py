#!/usr/bin/env python3
"""test_route_combo_dedupe.py — TF-IDF 领队组合不得重复同一引擎。

`tfidf_lead_combo` 在「TF-IDF 首选就是 anysearch」时会拼出
`['anysearch', 'anysearch']`。执行层把它当两个独立引擎并发跑两遍
（2026-10-17 实测 k8s 查询 3724/2923 ms，双倍配额），而 `wasted_ms`
还记 0。修复是去重保序。
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

from engine_policy import GENERAL_FREE_FALLBACK  # noqa: E402
from route_combo import _general_fallback, tfidf_lead_combo  # noqa: E402


class TestTfidfLeadCombo(unittest.TestCase):
    def test_best_anysearch_is_not_duplicated(self):
        combo = tfidf_lead_combo("anysearch", 0.30, {"anysearch", "octen"})
        self.assertEqual(combo, ["anysearch", "octen"])

    def test_weak_evidence_keeps_anysearch_lead(self):
        combo = tfidf_lead_combo("anysearch", 0.10, {"anysearch", "octen"})
        self.assertEqual(combo, ["anysearch", "octen"])

    def test_strong_octen_still_gets_anysearch_hedge(self):
        combo = tfidf_lead_combo("octen", 0.30, {"anysearch", "octen"})
        self.assertEqual(combo, ["octen", "anysearch"])

    def test_weak_vertical_pick_rides_behind_general_lead(self):
        combo = tfidf_lead_combo("usda", 0.145, {"anysearch", "octen", "usda"})
        self.assertEqual(combo, ["anysearch", "usda", "octen"],
                         "弱证据推荐保持辅源位次，octen 排第三（budget 会截）")

    def test_vertical_lead_gets_octen_hedge(self):
        combo = tfidf_lead_combo("zhihu", 0.30, {"anysearch", "octen", "zhihu"})
        self.assertEqual(combo, ["zhihu", "octen", "anysearch"])

    def test_disabled_engine_dropped(self):
        self.assertEqual(tfidf_lead_combo("octen", 0.30, {"anysearch"}), ["anysearch"])

    def test_all_disabled(self):
        self.assertEqual(tfidf_lead_combo("octen", 0.30, set()), [])


class TestGeneralFallbackOrder(unittest.TestCase):
    """2026-10-17 A/B 结论：octen 顶到第二顺位做 anysearch 的早停对冲。

    健康窗口里中位延迟无差（双引擎的早停由领队宽限窗决定）；anysearch
    抖动窗口里 octen（996ms / 100% 成功）先交出足够结果，把 p90 从
    3273ms 收到 1614ms、错误 9→0。local_bing 退第三位，仍是快速补充源。
    """

    def test_octen_is_second(self):
        self.assertEqual(GENERAL_FREE_FALLBACK[:3],
                         ("anysearch", "octen", "local_bing"))

    def test_general_fallback_preserves_order(self):
        enabled = {"anysearch", "octen", "local_bing", "local_search", "wikipedia"}
        combo = _general_fallback(enabled)
        self.assertEqual(combo[:3], ["anysearch", "octen", "local_bing"])
        self.assertEqual(combo[-1], "local_search")

    def test_missing_engines_are_filtered(self):
        combo = _general_fallback({"anysearch"})
        self.assertEqual(combo, ["anysearch"])

    def test_legacy_switch_removes_octen(self):
        import os
        from unittest.mock import patch
        with patch.dict(os.environ, {"ARGO_GENERAL_FALLBACK_LEGACY": "1"}):
            combo = _general_fallback(
                {"anysearch", "octen", "local_bing", "local_search"})
        self.assertNotIn("octen", combo)
        self.assertEqual(combo[:2], ["anysearch", "local_bing"])


if __name__ == "__main__":
    unittest.main()
