#!/usr/bin/env python3
"""test_rerank_tfidf.py — TF-IDF 重排模块测试。"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from rerank_tfidf import rerank, rerank_offline, _tokenize, _cosine_sim


class TestTokenize(unittest.TestCase):
    def test_cjk_bigram(self):
        tokens = _tokenize("贵州茅台股价")
        self.assertIn("贵州", tokens)
        self.assertIn("茅台", tokens)
        self.assertIn("股价", tokens)

    def test_english_words(self):
        tokens = _tokenize("Python asyncio async")
        self.assertIn("python", tokens)
        self.assertIn("asyncio", tokens)

    def test_mixed(self):
        tokens = _tokenize("Python 异步编程")
        self.assertIn("python", tokens)
        self.assertIn("异步", tokens)
        self.assertIn("编程", tokens)

    def test_stopchars_filtered(self):
        tokens = _tokenize("的了是和")
        # 含停用字的 bigram 应被过滤
        self.assertEqual(len(tokens), 0)

    def test_empty(self):
        self.assertEqual(_tokenize(""), [])


class TestCosineSim(unittest.TestCase):
    def test_identical(self):
        a = {"x": 1.0, "y": 1.0}
        self.assertAlmostEqual(_cosine_sim(a, a), 1.0)

    def test_orthogonal(self):
        a = {"x": 1.0}
        b = {"y": 1.0}
        self.assertAlmostEqual(_cosine_sim(a, b), 0.0)

    def test_empty(self):
        self.assertEqual(_cosine_sim({}, {"x": 1.0}), 0.0)
        self.assertEqual(_cosine_sim({"x": 1.0}, {}), 0.0)


class TestRerank(unittest.TestCase):
    def _make_candidates(self):
        return [
            {"title": "贵州茅台股价", "snippet": "贵州茅台 600519 股票行情", "_rrf_score": 0.8, "credibility_fast": 0.9, "source": "eastmoney"},
            {"title": "Python 异步编程指南", "snippet": "asyncio 教程", "_rrf_score": 0.7, "credibility_fast": 0.6, "source": "zhihu"},
            {"title": "白酒行业分析", "snippet": "白酒 行业 报告", "_rrf_score": 0.6, "credibility_fast": 0.7, "source": "xueqiu"},
        ]

    def test_rerank_reorders(self):
        candidates = self._make_candidates()
        result = rerank("贵州茅台股价", candidates, top_k=3, mode="deep")
        # 第一条应是贵州茅台
        self.assertIn("茅台", result[0]["title"])

    def test_rerank_fast_mode_skips(self):
        candidates = self._make_candidates()
        original = list(candidates)
        result = rerank("贵州茅台股价", candidates, top_k=3, mode="fast")
        self.assertEqual(result, original)

    def test_rerank_budget_mode_skips(self):
        candidates = self._make_candidates()
        original = list(candidates)
        result = rerank("贵州茅台股价", candidates, top_k=3, mode="budget")
        self.assertEqual(result, original)

    def test_rerank_empty_candidates(self):
        result = rerank("query", [], top_k=10, mode="deep")
        self.assertEqual(result, [])

    def test_rerank_empty_query(self):
        candidates = self._make_candidates()
        result = rerank("", candidates, top_k=3, mode="deep")
        self.assertEqual(len(result), 3)

    def test_rerank_top_k_limit(self):
        candidates = self._make_candidates()
        result = rerank("贵州茅台股价", candidates, top_k=2, mode="deep")
        # 只有前 2 条被重排，第 3 条不变
        self.assertEqual(len(result), 3)

    def test_offline_rerank(self):
        candidates = self._make_candidates()
        result = rerank_offline("贵州茅台股价", candidates, top_k=3)
        self.assertIn("_tfidf_score", result[0])
        self.assertIn("_rerank_score", result[0])


if __name__ == "__main__":
    unittest.main()
