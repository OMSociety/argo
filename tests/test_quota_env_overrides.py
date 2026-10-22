#!/usr/bin/env python3
"""2026-10-22：付费引擎次数额度的环境覆盖（DSH 设置页写入）。

背景：面板此前只有 DeepSeek 月度预算，其他付费/限额引擎的次数额度只能改
config.yaml。本组用例锁住三件事：

1. 面板变量能覆盖 profile 的 limit，周期沿用 config.yaml（日/月不同）。
2. 0 = 显式不限制；空/非法 = 保持声明值，不把额度误清零。
3. 覆盖真的参与可用性判定（不是只改显示）。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import quota  # noqa: E402

_OVERRIDE_ENVS = [name for name, _ in quota._QUOTA_LIMIT_ENV]


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for name in _OVERRIDE_ENVS:
        monkeypatch.delenv(name, raising=False)
    yield


def _manager(monkeypatch, tmp_path):
    monkeypatch.setattr(quota, "QUOTA_STATE_PATH", tmp_path / "quota.json",
                        raising=False)
    return quota.QuotaManager()


def test_default_limits_come_from_config(monkeypatch, tmp_path):
    mgr = _manager(monkeypatch, tmp_path)
    assert mgr._profiles["anysearch"]["limit"] == 1000
    assert mgr._profiles["anysearch"]["period"] == "day"
    assert mgr._profiles["yuanbao"]["limit"] == 2000
    assert mgr._profiles["yuanbao"]["period"] == "month"


def test_env_override_changes_limit_but_keeps_period(monkeypatch, tmp_path):
    monkeypatch.setenv("ARGO_QUOTA_ANYSEARCH_LIMIT", "5")
    monkeypatch.setenv("ARGO_QUOTA_YUANBAO_LIMIT", "12")
    mgr = _manager(monkeypatch, tmp_path)
    assert mgr._profiles["anysearch"]["limit"] == 5
    assert mgr._profiles["anysearch"]["period"] == "day"
    assert mgr._profiles["yuanbao"]["limit"] == 12
    assert mgr._profiles["yuanbao"]["period"] == "month"


def test_zero_means_unlimited(monkeypatch, tmp_path):
    monkeypatch.setenv("ARGO_QUOTA_ANYSEARCH_LIMIT", "0")
    mgr = _manager(monkeypatch, tmp_path)
    assert mgr._profiles["anysearch"]["limit"] is None


def test_invalid_value_keeps_declared_limit(monkeypatch, tmp_path):
    monkeypatch.setenv("ARGO_QUOTA_ANYSEARCH_LIMIT", "not-a-number")
    monkeypatch.setenv("ARGO_QUOTA_YUANBAO_LIMIT", "-3")
    mgr = _manager(monkeypatch, tmp_path)
    assert mgr._profiles["anysearch"]["limit"] == 1000
    assert mgr._profiles["yuanbao"]["limit"] == 2000


def test_override_participates_in_availability(monkeypatch, tmp_path):
    """覆盖到 5 次后，第 6 次必须判为不可用（不是只改面板显示）。"""
    monkeypatch.setenv("ARGO_QUOTA_ANYSEARCH_LIMIT", "5")
    mgr = _manager(monkeypatch, tmp_path)
    mgr.record_many([("anysearch", True)] * 5)
    assert mgr.is_available("anysearch") is False
    assert mgr.get_remaining_ratio("anysearch") == 0.0


def test_exa_budget_is_usd_and_drives_availability(monkeypatch, tmp_path):
    """Exa 是 $10/月额度：币种必须是 USD，且花完参与调度判定。"""
    monkeypatch.setenv("ARGO_BUDGET_EXA", "10")
    mgr = _manager(monkeypatch, tmp_path)
    profile = mgr._profiles["exa"]
    assert profile["budget_amount"] == 10
    assert profile["budget_currency"] == "USD"
    assert profile["cost_per_call"] == 0.01
    # 次数上限仍按 config 的 1000 存在；这里先摘掉，单测预算本身
    profile["limit"] = None
    mgr.record_many([("exa", True)] * 1000)
    assert mgr.is_over_budget("exa") is True
    assert mgr.is_available("exa") is False
