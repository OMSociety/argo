#!/usr/bin/env python3
"""caliber_isolation.py — 口径隔离：不同口径的引擎结果不直接 merge。

同口径引擎的结果才能 merge 到同一条目，不同口径的结果按优先级并列输出。
口径分类表 + 分组逻辑是纯函数，与 search_rank.py 的调度/融合职责不同。
"""

from __future__ import annotations

from typing import Any

_CALIBER_GROUPS = {
    "financial_data": frozenset({
        "fred", "worldbank", "eurostat", "frankfurter", "fx_rate",
        "eastmoney", "sina_quote", "tencent_quote", "yahoo_finance",
        "sec_companyfacts", "finviz", "nbs_stats", "un_comtrade",
        "em_flow", "em_miaoxiang", "tencent_kline", "jin10",
    }),
    "encyclopedia": frozenset({
        "wikipedia", "baidu_baike", "cn_encyclopedia", "wikidata",
        "wikisource", "wikimedia_commons", "dnb", "getty_heritage",
    }),
    "social": frozenset({
        "twitter", "weibo", "zhihu", "zhihu_global", "zhihu_user",
        "xiaohongshu", "wechat_sogou", "bilibili_hot", "douyin_hot",
        "weibo_hot", "toutiao_hot", "hackernews", "reddit",
    }),
    "code": frozenset({
        "github", "stackoverflow", "so", "gitlab", "deps_dev",
        "endoflife", "pypi", "npm", "crates_io",
    }),
    "news": frozenset({
        "google_news", "bing_rss", "cls_telegraph", "em_news_search",
        "em_global_news", "people_daily", "upi", "globo",
    }),
    "academic": frozenset({
        "arxiv", "pubmed", "google_scholar", "semantic_scholar",
        "crossref", "openalex", "doaj", "core", "gdacs",
        "clinicaltrials", "openfda", "uniprot", "rcsb_pdb",
    }),
    "media": frozenset({
        "imdb", "themoviedb", "tvmaze", "jikan", "deezer",
        "itunes", "listenbrainz", "figshare", "met_museum",
    }),
    "reference": frozenset({
        "open_library", "weread", "douban_book", "gutenberg",
        "stanford_encyclopedia", "rfc_editor", "us_legal", "legal",
        "courtlistener", "europeana", "hal", "eu_opendata",
    }),
}

# 口径优先级：数值越小优先级越高，排序时高口径的结果排在前面
_CALIBER_PRIORITY = {
    "financial_data": 0,
    "academic": 1,
    "encyclopedia": 2,
    "news": 3,
    "social": 4,
    "code": 5,
    "media": 6,
    "reference": 7,
    "general": 8,
}


def caliber_of(engine: str) -> str:
    """返回引擎的口径分类，未分类的引擎归为 general。"""
    for caliber, engines in _CALIBER_GROUPS.items():
        if engine in engines:
            return caliber
    return "general"


def group_by_caliber(ranked_lists: list[list[dict[str, Any]]]) -> dict[str, list[list[dict[str, Any]]]]:
    """按口径分组：同口径的引擎结果才能 merge。"""
    caliber_groups: dict[str, list[list[dict[str, Any]]]] = {}
    for results in ranked_lists:
        for r in results:
            eng = r.get("_engine") or r.get("source", "") or ""
            cal = caliber_of(eng)
            if cal not in caliber_groups:
                caliber_groups[cal] = []
            caliber_groups[cal].append([r])
    return caliber_groups


def merge_within_caliber(
    groups: list[list[dict[str, Any]]],
    k: int = 60,
    weighted: bool = True,
    lang: str | None = None,
    _canonical_url=None,
    _engine_weight=None,
) -> list[dict[str, Any]]:
    """同口径内做 RRF 融合。"""
    if _canonical_url is None:
        from url_canon import canonical_url as _canonical_url
    if _engine_weight is None:
        from search_rank import _engine_weight as _engine_weight

    scores: dict[str, float] = {}
    items: dict[str, dict[str, Any]] = {}

    for group in groups:
        for i, r in enumerate(group):
            key = (
                _canonical_url(r.get("url", ""))
                or (f"__title__:{r.get('title', '')}" if r.get("title") else "")
                or (f"__card__:{r.get('card_type', '')}" if r.get("card_type") else "")
                or f"__idx__:{id(r)}"
            )
            w = _engine_weight(r.get("_engine") or r.get("source") or "",
                               lang=lang) if weighted else 1.0
            scores[key] = scores.get(key, 0.0) + w / (k + i + 1)
            eng = r.get("_engine") or r.get("source", "") or ""
            if key not in items:
                item = dict(r)
                item["_rrf_score"] = 0.0
                cons: list[str] = []
                if eng:
                    cons.append(eng)
                item["consensus_engines"] = cons
                items[key] = item
            else:
                cur = items[key]
                new_txt = f"{r.get('title', '')} {r.get('snippet', '')}"
                cur_txt = f"{cur.get('title', '')} {cur.get('snippet', '')}"
                if len(new_txt) > len(cur_txt):
                    cur["title"] = r.get("title", cur.get("title"))
                    cur["snippet"] = r.get("snippet", cur.get("snippet"))
                sources = {cur.get("source", ""), r.get("source", "")}
                cur["source"] = "/".join(s for s in sources if s)
                cons = list(cur.get("consensus_engines") or [])
                if eng and eng not in cons:
                    cons.append(eng)
                cur["consensus_engines"] = cons

    ranked = sorted(scores.items(), key=lambda x: -x[1])
    out = []
    for key, _ in ranked:
        item = items[key]
        item["_rrf_score"] = round(scores[key], 6)
        out.append(item)
    return out


def merge_by_caliber(
    ranked_lists: list[list[dict[str, Any]]],
    k: int = 60,
    weighted: bool = True,
    lang: str | None = None,
    _canonical_url=None,
    _engine_weight=None,
) -> list[dict[str, Any]]:
    """口径隔离的 RRF 融合：同口径内 merge，不同口径按优先级并列输出。

    这是 rrf_merge 的口径隔离版本，调用方（search_rank.rrf_merge）传入
    私有函数引用，本模块不反向依赖 search_rank。

    当 weighted=False 时，不分组，走全局 RRF（经典 RRF 行为）。
    """
    if not weighted:
        # 经典 RRF：所有结果在同一个池中竞争，不分组
        # merge_within_caliber 期望 list[list[dict]]，把所有结果放在一个 group 中
        all_results = [r for results in ranked_lists for r in results]
        return merge_within_caliber(
            [all_results],
            k=k, weighted=False, lang=lang,
            _canonical_url=_canonical_url, _engine_weight=_engine_weight,
        )

    caliber_groups = group_by_caliber(ranked_lists)

    merged_by_caliber: dict[str, list[dict[str, Any]]] = {}
    for cal, groups in caliber_groups.items():
        merged_by_caliber[cal] = merge_within_caliber(
            groups, k=k, weighted=weighted, lang=lang,
            _canonical_url=_canonical_url, _engine_weight=_engine_weight,
        )

    # 不同口径按优先级排序后并列输出
    out = []
    for cal in sorted(merged_by_caliber.keys(),
                     key=lambda c: _CALIBER_PRIORITY.get(c, 8)):
        out.extend(merged_by_caliber[cal])
    return out
