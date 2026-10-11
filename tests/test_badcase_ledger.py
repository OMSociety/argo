"""badcase_ledger 单元测试：三源入账、幂等去重、门禁判定。"""
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import pytest  # noqa: E402

import badcase_ledger  # noqa: E402

_NOW = datetime.now().astimezone().isoformat(timespec="seconds")


@pytest.fixture()
def ledger_env(tmp_path, monkeypatch):
    state = tmp_path / "state"
    logs = state / "usage_log"
    logs.mkdir(parents=True)
    monkeypatch.setenv("ARGO_STATE_DIR", str(state))
    monkeypatch.setenv("ARGO_USAGE_LOG_DIR", str(logs))
    return logs


def _seed_sources(logs: Path):
    (logs / "query.jsonl").write_text("\n".join([
        json.dumps({"ts": _NOW, "stream": "query", "query": "错误查询",
                    "engines_used": ["anysearch"], "count": 0,
                    "errors": ["anysearch: timeout"], "mode": "auto"}),
        json.dumps({"ts": _NOW, "stream": "query", "query": "空结果查询",
                    "engines_used": ["octen", "slow_primary"], "count": 0,
                    "errors": [], "mode": "auto"}),  # 混夹具但真引擎在 → 入账
        json.dumps({"ts": _NOW, "stream": "query", "query": "正常查询",
                    "engines_used": ["anysearch"], "count": 5,
                    "errors": [], "mode": "auto"}),  # 正常 → 不入账
        json.dumps({"ts": _NOW, "stream": "query", "query": "夹具查询",
                    "engines_used": ["slow_primary"], "count": 3,
                    "errors": [], "mode": "auto"}),  # 全表外名 → 不入账
    ]) + "\n", encoding="utf-8")
    (logs / "recovery.jsonl").write_text(json.dumps(
        {"ts": _NOW, "stream": "recovery", "query": "恢复查询",
         "triggered": True, "recovered": True, "level_used": "L3",
         "strategy_used": "switch_engine", "steps_tried": 1}) + "\n",
        encoding="utf-8")
    (logs.parent / "circuit_breaker.json").write_text(json.dumps(
        {"engines": {"wikipedia": {"state": "open", "failures": 5,
                                   "opens": 1},
                     "zhihu": {"state": "closed", "failures": 0,
                               "opens": 0}}}), encoding="utf-8")


def test_ingest_three_sources_and_idempotent(ledger_env):
    _seed_sources(ledger_env)
    first = badcase_ledger.ingest()
    assert first["sources"] == 4  # 错误/空结果/恢复/breaker，正常与夹具排除
    assert first["added"] == 4
    again = badcase_ledger.ingest()
    assert again["added"] == 0 and again["total"] == 4  # 幂等
    kinds = json.loads(json.dumps(badcase_ledger.stats()))["by_kind"]
    assert kinds == {"query_error": 1, "empty_result": 1,
                     "recovery": 1, "breaker": 1}


def test_check_gate_threshold(ledger_env):
    _seed_sources(ledger_env)
    badcase_ledger.ingest()
    ok = badcase_ledger.check("1d", max_new=10)
    assert ok["ok"] is True and ok["new_badcases"] == 4
    strict = badcase_ledger.check("1d", max_new=3)
    assert strict["ok"] is False


def test_list_filter_by_kind(ledger_env):
    _seed_sources(ledger_env)
    badcase_ledger.ingest()
    rows = badcase_ledger._fetch("breaker", None, 10)
    assert len(rows) == 1 and rows[0]["engine"] == "wikipedia"
