#!/usr/bin/env python3
"""test_summary_field.py — Agent 档摘要（summary）的回归锁（离线）。

借鉴 DeepSeek Search 的 summary 语义（600-800 字给模型阅读，与 100-200 字
给人看的 snippet 分档），补上 Argo 的吸收断层。本文件锁三层：

  1. summarize_for_agent 纯函数：句界对齐截断（窗内取最后一个句界=预算内
     最大化）、短正文原样、空正文空串、无句界硬切；
  2. extract_fetch_evidence → store/lookup 往返：summary 随证据落缓存；
  3. backfill_results 回填：有核验证据的结果带 summary，没有的不造假。

运行：
    python3 -m pytest tests/test_summary_field.py -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from evidence_loop import (  # noqa: E402
    backfill_results,
    extract_fetch_evidence,
    summarize_for_agent,
)


class TestSummarizeForAgent(unittest.TestCase):
    """句界对齐截断：预算内最大化，不切半句话。"""

    def test_cuts_at_last_sentence_end_in_window(self):
        text = "这是第一句。这是第二句！第三问？"
        out = summarize_for_agent(text, max_chars=12)
        self.assertEqual(out, "这是第一句。这是第二句！")

    def test_short_content_unchanged(self):
        self.assertEqual(summarize_for_agent("短文", 800), "短文")
        self.assertEqual(summarize_for_agent("", 800), "")

    def test_no_sentence_end_hard_cut(self):
        text = "无句界内容" * 100
        out = summarize_for_agent(text, max_chars=100)
        self.assertLessEqual(len(out), 100)
        self.assertTrue(out)

    def test_never_returns_half_sentence_when_end_exists(self):
        text = "第一段结束。第二段内容还在继续写写写"
        out = summarize_for_agent(text, max_chars=10)
        self.assertEqual(out, "第一段结束。")
        # 对照：窗内唯一句界很靠前时，切在它后面仍优于硬切（30% 下限之内）
        out2 = summarize_for_agent("短。后面是很长的没有句界的内容" * 3, max_chars=20)
        self.assertTrue(out2.endswith("。"), f"应切在句界: {out2!r}")


class TestEvidenceCarriesSummary(unittest.TestCase):
    """extract_fetch_evidence 产出 summary，且随证据缓存往返。"""

    def _fetch_result(self):
        return {
            "success": True,
            "url": "https://example.com/a",
            "title": "标题",
            "content": "第一段正文。第二段正文。第三段正文。",
            "quality_score": 0.8,
            "content_ok": True,
        }

    def test_extract_includes_summary(self):
        ev = extract_fetch_evidence(self._fetch_result())
        self.assertIsNotNone(ev)
        self.assertEqual(ev["summary"], "第一段正文。第二段正文。第三段正文。")

    def test_store_lookup_roundtrip(self):
        ev = extract_fetch_evidence(self._fetch_result())
        from cache import SearchCache
        c = SearchCache(db_path=":memory:")
        from evidence_loop import store_fetch_evidence, lookup_fetch_evidence
        # set_evidence 是「并入 fetch 条目」语义（正文不在不写分——防调用方
        # 误判已核验），故先播种 fetch 条目，与 verify 真实链路的写入序一致。
        c.set_fetch("https://example.com/a", {
            "title": "标题", "content": "第一段正文。第二段正文。第三段正文。",
            "url": "https://example.com/a", "success": True,
        })
        store_fetch_evidence("https://example.com/a", ev, cache=c)
        back = lookup_fetch_evidence("https://example.com/a", cache=c)
        self.assertIsNotNone(back)
        self.assertEqual(back["summary"], ev["summary"])

    def test_backfill_attaches_summary_only_when_present(self):
        from cache import SearchCache
        from evidence_loop import store_fetch_evidence
        c = SearchCache(db_path=":memory:")
        ev = extract_fetch_evidence(self._fetch_result())
        c.set_fetch("https://example.com/a", {
            "title": "标题", "content": "第一段正文。第二段正文。第三段正文。",
            "url": "https://example.com/a", "success": True,
        })
        store_fetch_evidence("https://example.com/a", ev, cache=c)
        results = [
            {"title": "有证据", "url": "https://example.com/a"},
            {"title": "无证据", "url": "https://example.com/b"},
        ]
        backfill_results(results, cache=c)
        self.assertEqual(results[0].get("summary"), ev["summary"])
        self.assertNotIn("summary", results[1], "未核验结果不得出现 summary")


if __name__ == "__main__":
    unittest.main()
