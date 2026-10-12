#!/usr/bin/env python3
"""tests/test_local_search_budget.py — local-search 聚合预算语义（P0-1）。

守的缺陷：search_v3 曾把 `timeout` 同时当单引擎 HTTP 超时与整体聚合预算，
且 `except TimeoutError` 在 Python 3.9/3.10 上抓不到
`concurrent.futures.TimeoutError`（3.11 才并入内置类）→ 整体预算形同虚设，
异常穿透聚合层。本测试锁三件事：

  1. total_budget 到点即返回，不等慢引擎的自然完成（fast 引擎结果保留）
  2. 慢引擎被显式记为 timeout，而不是异常冒泡
  3. total_budget 与单引擎 timeout 是两个独立参数
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
for p in (ROOT / "sub-skills" / "local-search", ROOT / "scripts"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import search_v3  # noqa: E402


@pytest.fixture()
def fast_and_slow(monkeypatch):
    """fast 引擎立即返回，slow 引擎 1.5s 后才返回。"""
    def fake_search_one(name, query, n=5, timeout=None, since=None, until=None):
        if name == "slow":
            time.sleep(1.5)
            return [{"title": "slow result", "url": "https://s.example.com/1"}], None
        return [{"title": "fast result", "url": f"https://f.example.com/{name}"}], None
    monkeypatch.setattr(search_v3, "_search_one", fake_search_one)


def test_total_budget_returns_before_slow_engine(fast_and_slow):
    t0 = time.time()
    out = search_v3.search_engines(
        "测试", engines=["fast", "slow"], n=5, skip_cache=True,
        mode="auto", total_budget=0.4)
    elapsed = time.time() - t0
    assert elapsed < 1.2, f"total_budget 未生效：实耗 {elapsed:.2f}s（在等慢引擎）"
    assert "https://f.example.com/fast" in [r.get("url") for r in out["results"]]
    assert "slow" not in out["engines_used"]


def test_slow_engine_marked_timeout_not_raised(fast_and_slow):
    out = search_v3.search_engines(
        "测试", engines=["slow"], n=5, skip_cache=True,
        mode="auto", total_budget=0.3)
    assert any("timeout" in e for e in out["errors"]), out["errors"]
    assert out["results"] == []


def test_per_engine_timeout_independent_of_budget(monkeypatch):
    """单引擎 timeout=1.5 允许 1s 的引擎完成；总预算 10s 不提前砍。"""
    def fake_search_one(name, query, n=5, timeout=None, since=None, until=None):
        time.sleep(1.0)
        return [{"title": "ok", "url": "https://o.example.com/1"}], None
    monkeypatch.setattr(search_v3, "_search_one", fake_search_one)
    out = search_v3.search_engines(
        "测试", engines=["only"], n=5, skip_cache=True, mode="auto",
        timeout=1.5, total_budget=10)
    assert out["results"], "单引擎超时与总预算被混用，1s 引擎被误杀"


def test_fast_single_engine_no_poll_grid_penalty(monkeypatch):
    """快引擎（毫秒级返回）不得被 0.25s 轮询网格拖慢——完成事件即唤醒。

    回归（2026-10-12 审查）：daemon 线程改写后主循环用 sleep(0.25) 收尸，
    1 引擎/53ms 的场景退化成 ≥250ms。Event 唤醒后应回到接近真实的几十 ms。
    """
    def fake_search_one(name, query, n=5, timeout=None, since=None, until=None):
        time.sleep(0.03)
        return [{"title": "r", "url": f"https://x.example.com/{name}"}], None
    monkeypatch.setattr(search_v3, "_search_one", fake_search_one)
    t0 = time.time()
    out = search_v3.search_engines("测试", engines=["fast1"], n=5, skip_cache=True,
                                   mode="auto", total_budget=5.0)
    elapsed = time.time() - t0
    assert out["results"], "快引擎结果必须收到"
    assert elapsed < 0.2, f"快引擎被轮询网格拖慢：{elapsed:.3f}s（应 <0.2s）"


def test_early_stop_does_not_wait_slow_engine(monkeypatch):
    """够数早停立即返回，不 join 慢引擎（daemon 线程语义）。"""
    def fake_search_one(name, query, n=5, timeout=None, since=None, until=None):
        if name == "slow":
            time.sleep(3.0)
            return [{"title": "s", "url": "https://s.example.com"}], None
        return [{"title": f"r{i}", "url": f"https://f.example.com/{i}"}
                for i in range(5)], None
    monkeypatch.setattr(search_v3, "_search_one", fake_search_one)
    t0 = time.time()
    out = search_v3.search_engines("测试", engines=["fast1", "slow"], n=5,
                                   skip_cache=True, mode="auto", total_budget=30.0)
    elapsed = time.time() - t0
    assert elapsed < 2.0, f"早停未生效（在等慢引擎）：{elapsed:.2f}s"
    assert out["results"], "快引擎结果必须保留"
