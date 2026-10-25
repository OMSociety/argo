#!/usr/bin/env python3
"""test_engine_add.py — `argo engine add` 的纯函数与 dry-run。

不写仓库：只测派生逻辑、域归属建议、模板生成与 dry-run 编排。
真实写入路径（spec/backends/admission）由 --from-yaml/--admit 端到端覆盖，
本文件用 dry-run 与临时目录隔离，避免污染仓库。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPT_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import engine_add as ea  # noqa: E402


# ── 派生逻辑 ──────────────────────────────────────────────────────────────────

def test_derive_family_from_desc():
    spec = {"desc": "化学物质结构检索 分子式 化合物"}
    health = {"ok": True, "health": {"results": [
        {"title": "Aspirin", "snippet": "C9H8O4 molecular formula"}]}}
    assert ea.derive_family(spec, health) == "science_chem"


def test_derive_family_respects_declared():
    spec = {"family": "academic", "desc": "化学物质"}
    assert ea.derive_family(spec, {}) == "academic"


def test_derive_family_unknown_returns_empty():
    spec = {"desc": "zzzz qqqq"}
    assert ea.derive_family(spec, {}) == ""


def test_derive_langs_from_probe_query():
    spec = {}
    health = {"query": "阿司匹林 分子式"}
    assert "zh" in ea.derive_langs(spec, health["query"])


def test_derive_langs_multilingual_param():
    spec = {"url": "https://x/search?setlang={lang}"}
    langs = ea.derive_langs(spec, None)
    assert "*" in langs


def test_build_manifest_does_not_override_declared():
    spec = {"family": "code", "langs": ["en"], "coverage": ["tech"]}
    m = ea.build_manifest(spec, {})
    assert m["family"] == "code"
    assert m["langs"] == ["en"]
    assert m["coverage"] == ["tech"]


def test_suggest_domain_assignment_none():
    s = ea.suggest_domain_assignment("e", [], "", [])
    assert s["suggestion"] == "none"


def test_suggest_domain_assignment_append():
    s = ea.suggest_domain_assignment("e", ["chem_search"], "science_chem", ["general"])
    assert s["suggestion"] == "append_to_combo"
    assert s["domains"] == ["chem_search"]


# ── 模板生成 ──────────────────────────────────────────────────────────────────

class _Args:
    from_url = "https://api.example.com/v1/search"
    engine = ""
    desc = "示例搜索"
    query_param = "q"
    items_path = "results"
    env_key = "EXAMPLE_API_KEY"
    cost_tier = "free"
    timeout = 10.0
    demo = "test query"


def test_template_from_url():
    spec = ea._template_from_url("https://api.example.com/v1/search", "example", _Args())
    assert spec["engine_id"] == "example"
    assert spec["type"] == "http"
    assert spec["required_env"] == ["EXAMPLE_API_KEY"]
    assert spec["output_map"]["item_title"] == "title"


def test_slug_from_url():
    assert ea._slug_from_url("https://www.Example.COM/v1/search") == "example_com"


# ── CLI dry-run ────────────────────────────────────────────────────────────────

def test_cli_dry_run_engine(capsys):
    rc = ea.main(["add", "--engine", "arxiv", "--dry-run"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "arxiv" in out


def test_cli_dry_run_without_source_errors():
    rc = ea.main(["add", "--dry-run"])
    assert rc == 2


def test_cli_engine_add_alias():
    """`argo engine add ...` 与 `argo engine ...` 等价。"""
    rc = ea.main(["--engine", "arxiv", "--dry-run"])
    assert rc == 0
