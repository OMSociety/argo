#!/usr/bin/env python3
"""bench_tail_ab 的回放口径（2026-10-24，方案 A 的验收工具）。

这个工具存在的理由：尾宽策略改过多次、结论反复，因为没有一条**可回放**的
时间线。这里钉住它的三条口径，防止它自己先漂：

1. 合成引擎（基准/混沌用的 dead_primary 等）不得进回放——它们曾把慢源排行
   带偏（2026-10-21 实测）；
2. 单引擎查询不受尾宽影响（没有可对冲对象）；
3. 「放弃的慢源交付」必须被数出来——省下来的墙钟如果不是白等，就不是收益。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import bench_tail_ab as bench  # noqa: E402


def _rec(elapsed, engines, top, used=None):
    return {"elapsed_ms": elapsed, "engines_used": used or engines,
            "engine_latency_top": top}


def test_synthetic_engines_are_filtered_out():
    lines = [
        '{"elapsed_ms": 900, "engines_used": ["dead_primary"], "engine_latency_top": [["dead_primary", 800]]}',
        '{"elapsed_ms": 700, "engines_used": ["octen"], "engine_latency_top": [["octen", 600]]}',
    ]
    import tempfile
    p = Path(tempfile.mkdtemp()) / "query.jsonl"
    p.write_text("\n".join(lines), encoding="utf-8")
    got = bench.load_queries(p)
    assert len(got) == 1 and got[0]["engines_used"] == ["octen"]


def test_single_engine_queries_are_untouched():
    q = [_rec(900, ["octen"], [["octen", 850]])]
    out = bench.replay(q, {}, tail_s=0.1)
    assert out["old"]["p50"] == out["new"]["p50"] == 900
    assert out["saved_ms_total"] == 0


def test_shortening_tail_reports_lost_slow_deliveries():
    """慢源 3s 才回、尾宽砍到 0.6s：墙钟省下来，但那次交付确实没了，要计数。"""
    q = [_rec(3200, ["octen", "anysearch"],
              [["octen", 200], ["anysearch", 3100]])]
    out = bench.replay(q, {}, tail_s=0.6)
    assert out["saved_ms_total"] == 900          # 1.5s - 0.6s
    assert out["slow_delivery_lost"] == 1


def test_no_reduction_when_slow_engine_already_beat_the_window():
    """慢源在现行尾宽内就回来了：两套口径都不额外等，省 0、丢 0。"""
    q = [_rec(1000, ["octen", "anysearch"],
              [["octen", 200], ["anysearch", 900]])]
    out = bench.replay(q, {}, tail_s=0.1)
    assert out["saved_ms_total"] == 0
    assert out["slow_delivery_lost"] == 0


def test_quality_report_flags_engine_above_baseline(tmp_path):
    """质量画像：高于均线的引擎，报告里必须出现正的相对差值。

    这是「该不该缩尾宽」的判据来源——只看省了多少秒会得出「早收工合理」，
    但若被放弃的那台源比平均更相关，省下的就是准确性。2026-10-25 实测：
    anysearch 相关度 0.686、全库均线 0.572（+0.114），所以缩尾宽不成立。
    """
    import sqlite3

    db = tmp_path / "adaptive.db"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE engine_perf (engine TEXT, success INTEGER, "
                     "latency_ms REAL, cost REAL, created_at REAL, empty INTEGER, "
                     "quality REAL DEFAULT 0.0)")
        for i in range(10):
            conn.execute("INSERT INTO engine_perf VALUES ('good',1,100,0,0,0,0.8)", )
            conn.execute("INSERT INTO engine_perf VALUES ('bad',1,100,0,0,0,0.3)", )
        conn.commit()

    lost = [{"engine": "good", "extra_wait_ms": 2000, "p75_ms": 2400, "query": "q"},
            {"engine": "good", "extra_wait_ms": 1500, "p75_ms": 2400, "query": "q2"}]
    report = bench.quality_report(lost, {}, tmp_path, {"good": 2400})
    assert "good" in report
    assert "+0.25" in report          # 0.8 - 均线 0.55


def test_quality_report_survives_missing_db(tmp_path):
    """没有 adaptive.db（新机器）也要给出可用报告，而不是崩。"""
    report = bench.quality_report([{"engine": "x", "extra_wait_ms": 1}], {}, tmp_path, {})
    assert "anysearch" not in report and "质量口径" in report
