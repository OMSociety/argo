#!/usr/bin/env python3
"""source_selection.py — 通用层候选源的统一排序。

## 为什么（2026-10-26）

通用 fallback 此前是 `engine_policy.GENERAL_FREE_FALLBACK` 的静态元组，
再由 `filter_combo_by_policy` 按**位置**截断到前 2 位。实测后果：

  · 第一、二位是 octen（余额不足，403）与 anysearch（p50 1.7s），
    3015 条真实查询里 44.5% 最终由 anysearch 参与交付；
  · 实测 0.8–1.3s、词面质量更高的 tavily_free / parallel_free / firecrawl
    排在第 6–8 位，日常预算截断后**永远不可达**；
  · 学习器算了 engine×domain×lang 的分，但通用路径不读它，
    「这个源在我这里已经坏了」进不了选源。

本模块只做**排序**，不做过滤（quota/熔断/语言仍由既有层处理）。过滤放在
这里会让「为什么这个源没出现」多一个隐藏分支；排序只回答「同样可用时
先试谁」。

## 先验的来源

`GENERAL_PRIORS` 是 2026-10-26 单机实测的固定先验（4–6 条真实查询 ×
单引擎单跑；复跑入口 `python3 scripts/bench_general_pool.py`，脚本会用
隔离状态目录交错跑 static/dynamic 两臂）。它是**冷启动种子**，不是长期
真值：源一旦有 ≥3 条自适应样本，自适应分占 6 成、先验占 4 成。重测后用
新数据更新此表，不要按印象调。
"""

from __future__ import annotations

from typing import Callable

# 先验 = 实测延迟 + 词面相关 + 稳定性的人工压缩（0–1）。只列通用候选；
# 未列出的源给 DEFAULT_PRIOR，不会凭名字占便宜。
GENERAL_PRIORS: dict[str, float] = {
    # 0.6s / 0.76（6 条），中文硬新闻弱于 anysearch
    "yuanbao": 1.00,
    # 1.0s / 0.92（4 条），免 key 匿名通道
    "tavily_free": 0.98,
    # 1.1s / 0.92（4 条）
    "parallel_free": 0.96,
    # 1.3s / 0.88（4 条），1000 credits/月，配额层会限
    "firecrawl": 0.90,
    # 2.7s / 0.78（6 条），中文新闻与长尾覆盖最强，慢
    "anysearch": 0.86,
    # 0.4s，英文技术/国际新闻强，中文通用弱；官方 API 带 authority/date。
    # 付费，预算内才进池，fast/budget 永不进（见 _paid_candidate_allowed）。
    "deepseek_search": 0.84,
    # 2.3s / 0.89（4 条），慢但内容扎实，研究档应提权
    "uapi": 0.72,
    # 2.5s / 0.60（5 条），语义泛化，作最后备选
    "local_bing": 0.62,
    # 实测 4/4 零结果或不是通用搜索源：留在池里只作解释，排序垫底
    "local_baidu": 0.10,
    "wikipedia": 0.10,
    "octen": 0.10,
}
DEFAULT_PRIOR = 0.50

# 允许进入通用池的付费候选。与 paid_policy 的域级对冲是两条不同的路：
# 域级对冲只在 english_tech / intl_news_flash 的第二位；这里是通用池的
# 第 3+ 候选（日常预算截断到 2 时通常轮不到，研究档不截断才参与）。
# fast/budget 永不进；ARGO_PAID_SEARCH=off 或预算耗尽也不进。
PAID_GENERAL_CANDIDATES = frozenset({"deepseek_search"})

# 非中英查询的语言覆盖加成。先验表是在中英查询上测的；西里尔/阿拉伯/
# 日韩等脚本下，语言无关的覆盖源（anysearch/local_bing 带动态 setlang）
# 比英文快源更有召回价值。2026-10-26 全量测试的 cyrillic 用例暴露：
# 不做这层加成，top-2 会全被 tavily/parallel 占掉，语言源被预算截断。
_NON_LATIN_LANG_BOOST: dict[str, float] = {
    "anysearch": 0.35,
    "local_bing": 0.40,
}
_LATIN_OR_CN_LANGS = frozenset({"zh", "en", "mixed", "other", ""})

# 有 ≥3 条自适应样本时，先验与自适应分各占一半；否则先验做主。
_ADAPTIVE_BLEND_SAMPLES = 3


def _prior_for(engine: str, lang: str) -> float:
    prior = GENERAL_PRIORS.get(engine, DEFAULT_PRIOR)
    if lang not in _LATIN_OR_CN_LANGS:
        prior += _NON_LATIN_LANG_BOOST.get(engine, 0.0)
    return prior


def _is_research(mode: str, depth: str, context: str) -> bool:
    try:
        from engine_policy import is_research_context
        return is_research_context(mode=mode, depth=depth, context=context)
    except Exception:
        return mode == "deep" or depth == "deep" or context == "research"


def _usable(candidates: list[str], *, mode: str) -> list[str]:
    """硬性不可用（远端配额耗尽 / fast 档付费源）不参与排序。

    fail-open：quota 模块不可用时保留原列表，由执行层暴露真实失败。
    """
    out = list(candidates)
    try:
        from quota import get_quota_manager
        qm = get_quota_manager()
        try:
            exhausted = qm.remote_exhausted_marks()
            out = [e for e in out if e not in exhausted]
        except Exception:
            pass
        if mode in ("fast", "budget"):
            out = [e for e in out if qm.is_available(e, mode=mode)]
    except Exception:
        pass
    return out


def _paid_search_enabled() -> bool:
    try:
        from engine_env import get_env
        raw = str(get_env("ARGO_PAID_SEARCH", "auto") or "auto")
    except Exception:
        import os
        raw = os.environ.get("ARGO_PAID_SEARCH", "auto")
    return raw.strip().lower() not in ("off", "0", "false", "no")


def _paid_candidate_allowed(engine: str, mode: str) -> bool:
    """付费候选的准入：白名单 + 非 fast/budget + 开关开 + 预算未耗尽。

    与 paid_policy 的 `_paid_hedge_ready` 同一套门槛，只是位置不同：这里
    进通用池，那里插域 combo 第二位。花钱的事一律 fail-closed。
    """
    if engine not in PAID_GENERAL_CANDIDATES or mode in ("fast", "budget"):
        return False
    if not _paid_search_enabled():
        return False
    try:
        from engine_env import is_engine_allowed_by_env
        if not is_engine_allowed_by_env(engine):
            return False
    except Exception:
        pass
    try:
        from engine_admission import is_blocked
        if is_blocked(engine):
            return False
    except Exception:
        pass
    try:
        from quota import get_quota_manager
        return not get_quota_manager().is_hard_down(engine)
    except Exception:
        return False


def candidate_allowed(engine: str, enabled: set[str], mode: str) -> bool:
    """通用候选是否允许参与：enabled 成员，或预算内的白名单付费源。

    两条通用路径都要用这一处判据：`rank_general_candidates` 的池过滤，
    以及 `tfidf_lead_combo` 的最终 `out` 过滤。后者的 `if e in enabled`
    曾把 paid 候选单独丢掉——池排序里有它，组合装配时又被剔掉。
    """
    return engine in enabled or _paid_candidate_allowed(engine, mode)


def rank_general_candidates(
    candidates: list[str],
    *,
    enabled: set[str],
    mode: str = "auto",
    depth: str = "fast",
    context: str = "search",
    lang: str = "",
    score_fn: Callable[[str, str, str, str], tuple[float, int]] | None = None,
) -> list[str]:
    """按「先验 × 自适应 × 用途」排序通用候选源。

    `score_fn(engine, domain, lang, purpose) -> (score, samples)` 可注入，
    测试用假学习器即可确定性断言，不依赖本机 adaptive.db 的时点数据。
    """
    pool = _usable(candidates, mode=mode)
    pool = [e for e in pool if candidate_allowed(e, enabled, mode)]
    if not pool:
        return []

    purpose = "research" if _is_research(mode, depth, context) else "daily"
    if score_fn is None:
        def score_fn(engine: str, domain: str, q_lang: str,
                     use: str) -> tuple[float, int]:
            from adaptive import get_learner
            return get_learner().get_score_with_samples(
                engine, domain, q_lang, use)

    ranked: list[tuple[float, int, str]] = []
    for idx, engine in enumerate(pool):
        prior = _prior_for(engine, lang)
        try:
            adaptive_score, samples = score_fn(
                engine, "general_search", lang, purpose)
        except Exception:
            adaptive_score, samples = 0.5, 0
        if samples >= _ADAPTIVE_BLEND_SAMPLES:
            # 有样本时自适应占 6 成：先验是冷启动种子，不能让「高先验但已
            # 证实失败」的源靠乘法永远压住健康源（实测反例：先验 1.0、
            # 自适应 0 的源乘出来 0.5，仍高于先验 0.5、自适应 0.5 的健康源）。
            weight = 0.4 * prior + 0.6 * min(1.0, float(adaptive_score))
        else:
            weight = prior
        # idx 取负：同分保持候选池原顺序（稳定排序，便于 A/B 复现）
        ranked.append((-weight, idx, engine))
    ranked.sort()
    return [engine for _w, _i, engine in ranked]
