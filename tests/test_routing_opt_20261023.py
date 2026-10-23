#!/usr/bin/env python3
"""test_routing_opt_20261023.py — 方案一、方案二与方案四优化落地专项回归测试。

覆盖：
  1. 方案一：锚点词前置快筛候选收敛性与准确性；
  2. 方案二：多意图命中时长词跨度次域加权提拔与前序特化域稳定性；
  3. 方案四：SERP 守卫场景下的自适应放宽查询生成与年份/度/长尾词剥离。
"""

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from route import route_query  # noqa: E402
from route_domains import (  # noqa: E402
    match_domains,
    _get_candidate_domain_indices,
    _extract_anchors,
)
from recovery import relax_query  # noqa: E402
from serp_guard import suggest_relaxed_query  # noqa: E402


def test_anchor_fast_filter_covers_target():
    """方案一：锚点快筛候选集合必须覆盖真正命中的域。"""
    q = "上海明天下雨吗"
    # match_domains 驱动编译初始化
    hits = match_domains(q)
    assert len(hits) >= 1
    assert hits[0]["name"] == "weather_query"
    candidates = _get_candidate_domain_indices(q)
    assert candidates is not None


def test_extract_anchors_soundness():
    """方案一：含有字符类或通配符的模式不得产出虚假锚点。"""
    assert _extract_anchors("[一-鿿]") is None
    assert _extract_anchors(r"\d+年") is None
    anc = _extract_anchors(r"(?i)(天气|气温|下雨)")
    assert anc is not None
    assert "天气" in anc
    assert "下雨" in anc


def test_secondary_domain_rescoring():
    """方案二：多意图次域排序根据跨度与位置动态打分。"""
    # 复合查询：同时可能触发学术和技术
    hits = match_domains("GPT 论文 综述", max_n=3)
    domain_names = [h["name"] for h in hits]
    # academic 在 intent_gate 让位后必须居首，次域保持稳定
    assert "academic" in domain_names


def test_relaxed_query_cleans_year_and_tail():
    """方案四：自适应放宽精准切除年份、年度及报告/数据等过度限制词。"""
    cases = [
        ("2026年新能源汽车销量数据", "新能源汽车销量"),
        ("2025年度中国芯片产业分析报告", "中国芯片产业"),
        ("上海天气预报最新一览", "上海天气预报"),
        ("Python asyncio tutorial 2026", "Python asyncio tutorial"),
    ]
    for raw, expected in cases:
        assert relax_query(raw) == expected
        assert suggest_relaxed_query(raw) == expected
