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
    monkeypatch.setenv("ARGO_BUDGET_DEEPSEEK_SEARCH", "20")
    c = route_cache._route_state_fingerprint()
    assert c != b
    # 对冲位置（常驻第二位 vs 第三位）同样改变 combo，必须参与指纹
    monkeypatch.delenv("ARGO_PAID_HEDGE_DEFER", raising=False)
    d = route_cache._route_state_fingerprint()
    monkeypatch.setenv("ARGO_PAID_HEDGE_DEFER", "1")
    e = route_cache._route_state_fingerprint()
    assert d != e


def test_budget_hot_reload_and_breaker_respect(isolated, monkeypatch):
    """运行期改预算无需重建 QuotaManager 即生效；禁用或熔断的引擎不进对冲位。"""
    from quota import get_quota_manager
    qm = get_quota_manager()
    assert qm.budget_status("deepseek_search")["budget"] == pytest.approx(5.0)
    budget.set_budget("deepseek_search", 12.5, currency="CNY", period="month")
    # 触发跨引擎或重查：热读立即感知 budgets.json 变更
    assert qm.budget_status("deepseek_search")["budget"] == pytest.approx(12.5)

    monkeypatch.setenv("ARGO_PAID_SEARCH", "auto")
    monkeypatch.setattr(paid_policy, "_key_ready", lambda e: True)
    monkeypatch.setattr(paid_policy, "_budget_ok", lambda e: True)
    monkeypatch.setattr(paid_policy, "_env_allowed", lambda e: True)
    monkeypatch.setattr(paid_policy, "_admission_ok", lambda e: True)
    # 2026-10-26 修复：deepseek_search 是 explicit_only，本来就不在 enabled；
    # 付费对冲是显式白名单，不能再拿 enabled 判一次（否则策略永远不触发）。
    assert paid_policy.hedge_for(
        "english_tech", "auto", enabled={"tinyfish"}) == ["deepseek_search"]
    # 真正的禁用门槛仍生效：env 禁用 / 准入拉黑 → 回落 tinyfish
    monkeypatch.setattr(paid_policy, "_env_allowed", lambda e: False)
    assert paid_policy.hedge_for(
        "english_tech", "auto", enabled={"tinyfish"}) == ["tinyfish"]
    monkeypatch.setattr(paid_policy, "_env_allowed", lambda e: True)
    monkeypatch.setattr(paid_policy, "_admission_ok", lambda e: False)
    assert paid_policy.hedge_for(
        "english_tech", "auto", enabled={"tinyfish"}) == ["tinyfish"]


def test_paid_hedge_works_with_real_routable_enabled(monkeypatch):
    """生产接线回归：真实 routable enabled 不含 explicit_only 的 DeepSeek，
    付费白名单仍应命中；这正是 2026-10-21 到 10-26 的失效点。"""
    from config import get_engines, load_config
    import route_combo

    enabled = set(get_engines(load_config(), routable_only=True))
    assert "deepseek_search" not in enabled

    monkeypatch.setenv("ARGO_PAID_SEARCH", "auto")
    monkeypatch.setattr(paid_policy, "_key_ready", lambda e: True)
    monkeypatch.setattr(paid_policy, "_budget_ok", lambda e: True)
    monkeypatch.setattr(paid_policy, "_env_allowed", lambda e: True)
    monkeypatch.setattr(paid_policy, "_admission_ok", lambda e: True)
    monkeypatch.setattr(route_combo, "_breaker_blocked", lambda e: False)

    assert paid_policy.hedge_for(
        "english_tech", "auto", enabled=enabled) == ["deepseek_search"]
    assert paid_policy.hedge_for(
        "intl_news_flash", "auto", enabled=enabled) == ["deepseek_search"]


def test_hedge_position_default_and_defer(monkeypatch):
    """默认第二位；DEFER=1 时 english_tech 降到第三位，新闻域不变。"""
    import route_combo

    monkeypatch.setenv("ARGO_PAID_SEARCH", "auto")
    monkeypatch.delenv("ARGO_PAID_HEDGE_DEFER", raising=False)
    monkeypatch.setattr(paid_policy, "_key_ready", lambda e: True)
    monkeypatch.setattr(paid_policy, "_budget_ok", lambda e: True)
    monkeypatch.setattr(paid_policy, "_env_allowed", lambda e: True)
    monkeypatch.setattr(paid_policy, "_admission_ok", lambda e: True)
    monkeypatch.setattr(route_combo, "_breaker_blocked", lambda e: False)

    assert paid_policy.insert_hedge(
        ["anysearch", "exa"], "english_tech", "auto",
        enabled={"tinyfish"}) == ["anysearch", "deepseek_search", "exa"]

    monkeypatch.setenv("ARGO_PAID_HEDGE_DEFER", "1")
    assert paid_policy.insert_hedge(
        ["anysearch", "exa"], "english_tech", "auto",
        enabled={"tinyfish"}) == ["anysearch", "exa", "deepseek_search"]
    # 新闻域即便开了 DEFER 也保持第二位（收益最明确）
    assert paid_policy.insert_hedge(
        ["google_news", "em_global_news"], "global_event", "auto",
        enabled={"tinyfish"}) == [
            "google_news", "deepseek_search", "em_global_news"]


def test_batch14_hkex_s2t_longest_match_first():
    """长词优先：『回购注销』必须完整转为『購回註銷』，不被『回购→購回』提前截断。"""
    from engines_builders_batch14 import _hkex_s2t
    assert _hkex_s2t("腾讯回购注销公告") == "騰訊購回註銷公告"
    assert _hkex_s2t("股东大会决议") == "股東大會決議"
