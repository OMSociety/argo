#!/usr/bin/env python3
"""test_dedup_fuzzy — rapidfuzz 模糊近重复判定的回归锁（离线、确定性）。

## 这道锁在守什么

minhash_dedupe 的字符集 Jaccard 对「同文换站后缀」的对给分低：
「人民币兑美元中间价报6.7220 - 知乎」vs「人民币兑美元中间价报6.7220 | 知乎
专栏」token 集合差一个后缀词，minhash 0.7x < 0.85 阈值，两条同文漏合。
2026-10-16 用 15 个真实结果池实测：漏合 3 条跨站镜像条目、0 误合并。

修法（bench 驱动，数据在本次改动的提交说明里）：
  - rank_signals.fuzzy_near_dup：minhash 落在 [0.55, 0.85) 近似命中带内时，
    用 rapidfuzz token_set_ratio 复核；
  - band 闸门是硬约束：带外不调（全量逐对 800 条实测 2.34s，热路径付不起，
    带闸后每查询 0-6 次调用、<2.5ms）；
  - 数据行豁免先于模糊判定：fred/worldbank 观测期行只差日期数值，
    token_set_ratio 会给高分，不先排除会被并成一条。

三层检查：
  1. **可选依赖语义**：rapidfuzz 在/不在，行为都必须正确（在=多合，
      不在=逐位回退纯 minhash，不抛异常）；
  2. **band 闸门**：低于带下限不合并（防数据行/同模板文被错合）；
  3. **集成**：minhash_dedupe 端到端合并跨站后缀对、数据行不合并。

运行：
    python3 -m pytest tests/test_dedup_fuzzy.py -v
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from search_rank import minhash_dedupe  # noqa: E402

try:
    import rapidfuzz  # noqa: F401
    HAVE_RF = True
except ImportError:
    HAVE_RF = False


# ── fixture：真实形态的内容对 ────────────────────────────────────────────────

def _pair(suffix_a: str, suffix_b: str) -> tuple[dict, dict]:
    """同文不同站后缀（minhash 单独判据下的漏网形态）。"""
    base = "人民币兑美元中间价报6.7220 上调33点 创2022年7月初以来新高"
    return ({"title": f"{base}{suffix_a}", "url": "https://zhuanlan.zhihu.com/p/111",
             "snippet": base, "score": 0.9},
            {"title": f"{base}{suffix_b}", "url": "https://www.zhihu.com/question/222",
             "snippet": base, "score": 0.8})


class TestFuzzyNearDuplicate(unittest.TestCase):
    """rank_signals.fuzzy_near_dup 的判据语义。"""

    def _call(self, a: str, b: str, sim: float):
        from rank_signals import fuzzy_near_dup
        return fuzzy_near_dup(a, b, sim)

    @unittest.skipUnless(HAVE_RF, "rapidfuzz 未安装（可选依赖），跳过启用路径")
    def test_same_text_different_suffix_merges(self):
        a, b = _pair(" - 知乎", " | 知乎专栏")
        from rank_signals import _rf_token_set_ratio
        ratio = _rf_token_set_ratio(a["title"], b["title"])
        self.assertGreaterEqual(ratio, 0.88, "fixture 本身应过 token_set_ratio 阈值")
        # minhash 落在带内时，模糊判据应收头
        self.assertTrue(self._call(a["title"], b["title"], 0.60))

    def test_below_band_not_merged(self):
        """低于带下限（0.55）不调 rapidfuzz——band 闸门是热路径约束。"""
        a, b = _pair(" - 知乎", " | 知乎专栏")
        self.assertFalse(self._call(a["title"], b["title"], 0.54))

    def test_above_threshold_band_excluded(self):
        """minhash 已过阈值（≥0.85）不该走到模糊判据（调用方已先判）。"""
        a, b = _pair(" - 知乎", " | 知乎专栏")
        self.assertFalse(self._call(a["title"], b["title"], 0.90))

    def test_unrelated_texts_not_merged(self):
        a = {"title": "Python asyncio 事件循环 最佳实践"}
        b = {"title": "贵州茅台股价 今日行情"}
        self.assertFalse(self._call(a["title"], b["title"], 0.60))

    def test_empty_sig_not_merged(self):
        self.assertFalse(self._call("", "人民币兑美元中间价", 0.60))
        self.assertFalse(self._call("人民币兑美元中间价", "", 0.60))

    def test_env_flag_off_disables(self):
        a, b = _pair(" - 知乎", " | 知乎专栏")
        os.environ["ARGO_DEDUP_FUZZY"] = "0"
        try:
            self.assertFalse(self._call(a["title"], b["title"], 0.60))
        finally:
            os.environ.pop("ARGO_DEDUP_FUZZY", None)

    @unittest.skipUnless(HAVE_RF, "rapidfuzz 未安装（可选依赖）")
    def test_threshold_env_override(self):
        a, b = _pair(" - 知乎", " | 知乎专栏")
        os.environ["ARGO_DEDUP_FUZZY_THR"] = "0.99"
        try:
            self.assertFalse(self._call(a["title"], b["title"], 0.60),
                             "阈值调高到 0.99 后同一对应不再合并")
        finally:
            os.environ.pop("ARGO_DEDUP_FUZZY_THR", None)


class TestTitleSuffixNormalization(unittest.TestCase):
    """站后缀归一化：剥该剥的，不碰不该碰的（零依赖层）。"""

    def test_suffix_variants_normalize_to_same(self):
        from rank_signals import normalize_title_suffix as norm
        variants = ["人民币兑美元中间价报6.7220 上调33点 - 知乎",
                    "人民币兑美元中间价报6.7220 上调33点 | 知乎专栏",
                    "人民币兑美元中间价报6.7220 上调33点_百度百家号",
                    "人民币兑美元中间价报6.7220 上调33点 · 腾讯新闻"]
        norms = {norm(t) for t in variants}
        self.assertEqual(len(norms), 1, f"四个站后缀变体应归一到同一标题，实际 {norms}")

    def test_site_names_not_at_end_are_kept(self):
        from rank_signals import normalize_title_suffix as norm
        keep = ["我在知乎的日子", "小红书穿搭笔记", "CSDN 编程指北",
                "掘金前端小册", "网易云音乐热歌榜"]
        # 纯后缀标题支持刷到空（无内容可留，空签后续判据不合并）
        self.assertEqual(norm("- 知乎"), "")
        for t in keep:
            self.assertEqual(norm(t), t, f"{t!r} 不该被剥")

    def test_empty_and_plain_titles(self):
        from rank_signals import normalize_title_suffix as norm
        self.assertEqual(norm(""), "")
        self.assertEqual(norm("普通标题"), "普通标题")


class TestMinhashDedupeIntegration(unittest.TestCase):
    """minhash_dedupe 端到端：跨站后缀对合并、数据行不合并。"""

    def test_cross_site_suffix_pair(self):
        a, b = _pair(" - 知乎", " | 知乎专栏")
        kept, removed = minhash_dedupe([a, b])
        self.assertEqual(len(kept), 1, f"同文不同站后缀应合并，实际保留 {len(kept)}")
        self.assertEqual(removed, 1)
        self.assertTrue(kept[0]["score"] >= 0.9, "应保留分数高的首条")

    def test_data_rows_never_merged(self):
        """数据行豁免先于模糊判定：只差日期/数值的两行不得被并。"""
        rows = [
            {"title": "美元指数（贸易加权） · 2026-10-08 = 121.447",
             "url": "https://fred.stlouisfed.org/series/DTWEXBGS?obs=2026-10-08"},
            {"title": "美元指数（贸易加权） · 2026-10-06 = 120.898",
             "url": "https://fred.stlouisfed.org/series/DTWEXBGS?obs=2026-10-06"},
        ]
        kept, removed = minhash_dedupe(rows)
        self.assertEqual(removed, 0, "不同观测期的数据行不得合并")
        self.assertEqual(len(kept), 2)

    def test_distinct_articles_kept(self):
        items = [
            {"title": "OpenAI 发布 GPT-5.5 面向订阅用户",
             "url": "https://example.com/a", "score": 0.9},
            {"title": "Python 3.14 正式发布 新增特性一览",
             "url": "https://example.com/b", "score": 0.8},
            {"title": "人民币兑美元中间价报6.7220",
             "url": "https://example.com/c", "score": 0.7},
        ]
        kept, removed = minhash_dedupe(items)
        self.assertEqual(removed, 0, "三篇不同文章一条都不该合")
        self.assertEqual(len(kept), 3)

    def test_env_flag_off_disables_rf_layer_only(self):
        """ARGO_DEDUP_FUZZY=0 只关 rapidfuzz 层；站后缀归一化是零依赖层，照常生效。"""
        # 镜像站型对（归一化治不了），隔离出 rf 层的行为
        # 与真实池同形态：标题+同源 snippet（镜像仓库列表条目；真实 akshare
        # 池里这对的 minhash≈0.75 落在带内，无 snippet 时签名太短会跌到带外）
        _snip = ("Open-source web crawler and scraper for LLMs and AI agents: "
                 "any website into clean, LLM-ready Markdown. Run it yourself, "
                 "or use Crawl4AI Cloud with one key.")
        mirror = [
            {"title": "unclecode/crawl4ai", "url": "https://github.com/unclecode/crawl4ai",
             "snippet": _snip, "score": 0.9},
            {"title": "aemamazab/https-github.com-unclecode-crawl4ai",
             "url": "https://github.com/aemamazab/https-github.com-unclecode-crawl4ai",
             "snippet": _snip, "score": 0.8},
        ]
        os.environ["ARGO_DEDUP_FUZZY"] = "0"
        try:
            kept, _ = minhash_dedupe(mirror)
            self.assertEqual(len(kept), 2,
                             "关开关后须回退纯 minhash+归一化（镜像对不合并）")
        finally:
            os.environ.pop("ARGO_DEDUP_FUZZY", None)
        if HAVE_RF:
            _, removed = minhash_dedupe(mirror)
            self.assertEqual(removed, 1, "开关恢复后同一对应重新合并")

    def test_normalization_layer_always_on(self):
        """零依赖的站后缀归一不受 ARGO_DEDUP_FUZZY 开关影响。"""
        a, b = _pair(" - 知乎", " | 知乎专栏")
        os.environ["ARGO_DEDUP_FUZZY"] = "0"
        try:
            _, removed = minhash_dedupe([a, b])
            self.assertEqual(removed, 1, "关 rf 开关后归一化层仍应合并同文换站对")
        finally:
            os.environ.pop("ARGO_DEDUP_FUZZY", None)


    def test_chain_of_suffix_variants(self):
        """一篇文的四个站后缀变体，合并后只剩一条。"""
        variants = []
        for i, suf in enumerate([" - 知乎", " | 知乎专栏", "_百度百家号", " · 腾讯新闻"]):
            variants.append({"title": f"人民币兑美元中间价报6.7220 上调33点{suf}",
                             "url": f"https://site{i}.example.com/p/{i}",
                             "snippet": "人民币兑美元中间价报6.7220 上调33点",
                             "score": 0.9 - i * 0.05})
        kept, removed = minhash_dedupe(variants)
        self.assertEqual(len(kept), 1, f"四个站后缀变体应并为一条，实际 {len(kept)}")
        self.assertEqual(kept[0]["score"], 0.9, "保留分数最高者")


if __name__ == "__main__":
    unittest.main()
