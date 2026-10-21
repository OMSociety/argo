#!/usr/bin/env python3
"""test_output_uncertainty — 综合可信度（meta.uncertainty）的门禁（2026-10-21）。

## 背景

argo 的输出一直有 `funnel`（六段计数）、`limitations`（逐条局限）、
`evidence_loop`（核验状态），信息量足够，但**没有一个整体等级**：消费者
要自己交叉比对五六个字段才能决定「这批结果能不能直接引用」。

dsh-free-search 的 `meta.uncertainty` 是同一件事：一个 level + 一组 notes。
本次按 argo 已有数据重算，不新增采集。

## 锁什么

1. 各信号 → level 的映射（空/单来源/双来源/同站/聚合站/时间窗失效/引擎失败）。
2. 与 `limitations` 不重复：早停、降级、缓存复用已有表述，不出现在 notes 里。
3. `--fields agent` 必须保留 `meta`（否则 agent 拿不到整体判断）。
4. 门禁有牙：把聚合站词表清空，第 5 条必须失败。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import search  # noqa: E402
import search_output  # noqa: E402
from search_output import _strip_for_agent, build_uncertainty  # noqa: E402


def _r(url: str, **kw) -> dict:
    d = {"title": "t", "snippet": "s", "url": url}
    d.update(kw)
    return d


class TestBuildUncertainty:
    def test_empty_is_low(self):
        out = build_uncertainty({"results": []})
        assert out["level"] == "low"
        assert out["notes"] == ["没有返回结果"]

    def test_single_source_is_low(self):
        out = build_uncertainty({"results": [_r("https://a.com/1")]})
        assert out["level"] == "low"
        assert any("1 个来源" in n for n in out["notes"])

    def test_two_sources_is_medium(self):
        out = build_uncertainty(
            {"results": [_r("https://a.com/1"), _r("https://b.com/1")]})
        assert out["level"] == "medium"
        assert any("2 个来源" in n for n in out["notes"])

    def test_same_host_is_medium(self):
        """同一站点的两次出现不是多源印证。"""
        out = build_uncertainty(
            {"results": [_r("https://a.com/1"), _r("https://a.com/2"),
                         _r("https://a.com/3")]})
        assert out["level"] == "medium"
        assert any("同一站点" in n for n in out["notes"])

    def test_www_prefix_does_not_split_hosts(self):
        """www.a.com 与 a.com 是同一站——归一化漏掉 www 会把同站判成多源。"""
        out = build_uncertainty(
            {"results": [_r("https://www.a.com/1"), _r("https://a.com/2")]})
        assert out["level"] == "medium"

    def test_aggregator_host_is_medium(self):
        out = build_uncertainty(
            {"results": [_r("https://github.com/1"),
                         _r("https://baijiahao.baidu.com/2")]})
        assert out["level"] == "medium"
        assert any("聚合站" in n for n in out["notes"])

    def test_aggregator_subdomain_counts(self):
        out = build_uncertainty(
            {"results": [_r("https://github.com/1"),
                         _r("https://www.toutiao.com/2")]})
        assert any("聚合站" in n for n in out["notes"])

    def test_time_filter_warning_downgrades(self):
        out = build_uncertainty({
            "results": [_r("https://a.com/1"), _r("https://b.com/2"),
                        _r("https://c.com/3")],
            "time_filter_warning": "引擎未返回 published_at，时间窗未实际过滤",
        })
        assert out["level"] == "medium"
        assert any("时间窗未实际过滤" in n for n in out["notes"])

    def test_engine_failures_are_low(self):
        out = build_uncertainty({
            "results": [_r("https://a.com/1"), _r("https://b.com/2"),
                        _r("https://c.com/3")],
            "engine_outcomes": [
                {"engine": "x", "status": "ok"},
                {"engine": "y", "status": "timeout"},
            ],
        })
        assert out["level"] == "low"
        assert any("引擎未交出结果" in n for n in out["notes"])

    def test_non_error_outcomes_do_not_downgrade(self):
        """no-results / skipped-quota-exhausted 不算失败（与 errors 同口径）。"""
        out = build_uncertainty({
            "results": [_r("https://a.com/1"), _r("https://b.com/2"),
                        _r("https://c.com/3")],
            "engine_outcomes": [
                {"engine": "x", "status": "no-results"},
                {"engine": "y", "status": "skipped-quota-exhausted"},
            ],
        })
        assert out["level"] == "high"
        assert out["notes"] == []

    def test_clean_result_is_high_with_no_notes(self):
        out = build_uncertainty({
            "results": [_r("https://a.com/1"), _r("https://b.com/2"),
                        _r("https://c.com/3")],
        })
        assert out == {"level": "high", "notes": []}

    def test_no_duplication_with_limitations(self):
        """早停/降级/缓存复用已有 limitations 表述，notes 里不该再出现。

        同一件事两条表述会互相削弱——读者不知道该信哪条。
        """
        out = build_uncertainty({
            "results": [_r("https://a.com/1"), _r("https://b.com/2"),
                        _r("https://c.com/3")],
            "early_stopped": True,
            "recovery": {"engine": "x"},
            "cached": True,
            "semantic_hit": True,
        })
        for n in out["notes"]:
            assert "early_stop" not in n, n
            assert "recovery" not in n, n
            assert "cache" not in n, n

    def test_gate_has_teeth(self):
        """清空聚合站词表，第 5 条必须失败——否则门禁是摆设。"""
        original = search_output._AGGREGATOR_HOSTS
        try:
            search_output._AGGREGATOR_HOSTS = frozenset()
            out = build_uncertainty({
                "results": [_r("https://github.com/1"),
                            _r("https://gitlab.com/2"),
                            _r("https://baijiahao.baidu.com/3")],
            })
            assert out["level"] == "high", "词表清空后聚合站信号应消失"
            assert out["notes"] == []
        finally:
            search_output._AGGREGATOR_HOSTS = original

    def test_level_never_upgrades(self):
        """单来源已判 low 时，同站判定不得把它抬回 medium。

        顺序 if/elif 覆盖同一个变量时，后一条会把前一条的降级抬回去
        （方向相反的赋值），这是本类逻辑最易犯的错。
        """
        out = build_uncertainty(
            {"results": [_r("https://a.com/1")]})
        assert out["level"] == "low"


class TestAgentTier:
    """--fields agent 必须保留 meta（否则 agent 拿不到整体判断）。"""

    def _payload(self) -> dict:
        return {
            "query": "q", "status": "completed", "count": 1, "results": [],
            "fetch_required": False, "evidence_loop": {},
            "errors": [], "limitations": [],
            "meta": {"uncertainty": {"level": "medium", "notes": ["n"]}},
            "tfidf_scores": [0.1], "engine_outcomes": [{"engine": "x"}],
            "elapsed_ms": 12, "route_reason": "r", "cached": True,
        }

    def test_meta_survives_agent_tier(self):
        out = _strip_for_agent(self._payload())
        assert "meta" in out, "--fields agent 剥掉了 meta.uncertainty"
        assert out["meta"] == {"uncertainty": {"level": "medium", "notes": ["n"]}}

    def test_meta_absent_does_not_crash(self):
        """老缓存条目没有 meta——裁剪必须容忍缺失，不能 KeyError。"""
        payload = self._payload()
        del payload["meta"]
        out = _strip_for_agent(payload)
        assert "meta" not in out

    def test_search_module_reexports_strip(self):
        """search._strip_for_agent 是既有对外面，保持可用。"""
        assert search._strip_for_agent is _strip_for_agent


if __name__ == "__main__":
    unittest.main()
