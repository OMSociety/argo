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
    """组合语义（领队/辅源/对冲/去重）。

    对冲位 2026-10-26 起由 source_selection 按实测先验排序（原写死
    octen/anysearch）。这里注入固定 score_fn，让先验单独决定顺序，测试
    不随本机 adaptive.db 的时点数据漂移。
    """

    @staticmethod
    def _flat(_engine, _domain, _lang, _purpose):
        return 0.5, 0

    def _combo(self, best, score, enabled):
        return tfidf_lead_combo(best, score, enabled, score_fn=self._flat)

    def test_best_anysearch_is_not_duplicated(self):
        combo = self._combo("anysearch", 0.30, {"anysearch", "yuanbao"})
        self.assertEqual(combo, ["anysearch", "yuanbao"])

    def test_weak_evidence_keeps_general_lead(self):
        combo = self._combo("anysearch", 0.10, {"anysearch", "yuanbao"})
        self.assertEqual(combo, ["yuanbao", "anysearch"])

    def test_strong_low_ranked_engine_gets_general_hedge(self):
        combo = self._combo("octen", 0.30,
                            {"anysearch", "yuanbao", "octen"})
        self.assertEqual(combo, ["octen", "yuanbao", "anysearch"])

    def test_weak_vertical_pick_rides_behind_general_lead(self):
        combo = self._combo("usda", 0.145,
                            {"anysearch", "yuanbao", "usda"})
        self.assertEqual(combo, ["yuanbao", "usda", "anysearch"],
                         "弱证据推荐保持辅源位次，第二个通用源顺延到第三位")

    def test_vertical_lead_gets_general_hedge(self):
        combo = self._combo("zhihu", 0.30,
                            {"anysearch", "yuanbao", "zhihu"})
        self.assertEqual(combo, ["zhihu", "yuanbao", "anysearch"])

    def test_disabled_engine_dropped(self):
        self.assertEqual(self._combo("octen", 0.30, {"anysearch"}),
                         ["anysearch"])

    def test_all_disabled(self):
        self.assertEqual(self._combo("octen", 0.30, set()), [])


class TestGeneralFallbackOrder(unittest.TestCase):
    """2026-10-21 A/B 结论：octen 领队，anysearch 退到对冲位。

    交错对拍（6 对，seed 11）：octen 领队 5:1 胜，中位快 804ms，
    p90 1643→716ms，结果数中位同为 8。生产日志同向：general_search
    的 346 条里 324 条最后一棒是 anysearch（p50 1932ms）。local_bing 仍第三。
    """

    def test_octen_is_first(self):
        self.assertEqual(GENERAL_FREE_FALLBACK[:3],
                         ("octen", "anysearch", "local_bing"))

    def test_general_fallback_preserves_order(self):
        """静态臂：ORDER 与 GENERAL_FREE_FALLBACK 一致（默认已改为实测排序）。"""
        import os
        from unittest.mock import patch
        enabled = {"anysearch", "octen", "local_bing", "local_search", "wikipedia"}
        with patch.dict(os.environ, {"ARGO_GENERAL_FALLBACK_STATIC": "1"}):
            combo = _general_fallback(enabled)
        self.assertEqual(combo[:3], ["octen", "anysearch", "local_bing"])
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
