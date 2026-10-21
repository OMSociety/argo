#!/usr/bin/env python3
"""paid_policy.py — 付费搜索的自动对冲位（2026-10-21，方案一）。

只解决一件事：在**已证明有优势的域**里，把付费引擎放到 combo 第二位当对冲，
而不是让它进通用候选池（那会被 TF-IDF/兜底带到任意查询并扣费）。

策略：
  - `ARGO_PAID_SEARCH=off` → 完全关闭；缺省 `auto`。
  - 该域在 `PAID_DOMAIN_HEDGES` 里，且引擎 key 就绪、月度预算未用完
    → 返回该引擎；预算用完/无 key → 回落 `tinyfish`（免费、带日期），
    再不行返回空，由原 combo 继续。
  - `fast`/`budget` 模式不参与（与 quota 的成本纪律一致）。

当前只开两个域：`english_tech`、`intl_news_flash`。依据 2026-10-21 多引擎
实测：DeepSeek 在英文技术/英文新闻上 p50 515ms、日期覆盖 23/39，明显优于
anysearch/Exa/Tavily；中文宽泛新闻与金融原文反而更差，故不纳入。
"""

from __future__ import annotations

import os

__all__ = ["PAID_DOMAIN_HEDGES", "hedge_for", "insert_hedge"]

PAID_DOMAIN_HEDGES: dict[str, str] = {
    "english_tech": "deepseek_search",
    "intl_news_flash": "deepseek_search",
}

_FREE_FALLBACK = "tinyfish"


def _enabled() -> bool:
    return (os.environ.get("ARGO_PAID_SEARCH", "auto").strip().lower()
            not in ("off", "0", "false", "no"))


def _key_ready(engine: str) -> bool:
    try:
        from engine_env import missing_env_for
        return not missing_env_for(engine)
    except Exception:
        return False


def _budget_ok(engine: str) -> bool:
    try:
        from quota import get_quota_manager
        qm = get_quota_manager()
        return (not qm.is_over_budget(engine)) and (not qm.is_hard_down(engine))
    except Exception:
        # 预算层读失败时 fail-closed：宁可不自动花钱
        return False


def hedge_for(domain: str, mode: str = "auto") -> list[str]:
    """返回该域应插入的付费/回落引擎（0 或 1 个）。永不抛异常。"""
    if not _enabled() or mode in ("fast", "budget"):
        return []
    engine = PAID_DOMAIN_HEDGES.get(str(domain or ""))
    if not engine:
        return []
    try:
        if _key_ready(engine) and _budget_ok(engine):
            return [engine]
        # 付费位不可用：TinyFish 是免费且带发布日期的回落位
        if _key_ready(_FREE_FALLBACK) and _budget_ok(_FREE_FALLBACK):
            return [_FREE_FALLBACK]
    except Exception:
        return []
    return []


def insert_hedge(combo: list[str], domain: str, mode: str = "auto") -> list[str]:
    """把付费/回落引擎插到 combo 第二位（原地改并返回，便于链式调用）。"""
    for engine in reversed(hedge_for(domain, mode)):
        if engine not in combo:
            combo.insert(min(1, len(combo)), engine)
    return combo
