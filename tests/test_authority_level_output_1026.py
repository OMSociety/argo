#!/usr/bin/env python3
"""输出层权威等级回填（2026-10-26）。

DeepSeek Search 的原生 authority 0-4 是 v2.9.6 接入时的核心差异点，但
`search_rank` 只在五维精排里写 `authority_level`；单引擎 `--engine`、
付费对冲第二位、部分 fast 路径不走精排，agent 档于是只看到空的
authority_level。这里锁「上游有值就必须转成等级」以及「已有等级不覆盖」。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from search_output import _ensure_authority_levels  # noqa: E402


def test_upstream_authority_becomes_level():
    rows = [
        {"upstream_authority": "4"},
        {"upstream_authority": "0"},
        {"upstream_authority": "3"},
    ]
    _ensure_authority_levels(rows)
    assert [r["authority_level"] for r in rows] == [4, 0, 3]


def test_unknown_upstream_falls_back_to_own_score():
    rows = [{"upstream_authority": "-1", "authority": 0.9}]
    _ensure_authority_levels(rows)
    assert rows[0]["authority_level"] == 4


def test_missing_upstream_is_left_to_rerank():
    rows = [{"authority": 0.5}, {"upstream_authority": None}]
    _ensure_authority_levels(rows)
    assert all(r.get("authority_level") is None for r in rows)


def test_existing_level_is_not_overwritten():
    rows = [{"upstream_authority": "1", "authority_level": 4}]
    _ensure_authority_levels(rows)
    assert rows[0]["authority_level"] == 4
