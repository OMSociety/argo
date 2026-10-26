#!/usr/bin/env python3
"""早停质量门的区分性判据（2026-10-26）。

真实漏网案例：查询「git commit」时 local_bing 返回 8 条泛化 Git 页，
旧判据「过半结果命中任意查询词」放行 → 早停，真正对题的 git-commit
手册页被取消。本文件钉住「只命中泛词不算够用」，同时锁住三类不能误伤
的形态：长查询的部分覆盖、单词查询、单条一词答案。
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from query_signals import query_coverage_ok, results_sufficient  # noqa: E402


def _rs(*pairs: tuple[str, str]) -> list[dict[str, str]]:
    return [{"title": title, "snippet": snippet} for title, snippet in pairs]


class TestDiscriminativeCoverage(unittest.TestCase):
    def test_head_only_latin_is_rejected(self):
        results = _rs(
            ("Git - Wikipedia", "Git is a distributed version control software."),
            ("Git for Windows", "Git for Windows focuses on offering tools."),
            ("Git - Documentation", "The official man pages included in Git."),
        )
        self.assertFalse(query_coverage_ok(results, "git commit"),
                         "只命中工具名 git、没有一条命中 commit，不算够用")

    def test_two_term_match_is_accepted(self):
        results = _rs(
            ("git-commit(1) Manual Page",
             "Create a new commit containing the current contents."),
            ("Git - Wikipedia", "distributed version control"),
        )
        self.assertTrue(query_coverage_ok(results, "git commit"))

    def test_long_query_partial_match_is_accepted(self):
        results = _rs(
            ("Quiet Keyboard Picks for Open Offices (2026)",
             "These quiet keyboards are office friendly."),
            ("Mechanical Keyboard Noise Guide", "How loud is your board?"),
            ("Office Setup Ideas", "Keyboards and desks."),
        )
        self.assertTrue(query_coverage_ok(
            results, "quiet mechanical keyboard office use review"),
            "长查询的正常结果本就只覆盖部分主题词，不能误伤")

    def test_cjk_term_level_not_bigram_count(self):
        only_solar = _rs(
            ("太阳能电池市场报告", "光伏装机量持续增长。"),
            ("太阳能产业链", "硅料价格波动。"),
            ("光伏组件出货", "组件效率提升。"),
        )
        self.assertFalse(query_coverage_ok(
            only_solar, "钙钛矿 太阳能 稳定性 on12"),
            "只命中「太阳能」一个主题词，不该被 bigram 数骗过")

        perovskite = _rs(
            ("钙钛矿太阳能电池稳定性获极大提升", "研究团队提升了器件稳定性。"),
            ("钙钛矿光伏进展", "效率与稳定性协同提升。"),
            ("太阳能电池综述", "各类材料对比。"),
        )
        self.assertTrue(query_coverage_ok(
            perovskite, "钙钛矿 太阳能 稳定性 on12"))

    def test_cjk_intent_words_are_not_terms(self):
        """「如何/怎么」是意图词，不得把一条答对的部署结果判负。"""
        results = _rs(
            ("Kubernetes 部署指南", "从构建到上线的部署步骤。"),
            ("生产环境部署流程", "灰度发布与回滚。"),
            ("自动化部署工具", "常见部署工具对比。"),
        )
        for query in ("如何 部署", "怎么 部署", "部署"):
            self.assertTrue(query_coverage_ok(results, query), query)

    def test_single_result_answer_is_not_junk(self):
        """一条「Paris」是答案，不是包索引噪声。"""
        self.assertTrue(query_coverage_ok(
            _rs(("Paris", "Paris is the capital of France.")),
            "what is the capital of France"))

    def test_single_term_query_bypasses_rule(self):
        self.assertTrue(query_coverage_ok(
            _rs(("Crawl4AI - GitHub", "Open source LLM friendly crawler.")),
            "Crawl4AI"))

    def test_package_index_junk_still_rejected(self):
        results = _rs(
            ("requests", "python package"),
            ("flask", "python package"),
            ("numpy", "python package"),
        )
        self.assertFalse(query_coverage_ok(results, "requests 库 安装"))


class TestAuthorityAwareStop(unittest.TestCase):
    """权威信号参与早停：高权威可少一条，无权威要求明确过半。"""

    def test_high_authority_allows_two_results(self):
        results = [
            {"title": "git-commit manual", "snippet": "commit docs",
             "authority_level": 4},
            {"title": "git commit guide", "snippet": "commit steps",
             "authority_level": 3},
        ]
        self.assertTrue(results_sufficient(results, mode="auto",
                                           query="git commit"))

    def test_two_plain_results_still_not_enough(self):
        results = [
            {"title": "git-commit manual", "snippet": "commit docs"},
            {"title": "git commit guide", "snippet": "commit steps"},
        ]
        self.assertFalse(results_sufficient(results, mode="auto",
                                            query="git commit"))

    def test_no_authority_requires_clear_majority(self):
        base = [
            ("git commit manual", "commit docs"),
            ("git commit guide", "commit steps"),
            ("documentation page", "reference manual"),
            ("unrelated page", "nothing here"),
        ]
        marginal = _rs(*base)
        self.assertFalse(results_sufficient(marginal, mode="auto",
                                            query="git commit"),
                         "4 条只中 2 条且无权威信号，早停应被拒")
        clear = _rs(*base, ("git commit examples", "commit workflow"))
        self.assertTrue(results_sufficient(clear, mode="auto",
                                           query="git commit"))


if __name__ == "__main__":
    unittest.main()
