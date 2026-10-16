#!/usr/bin/env python3
"""test_postprocess_signals — 加工段两个可选信号钩子的回归锁（离线）。

2026-10-16 从 search_pipeline.postprocess 提取这两个特性时立此锁。提取的
收益是主管线只留调用点（search_pipeline 曾因此顶破模块体积门禁），代价
是多一层indirection——本文件锁住三层语义，防「搬家搬坏」：

1. **ran 标志**：apply_tfidf_polish 的第三个返回值是「本轮排序有没有
   TF-IDF 贡献」的唯一真相，调用方据此决定 none 兜底。2026-10-16 修的
   边缘态：rerank_tfidf 抛异常时旧接线会留 stale rank_method（既不精排
   也不标 none），现在 ran=False → 调用方正确落 none；
2. **触发条件**：非降级态 / 结果不足 / fast·budget 档 / 开关关，四种不
   触发路径都不得改写 rank_method；
3. **降级语义**：两个函数任何内部异常都不得外抛（主管线不背特性的异常面）。

运行：
    python3 -m pytest tests/test_postprocess_signals.py -v
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from postprocess_signals import apply_tfidf_polish, detect_number_conflict  # noqa: E402

DEGRADED = "skipped_no_key"   # 典型降级态：无 Bocha Key（零依赖用户的常态）
OK_STATUS = "ok"              # 精排成功态：抛光不应触发


def _cands(n: int = 3) -> list[dict]:
    return [{"title": f"结果{i} 标题", "snippet": f"片段{i}", "_rrf_score": 0.9 - i * 0.1}
            for i in range(n)]


class TestApplyTfidfPolish(unittest.TestCase):
    """TF-IDF 抛光的触发条件与 ran 语义。"""

    def test_degraded_status_runs_and_marks(self):
        merged, rank_method, ran = apply_tfidf_polish(
            "查询", _cands(), 5, "auto", DEGRADED, "none")
        self.assertTrue(ran)
        self.assertEqual(rank_method, "tfidf")
        self.assertTrue(all("_tfidf_score" in c for c in merged))

    def test_ok_status_not_triggered(self):
        merged, rank_method, ran = apply_tfidf_polish(
            "查询", _cands(), 5, "auto", OK_STATUS, "bocha")
        self.assertFalse(ran)
        self.assertEqual(rank_method, "bocha", "非降级态不得改写 rank_method")

    def test_fast_mode_not_triggered(self):
        merged, _, ran = apply_tfidf_polish(
            "查询", _cands(), 5, "fast", DEGRADED, "none")
        self.assertFalse(ran, "fast 档不得触发（rerank_tfidf 内部也会跳过）")

    def test_single_result_not_triggered(self):
        _, _, ran = apply_tfidf_polish(
            "查询", _cands(1), 5, "auto", DEGRADED, "none")
        self.assertFalse(ran, "结果不足 2 条不值得重排")

    def test_empty_merged_not_triggered(self):
        _, _, ran = apply_tfidf_polish("查询", [], 5, "auto", DEGRADED, "none")
        self.assertFalse(ran)

    def test_env_flag_off_not_triggered(self):
        os.environ["ARGO_TFIDF_RERANK"] = "0"
        try:
            _, rank_method, ran = apply_tfidf_polish(
                "查询", _cands(), 5, "auto", DEGRADED, "none")
            self.assertFalse(ran)
            self.assertEqual(rank_method, "none")
        finally:
            os.environ.pop("ARGO_TFIDF_RERANK", None)

    def test_rerank_exception_returns_ran_false(self):
        """边缘态（2026-10-16 修复）：重排器抛异常 → ran=False 且不外抛。

        旧接线在 try 失败后不落 none，rank_method 停留 stale 值——调用方
        读到「有排序方法」但实际没有任何重排发生过。
        """
        def _boom(*a, **k):
            raise RuntimeError("rerank exploded")
        with patch.dict(sys.modules, {"rerank_tfidf": type("M", (), {"rerank": staticmethod(_boom)})()}):
            merged, rank_method, ran = apply_tfidf_polish(
                "查询", _cands(), 5, "auto", DEGRADED, "none")
        self.assertFalse(ran, "重排器异常等价于无贡献")
        self.assertEqual(rank_method, "none", "异常路径不得留 stale rank_method")
        self.assertEqual(len(merged), 3, "异常路径原样返回候选")

    def test_rank_method_suffix_appended(self):
        """local 五维已跑过时，标记应为叠加而非覆盖。"""
        merged, rank_method, ran = apply_tfidf_polish(
            "查询", _cands(), 5, "auto", DEGRADED, "local_five_dim")
        self.assertTrue(ran)
        self.assertEqual(rank_method, "local_five_dim+tfidf")


class TestDetectNumberConflict(unittest.TestCase):
    """数字交叉验证信号的触发条件与降级。"""

    def test_non_deep_mode_returns_none(self):
        self.assertIsNone(detect_number_conflict("查询", _cands(3), "fast", "fast"))
        self.assertIsNone(detect_number_conflict("查询", _cands(3), "budget", "balanced"))

    def test_too_few_results_returns_none(self):
        self.assertIsNone(detect_number_conflict("查询", _cands(2), "auto", "balanced"))

    def test_no_conflict_returns_none(self):
        self.assertIsNone(detect_number_conflict(
            "天气", _cands(3), "auto", "balanced"))

    def test_env_flag_off_returns_none(self):
        os.environ["ARGO_NUMBER_CROSSCHECK"] = "0"
        try:
            self.assertIsNone(detect_number_conflict(
                "查询", _cands(3), "auto", "balanced"))
        finally:
            os.environ.pop("ARGO_NUMBER_CROSSCHECK", None)

    def test_crosscheck_exception_returns_none(self):
        """内部异常不得外抛（主管线不背特性的异常面）。"""
        def _boom(*a, **k):
            raise RuntimeError("crosscheck exploded")
        with patch.dict(sys.modules, {"fact_crosscheck": type("M", (), {"crosscheck_numbers": staticmethod(_boom)})()}):
            out = detect_number_conflict("查询", _cands(3), "auto", "balanced")
        self.assertIsNone(out)


if __name__ == "__main__":
    unittest.main()
