#!/usr/bin/env python3
"""漂移阈值的契约：跌多少算跌、什么不算。

这些用例锁的是「夜间红了代表什么」。阈值写松了没人知道，写紧了会天天误报，
所以把边界钉成数字：少 1 条允许、少 2 条报；体积涨 20% 报；新用例不报；
`save_baseline` 的外层 `report` 键要能穿透。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPT_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import ci_drift_gate  # noqa: E402


def _report(cases: list[dict]) -> dict:
    return {"n_cases": len(cases), "cases": cases, "total_missing": 1}


def _case(cid: str, kept: int = 5, size: int = 3000) -> dict:
    return {"id": cid, "kept": kept, "bytes": size}


def test_same_numbers_pass():
    r = _report([_case("a"), _case("b")])
    assert ci_drift_gate.violations(r, r) == []


def test_one_result_fewer_is_tolerated():
    base = _report([_case("a", kept=5)])
    cur = _report([_case("a", kept=4)])
    assert ci_drift_gate.violations(base, cur) == []


def test_two_results_fewer_is_reported():
    base = _report([_case("a", kept=5)])
    cur = _report([_case("a", kept=3)])
    assert ci_drift_gate.violations(base, cur) == ["a: 结果 3 条，基线 5 条"]


def test_output_growth_beyond_20_percent_is_reported():
    base = _report([_case("a", size=3000)])
    cur = _report([_case("a", size=3600)])       # 正好 20%，允许
    assert ci_drift_gate.violations(base, cur) == []
    cur = _report([_case("a", size=3601)])
    assert len(ci_drift_gate.violations(base, cur)) == 1


def test_new_case_without_baseline_is_not_drift():
    base = _report([_case("a")])
    cur = _report([_case("a"), _case("b", kept=1, size=10)])
    assert ci_drift_gate.violations(base, cur) == []


def test_baseline_wrapper_is_unwrapped(tmp_path: Path):
    base = {"_meta": {"saved_at": "x"}, "report": _report([_case("a", kept=5)])}
    cur = _report([_case("a", kept=2)])
    p = tmp_path / "base.json"
    p.write_text(json.dumps(base), encoding="utf-8")
    assert ci_drift_gate.violations(ci_drift_gate._load(p), cur) == ["a: 结果 2 条，基线 5 条"]


def test_missing_file_exits_2_not_1(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", [
        "ci_drift_gate.py", "--baseline", str(tmp_path / "nope.json"),
        "--current", str(tmp_path / "nope2.json")])
    assert ci_drift_gate.main() == 2
    assert "读不到报告" in capsys.readouterr().err


def test_violation_exits_1(tmp_path: Path, monkeypatch, capsys):
    base = tmp_path / "base.json"
    cur = tmp_path / "cur.json"
    base.write_text(json.dumps({"report": _report([_case("a", kept=5)])}), encoding="utf-8")
    cur.write_text(json.dumps(_report([_case("a", kept=1)])), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", [
        "ci_drift_gate.py", "--baseline", str(base), "--current", str(cur)])
    assert ci_drift_gate.main() == 1
    assert "a: 结果 1 条" in capsys.readouterr().err


def test_pass_exits_0_and_mentions_missing_as_info(tmp_path: Path, monkeypatch, capsys):
    base = tmp_path / "base.json"
    cur = tmp_path / "cur.json"
    base.write_text(json.dumps({"report": _report([_case("a")])}), encoding="utf-8")
    cur.write_text(json.dumps(_report([_case("a")])), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", [
        "ci_drift_gate.py", "--baseline", str(base), "--current", str(cur)])
    assert ci_drift_gate.main() == 0
    assert "不算漂移" in capsys.readouterr().out
