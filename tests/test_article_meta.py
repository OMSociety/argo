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


# ─── JSON-LD（2026-10-26，对标 pagesift 的结构化数据提取）────────────────────

def test_jsonld_basic_fields():
    html = """
    <html><head>
      <script type="application/ld+json">
        {"@type":"NewsArticle","headline":"突发：示例新闻标题",
         "datePublished":"2026-10-01T08:00:00+08:00",
         "author":{"@type":"Person","name":"李四"},
         "publisher":{"@type":"Organization","name":"示例通讯社"},
         "description":"事件经过与后续处置"}
      </script>
    </head><body>
      <article><a href="/a">相关报道</a></article>
    </body></html>
    """
    meta = extract_article_meta(html, "https://example.com/news/1")
    assert meta["headline"] == "突发：示例新闻标题"
    assert meta["published_at"] == "2026-10-01T08:00:00+08:00"
    assert meta["byline"] == "李四"
    assert meta["site_name"] == "示例通讯社"
    assert meta["excerpt"] == "事件经过与后续处置"
    assert meta["links"] == [{"url": "https://example.com/a", "text": "相关报道"}]


def test_jsonld_meta_wins_over_ld():
    """meta 与 JSON-LD 双源并存时 meta 优先，ld 只补缺失字段（headline 仅 ld 有）。"""
    html = """
    <html><head>
      <meta name="author" content="张三">
      <meta property="article:published_time" content="2026-09-01T09:00:00Z">
      <script type="application/ld+json">
        {"@type":"Article","headline":"LD标题","datePublished":"2026-10-01T08:00:00Z",
         "author":{"name":"李四"}}
      </script>
    </head><body></body></html>
    """
    meta = extract_article_meta(html, "https://example.com/post/2")
    assert meta["byline"] == "张三"
    assert meta["published_at"] == "2026-09-01T09:00:00Z"
    assert meta["headline"] == "LD标题"


def test_jsonld_graph_list_and_cjk_date():
    html = """
    <script type="application/ld+json">
      {"@graph":[{"@type":"WebSite","name":"示例站"},
                 {"@type":"BlogPosting","datePublished":"2026年10月1日",
                  "author":[{"@type":"Person","name":"王五"},
                            {"@type":"Person","name":"赵六"}]}]}
    </script>
    """
    meta = extract_article_meta(html, "https://example.com/blog/3")
    assert meta["published_at"] == "2026-10-01"
    assert meta["byline"] == "王五, 赵六"


def test_jsonld_date_formats_normalized():
    cases = {
        "2026/10/1": "2026-10-01",
        "2026-10-01 08:00": "2026-10-01T08:00",
        "2026-10-01T08:00:00Z": "2026-10-01T08:00:00Z",
        "2026.10.01": "2026-10-01",
    }
    for raw, want in cases.items():
        html = (f'<script type="application/ld+json">'
                f'{{"@type":"Article","datePublished":"{raw}"}}</script>')
        meta = extract_article_meta(html, "https://example.com/")
        assert meta["published_at"] == want, raw


def test_jsonld_malformed_and_unparseable_date_dropped():
    """非法 JSON 跳过不影响其余段落；解析不出的日期交空串丢弃，不透传原文。"""
    html = """
    <script type="application/ld+json">not json at all</script>
    <script type="application/ld+json">
      {"@type":"Article","datePublished":"发布于上周","headline":"可解析字段仍在"}
    </script>
    """
    meta = extract_article_meta(html, "https://example.com/")
    assert "published_at" not in meta
    assert meta["headline"] == "可解析字段仍在"


def test_jsonld_falls_back_to_non_article_nodes():
    """页面只有 Organization 等非文章节点时，缺失字段放宽到全节点提取。"""
    html = """
    <script type="application/ld+json">
      {"@type":"Organization","name":"示例机构","description":"机构简介"}
    </script>
    """
    meta = extract_article_meta(html, "https://example.com/about")
    assert meta["site_name"] == "示例机构"
    assert meta["excerpt"] == "机构简介"


def test_jsonld_regular_script_not_captured():
    """普通 JS 脚本不进 ld 提取，行为与从前一致。"""
    html = """
    <script>var config = {"datePublished": "1999-01-01"};</script>
    <script type="text/javascript">console.log("hi");</script>
    """
    meta = extract_article_meta(html, "https://example.com/")
    assert meta == {}
