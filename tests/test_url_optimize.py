#!/usr/bin/env python3
"""test_url_optimize.py — URL 优化纯函数的回归锁。

两条容易静默退化的行为：
  1. `normalize_url` 的 docstring 一直写「去掉 fragment」，旧实现却把
     fragment 原样带回来——同一页面的锚点变体会在缓存/去重里裂成多条；
  2. tracking 参数清理必须在 Reddit 主机重写之后重新解析（历史踩雷：
     用重写前的 parsed 会把 old.reddit 又改回 www）。
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

from url_optimize import normalize_url, optimize_url  # noqa: E402


class TestNormalize(unittest.TestCase):
    def test_fragment_removed(self):
        self.assertEqual(
            normalize_url("https://Example.COM/a/b#section-2?x=1"),
            "https://example.com/a/b")

    def test_default_port_removed(self):
        self.assertEqual(normalize_url("https://example.com:443/a"),
                         "https://example.com/a")

    def test_trailing_slash_preserved(self):
        self.assertEqual(normalize_url("https://example.com/a/"),
                         "https://example.com/a/")

    def test_empty(self):
        self.assertEqual(normalize_url(""), "")


class TestOptimize(unittest.TestCase):
    def test_tracking_params_removed(self):
        out = optimize_url("https://example.com/a?utm_source=x&id=7&fbclid=y")
        self.assertNotIn("utm_source", out)
        self.assertNotIn("fbclid", out)
        self.assertIn("id=7", out)

    def test_reddit_rewrite_survives_tracking_cleanup(self):
        out = optimize_url("https://www.reddit.com/r/x?utm_source=z")
        self.assertTrue(out.startswith("https://old.reddit.com/r/x"), out)
        self.assertNotIn("utm_source", out)

    def test_fragment_removed_through_optimize(self):
        self.assertNotIn("#", optimize_url("https://example.com/a#top"))


if __name__ == "__main__":
    unittest.main()
