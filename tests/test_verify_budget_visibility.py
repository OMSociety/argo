#!/usr/bin/env python3
"""2026-10-22 方案一回归：verify 预算/可见性、研究扩词、失败归因。

四类问题的共同点都是「付了成本却看不见/说不清」，本文件把修复口径锁死：

1. verify 的全局墙钟预算：到点未回的 URL 必须进 pending，不能拖住整次调用。
   （修复前实测 --verify 3 最坏 9.7s，主搜索只有 1.2s。）
2. agent 档必须保留 verify / evidence_reorder 的精简结论；此前整块剥掉，
   调用方付了几秒核验只看到一个 verified_count。
3. 中英混合查询的单 token 扩词（Rust 异步运行时 → Rust）必须被拦下。
4. usage_log 的失败类别与合成引擎过滤：errors 只记「几条」，类别才能归因；
   基准的 fake 引擎组合不得进生产日志。
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import evidence_loop  # noqa: E402
import research_expand  # noqa: E402
import search_attribution  # noqa: E402
import search_cli  # noqa: E402
import search_output  # noqa: E402

_CONTENT = (
    "Gold price reached $2,950 per ounce in August 2026, up 8% year-over-year. "
    "Central banks added 400 tonnes to reserves, compared to 320 tonnes in 2024. "
    "Market analysts define this as a structural shift in demand. " * 3
)


def _ok_fetch(url, max_chars=8000, timeout=5.0):
    return {"url": url, "success": True, "title": "T", "content": _CONTENT,
            "length": len(_CONTENT), "quality_score": 0.7, "content_ok": True,
            "page_type": "article", "source_type": "news",
            "fetch_method": "mock", "cached": False}


# ── 1. verify 全局预算 ───────────────────────────────────────────────────────

def test_verify_budget_marks_unfinished_pending(monkeypatch):
    """预算到点：慢 URL 进 pending，调用按时返回，已回的照常回填。"""
    monkeypatch.setenv("ARGO_VERIFY_BUDGET_S", "0.15")
    results = [
        {"url": "https://v.com/fast", "title": "Fast", "absorption": 0.2},
        {"url": "https://v.com/slow", "title": "Slow", "absorption": 0.2},
    ]

    def _fetch(url, max_chars=8000, timeout=5.0):
        if "slow" in url:
            time.sleep(1.2)  # 远超预算，且模拟不可中断的 fetch 链
        return _ok_fetch(url)

    t0 = time.monotonic()
    v = evidence_loop.verify_results(results, "q", fetch_fn=_fetch, top_k=2)
    elapsed = time.monotonic() - t0

    assert elapsed < 0.8, f"预算未生效：{elapsed:.2f}s"
    assert "https://v.com/slow" in v["pending"]
    assert "https://v.com/fast" not in v["pending"]
    assert len(v["verified"]) == 1
    assert v["revision_summary"]["n"] == 1


def test_verify_budget_zero_keeps_full_chain(monkeypatch):
    """ARGO_VERIFY_BUDGET_S=0：回退逐 URL 完整降级链（可回滚开关）。"""
    monkeypatch.setenv("ARGO_VERIFY_BUDGET_S", "0")
    results = [{"url": "https://v.com/a", "title": "A", "absorption": 0.2},
               {"url": "https://v.com/b", "title": "B", "absorption": 0.2}]
    v = evidence_loop.verify_results(results, "q", fetch_fn=_ok_fetch, top_k=2)
    assert len(v["verified"]) == 2
    assert v["pending"] == []


def test_verify_budget_env_invalid_falls_back(monkeypatch):
    monkeypatch.setenv("ARGO_VERIFY_BUDGET_S", "not-a-number")
    assert evidence_loop._verify_budget_s() == 5.0


# ── 2. 时间账与 agent 可见性 ─────────────────────────────────────────────────

def test_verify_timing_keeps_three_totals_consistent():
    timing = {"stages_ms": 1000.0, "elapsed_ms": 1000.0,
              "process_ms": 1050.0, "stages": []}
    search_cli._merge_verify_timing(timing, 9000.0)
    assert timing["stages_ms"] == 10000.0
    assert timing["elapsed_ms"] == 10000.0
    assert timing["process_ms"] == 10050.0
    assert timing["stages"][-1]["stage"] == "verify"
    # 总账不得小于分项之和（修复前的 1173 vs 10967）
    assert timing["elapsed_ms"] >= timing["stages_ms"]


def test_agent_keeps_slim_verify_and_reorder():
    payload = {
        "query": "q",
        "results": [{"title": "T", "url": "https://v.com/a"}],
        "verify": {
            "verified": [{
                "url": "https://v.com/a", "title": "T", "word_count": 321,
                "pre_absorption": 0.2, "post_absorption": 0.6,
                "delta": 0.4, "fetch_method": "http", "content_ok": True,
            }],
            "revision_summary": {"n": 1, "improved": 1, "mean_delta": 0.4},
            "pending": [], "skipped_cached": 2,
        },
        "evidence_reorder": {
            "reordered": True, "moved": 1,
            "adjusted": [{"url": "https://v.com/a", "pre_score": 1, "post_score": 2}],
        },
    }
    out = search_output._strip_for_agent(payload)
    assert out["verify"]["revision_summary"]["n"] == 1
    assert out["verify"]["skipped_cached"] == 2
    assert out["verify"]["verified"] == [{
        "url": "https://v.com/a", "delta": 0.4,
        "post_absorption": 0.6, "fetch_method": "http",
    }]
    # 逐条 title/word_count 是重复信息，不该进 agent 档
    assert "title" not in out["verify"]["verified"][0]
    assert out["evidence_reorder"] == {"reordered": True, "moved": 1}


# ── 3. 研究扩词：单 token 不单飞 ──────────────────────────────────────────────

def test_english_anchor_blocks_single_short_token():
    assert research_expand._english_anchor("Rust 异步运行时怎么选") == ""
    assert research_expand._english_anchor("AI 监管 新规") == ""
    assert research_expand._english_anchor("600519 股价") == ""


def test_english_anchor_keeps_meaningful_terms():
    assert research_expand._english_anchor("kubernetes 入门") == "kubernetes"
    assert research_expand._english_anchor("Python 异步编程") == "Python"
    assert research_expand._english_anchor("AI agent 最新进展") == "AI agent"
    assert research_expand._english_anchor("Claude Code 最新版本") == "Claude Code"


def test_expand_query_no_single_token_subquery():
    subs = [x["query"] for x in research_expand.expand_query("Rust 异步运行时怎么选")]
    assert "Rust" not in subs
    assert all(len(q.split()) > 1 or len(q) >= 8 for q in subs)


# ── 4. 失败归因与合成引擎过滤 ─────────────────────────────────────────────────

def test_failure_kinds_are_categorical():
    kinds = search_attribution.failure_kinds([
        {"engine": "a", "status": "skipped-quota-exhausted"},
        {"engine": "b", "status": "timeout"},
        {"engine": "c", "status": "ok"},
    ])
    assert kinds == ["quota", "transient"]


def test_synthetic_runs_are_excluded():
    assert search_attribution.is_synthetic_run(["dead_primary", "octen"])
    assert not search_attribution.is_synthetic_run(["octen", "anysearch"])


def test_skipped_sources_names_the_culprit():
    names = search_attribution.skipped_sources([
        {"engine": "bocha", "status": "skipped-quota-exhausted"},
        {"engine": "bocha", "status": "skipped-quota-exhausted"},
        {"engine": "zhihu", "status": "auth-failed"},
        {"engine": "x", "status": "timeout"},
    ])
    assert names == ["bocha", "zhihu"]
