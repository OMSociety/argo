#!/usr/bin/env python3
"""test_cache_conn_scope.py — 缓存连接的作用域语义（B-2）。

背景（2026-10-15）：缓存层 9 处调用点此前写的是
`with self._connect() as conn:`。sqlite3 的**连接**上下文管理器管的是
**事务**（正常退出 commit、异常 rollback），它不关连接——每跑一次就新建并
遗弃一条文件连接。进程里跑几千次缓存操作就攒下几千个 fd，长驻 MCP 进程
迟早撞 ulimit（EMFILE），而报错点会落在完全无关的 socket/文件调用上。

覆盖四件事：
  1. 出作用域后自建连接确实关掉了；
  2. `:memory:` 是共享连接，不能被关（关掉等于内存缓存整层作废）；
  3. 作用域语义 = commit / rollback（异常路径不留半截事务）；
  4. 端到端：公共 API 连打 40 轮，本进程 fd 数不增长（旧实现每轮 +6）。
"""

import os
import sqlite3
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import cache  # noqa: E402


def _scalar(db_path: str, sql: str):
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(sql).fetchone()[0]
    finally:
        conn.close()


def _fd_count():
    """本进程当前打开的 fd 数；两个平台前缀都试（macOS /dev/fd、Linux /proc）。"""
    for probe in ("/dev/fd", "/proc/self/fd"):
        if os.path.isdir(probe):
            return len(os.listdir(probe))
    return None


def test_file_connection_closed_after_scope(tmp_path):
    c = cache.SQLiteCache(db_path=str(tmp_path / "cache.db"))
    with c._conn() as conn:
        assert conn.execute("SELECT 1").fetchone() == (1,)
    with pytest.raises(sqlite3.ProgrammingError):
        conn.execute("SELECT 1")


def test_memory_connection_is_not_closed(tmp_path):
    """:memory: 每次 connect 都是独立空库 —— 共享连接必须活过作用域。"""
    c = cache.SQLiteCache(db_path=":memory:")
    with c._conn() as conn:
        assert conn is c._mem_conn
    assert c._mem_conn.execute("SELECT 1").fetchone() == (1,)
    # 真的还能用，不只是「对象还在」
    c.set("k", "q", "e", 5, {"results": [{"title": "t"}]}, "general", 60)
    assert c.get("k") is not None


def test_scope_commits_on_success(tmp_path):
    """作用域正常退出 = 提交（调用方没显式 commit 时也成立）。"""
    db = str(tmp_path / "cache.db")
    c = cache.SQLiteCache(db_path=db)
    with c._conn() as conn:
        conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
                     ("scope_probe", "v"))
    assert _scalar(db, "SELECT value FROM meta WHERE key='scope_probe'") == "v"


def test_scope_rolls_back_on_exception(tmp_path):
    """作用域异常退出 = 回滚，且连接照样关掉（不留半截事务）。"""
    db = str(tmp_path / "cache.db")
    c = cache.SQLiteCache(db_path=db)

    class Boom(RuntimeError):
        pass

    with pytest.raises(Boom):
        with c._conn() as conn:
            conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
                         ("scope_boom", "x"))
            raise Boom("boom")

    assert _scalar(db, "SELECT COUNT(*) FROM meta WHERE key='scope_boom'") == 0
    with pytest.raises(sqlite3.ProgrammingError):
        conn.execute("SELECT 1")


def test_public_api_does_not_leak_connections(tmp_path):
    """端到端：走公共 API 40 轮，fd 数不增长。

    旧实现（`with self._connect()`）每轮泄漏 5–6 条连接，本用例会看到
    fd 增长上百；阈值 10 只用来吸收解释器自身的抖动。
    """
    before = _fd_count()
    if before is None:
        pytest.skip("本平台无法枚举进程 fd")

    c = cache.SQLiteCache(db_path=str(tmp_path / "cache.db"))
    for i in range(40):
        c.set(f"k{i:03d}", f"q{i}", "e", 5, {"results": [{"title": "t"}]},
              "general", 60)
        c.get(f"k{i:03d}")
        c.has_live(f"k{i:03d}")
        c.find_similar(f"q{i}", "e")
        c.stats
        c.size_mb

    after = _fd_count()
    assert after - before < 10, (
        f"缓存操作泄漏连接：fd {before} → {after}（40 轮 = {after - before} 条）"
    )
