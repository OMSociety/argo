"""seek_fts 单元测试：索引生命周期、CJK 短语、降级契约与结果 parity。

契约基线见 seek_fts 模块 docstring；行抽取口径对齐 rg 恒定 -i。
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import seek_fts  # noqa: E402


@pytest.fixture()
def fts_env(tmp_path, monkeypatch):
    """独立索引库 + 开关打开；返回 (状态目录, 搜索树)。"""
    state = tmp_path / "state"
    tree = tmp_path / "tree"
    state.mkdir()
    tree.mkdir()
    monkeypatch.setenv("ARGO_STATE_DIR", str(state))
    monkeypatch.setenv("ARGO_LOCAL_FTS", "1")
    return state, tree


def _write(tree: Path, rel: str, text: str) -> Path:
    p = tree / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def _build(tree):
    info = seek_fts.refresh(str(tree))
    assert info["complete"] == 1, f"首建必须完成: {info}"
    return info


# ── 建库与查询 ────────────────────────────────────────────────────────────────

def test_build_and_english_query(fts_env):
    _state, tree = fts_env
    _write(tree, "a.py", "def alpha(x):\n    return StateRoot(x)\n")
    _write(tree, "b.md", "plain text without the term\n")
    _build(tree)
    rows = seek_fts.content_candidates("stateroot", str(tree))
    assert rows == [(str(tree / "a.py"), 2, "return StateRoot(x)")]


def test_cjk_two_char_phrase(fts_env):
    """wechat-digger 实战坑回归：2 字中文必须以逐字短语命中。"""
    _state, tree = fts_env
    _write(tree, "n.md", "前面若干字，迁移完成于此。\n英文行 migration done\n")
    _build(tree)
    rows = seek_fts.content_candidates("迁移", str(tree))
    assert rows == [(str(tree / "n.md"), 1, "前面若干字，迁移完成于此。")]


def test_case_insensitive_matches_rg(fts_env):
    """rg 恒定 -i：小写查询必须命中大写原文。"""
    _state, tree = fts_env
    _write(tree, "c.py", "USE UPPER CASE HERE\n")
    _build(tree)
    assert seek_fts.content_candidates("upper case", str(tree)) == [
        (str(tree / "c.py"), 1, "USE UPPER CASE HERE")]


def test_line_truncation_matches_seek_truncate(fts_env):
    _state, tree = fts_env
    long_line = "x" * 200 + " needle " + "y" * 200
    _write(tree, "l.txt", long_line + "\n")
    _build(tree)
    rows = seek_fts.content_candidates("needle", str(tree))
    assert rows[0][2] == "x" * 119 + "…"


# ── 降级契约 ─────────────────────────────────────────────────────────────────

def test_disabled_flag_returns_none(fts_env, monkeypatch):
    _state, tree = fts_env
    _write(tree, "a.py", "needle here\n")
    _build(tree)
    monkeypatch.setenv("ARGO_LOCAL_FTS", "0")
    assert seek_fts.content_candidates("needle", str(tree)) is None
    assert not seek_fts.query_suitable("needle")


def test_regex_metachars_rejected(fts_env):
    _state, tree = fts_env
    assert not seek_fts.query_suitable("foo.*bar")
    assert not seek_fts.query_suitable("interface{}")
    assert not seek_fts.query_suitable("a|b")
    assert seek_fts.query_suitable("plain_words")


def test_incomplete_index_falls_back(fts_env):
    """未建成（complete=0）宁可慢不可漏：返回 None 走 rg。"""
    _state, tree = fts_env
    _write(tree, "a.py", "needle here\n")
    seek_fts.refresh(str(tree), budget_s=0.0)  # 0 预算：清单都不走完
    assert seek_fts.content_candidates("needle", str(tree)) is None


def test_zero_hit_on_complete_index_is_truthy_empty(fts_env):
    """索引完整时零命中是真没有（[]），不再回退 rg 空扫。"""
    _state, tree = fts_env
    _write(tree, "a.py", "something\n")
    _build(tree)
    assert seek_fts.content_candidates("zzzznothing", str(tree)) == []


def test_subdir_query_uses_parent_index(fts_env):
    _state, tree = fts_env
    _write(tree, "sub/deep.py", "needle in subdir\n")
    _write(tree, "top.py", "needle at top\n")
    _build(tree)
    rows = seek_fts.content_candidates("needle", str(tree / "sub"))
    assert rows == [(str(tree / "sub" / "deep.py"), 1, "needle in subdir")]


# ── 增量生命周期 ─────────────────────────────────────────────────────────────

def test_incremental_add_modify_delete(fts_env):
    _state, tree = fts_env
    f = _write(tree, "a.py", "old content needle\n")
    _write(tree, "gone.py", "needle will vanish\n")
    _build(tree)
    f.write_text("changed entirely\n", encoding="utf-8")
    _write(tree, "new.py", "fresh needle lands\n", )
    (tree / "gone.py").unlink()
    _build(tree)  # 再次 refresh 收齐增删改
    assert seek_fts.content_candidates("needle", str(tree)) == [
        (str(tree / "new.py"), 1, "fresh needle lands")]


def test_gitignore_respected_via_rg_listing(fts_env):
    """覆盖面 parity：git 仓里 .gitignore 的文件不进索引（rg --files 的语义）。

    非 git 目录 rg 本来就不应用 .gitignore（搜索与清单同一行为，parity 成立），
    所以这里必须建真仓。
    """
    _state, tree = fts_env
    subprocess.run(["git", "init", "-q", str(tree)], check=True, timeout=30)
    (tree / ".gitignore").write_text("ignored*\n", encoding="utf-8")
    _write(tree, "kept.py", "needle kept\n")
    _write(tree, "ignored.py", "needle hidden by gitignore\n")
    _build(tree)
    assert seek_fts.content_candidates("needle", str(tree)) == [
        (str(tree / "kept.py"), 1, "needle kept")]


def test_binary_files_skipped(fts_env):
    _state, tree = fts_env
    (tree / "bin.dat").write_bytes(b"needle\x00binary")
    _write(tree, "text.py", "needle text\n")
    _build(tree)
    assert seek_fts.content_candidates("needle", str(tree)) == [
        (str(tree / "text.py"), 1, "needle text")]


def test_large_body_capped(fts_env):
    """正文截到 _MAX_BODY_BYTES：更深行不在索引（已知偏差），截内行可命中。"""
    _state, tree = fts_env
    head = "needle in head\n"
    body = "x" * seek_fts._MAX_BODY_BYTES + "\n"  # 超界大行，挤掉 tail
    tail = "needle in tail\n"
    _write(tree, "big.log", head + body + tail)
    _build(tree)
    rows = seek_fts.content_candidates("needle", str(tree))
    assert [r[2] for r in rows] == ["needle in head"]


# ── 一致性与健壮性 ───────────────────────────────────────────────────────────

def test_determinism_two_runs_same_order(fts_env):
    _state, tree = fts_env
    for i in range(6):
        _write(tree, f"f{i}.py", f"needle {i}\n")
    _build(tree)
    first = seek_fts.content_candidates("needle", str(tree))
    assert first == seek_fts.content_candidates("needle", str(tree))


def test_corrupt_db_falls_back_to_rg(fts_env):
    _state, tree = fts_env
    _write(tree, "a.py", "needle here\n")
    _build(tree)
    seek_fts.index_db_path().write_bytes(b"not a sqlite file at all")
    assert seek_fts.content_candidates("needle", str(tree)) is None


def test_mtime_window_filters_files(fts_env):
    import time as _t
    _state, tree = fts_env
    p = _write(tree, "a.py", "needle here\n")
    _build(tree)
    future = _t.time() + 3600
    os.utime(p, (future, future))
    seek_fts.refresh(str(tree))  # 把新 mtime 收进索引
    rows = seek_fts.content_candidates("needle", str(tree),
                                       until_ts=_t.time())
    assert rows == []  # 文件 mtime 在窗口外 → 不命中


def test_cli_rebuild_and_status(fts_env):
    _state, tree = fts_env
    _write(tree, "a.py", "needle\n")
    env = dict(os.environ)
    r = subprocess.run(
        [sys.executable, str(SCRIPTS / "seek_fts.py"), "rebuild", str(tree)],
        capture_output=True, text=True, env=env, timeout=60)
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)["complete"] == 1
    r = subprocess.run(
        [sys.executable, str(SCRIPTS / "seek_fts.py"), "status", str(tree)],
        capture_output=True, text=True, env=env, timeout=60)
    assert json.loads(r.stdout)["indexed"] == 1


def test_seek_integration_fts_and_rg_parity(fts_env):
    """端到端：同一条查询，FTS 开与关（rg 主路）结果集一致。"""
    _state, tree = fts_env
    _write(tree, "x.py", "alpha does stateroot things\nsecond line\n")
    _write(tree, "y.md", "另一段：状态根相关\nstateroot mentioned\n")
    _build(tree)
    env = dict(os.environ)
    cmd = [sys.executable, str(SCRIPTS / "seek.py"), "stateroot",
           "--path", str(tree), "--json", "--include-noise"]
    on = json.loads(subprocess.run(cmd, capture_output=True, text=True,
                                   env={**env, "ARGO_LOCAL_FTS": "1"},
                                   timeout=60).stdout)["results"]
    off = json.loads(subprocess.run(cmd, capture_output=True, text=True,
                                    env={**env, "ARGO_LOCAL_FTS": "0"},
                                    timeout=60).stdout)["results"]
    assert [(r["path"], r["line"]) for r in on] == \
        [(r["path"], r["line"]) for r in off]
    assert on, "两条路都必须命中"
