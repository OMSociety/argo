#!/usr/bin/env python3
"""postprocess_signals.py — 加工段两个可选信号：TF-IDF 语义抛光 + 数字交叉验证。

2026-10-16 从 search_pipeline.postprocess 提取（方案二梳理的「真源收敛」一步）。
留在主管线里的代价是实测过的：+37 行把 search_pipeline 顶破祖父上限 1033，
且每个特性自带 try/except + 环境开关，主管线的异常面被无谓放大。提取后：

  - 主管线每个特性只留 3~4 行调用点（与 search_attribution / phrase_filter
    同一形态，本文件也只留调用点的那条纪律在这里是反过来的应用）；
  - 开关与它守护的功能同文件：ARGO_TFIDF_RERANK / ARGO_NUMBER_CROSSCHECK
    不再散在主管线里，读代码的人在同一处看到「功能+门控+降级」；
  - 失败各自降级：本模块的函数不向主管线抛异常，异常只留一行日志。

两个入口都是「纯加工」签名：吃主管线的中间态，吐改写后的结果。
"""
from __future__ import annotations

from typing import Any, Callable


def apply_tfidf_polish(
    query: str,
    merged: list[dict[str, Any]],
    max_results: int,
    mode: str,
    reranker_status: str,
    rank_method: str,
    log: Callable[[str], None] | None = None,
) -> tuple[list[dict[str, Any]], str, bool]:
    """精排降级时的零依赖 TF-IDF 语义抛光（防 SERP 壳链靠 RRF 高分回顶）。

    返回 (merged, rank_method, ran)：
      - ran=True：确实重排过，rank_method 已带 "+tfidf"/"tfidf" 标记；
      - ran=False：未触发（开关关 / fast 档 / 结果不足 / 非降级态）或执行
        失败。两者对调用方含义相同——本轮排序没有 TF-IDF 贡献——由调用方
        决定 none 兜底；异常只留一行日志，不外抛。

    mode 透传给 rerank_tfidf：fast/budget 档其内部直接跳过（零延迟）。
    """
    from search_rank import _RERANK_DEGRADED_STATUSES

    # fast/budget 档先拦：rerank_tfidf 内部虽也会跳过，但那样 ran 会被误置
    # True、rank_method 被误标 "+tfidf"——本轮实际没有任何重排贡献
    # （2026-10-16 本模块测试锁住该语义）。
    if mode in ("fast", "budget"):
        return merged, rank_method, False
    if not merged or len(merged) <= 1:
        return merged, rank_method, False
    if reranker_status not in _RERANK_DEGRADED_STATUSES:
        return merged, rank_method, False
    try:
        from engine_env import env_flag
        if not env_flag("ARGO_TFIDF_RERANK", True):
            return merged, rank_method, False
        from rerank_tfidf import rerank as _tfidf_rerank
        merged = _tfidf_rerank(query, merged, top_k=max_results, mode=mode)
        rank_method = (rank_method + "+tfidf") if rank_method != "none" else "tfidf"
        return merged, rank_method, True
    except Exception as e:
        if log:
            log(f"TF-IDF rerank 跳过: {type(e).__name__}")
        return merged, rank_method, False


def detect_number_conflict(
    query: str,
    merged: list[dict[str, Any]],
    mode: str,
    depth: str,
    log: Callable[[str], None] | None = None,
) -> dict[str, Any] | None:
    """多源同指标数值分歧信号（与 fact_alignment 并列的轻量核验提示）。

    仅 deep/auto 且结果 ≥3 时启用；只对比前 10 条（O(n) 正则扫描，<1ms）。
    有分歧返回 {has_conflict, indicator, values, sources, suggestion}，
    无分歧 / 未启用 / 执行失败返回 None（异常只留一行日志不外抛）。
    values[i] 与 sources[i] 同序配对。
    """
    if not merged or len(merged) < 3 or mode in ("fast", "budget") or depth == "fast":
        return None
    try:
        from engine_env import env_flag
        if not env_flag("ARGO_NUMBER_CROSSCHECK", True):
            return None
        from fact_crosscheck import crosscheck_numbers
        nc = crosscheck_numbers(query, merged[:10])
        if nc.get("has_conflict"):
            return {
                "has_conflict": True,
                "indicator": nc.get("indicator", ""),
                "values": nc.get("values", []),
                "sources": nc.get("sources", []),
                "suggestion": nc.get("suggestion", ""),
            }
    except Exception as e:
        if log:
            log(f"数字交叉验证跳过: {type(e).__name__}")
    return None
