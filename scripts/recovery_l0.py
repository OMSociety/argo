#!/usr/bin/env python3
"""recovery_l0 — 恢复链 L0：early-stop 误判时补跑被跳过的同域引擎。

early-stop 触发后 merged 归零（壳/噪声被下游过滤清零），combo 里
routed 但未调用的引擎是最小成本恢复对象——它们与已跑引擎同域，
比 L3 换跨域引擎更可能交付本域结果（2026-10-11 热榜实测：
wave-1 首引擎交壳骗过早停、同域真榜单引擎被 cancelled，merged
归零触发 2.3s 跨域恢复链）。

L0 是恢复决策树的第 0 级：补跑本 combo 的 skipped 引擎，非空
即采用；失败才落 L3 换引擎。执行器由调用方注入（search_pipeline
的 _run_one/_ingest 闭包），本模块不依赖编排状态，与 recovery.py
的 L1–L4 决策树职责分离。
"""

from __future__ import annotations

from typing import Any, Callable

from search_rank import deduplicate_by_url, rrf_merge


def maybe_retry_skipped(
    early_stopped: bool,
    engines_combo: list[str],
    raw_results: dict[str, list[dict[str, Any]]],
    available_engines: Callable[[], list[str] | set[str]],
    query: str,
    run_one: Callable[..., tuple[str, list[dict[str, Any]], Any, float]],
    ingest: Callable[..., None],
    max_results: int,
    emit_usage: Callable[[str, dict[str, Any]], bool] | None,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    """early-stop 误判后的 L0 恢复：补跑被跳过的同域引擎。

    返回 (结果, 恢复结论)。结果非空时调用方将其作为 merged、
    结论随顶层 recovery 字段输出；为空返回 ([], None)，调用方
    落 L3 换引擎。补跑结果按引擎记回 raw_results（provenance
    与自适应学习可见），并按恢复流发射使用日志。
    """
    if not early_stopped:
        return [], None
    skipped = [e for e in engines_combo if e not in raw_results]
    if not skipped:
        return [], None
    try:
        available = set(available_engines())
    except Exception:
        available = None
    lists: list[list[dict[str, Any]]] = []
    for eng in skipped:
        if available is not None and eng not in available:
            continue
        try:
            _e, res, _out, _lat = run_one(eng)
            ingest(_e, res, _out, _lat)
            goods = [r for r in res
                     if isinstance(r, dict) and "error" not in r]
            if goods:
                lists.append(goods)
        except Exception:
            continue
    if not lists:
        return [], None
    merged = (rrf_merge(lists) if len(lists) > 1
              else deduplicate_by_url(lists[0]))
    merged = merged[:max_results]
    if not merged:
        return [], None
    by_eng: dict[str, list[dict[str, Any]]] = {}
    for r in merged:
        eng = r.get("_engine") or r.get("source") or ""
        if eng:
            r.setdefault("consensus_engines", [eng])
            by_eng.setdefault(eng, []).append(r)
    for eng, lst in by_eng.items():
        raw_results.setdefault(eng, lst)
    info = {
        "triggered": True,
        "recovered": True,
        "level_used": "L0",
        "strategy_used": "retry_skipped",
        "steps_tried": [{
            "level": "L0",
            "strategy": "retry_skipped",
            "query": query,
            "engines": skipped,
            "outcome": f"{len(merged)} results",
        }],
        "final_query": query,
        "note": "early-stop 误判后补跑 skipped 引擎成功",
    }
    if emit_usage is not None:
        try:
            emit_usage("recovery", {
                "query": (query[:60] if query else query),
                "triggered": True,
                "recovered": True,
                "level_used": "L0",
                "strategy_used": "retry_skipped",
                "steps_tried": 1,
                "final_query": (query[:60] if query else query),
                "note": info["note"],
            })
        except Exception:
            pass
    return merged, info
