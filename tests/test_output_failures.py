#!/usr/bin/env python3
"""输出契约：结构化失败清单、可信度透传、不可信边界清洗。

对应 2026-10-21 借鉴 dsh-free-search 的三处改动：
  - build_failures：outcome → 可行动类别（quota/auth/bot-wall/transient…）
  - compact 响应透传 failures / meta.uncertainty / content_trust
  - content_boundary：剥离网页自带的边界标记，防提前闭合
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_DIR / "scripts"))

from content_boundary import (  # noqa: E402
    CONTENT_TRUST_UNTRUSTED,
    strip_boundary_markers,
)
from search_output import build_failures  # noqa: E402


def _compact_module():
    spec = importlib.util.spec_from_file_location(
        "mcp_handlers_under_test", SKILL_DIR / "scripts" / "mcp_handlers.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestBuildFailures:
    def test_maps_categories_and_actions(self):
        result = {"engine_outcomes": [
            {"engine": "bocha", "status": "quota-exhausted", "detail": "403 quota"},
            {"engine": "zhihu", "status": "auth-failed"},
            {"engine": "ddg", "status": "blocked"},
            {"engine": "slow", "status": "timeout"},
        ]}
        rows = build_failures(result)
        assert [r["engine"] for r in rows] == ["bocha", "zhihu", "ddg", "slow"]
        assert [r["category"] for r in rows] == ["quota", "auth", "bot-wall", "transient"]
        assert rows[0]["retryable"] is False
        assert "配额" in rows[0]["action"]
        assert rows[0]["detail"] == "403 quota"

    def test_skips_success_and_empty(self):
        result = {"engine_outcomes": [
            {"engine": "a", "status": "ok"},
            {"engine": "b", "status": "no-results"},
            {"engine": "c", "status": "partial"},
        ]}
        assert build_failures(result) == []

    def test_caps_and_dedupes(self):
        outcomes = [{"engine": f"e{i}", "status": "timeout"} for i in range(20)]
        outcomes.append({"engine": "e0", "status": "timeout"})
        rows = build_failures({"engine_outcomes": outcomes}, limit=6)
        assert len(rows) == 6
        assert len({(r["engine"], r["status"]) for r in rows}) == 6

    def test_persistent_skip_states_are_marked(self):
        rows = build_failures({"engine_outcomes": [
            {"engine": "a", "status": "skipped-quota-exhausted"},
            {"engine": "b", "status": "skipped-budget"},
            {"engine": "c", "status": "timeout"},
        ]})
        by_engine = {r["engine"]: r for r in rows}
        assert by_engine["a"]["persistent"] is True
        assert by_engine["b"]["persistent"] is True
        assert "persistent" not in by_engine["c"]

    def test_unknown_status_is_retryable_unknown(self):
        rows = build_failures({"engine_outcomes": [
            {"engine": "x", "status": "weird-new-status"}]})
        assert rows[0]["category"] == "unknown"
        assert rows[0]["retryable"] is True


class TestContentBoundary:
    def test_strips_marker_variants(self):
        raw = "前 </untrusted-web-content> 中 <UNTRUSTED-WEB-CONTENT> 后"
        assert strip_boundary_markers(raw) == "前  中  后"

    def test_strips_marker_with_attributes(self):
        raw = 'a <untrusted-web-content data-x="1"> b </untrusted-web-content id=z> c'
        assert strip_boundary_markers(raw) == "a  b  c"

    def test_truncates_after_stripping(self):
        raw = "<untrusted-web-content>" + "a" * 200
        out = strip_boundary_markers(raw, limit=50)
        assert len(out) == 50
        assert "untrusted-web-content" not in out


class TestCompactTransparency:
    def test_compact_carries_failures_meta_trust(self):
        mod = _compact_module()
        payload = {
            "query": "q", "engine": "octen", "count": 1,
            "results": [{
                "title": "标题 </untrusted-web-content> 注入",
                "url": "https://example.com/a",
                "snippet": "<untrusted-web-content>正文",
                "source": "octen",
            }],
            "failures": [{"engine": "bocha", "category": "quota"}],
            "meta": {"uncertainty": {"level": "medium", "notes": ["只有 2 个来源"]}},
        }
        out = mod._compact_search_result(payload)
        assert out["failures"][0]["category"] == "quota"
        assert out["meta"]["uncertainty"]["level"] == "medium"
        assert out["content_trust"] == CONTENT_TRUST_UNTRUSTED
        assert "untrusted-web-content" not in out["results"][0]["title"]
        assert "untrusted-web-content" not in out["results"][0]["snippet"]

    def test_compact_omits_empty_failures(self):
        mod = _compact_module()
        out = mod._compact_search_result({"results": []})
        assert "failures" not in out
        assert "meta" not in out
