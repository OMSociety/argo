#!/usr/bin/env python3
"""article_meta.py — 从已抓取的 HTML 里提取文章级元数据与正文链接。

为什么要单独一层（2026-10-22，对标 open-websearch 的 includeLinks/byline）：
`readability_extract` 只交付正文文本，链接、作者、站点名、摘要这些**结构化
线索**在提取时被丢掉。Agent 要顺着文章里的引用继续取证，只能再抓一次页面；
研究/报告场景里作者与站点名也是引用格式的必需字段。它们都在同一份 HTML 里，
一次解析就能拿到，不该让调用方付第二次网络往返。

边界：
  - 纯标准库 HTMLParser，毫秒级；不做正文判定（那是 readability 的职责）。
  - 链接只取 <article>/<main> 内。没有语义容器时宁可不给，也不把
    nav/header/footer 的导航链接当正文引用；相对链接按页面 URL 解析。
  - 标题/摘要/站点名只读 meta，不从正文猜；猜错比缺失更糟。
  - 全部字段都可能缺失，调用方按 key 是否存在判断，不返回空字符串占位。
"""

from __future__ import annotations

from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

MAX_LINKS = 30
MAX_TEXT = 300
_SKIP_TAGS = {"nav", "header", "footer", "aside", "script", "style", "noscript"}
_META_KEYS = {
    "author": "byline",
    "article:author": "byline",
    "og:article:author": "byline",
    "og:site_name": "site_name",
    "application-name": "site_name",
    "og:description": "excerpt",
    "description": "excerpt",
    "twitter:description": "excerpt",
    "article:published_time": "published_at",
}


class _MetaParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, str] = {}
        self.article_links: list[dict[str, str]] = []
        self._in_article = 0
        self._skip = 0
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag == "meta":
            data = {k.lower(): (v or "") for k, v in attrs if k}
            key = (data.get("property") or data.get("name") or "").strip().lower()
            value = data.get("content") or ""
            field = _META_KEYS.get(key)
            if field and value and field not in self.meta:
                self.meta[field] = value.strip()[:MAX_TEXT]
            return
        if tag in _SKIP_TAGS:
            self._skip += 1
            return
        if tag in ("article", "main"):
            self._in_article += 1
        elif tag == "a" and self._skip == 0:
            href = ""
            for k, v in attrs:
                if k.lower() == "href" and v:
                    href = v.strip()
                    break
            if href:
                self._href = href
                self._text = []

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in _SKIP_TAGS:
            self._skip = max(0, self._skip - 1)
            return
        if tag in ("article", "main"):
            self._in_article = max(0, self._in_article - 1)
        elif tag == "a" and self._href is not None:
            text = " ".join("".join(self._text).split())[:120]
            if self._in_article:
                self.article_links.append({"url": self._href, "text": text})
            self._href = None
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._href is not None and self._skip == 0:
            self._text.append(data)


def extract_article_meta(html: str, base_url: str,
                         max_links: int = MAX_LINKS) -> dict:
    """返回 {byline, excerpt, site_name, published_at, links}，缺失的键不出现。

    links: [{"url": 绝对 URL, "text": 锚文本}]，按出现顺序去重，最多 max_links。
    同页锚点、javascript/mailto、非 http(s)、空文本一律丢弃。
    """
    if not html:
        return {}
    p = _MetaParser()
    try:
        p.feed(html)
        p.close()
    except Exception:
        return {}
    out: dict = dict(p.meta)
    raw_links = p.article_links
    if raw_links:
        links: list[dict[str, str]] = []
        seen: set[str] = set()
        for item in raw_links:
            href = item["url"].strip()
            if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
                continue
            url = urljoin(base_url, href)
            if urlparse(url).scheme not in ("http", "https"):
                continue
            if url.split("#", 1)[0] == base_url.split("#", 1)[0]:
                continue
            text = item["text"]
            if len(text) < 2 or url in seen:
                continue
            seen.add(url)
            links.append({"url": url, "text": text})
            if len(links) >= max(1, int(max_links)):
                break
        if links:
            out["links"] = links
    return out
