"""usage_log_clean 单元测试：夹具隔离、别名豁免、干跑与原子落盘。"""
import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import pytest  # noqa: E402

import usage_log_clean  # noqa: E402


@pytest.fixture()
def log_env(tmp_path, monkeypatch):
    d = tmp_path / "usage_log"
    d.mkdir()
    monkeypatch.setenv("ARGO_USAGE_LOG_DIR", str(d))
    return d / "query.jsonl"


def _line(*engines):
    return json.dumps({"ts": "2026-10-11T00:00:00+08:00", "stream": "query",
                       "elapsed_ms": 800, "engines_used": list(engines),
                       "count": 3, "mode": "auto"}, ensure_ascii=False)


def test_dry_run_reports_without_touching(log_env):
    log_env.write_text("\n".join([
        _line("anysearch", "local_bing"),
        _line("slow_primary", "g1"),
    ]) + "\n", encoding="utf-8")
    report = usage_log_clean._clean(log_env, apply=False)
    assert report["total"] == 2 and report["kept"] == 1
    assert report["quarantined"] == 1 and report["applied"] is False
    assert log_env.read_text(encoding="utf-8").count("\n") == 2  # 文件未动


def test_apply_quarantines_fixtures_keeps_real_and_alias(log_env):
    log_env.write_text("\n".join([
        _line("anysearch"),
        _line("fast_garbage", "rescuer"),
        _line("openlibrary"),   # 历史别名：保留
        _line("bing"),          # 历史别名：保留
        _line("slow_primary"),
    ]) + "\n", encoding="utf-8")
    report = usage_log_clean._clean(log_env, apply=True)
    assert report["applied"] is True and report["kept"] == 3
    assert report["quarantined"] == 2
    kept_used = [json.loads(l)["engines_used"]
                 for l in log_env.read_text(encoding="utf-8").splitlines() if l]
    assert kept_used == [["anysearch"], ["openlibrary"], ["bing"]]
    q_path = Path(report["quarantine_path"])
    assert q_path.exists() and q_path.read_text(encoding="utf-8").count("\n") == 2


def test_broken_line_kept_not_quarantined(log_env):
    log_env.write_text("not-json\n" + _line("g1") + "\n", encoding="utf-8")
    report = usage_log_clean._clean(log_env, apply=True)
    assert report["kept"] == 1 and report["quarantined"] == 1
    assert "not-json" in log_env.read_text(encoding="utf-8")


def test_apply_keeps_lines_appended_during_window(log_env, monkeypatch):
    """读写窗口内追加的新行不得丢失（旧实现整文件替换为快照视图）。"""
    log_env.write_text("\n".join([_line("anysearch"), _line("slow_primary")]) + "\n",
                       encoding="utf-8")
    orig_read = Path.read_text

    calls = {"n": 0}

    def read_then_append(self, *a, **kw):
        text = orig_read(self, *a, **kw)
        if self == log_env and calls["n"] == 0:
            calls["n"] += 1
            # 模拟窗口内并发追加一条真实查询（直接改盘）
            with open(log_env, "a", encoding="utf-8") as f:
                f.write(_line("octen") + "\n")
            # 返回快照（不含刚落盘的那行）——旧实现由此开始丢数据
            return text
        return text

    monkeypatch.setattr(Path, "read_text", read_then_append)
    report = usage_log_clean._clean(log_env, apply=True)
    monkeypatch.undo()
    kept = [json.loads(l)["engines_used"]
            for l in log_env.read_text(encoding="utf-8").splitlines() if l]
    assert ["octen"] in kept, f"窗口内追加行被静默丢弃：{kept}"
    assert report["quarantined"] == 1
