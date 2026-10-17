#!/usr/bin/env python3
"""test_query_operators.py — 查询操作符契约层的回归锁（离线）。

借鉴 DeepSeek Search 的操作符透传语义（api-docs.deepseek.com/zh-cn/guides/
search），落地为 Argo 的解析层：Google 风格查询里的指令从路由与检索两侧
剥掉，结构化进 operators（v1 消费：langs→路由语言覆盖、after/before→时间
窗兜底、exclude_terms→融合后过滤；sites 记入可观测，按引擎下推是后续增量）。

本文件锁三层：
  1. 解析器：八类操作符、多站点 OR、词内连字符、裸 OR 不误伤、无操作符零改动；
  2. 路由隔离：site: 不再把路由锁死进错误域（实测前 `DeepSeek site:github.com`
     → code_search，应为 ai_model）；
  3. prepare 汇合：-词的排除项并入 query_understanding 的 exclude_terms。

运行：
    python3 -m pytest tests/test_query_operators.py -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from query_operators import parse_query_operators  # noqa: E402


class TestParser(unittest.TestCase):
    """八类操作符的解析契约。"""

    def test_site_positive(self):
        clean, ops = parse_query_operators("DeepSeek site:github.com")
        self.assertEqual(clean, "DeepSeek")
        self.assertEqual(ops["sites"], ["github.com"])

    def test_site_exclude(self):
        clean, ops = parse_query_operators("DeepSeek -site:example.com")
        self.assertEqual(clean, "DeepSeek")
        self.assertEqual(ops["exclude_sites"], ["example.com"])

    def test_multi_site_or_connector_consumed(self):
        clean, ops = parse_query_operators(
            "DeepSeek site:github.com OR site:huggingface.co lang:zh after:2025")
        self.assertEqual(clean, "DeepSeek")
        self.assertEqual(ops["sites"], ["github.com", "huggingface.co"])
        self.assertEqual(ops["langs"], ["zh"])
        self.assertEqual(ops["after"], "2025")

    def test_exclude_term_with_inner_hyphen(self):
        clean, ops = parse_query_operators("GPT-4o -gpt-3")
        self.assertEqual(clean, "GPT-4o")
        self.assertEqual(ops["exclude_terms"], ["gpt-3"])

    def test_exclude_phrase(self):
        clean, ops = parse_query_operators('DeepSeek -"release notes"')
        self.assertEqual(clean, "DeepSeek")
        self.assertEqual(ops["exclude_terms"], ["release notes"])

    def test_exact_phrase_stays_in_clean(self):
        """「"短语"」是意图本体不是指令——留在 clean_query 供 phrase_filter。"""
        clean, ops = parse_query_operators('DeepSeek "精确短语"')
        self.assertEqual(clean, 'DeepSeek "精确短语"')
        self.assertEqual(ops["exclude_terms"], [])

    def test_lang_multi(self):
        clean, ops = parse_query_operators("模型 lang:zh,en")
        self.assertEqual(clean, "模型")
        self.assertEqual(ops["langs"], ["zh", "en"])

    def test_date_window(self):
        clean, ops = parse_query_operators("茅台 after:2026-01-01 before:2026-06-01")
        self.assertEqual(clean, "茅台")
        self.assertEqual(ops["after"], "2026-01-01")
        self.assertEqual(ops["before"], "2026-06-01")

    def test_date_year_only(self):
        _, ops = parse_query_operators("模型 after:2025")
        self.assertEqual(ops["after"], "2025")

    def test_no_operator_untouched(self):
        q = "普通查询无操作符"
        clean, ops = parse_query_operators(q)
        self.assertEqual(clean, q)
        self.assertFalse(any([ops["sites"], ops["exclude_sites"],
                              ops["exclude_terms"], ops["langs"],
                              ops["after"], ops["before"], ops["dropped"]]))

    def test_bare_or_preserved(self):
        """查询自身的布尔 OR（非站点连接词）必须原样保留。"""
        clean, _ = parse_query_operators("Rust OR Go 后端选型")
        self.assertEqual(clean, "Rust OR Go 后端选型")

    def test_spaced_dash_not_exclusion(self):
        """空格-空格是分隔符不是排除号（Google 语义只认紧贴的 -）。"""
        clean, ops = parse_query_operators("python - django tutorial")
        self.assertEqual(clean, "python - django tutorial")
        self.assertEqual(ops["exclude_terms"], [])

    def test_empty_and_garbage(self):
        self.assertEqual(parse_query_operators(""), ("", parse_query_operators("")[1]))
        clean, ops = parse_query_operators("!!!")
        self.assertEqual(clean, "!!!")
        self.assertEqual(ops["dropped"], [])


class TestRoutingIsolation(unittest.TestCase):
    """site: 不再把路由锁死进错误域（解析层存在的理由）。"""

    def test_site_does_not_hijack_domain(self):
        from route import route_query
        hijacked = route_query("DeepSeek site:github.com", mode="auto").get("domain")
        clean_side = route_query("DeepSeek", mode="auto").get("domain")
        self.assertEqual(hijacked, "code_search",
                         "对照组：site: 形态今天以前确实锁进 code_search")
        self.assertEqual(clean_side, "ai_model",
                         "剥掉 site: 后应回自然域（ai_model）")
        self.assertNotEqual(hijacked, clean_side)

    def test_lang_override_changes_combo(self):
        from route import route_query
        d = route_query("茅台 股价 行情", mode="auto", lang_override=["ja"])
        feats = d.get("features") or {}
        self.assertEqual(feats.get("primary_lang"), "ja")
        # ja 覆盖应换到 ja 友好组合（hatena 等在列）
        self.assertIn("hatena_bookmark", d.get("engines_combo") or [])

    def test_lang_override_bypasses_route_cache(self):
        """lang_override 改变决策本身，不能与无覆盖查询共享缓存键。"""
        from route import route_query_cached
        d = route_query_cached("茅台 股价 行情", mode="auto", lang_override=["en"])
        self.assertNotEqual(d.get("route_cached"), True,
                            "带 lang_override 的决策不得来自磁盘缓存")


class TestPrepareMergesExcludeTerms(unittest.TestCase):
    """prepare 把 -词的排除项并入 query_understanding 的通道。"""

    def test_operator_exclude_merged(self):
        from search_entry import prepare
        from cache import SearchCache
        cache = SearchCache(db_path=":memory:")
        decision = {
            "domain": "general", "engine": "auto",
            "engines_combo": ["anysearch"], "parallel": False,
            "operators": {"exclude_terms": ["广告", "推广"]},
        }
        prepared = prepare("贵州茅台 股价 -广告", decision, 5, 8, "balanced",
                           cache, skip_cache=True,
                           hooks=__import__("search_entry")._SearchHooks(
                               engine_search=lambda *a, **k: [],
                               available_engines=lambda: ["anysearch"],
                               get_cost_factor=lambda e: 1.0,
                               get_engines=lambda **k: {"anysearch": {}},
                               get_execution_config=lambda: {},
                               missing_env_for=lambda e: [],
                               classify_outcome=lambda *a, **k: {},
                               note_quota_exhausted=lambda *a, **k: None,
                               per_engine_budget_s=8.0, fast_budget_s=6.0,
                               auto_budget_s=10.0, deep_budget_s=15.0,
                               primary_grace_s=1.0, straggler_grace_s=0.5,
                               straggler_tail_fn=lambda e: 0.5,
                               serial_stagger_s=0.25))
        from search_entry import _SearchRequest  # noqa: F401
        # prepare 的 exclude_terms 落在请求对象上（noise 过滤的输入）
        req = prepared.req if hasattr(prepared, "req") else prepared
        excl = list(getattr(req, "exclude_terms", None) or [])
        for t in ("广告", "推广"):
            self.assertIn(t, excl, f"操作符排除词 {t} 应并入 exclude_terms")


if __name__ == "__main__":
    unittest.main()
