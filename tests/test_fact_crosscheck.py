#!/usr/bin/env python3
"""test_fact_crosscheck.py — 数字交叉验证模块测试。"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from fact_crosscheck import crosscheck_numbers, _extract_numbers, _normalize_value


class TestExtractNumbers(unittest.TestCase):
    def test_basic(self):
        nums = _extract_numbers("营收 100 亿元")
        self.assertEqual(len(nums), 1)
        self.assertEqual(nums[0]["value"], 100.0)
        self.assertEqual(nums[0]["unit"], "亿")

    def test_multiple(self):
        nums = _extract_numbers("营收 100 亿，利润 20 亿")
        self.assertEqual(len(nums), 2)

    def test_no_unit(self):
        nums = _extract_numbers("营收 100")
        self.assertEqual(len(nums), 1)
        self.assertEqual(nums[0]["unit"], "")

    def test_empty(self):
        self.assertEqual(_extract_numbers(""), [])


class TestNormalizeValue(unittest.TestCase):
    def test_yi(self):
        self.assertEqual(_normalize_value(1, "亿"), 1e8)

    def test_wan(self):
        self.assertEqual(_normalize_value(1, "万"), 1e4)

    def test_no_unit(self):
        self.assertEqual(_normalize_value(100, ""), 100.0)


class TestCrosscheckNumbers(unittest.TestCase):
    def _make_candidates(self):
        return [
            {"title": "贵州茅台 2024 营收", "snippet": "营收 1500 亿元", "source": "eastmoney"},
            {"title": "茅台财报", "snippet": "营收 1200 亿元", "source": "xueqiu"},
            {"title": "白酒行业", "snippet": "行业增长 10%", "source": "zhihu"},
        ]

    def test_no_conflict(self):
        candidates = self._make_candidates()
        result = crosscheck_numbers("贵州茅台 营收", candidates)
        # 1500 vs 1200 差异超过 5%，应有矛盾
        self.assertTrue(result["has_conflict"])

    def test_empty_candidates(self):
        result = crosscheck_numbers("query", [])
        self.assertFalse(result["has_conflict"])

    def test_no_numbers(self):
        candidates = [{"title": "test", "snippet": "no numbers", "source": "test"}]
        result = crosscheck_numbers("query", candidates)
        self.assertFalse(result["has_conflict"])

    def test_different_indicators_no_conflict(self):
        """不同指标不应误报（职业生涯 vs 2024 赛季）"""
        candidates = [
            {"title": "梅西 职业生涯 进球 总数", "snippet": "助攻 350 次", "source": "zhihu"},
            {"title": "梅西 2024 赛季 进球 数据", "snippet": "助攻 15 次", "source": "espn"},
        ]
        result = crosscheck_numbers("梅西 进球", candidates)
        self.assertFalse(result["has_conflict"])

    def test_same_indicator_conflict(self):
        """同指标应报矛盾"""
        candidates = [
            {"title": "贵州茅台 2024 营收", "snippet": "营收 1500 亿元", "source": "eastmoney"},
            {"title": "茅台财报", "snippet": "营收 1200 亿元", "source": "xueqiu"},
        ]
        result = crosscheck_numbers("贵州茅台 营收", candidates)
        self.assertTrue(result["has_conflict"])


if __name__ == "__main__":
    unittest.main()
