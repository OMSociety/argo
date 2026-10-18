#!/usr/bin/env python3
"""test_authority_level.py — 离散权威等级与上游信号透传的回归锁（离线）。

2026-10-17 借鉴 DeepSeek Search 的两处设计（api-docs.deepseek.com/zh-cn/
guides/search）落到 Argo：

  1. authority 0-4 离散等级（≥3 极权威，-1 未知）——连续分对 Agent 是弱
     信号（不知道该在哪切），离散等级才能直接当闸门用（≥3 才进事实链）；
  2. 上游源原生结构化信号透传（upstream_authority/upstream_score）——不
     覆盖 Argo 自己的 authority/score（排序用），原名落盘由输出层采信。

与既有 authority_tier（high/medium/low/very_low）的关系：同源不同形，
tier 是内部排序语义，level 是对外可解释语义，共用一条 authority 连续分，
不产生第二套评分。

运行：
    python3 -m pytest tests/test_authority_level.py -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from rank_signals import authority_level  # noqa: E402


class TestAuthorityLevelMapping(unittest.TestCase):
    """自有映射：连续 authority 分 → 0-4（阈值按 2026-10-17 实测分布校准）。"""

    def test_bands(self):
        cases = [
            (1.0, 4), (0.95, 4), (0.85, 4),      # 官方/一手
            (0.84, 3), (0.72, 3), (0.70, 3),     # 知名第三方
            (0.69, 2), (0.55, 2), (0.50, 2),     # 一般可信
            (0.49, 1), (0.35, 1), (0.30, 1),     # UGC/低可信
            (0.29, 0), (0.12, 0), (0.0, 0),      # SERP/跳转链/未知
        ]
        for score, want in cases:
            self.assertEqual(authority_level(score), want,
                             f"authority={score} 应映射 {want}")

    def test_garbage_score_returns_zero(self):
        for bad in (None, "", "abc", [], {}):
            self.assertEqual(authority_level(bad), 0, f"{bad!r} 应落 0")

    def test_string_score_coerced(self):
        self.assertEqual(authority_level("0.9"), 4)
        self.assertEqual(authority_level("0.5"), 2)


class TestUpstreamAuthorityPreferred(unittest.TestCase):
    """上游源原生 0-4 优先采信（DeepSeek search 的 authority 字段）。"""

    def test_upstream_value_wins(self):
        self.assertEqual(authority_level(0.5, "3"), 3)
        self.assertEqual(authority_level(0.95, "1"), 1)

    def test_upstream_unknown_falls_back(self):
        """-1 = 上游未知（DeepSeek 语义）→ 回退自有映射，不是落 0 也不是信 -1。"""
        self.assertEqual(authority_level(0.95, "-1"), 4)
        self.assertEqual(authority_level(0.5, "-1"), 2)

    def test_upstream_unparseable_falls_back(self):
        self.assertEqual(authority_level(0.5, "garbage"), 2)
        self.assertEqual(authority_level(0.5, "9"), 2)   # 越界值不采信
        self.assertEqual(authority_level(0.5, ""), 2)    # 空串=未提供


class TestUpstreamFieldPassthrough(unittest.TestCase):
    """output_map 的 item_upstream_* 透传（不覆盖 Argo 自己的字段）。"""

    def test_parser_passes_upstream_fields(self):
        from engines_base import _make_field_parser
        p = _make_field_parser("results", {
            "title": "title", "url": "url", "snippet": "snippet",
            "upstream_authority": "authority", "upstream_score": "rerank_score",
        }, None)
        out = p({"results": [{
            "title": "t", "url": "https://x.com/a", "snippet": "s",
            "authority": 3, "rerank_score": 2.4,
        }]})
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["upstream_authority"], "3")
        self.assertEqual(out[0]["upstream_score"], "2.4")
        # 不覆盖 Argo 自己的 authority/score 键（那两个由排序层管）
        self.assertNotIn("authority", out[0])
        self.assertNotIn("score", out[0])

    def test_parser_omits_absent_fields(self):
        from engines_base import _make_field_parser
        p = _make_field_parser("results", {
            "title": "title", "url": "url",
            "upstream_authority": "authority", "upstream_score": "rerank_score",
        }, None)
        out = p({"results": [{"title": "t", "url": "https://x.com/a"}]})
        self.assertNotIn("upstream_authority", out[0])


class TestDeepseekSpecContract(unittest.TestCase):
    """deepseek_search spec 的契约（默认开 + 无 key 自动跳过 + 显式调用）。"""

    def _spec(self):
        import yaml
        p = ROOT / "engines" / "specs" / "deepseek_search.yaml"
        self.assertTrue(p.exists(), "deepseek_search.yaml 应存在")
        return yaml.safe_load(p.read_text(encoding="utf-8"))

    def test_default_enabled_but_explicit_only(self):
        """2026-10-18：产品决策改为默认开（4a71693）。

        默认开不等于自动路由：付费源不进任何 combo，只经 --engine 显式调用。
        「无 key 自动跳过」由 required_env + routable 过滤保证，不靠 enabled=false。
        """
        s = self._spec()
        self.assertTrue(s.get("enabled"), "默认开：无 key 由 required_env 兜底")
        self.assertTrue(s.get("explicit_only"),
                        "付费源必须显式调用，不得进自动路由")
        self.assertIn("DEEPSEEK_API_KEY", s.get("required_env") or [],
                      "无 key 时须能自动跳过")

    def test_paid_cost_and_env(self):
        s = self._spec()
        self.assertEqual(s.get("cost_tier"), "paid")
        self.assertIn("DEEPSEEK_API_KEY", s.get("required_env") or [])
        self.assertEqual(s.get("method"), "POST")

    def test_upstream_output_map_declared(self):
        s = self._spec()
        om = s.get("output_map") or {}
        self.assertEqual(om.get("item_upstream_authority"), "authority")
        self.assertEqual(om.get("item_upstream_score"), "rerank_score")


if __name__ == "__main__":
    unittest.main()
