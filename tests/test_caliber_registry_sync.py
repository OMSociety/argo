#!/usr/bin/env python3
"""test_caliber_registry_sync.py — 口径分类表不得引用已不存在的引擎。

`caliber_isolation._CALIBER_GROUPS` 是手工维护的分类表：新引擎默认落
general，旧引擎下线后名字会留在表里。后者不会报错（分类表只是查表），
但会让「这个引擎属于哪个口径」的文档持续说谎，也让未来重新接入同名引擎
时静默继承一个未经复核的分类。

本测试把「表里的名字必须真实存在于 config.yaml」变成门禁；2026-10-17
首次跑出 15 个陈旧条目（crates_io / pubmed / themoviedb / legal …），
已按当前注册表改名或删除。
"""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))


def test_every_caliber_engine_is_registered():
    import config
    from caliber_isolation import _CALIBER_GROUPS

    configured = set(config.get_engines(config.load_config()))
    listed = set().union(*_CALIBER_GROUPS.values())
    stale = sorted(listed - configured)
    assert not stale, f"口径分类表引用了不存在的引擎：{stale}"


def test_groups_are_non_empty():
    from caliber_isolation import _CALIBER_GROUPS

    empty = [name for name, members in _CALIBER_GROUPS.items() if not members]
    assert not empty, f"空口径组：{empty}"


def test_priority_covers_every_group():
    from caliber_isolation import _CALIBER_GROUPS, _CALIBER_PRIORITY

    missing = sorted(set(_CALIBER_GROUPS) - set(_CALIBER_PRIORITY))
    assert not missing, f"口径组缺优先级：{missing}"
