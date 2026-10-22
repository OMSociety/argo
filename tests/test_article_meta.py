#!/usr/bin/env python3
"""article_meta 的纯函数测试：链接解析、meta 读取、上限与降噪。

在线抓取路径不在这里复测（fetch_v3 的集成已有独立用例）；本文件只锁住
「从同一份 HTML 里一次拿全结构化线索」的契约，避免以后有人把它改成
按需正则导致相对链接/去重/上限回归。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from article_meta import extract_article_meta  # noqa: E402


def test_meta_and_article_links():
    html = """
    <html><head>
      <meta name="author" content="张三">
      <meta property="og:site_name" content="示例站">
      <meta property="og:description" content="一篇讲抓取的文章">
      <meta property="article:published_time" content="2026-10-01T08:00:00Z">
    </head><body>
      <nav><a href="/nav">导航</a></nav>
      <article>
        <p>正文 <a href="/a">第一篇</a> 与 <a href="https://other.com/b">第二篇</a></p>
      </article>
      <footer><a href="/footer">页脚</a></footer>
    </body></html>
    """
    meta = extract_article_meta(html, "https://example.com/post/1")
    assert meta["byline"] == "张三"
    assert meta["site_name"] == "示例站"
    assert meta["excerpt"] == "一篇讲抓取的文章"
    assert meta["published_at"].startswith("2026-10-01")
    assert meta["links"] == [
        {"url": "https://example.com/a", "text": "第一篇"},
        {"url": "https://other.com/b", "text": "第二篇"},
    ]


def test_body_only_returns_no_links():
    """无 article/main 时宁可不给，也不把导航链接当正文引用。"""
    html = """
    <html><body>
      <a href="/nav">导航</a>
      <a href="/ok">正文链接</a>
    </body></html>
    """
    assert "links" not in extract_article_meta(html, "https://example.com/")


def test_article_filters_noise_and_resolves_relative():
    html = """
    <article>
      <a href="#top">回顶部</a>
      <a href="javascript:void(0)">脚本</a>
      <a href="mailto:a@b.com">邮件</a>
      <a href="/ok">可用链接</a>
      <a href="/ok">重复链接</a>
    </article>
    """
    meta = extract_article_meta(html, "https://example.com/same#frag")
    assert meta["links"] == [{"url": "https://example.com/ok", "text": "可用链接"}]


def test_link_cap():
    links = "".join(f'<a href="/l{i}">链接{i}</a>' for i in range(50))
    meta = extract_article_meta(f"<article>{links}</article>", "https://example.com/", max_links=5)
    assert len(meta["links"]) == 5


def test_empty_html_returns_empty():
    assert extract_article_meta("", "https://example.com/") == {}
