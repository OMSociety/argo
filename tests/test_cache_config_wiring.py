#!/usr/bin/env python3
"""test_cache_config_wiring.py — config.yaml 的 cache.enabled / cache.max_size_mb（B-3）。

背景（2026-10-15）：这两个键是**死配置**。`DEFAULT_CONFIG["cache"]` 定义了它们、
config.yaml 也写着 `enabled: true` / `max_size_mb: 200`，但代码从不读：
  - `SQLiteCache._evict_if_needed` 的字面量口径是模块常量 `MAX_DB_SIZE_MB`，
    改配置无效，只能改源码；
  - `enabled: false` 没有任何效果，关不掉缓存。
「配了但不生效」比「没有这个配置项」更坏——用户按 README 改完，行为不变，
只能怀疑自己改错了地方。

覆盖：
  1. 真源 config.yaml 的两个值真的被读进对象（配置→代码接线存在）；
  2. `enabled: false` 时读恒 miss、写不落盘，且**旧条目也不再被交付**；
  3. `max_size_mb` 真的当驱逐阈值用（不是只存下来看看）。
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
from config import get_cache_config  # noqa: E402


def _rows(db_path: str) -> int:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute("SELECT COUNT(*) FROM search_cache").fetchone()[0]
    finally:
        conn.close()


def _payload() -> str:
    """不可压缩载荷：`_serialize` 对 >阈值的正文做 gzip，重复字符压不出体积。"""
    import random
    import string
    rnd = random.Random(20261015)
    return "".join(rnd.choice(string.printable) for _ in range(3000))


@pytest.fixture()
def patched_config(monkeypatch):
    """在**读取处**打桩（cache.get_cache_config），并保证用完还原。"""
    def _apply(**overrides):
        cfg = {"enabled": True, "ttl": 3600, "max_size_mb": 200}
        cfg.update(overrides)
        monkeypatch.setattr(cache, "get_cache_config", lambda: dict(cfg))
        return cfg
    return _apply


def test_config_values_reach_the_objects(patched_config, tmp_path):
    """配置的两个值都必须落到对象上（旧实现 max_size_mb 无处可落）。"""
    live = get_cache_config()
    sc = cache.SearchCache(db_path=str(tmp_path / "cache.db"))
    assert sc.enabled is bool(live.get("enabled", True))
    assert sc._l2._max_size_mb == float(live["max_size_mb"]), (
        "cache.max_size_mb 没有进到驱逐阈值"
    )
    assert sc.stats["enabled"] is True

    # 真源恰好等于模块常量（200），只用它验不出「读配置」和「读常量」的区别；
    # 换一个常量绝不会取到的值再验一次，判据才和常量解耦。
    patched_config(max_size_mb=37)
    assert cache.SearchCache(db_path=str(tmp_path / "b.db"))._l2._max_size_mb == 37.0


def test_enabled_false_turns_cache_off(patched_config, tmp_path):
    """enabled=false：写入丢弃、读取恒 miss，且旧条目也不交付。"""
    db = str(tmp_path / "cache.db")

    # 先用「开着」的缓存写一条，作为「关掉后不得交付」的旧条目
    on = cache.SearchCache(db_path=db)
    on.set("旧查询", "e", 5, {"results": [{"title": "陈货"}]}, "general")
    assert _rows(db) == 1, "前置写入失败，后续断言无意义"

    patched_config(enabled=False)
    off = cache.SearchCache(db_path=db)
    assert off.enabled is False
    assert off.stats["enabled"] is False

    assert off.get("旧查询", "e", 5, "general") is None, (
        "关缓存后仍交付旧条目——语义应是「没有缓存」，不是「不写但照读」"
    )
    off.set("新查询", "e", 5, {"results": [{"title": "新货"}]}, "general")
    assert off.get("新查询", "e", 5, "general") is None
    assert off._l1.stats["size"] == 0, "L1 也应一并停用"
    assert _rows(db) == 1, f"关缓存后仍写盘：rows={_rows(db)}"
    off.set_engine("新查询", "e", 5, [{"title": "x"}], "general")
    assert off.get_engine("新查询", "e", 5, "general") is None
    assert _rows(db) == 1, f"set_engine 在关缓存状态下仍写盘：rows={_rows(db)}"
    assert off.get_fetch("https://example.com/a") is None


def test_max_size_mb_is_the_eviction_limit(patched_config, tmp_path):
    """max_size_mb=1 必须真的当阈值用：库有界、且驱逐不是「删空」。"""
    patched_config(max_size_mb=1)
    db = str(tmp_path / "cache.db")
    sc = cache.SearchCache(db_path=db)
    assert sc._l2._max_size_mb == 1.0
    payload = _payload()

    for i in range(400):
        sc.set(f"q{i:04d}", "e", 5, {"results": [{"title": payload}]}, "general")

    size_mb = os.path.getsize(db) / 1024 / 1024
    rows = _rows(db)
    assert size_mb < 1.0 * 2.5, f"max_size_mb=1 未被遵守，库体积 {size_mb:.2f} MB"
    assert rows < 400, f"从未发生驱逐（配置阈值没生效）：rows={rows}"
    assert rows > 0, "驱逐把整库删空了"
    # 驱逐后缓存仍可用（与 test_cache_reclaim 同一条底线）
    sc.set("keep", "e", 5, {"results": [{"title": "alive"}]}, "general")
    assert sc.get("keep", "e", 5, "general") is not None
