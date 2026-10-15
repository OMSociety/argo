#!/usr/bin/env python3
"""test_b4_knobs.py — B-4 的两个旋钮：编排并发上限 + 本地检索缓存 TTL。

并发 3→6（`execution.max_parallel_engines`）：
  - 真源 config.yaml 的值必须真的被调度读到（否则又是一处「配了不生效」）；
  - `ARGO_MAX_PARALLEL_ENGINES` 是 A/B / 运维覆盖口，必须压过配置；
  - 非法取值回落配置，绝不抛异常（旋钮是加速器不是依赖）；
  - deep 档不得低于日常档（B-4 把日常档提到 6 之后，deep 的定值 5 会变成
    「深研比日常更保守」，与它自己的注释相反）。

local_seek TTL 300→3600：
  - 常量与落盘/进程内两条读路径共用同一个值；
  - 超过旧 TTL（300s）但未超新 TTL（3600s）的条目必须命中——旧语义下它是
    miss（这条就是本次改动的行为差）；
  - 超过 3600s 必须失效（TTL 变长 ≠ 过期语义消失）。
"""

import sys
import types
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import config  # noqa: E402
import engine_dispatch as ed  # noqa: E402
import local_seek as ls  # noqa: E402

_ENV = "ARGO_MAX_PARALLEL_ENGINES"


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv(_ENV, raising=False)


def _patch_config_value(monkeypatch, value):
    # 必须 patch **sys.modules 里活着的那个 config 模块对象**，不是本模块
    # import 时绑定的名字：test_argo_paths 的 sys.modules.pop + 重导入会造出
    # 一个新模块对象，此后 `import config` 拿旧对象、engine_dispatch 函数内
    # `from config import ...` 拿新对象——patch 旧对象对调度侧零影响，
    # test_deep_never_below_configured 在完整测试跑里必然红（独立跑全绿）。
    # 取 sys.modules 现值使 patch 对「谁在读」永远成立，与别名分裂无关。
    import sys as _sys
    live = _sys.modules.get("config") or config
    monkeypatch.setattr(live, "get_execution_config",
                        lambda *a, **k: {"max_parallel_engines": value})


# ── 并发上限 ──────────────────────────────────────────────────────────────────

def test_shipped_config_value_reaches_the_scheduler():
    """真源 config.yaml 写 6，调度就必须拿 6（这就是 3→6 的落地判据）。"""
    declared = (yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
                or {}).get("execution", {}).get("max_parallel_engines")
    assert declared == 6, f"config.yaml 的并发值不是 6：{declared!r}"
    config.load_config(force=True)  # 屏蔽进程内/磁盘配置缓存的陈旧值
    assert ed._max_parallel_engines() == 6


def test_env_override_beats_config(monkeypatch):
    _patch_config_value(monkeypatch, 6)
    monkeypatch.setenv(_ENV, "3")
    assert ed._max_parallel_engines() == 3
    monkeypatch.setenv(_ENV, "6")
    assert ed._max_parallel_engines() == 6


def test_invalid_env_falls_back_to_config(monkeypatch):
    _patch_config_value(monkeypatch, 6)
    for bad in ("abc", "0", "-2", "2.5", ""):
        monkeypatch.setenv(_ENV, bad)
        assert ed._max_parallel_engines() == 6, f"{bad!r} 应回落配置而不是抛异常"


def test_deep_never_below_configured(monkeypatch):
    _patch_config_value(monkeypatch, 2)
    assert ed._max_parallel_engines(depth="deep") == 5   # 老底线仍在
    _patch_config_value(monkeypatch, 6)
    assert ed._max_parallel_engines(depth="deep") == 6   # 不得比日常档更保守
    _patch_config_value(monkeypatch, 9)
    assert ed._max_parallel_engines(depth="deep") == 9


def test_env_override_applies_to_deep_too(monkeypatch):
    _patch_config_value(monkeypatch, 6)
    monkeypatch.setenv(_ENV, "3")
    assert ed._max_parallel_engines(depth="deep") == 5   # max(5, 3)


# ── local_seek TTL ────────────────────────────────────────────────────────────

def test_ttl_constant_is_one_hour():
    assert ls._LOCAL_SEEK_TTL_S == 3600.0


class _FrozenClock(types.SimpleNamespace):
    """只冻 local_seek 眼里的时间，不动全局 time.time。"""

    def __init__(self, t: float):
        super().__init__(time=lambda: t)


def test_disk_cache_hit_survives_past_old_ttl(tmp_path, monkeypatch):
    """600s 的条目：旧 TTL(300s) 下是 miss，新 TTL(3600s) 下必须命中。"""
    base = 1_700_000_000.0
    monkeypatch.setattr(ls, "_seek_disk_cache_path", lambda: tmp_path / "lsc.json")
    monkeypatch.setattr(ls, "time", _FrozenClock(base))
    ls._seek_disk_cache_put("k|5|/d", [{"title": "A"}])

    monkeypatch.setattr(ls, "time", _FrozenClock(base + 600))
    got = ls._seek_disk_cache_get("k|5|/d")
    assert got and got[0]["title"] == "A", "TTL 变长后 600s 的条目仍被当成过期"

    monkeypatch.setattr(ls, "time", _FrozenClock(base + 3660))
    assert ls._seek_disk_cache_get("k|5|/d") is None, "超过 3600s 必须失效"


def test_inprocess_cache_hit_survives_past_old_ttl(tmp_path, monkeypatch):
    """进程内那条读路径必须与落盘层同口径（两处各写一个 TTL 就会分叉）。"""
    import seek_locator
    target = str(tmp_path)
    monkeypatch.setattr(ls, "_seek_disk_cache_path",
                        lambda: tmp_path / "nonexistent.json")
    # 失手走到真检索时立刻短路：本用例只验证缓存层
    monkeypatch.setattr(seek_locator, "resolve_seek_py", lambda: None)

    base = 1_700_000_000.0
    monkeypatch.setattr(ls, "time", _FrozenClock(base))

    ls._LOCAL_SEEK_CACHE.clear()
    try:
        ls._LOCAL_SEEK_CACHE[f"q|5|{target}"] = (base - 600, [{"title": "cached"}])
        got = ls._run_local_seek("q", 5, search_dir=target)
        assert got == [{"title": "cached"}], (
            f"600s 的进程内条目未命中（旧 300s TTL 的残留语义）：{got}"
        )
        # 过期仍要过期
        ls._LOCAL_SEEK_CACHE[f"q|5|{target}"] = (base - 3660, [{"title": "cached"}])
        assert ls._run_local_seek("q", 5, search_dir=target) == []
    finally:
        ls._LOCAL_SEEK_CACHE.clear()
