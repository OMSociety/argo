#!/usr/bin/env python3
"""test_fx_query_domain — fx_query 域与货币对解析的回归锁（离线、确定性）。

## 这道锁在守什么

2026-10-16 实测事故：「人民币 汇率 中间价 今日」→ 域 macro_data，主路径
FRED/worldbank 对人民币汇率返回 0 条 → 零结果恢复链拉来 local_bing →
交付维基/百科词条。两个各自独立的缺陷叠乘：

  ① **位次休眠**：fx_rate 在 macro_data combo 位次 5，fast 预算窗 2 /
     auto 3，永不参与自动路由（test_new_source_reachability 台账曾登记）；
  ② **退化货币对**：_parse_pair 对单别名词（「人民币汇率」）解析出
     CNY→CNY，引擎看着在 combo 里，真跑也只会返回「1 CNY = 1 CNY」。

修法：新建 fx_query 域（位于 macro_data 之前独享 FX 意图，fx_rate 进位次
1、eastmoney 进位次 2 补「今日中间价」时效语义），并把货币对解析重写为
模块级 parse_fx_pair（可测、合法 ISO 过滤、CNY/USD 市场报价方向）。

本文件三类检查：

1. **路由正例**：六种 FX 问法命中 fx_query 且前两位是 fx_rate/eastmoney；
2. **路由负例**：宏观/美股/A股/财经新闻等相邻查询不得被 fx_query 抢走
   （域命中锁死 combo，误抢比漏接更难纠——precision 测试的同一论断）；
3. **货币对解析**：单别名词、显式兑/斜杠、ISO 缩写污染（GDP/CPI）、
   CNY→CNY 退化、USD/JPY 市场方向，逐条锁定。

运行：
    python3 -m pytest tests/test_fx_query_domain.py -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))


def _route(query: str, mode: str = "auto", depth: str = "fast") -> dict:
    from route import route_query
    return route_query(query, mode=mode, depth=depth)


class TestFxQueryRouting(unittest.TestCase):
    """正例：FX 问法必须命中 fx_query，且快源在预算窗内。"""

    CASES = [
        "人民币 汇率 中间价 今日",
        "美元 人民币 汇率",
        "美元兑人民币",
        "人民币兑美元汇率",
        "离岸人民币 汇率 走势",
        "USD CNY exchange rate",
    ]

    def test_positive_queries_hit_fx_query(self):
        for q in self.CASES:
            d = _route(q)
            self.assertEqual(
                d.get("domain"), "fx_query",
                f"{q!r} 应命中 fx_query，实际 {d.get('domain')}")

    def test_fx_rate_lead_and_eastmoney_second(self):
        """fx_rate 进位次 1（fast 预算窗 2 内可达）——事故根因①的回归锁。"""
        for q in self.CASES:
            combo = _route(q).get("engines_combo") or []
            self.assertEqual(combo[:2], ["fx_rate", "eastmoney"],
                             f"{q!r} 的 combo 前两位应为 fx_rate/eastmoney，实际 {combo[:3]}")

    def test_fast_budget_window_keeps_both(self):
        """fast 档策略裁剪后，fx_rate 与 eastmoney 都还在（位次休眠锁）。"""
        from engine_policy import filter_combo_by_policy
        combo = _route("人民币 汇率 中间价 今日").get("engines_combo") or []
        kept = filter_combo_by_policy(combo, mode="fast", depth="fast")
        self.assertIn("fx_rate", kept, f"fast 窗内应保留 fx_rate，实际 {kept}")
        self.assertIn("eastmoney", kept, f"fast 窗内应保留 eastmoney，实际 {kept}")


class TestFxQueryDoesNotSteal(unittest.TestCase):
    """负例：相邻域查询不得被 fx_query 抢走（每条配一条对照防过杀）。"""

    NEGATIVES = [
        # (查询, 期望域, 说明)
        ("美元指数", "macro_data", "美元指数是宏观 DXY，不是汇率兑换"),
        ("美国 CPI 最新", "macro_data", "美国宏观不受影响"),
        ("10年期国债收益率", "macro_data", "macro_data 自身触发词仍在"),
        ("外汇储备 最新", "chinese_general", "外汇储备未被 unless 外的方式误放行"),
        ("美联储 加息", "financial_news", "利率政策是新闻不是牌价"),
        ("英伟达 财报", "financial_news", "财报域不被汇率词干扰"),
        ("茅台 股价", "stock_query", "A股行情域在前仍优先"),
    ]

    def test_negatives_not_fx_query(self):
        for q, want, why in self.NEGATIVES:
            d = _route(q)
            self.assertNotEqual(
                d.get("domain"), "fx_query",
                f"{q!r}（{why}）不应命中 fx_query")

    def test_negatives_hit_expected_domain(self):
        """对照：每个负例仍落在它该在的域——防「为躲 fx_query 全量失能」。"""
        for q, want, why in self.NEGATIVES:
            self.assertEqual(
                _route(q).get("domain"), want,
                f"{q!r}（{why}）应命中 {want}，实际 {_route(q).get('domain')}")


class TestParseFxPair(unittest.TestCase):
    """parse_fx_pair 逐条锁定（引擎返回统一 bit，解析是纯函数）。"""

    CASES = [
        # 单别名词：非人民币货币 → 它对 CNY；人民币自身 → USD/CNY 市场报价
        ("人民币汇率", ("USD", "CNY")),
        ("人民币 汇率 中间价 今日", ("USD", "CNY")),
        ("美元汇率", ("USD", "CNY")),
        ("日元汇率", ("JPY", "CNY")),
        ("港币 汇率", ("HKD", "CNY")),
        ("离岸人民币 汇率", ("CNH", "CNY")),
        # 显式方向：兑/斜杠
        ("美元兑人民币", ("USD", "CNY")),
        ("人民币兑美元中间价", ("USD", "CNY")),   # CNY 对 → USD/CNY 报价口径
        ("欧元兑美元", ("EUR", "USD")),           # EUR/GBP/AUD/NZD 豁免
        ("英镑 兑 欧元", ("GBP", "EUR")),
        ("USD CNY", ("USD", "CNY")),
        ("CNY USD", ("USD", "CNY")),              # 显式 USD/CNY 顺序
        ("USD/CNH", ("USD", "CNH")),
        ("USD JPY", ("USD", "JPY")),
        ("日元兑美元", ("USD", "JPY")),           # 非豁免货币对 USD → USD/X
        ("exchange rate USD to CNY", ("USD", "CNY")),
        # 缩写污染与退化对：一律不出网
        ("GDP 汇率", ("", "")),
        ("CPI 数据", ("", "")),
        ("比特币 汇率", ("", "")),
        ("10年期国债收益率", ("", "")),
        ("人民币 兑 人民币", ("", "")),           # 退化对显式拒识
    ]

    def test_pair_cases(self):
        from engines_builders_data_macro import parse_fx_pair
        for q, want in self.CASES:
            self.assertEqual(
                parse_fx_pair(q), want,
                f"{q!r} 解析结果应为 {want}，实际 {parse_fx_pair(q)}")

    def test_never_returns_self_pair(self):
        """任何输入都不得解析出 X==Y（事故根因②的硬锁）。"""
        from engines_builders_data_macro import parse_fx_pair
        probes = [q for q, _ in self.CASES] + [
            "人民币", "汇率", "美元", "人民币 兑 人民币 汇率", "CNY CNY",
            "人民币兑人民币", "港币 兑 港币",
        ]
        for q in probes:
            base, target = parse_fx_pair(q)
            self.assertFalse(
                base and base == target,
                f"{q!r} 解析出退化对 {base}→{target}")


class TestFxQueryDomainContract(unittest.TestCase):
    """域声明字段在 schema 白名单内、combo 结构合规（与 schema 门禁互锁）。"""

    def test_fx_query_declared_and_enabled_engines(self):
        from config import load_config
        domains = {d.get("name"): d for d in load_config().get("domains") or []
                   if isinstance(d, dict)}
        self.assertIn("fx_query", domains, "config.yaml 必须声明 fx_query 域")
        d = domains["fx_query"]
        engines = load_config().get("engines") or {}
        for e in d.get("engines_combo") or []:
            spec = engines.get(e) or {}
            self.assertTrue(
                spec.get("enabled", True),
                f"fx_query combo 的 {e} 未启用（命中即零结果）")

    def test_fx_query_before_macro_data(self):
        """先命中先赢：fx_query 必须排在 macro_data 之前，否则白接。"""
        from config import load_config
        names = [d.get("name") for d in load_config().get("domains") or []
                 if isinstance(d, dict)]
        self.assertLess(
            names.index("fx_query"), names.index("macro_data"),
            "fx_query 须声明在 macro_data 之前（汇率意图独享）")


if __name__ == "__main__":
    unittest.main()
