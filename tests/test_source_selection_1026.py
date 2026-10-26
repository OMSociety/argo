#!/usr/bin/env python3
"""通用层选源排序（source_selection）的契约测试。

钉住三件事：
  1. 无自适应样本时，实测先验决定顺序（tavily/yuanbao 在 local_bing 前）；
  2. 有 ≥3 条样本时，自适应分能翻转先验（坏源被降下去）；
  3. 研究档把 purpose="research" 传下去（延迟悬崖 2s→8s 的入口）。
"""

from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import general_pool  # noqa: E402
from adaptive import AdaptiveLearner  # noqa: E402
from source_selection import rank_general_candidates  # noqa: E402

_POOL = ["local_bing", "anysearch", "tavily_free", "yuanbao", "parallel_free"]


class TestGeneralRanking(unittest.TestCase):
    def test_priors_decide_when_no_samples(self):
        def score_fn(_e, _d, _l, _p):
            return 0.5, 0

        out = rank_general_candidates(
            _POOL, enabled=set(_POOL), mode="auto", depth="fast",
            context="search", score_fn=score_fn)
        self.assertEqual(out[0], "yuanbao")
        self.assertLess(out.index("tavily_free"), out.index("local_bing"))
        self.assertEqual(out[-1], "local_bing")

    def test_adaptive_flips_prior_with_enough_samples(self):
        def score_fn(engine, _d, _l, _p):
            if engine == "local_bing":
                return 1.0, 5
            if engine == "tavily_free":
                return 0.2, 5
            return 0.5, 0

        out = rank_general_candidates(
            _POOL, enabled=set(_POOL), mode="auto", depth="fast",
            context="search", score_fn=score_fn)
        self.assertLess(out.index("local_bing"), out.index("tavily_free"),
                        "有足够样本时，自适应分必须能推翻先验")

    def test_research_purpose_is_passed(self):
        seen: list[str] = []

        def score_fn(_e, _d, _l, purpose):
            seen.append(purpose)
            return 0.5, 0

        rank_general_candidates(
            _POOL, enabled=set(_POOL), mode="deep", depth="deep",
            context="search", score_fn=score_fn)
        self.assertEqual(set(seen), {"research"})

    def test_non_latin_script_prioritises_language_coverage(self):
        """西里尔/阿拉伯等脚本下，语言覆盖源必须留在 top-2。"""
        out = rank_general_candidates(
            _POOL, enabled=set(_POOL), mode="auto", depth="fast",
            context="search", lang="cyrillic",
            score_fn=lambda *a: (0.5, 0))
        self.assertTrue(
            {"anysearch", "local_bing"} & set(out[:2]),
            f"非拉丁脚本 top-2 缺语言覆盖源：{out}")

    def test_dead_high_prior_loses_to_healthy_lower_prior(self):
        """高先验但已证实失败的源，必须让位给健康源（加法混合，不是乘法）。"""
        def score_fn(engine, _d, _l, _p):
            return {"yuanbao": (0.0, 5), "local_bing": (1.0, 5)}.get(
                engine, (0.5, 0))

        out = rank_general_candidates(
            _POOL, enabled=set(_POOL), mode="auto", depth="fast",
            context="search", score_fn=score_fn)
        self.assertLess(out.index("local_bing"), out.index("yuanbao"))

    def test_empty_pool_returns_empty(self):
        self.assertEqual(rank_general_candidates(
            [], enabled=set(), score_fn=lambda *a: (0.5, 0)), [])


class TestResearchLatencyCliff(unittest.TestCase):
    """研究档把延迟悬崖从 2s 抬到 8s——这条判据必须有直接测试。"""

    def test_research_scores_slow_source_higher(self):
        learner = AdaptiveLearner.__new__(AdaptiveLearner)
        row = (10, 10, 10, 4000.0, 0.0, 0.8, 8.0, time.time())
        daily = learner._score_from_row(row, "daily")
        research = learner._score_from_row(row, "research")
        self.assertLess(daily, research,
                        "4s 的源在日常档应被 2s 悬崖压住，研究档不该")


class TestGeneralOrderPinning(unittest.TestCase):
    """逃生门的边界：拼错引擎名不得让动态排序静默失效。"""

    def test_unknown_lead_does_not_pin(self):
        with patch.object(
                general_pool, "_get_env",
                side_effect=lambda name, default="": (
                    "garbage" if name.endswith("LEAD") else "")), \
                patch.object(general_pool, "_env_flag", return_value=False):
            _order, pinned = general_pool.general_order()
        self.assertFalse(pinned)

    def test_known_lead_pins(self):
        with patch.object(
                general_pool, "_get_env",
                side_effect=lambda name, default="": (
                    "anysearch" if name.endswith("LEAD") else "")), \
                patch.object(general_pool, "_env_flag", return_value=False):
            order, pinned = general_pool.general_order()
        self.assertTrue(pinned)
        self.assertEqual(order[0], "anysearch")

    def test_excluded_engines_are_not_reintroduced(self):
        """配置池排除的 local_baidu/wikipedia 不得由兜底分支放回。"""
        out = general_pool.ranked_general(
            {"local_baidu", "wikipedia"}, score_fn=lambda *a: (0.5, 0))
        self.assertEqual(out, [])


if __name__ == "__main__":
    unittest.main()
