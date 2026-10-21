#!/usr/bin/env python3
"""月度预算与付费对冲位的门禁（2026-10-21）。

锁三件事：
1. 预算只对**成功调用**计费（DeepSeek 只对成功请求收费），失败不消耗预算；
2. 预算到顶后 `is_over_budget` 为真，显式调用由 dispatch 返回可行动错误；
3. 付费对冲只在白名单域、key 就绪、预算未用完时插入；预算用完回落 TinyFish。

知乎全网的 publish_time / db: 操作符也在这里锁拼装，避免参数回归。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import budget  # noqa: E402
import paid_policy  # noqa: E402


@pytest.fixture()
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("ARGO_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("ARGO_BUDGET_FILE", str(tmp_path / "budgets.json"))
    monkeypatch.delenv("ARGO_BUDGETS_JSON", raising=False)
    monkeypatch.delenv("ARGO_BUDGET_DEEPSEEK_SEARCH", raising=False)
    import quota
    old = quota._manager
    quota._manager = None
    yield tmp_path
    quota._manager = old


def test_default_budget_is_deepseek_five_cny(isolated):
    entry = budget.load_budgets()["deepseek_search"]
    assert entry["amount"] == 5.0
    assert entry["currency"] == "CNY"
    assert entry["period"] == "month"


def test_set_and_unset_budget(isolated):
    budget.set_budget("deepseek_search", 3.0, currency="CNY", period="month")
    assert budget.load_budgets()["deepseek_search"]["amount"] == 3.0
    assert budget.unset_budget("deepseek_search") is True
    # 删除文件条目后回到默认 5
    assert budget.load_budgets()["deepseek_search"]["amount"] == 5.0


def test_budget_counts_only_success(isolated):
    from quota import get_quota_manager
    qm = get_quota_manager()
    qm.record("deepseek_search", success=False)
    qm.record("deepseek_search", success=True)
    st = qm.get_stats()["deepseek_search"]
    assert st["cost_used"] == pytest.approx(0.005)
    assert st["total_cost"] == pytest.approx(0.005)


def test_budget_exhaustion(isolated):
    budget.set_budget("deepseek_search", 0.01, currency="CNY", period="month")
    from quota import get_quota_manager
    qm = get_quota_manager()
    assert qm.is_over_budget("deepseek_search") is False
    qm.record("deepseek_search", success=True)
    qm.record("deepseek_search", success=True)
    assert qm.is_over_budget("deepseek_search") is True
    assert qm.get_stats()["deepseek_search"]["budget"] == pytest.approx(0.01)


def test_hedge_off_and_fast(monkeypatch):
    monkeypatch.setenv("ARGO_PAID_SEARCH", "off")
    assert paid_policy.hedge_for("english_tech", "auto") == []
    monkeypatch.setenv("ARGO_PAID_SEARCH", "auto")
    assert paid_policy.hedge_for("english_tech", "fast") == []


def test_hedge_prefers_deepseek_then_tinyfish(monkeypatch):
    monkeypatch.setenv("ARGO_PAID_SEARCH", "auto")
    monkeypatch.setattr(paid_policy, "_key_ready", lambda e: True)
    monkeypatch.setattr(paid_policy, "_budget_ok", lambda e: True)
    assert paid_policy.hedge_for("english_tech", "auto") == ["deepseek_search"]
    monkeypatch.setattr(paid_policy, "_budget_ok",
                        lambda e: e != "deepseek_search")
    assert paid_policy.hedge_for("english_tech", "auto") == ["tinyfish"]
    assert paid_policy.hedge_for("academic", "auto") == []


def test_zhihu_global_publish_filter_and_db_operator():
    from engines_builders_batch10 import (
        _build_zhihu_publish_filter,
        _parse_db_operator,
    )
    from datetime import datetime
    expected = int(datetime.fromisoformat("2026-10-01").timestamp())
    assert _build_zhihu_publish_filter("2026-10-01", None) == \
        f"publish_time>={expected}"
    assert _parse_db_operator("db:realtime AI news") == ("realtime", "AI news")
    assert _parse_db_operator("普通查询") == ("all", "普通查询")


def test_route_cache_fingerprint_tracks_paid_switch(monkeypatch):
    """ARGO_PAID_SEARCH 改路由组合，必须让路由缓存换键（否则 off 不生效）。"""
    import route_cache
    monkeypatch.setenv("ARGO_GENERAL_FALLBACK_LEAD", "")
    monkeypatch.setenv("ARGO_GENERAL_FALLBACK_LEGACY", "")
    monkeypatch.setenv("ARGO_PAID_SEARCH", "auto")
    a = route_cache._route_state_fingerprint()
    monkeypatch.setenv("ARGO_PAID_SEARCH", "off")
    b = route_cache._route_state_fingerprint()
    assert a and b and a != b
