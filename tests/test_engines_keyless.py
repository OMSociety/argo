#!/usr/bin/env python3
"""免 key 通道：Keenable 文本块解析（纯函数，不联网）。

匿名端点返回的是人读文本块（Title/URL/Published/Snippets，`---` 分隔），
不是 JSON；解析器必须能处理缺字段、空块与 HTML 残留，且不能把坏块当成结果。
"""

from __future__ import annotations

import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_DIR / "scripts"))

from engines_builders_keyless import (  # noqa: E402
    _KEENABLE_BLOCK_RE,
    _keenable_block_to_result,
)

SAMPLE = """Title: OpenAI News
URL: https://openai.com/news?read=full
Published: 2026-10-20
Acquired: 2026-10-21
Snippets:
[OpenAI acquires Orchestra](/index/a)
[...]
[GPT-6 update](https://example.com/x)

---

Title: Second result
URL: https://example.com/second
Snippets:
plain body
"""


class TestKeenableBlockParse:
    def test_parses_blocks_and_trims_snippet(self):
        rows = [_keenable_block_to_result(b) for b in _KEENABLE_BLOCK_RE.split("\n" + SAMPLE)]
        rows = [r for r in rows if r]
        assert len(rows) == 2
        assert rows[0]["title"] == "OpenAI News"
        assert rows[0]["url"].startswith("https://openai.com/")
        assert rows[0]["published_at"] == "2026-10-20"
        assert "[...]" not in rows[0]["snippet"]
        assert "OpenAI acquires" in rows[0]["snippet"]
        assert rows[1]["source"] == "keenable_free"

    def test_skips_blocks_without_title_or_url(self):
        assert _keenable_block_to_result("Title: only title") is None
        assert _keenable_block_to_result("URL: https://x.test") is None
        assert _keenable_block_to_result("") is None

    def test_truncates_long_snippet(self):
        block = "Title: t\nURL: https://x.test\nSnippets:\n" + ("a" * 500)
        row = _keenable_block_to_result(block)
        assert row is not None
        assert len(row["snippet"]) == 300
