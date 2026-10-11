#!/usr/bin/env python3
"""test_sufficient_shell_filter — 壳链不算「够数」的充分性口径（全 mock）。

2026-10-11 热榜实测的事故类：early-stop 的两条路径（wave-1 的
results_sufficient、wave-2 的 cumulative_sufficient）此前把 SERP 壳
链算作有效结果——baidu_hot 交 10 条 baidu.com/s?wd= 壳即触发早停、
同域真榜单引擎被 cancelled，壳随后被漏斗壳过滤整批清零、merged 归零
触发 2.3s 恢复链。修复后壳过滤统一走 serp_guard.drop_shell_urls
（与漏斗过滤、恢复链 L0/L3 收口同一出口），壳从一开始就不算「够」。

守护的是口径，不是具体阈值：计数/snippet 阈值是既有设计，本文件只锁
「壳不参与计数」与「无 url 结构化快照不受影响」。
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from query_signals import cumulative_sufficient, results_sufficient  # noqa: E402

QUERY = "今天热搜"


def _shells(n: int = 5) -> list[dict]:
    """热榜壳链同款：计数与 snippet 都达标、URL 是 SERP（baidu /s?wd=）。"""
    return [{"title": f"{QUERY} 榜单 {i}", "snippet": f"{QUERY}实时榜单第 {i} 位",
             "url": f"https://www.baidu.com/s?wd={QUERY}{i}"} for i in range(n)]


def _real(n: int = 5) -> list[dict]:
    return [{"title": f"{QUERY} 真榜单 {i}", "snippet": f"{QUERY}第 {i} 位",
             "url": f"https://tophub.today/hot/{i}"} for i in range(n)]


def _no_url(n: int = 5) -> list[dict]:
    """无 url 的结构化快照（行情/天气）：壳判定只看 URL，不受影响。"""
    return [{"title": f"{QUERY} {i}", "snippet": f"{QUERY}快照 {i}",
             "value": i} for i in range(n)]


class TestResultsSufficientShellFilter:
    """wave-1「先合格者赢」路径的壳口径。"""

    def test_shell_only_results_never_sufficient(self):
        """5 条壳（计数/snippet 均达标）→ 必须不够数。

        修复前这条返回 True：壳骗过早停、真榜单引擎被 cancelled，
        随后壳被漏斗过滤清零、merged 归零触发恢复链。
        """
        assert results_sufficient(_shells(), mode="auto", query=QUERY) is False

    def test_real_results_still_sufficient(self):
        """同等数量的真 URL → 照常够数（壳过滤不得连坐真结果）。"""
        assert results_sufficient(_real(), mode="auto", query=QUERY) is True

    def test_mixed_shells_and_real_is_sufficient(self):
        """壳+真混合：壳不参与计数但也不拖累真结果够数。"""
        mixed = _shells(3) + _real(3)
        assert results_sufficient(mixed, mode="auto", query=QUERY) is True

    def test_no_url_snapshots_unaffected(self):
        """无 url 的结构化快照（行情/天气）不受壳判定影响。"""
        assert results_sufficient(_no_url(), mode="auto", query=QUERY) is True

    def test_fail_open_without_guard(self):
        """serp_guard 不可用 → 壳不过滤（fail-open，与模块容错一致）。"""
        with patch.dict(sys.modules, {"serp_guard": None}):
            assert results_sufficient(
                _shells(), mode="auto", query=QUERY) is True


class TestCumulativeSufficientShellFilter:
    """wave-2 跨引擎累计路径的壳口径。"""

    def test_cumulative_shells_from_one_engine_not_sufficient(self):
        raw = {"baidu_hot": _shells()}
        assert cumulative_sufficient(raw, mode="auto", query=QUERY) is False

    def test_cumulative_real_results_sufficient(self):
        raw = {"baidu_hot": _shells(3), "toutiao_hot": _real(3)}
        assert cumulative_sufficient(raw, mode="auto", query=QUERY) is True

    def test_cumulative_mixed_real_only_enough(self):
        """仅 2 条真结果 + 5 条壳：壳补不了真结果的数。"""
        raw = {"baidu_hot": _shells(), "toutiao_hot": _real(2)}
        assert cumulative_sufficient(raw, mode="auto", query=QUERY) is False


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
