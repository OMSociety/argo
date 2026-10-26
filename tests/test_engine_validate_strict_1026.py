#!/usr/bin/env python3
"""engine_validate --strict 的退出码契约（2026-10-26 夜间交付门禁）。

背景：夜间 source-canary 依赖 engine_validate 的退出码，而它原来只把
status=="fail" 记为失败；源被禁用、缺 key、改名时 run_health 返回
status=="skipped"，退出码仍是 0——关键源消失，门禁全绿。--strict 把
skipped 也判失败，默认仍宽松（批量体检时跳过未配置源不是故障）。
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import engine_validate  # noqa: E402


def _run(argv: list[str], status: str) -> int:
    with patch.object(sys, "argv", ["engine_validate.py"] + argv), \
            patch.object(engine_validate, "validate_engine",
                         return_value={"engine": "fake", "status": status}):
        return engine_validate.main()


def test_strict_treats_skipped_as_failure():
    assert _run(["--engines", "fake", "--stage", "health", "--strict"],
                "skipped") == 1


def test_default_allows_skipped():
    assert _run(["--engines", "fake", "--stage", "health"],
                "skipped") == 0


def test_strict_passes_on_pass():
    assert _run(["--engines", "fake", "--stage", "health", "--strict"],
                "pass") == 0
