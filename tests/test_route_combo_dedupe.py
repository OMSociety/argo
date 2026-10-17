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

from route_combo import tfidf_lead_combo  # noqa: E402


class TestTfidfLeadCombo(unittest.TestCase):
    def test_best_anysearch_is_not_duplicated(self):
        combo = tfidf_lead_combo("anysearch", 0.30, {"anysearch", "octen"})
        self.assertEqual(combo, ["anysearch"])

    def test_weak_evidence_is_not_duplicated(self):
        combo = tfidf_lead_combo("anysearch", 0.10, {"anysearch"})
        self.assertEqual(combo, ["anysearch"])

    def test_strong_other_leads_then_anysearch(self):
        combo = tfidf_lead_combo("octen", 0.30, {"anysearch", "octen"})
        self.assertEqual(combo, ["octen", "anysearch"])

    def test_disabled_engine_dropped(self):
        self.assertEqual(tfidf_lead_combo("octen", 0.30, {"anysearch"}), ["anysearch"])

    def test_all_disabled(self):
        self.assertEqual(tfidf_lead_combo("octen", 0.30, set()), [])


if __name__ == "__main__":
    unittest.main()
