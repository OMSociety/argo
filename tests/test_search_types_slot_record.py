#!/usr/bin/env python3
"""test_search_types_slot_record — 零依赖 dataclass 替代的门禁（2026-10-21）。

## 背景（这个文件为什么存在）

`slot_record` 用 `cls.__dict__.get("__annotations__", {})` 读注解。但
Python 3.14 的 PEP 649 惰性注解下，**没有 `from __future__ import
annotations` 的模块里 `__annotations__` 根本不在类的 `__dict__`**（由
`__annotate__` 描述子按需计算）。取到 `{}` 的后果是类静默变成「零字段」，
实例化时报一个与真因毫不相干的 `TypeError: unexpected keyword argument`。

仓库自己的模块都带 future import，所以被 house style 掩盖着——这是哑雷，
不是当下的故障。本文件把它变成一条会红的门禁。

## 锁什么

1. PEP 649：无 future import 的模块里，`_slot_fields` 必须仍然正确。
2. 兼容面：`dataclasses.is_dataclass` / `replace` / `fields` 都要能用。
   （`fields` 曾返回 `()`——它按 `_field_type is dataclasses._FIELD` 过滤，
   而 `_FieldMeta` 原先把 `_field_type` 写死成 None。）
3. 行为：默认工厂互不共享、frozen 拒绝写入、缺参/多参报错。
4. 门禁有牙：把 `_class_annotations` 换回旧写法，第 1 条必须失败。
"""
from __future__ import annotations

import dataclasses
import importlib.util
import sys

import pytest
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import search_types  # noqa: E402
from search_types import slot_field, slot_record, slot_replace  # noqa: E402


@slot_record
class _Plain:
    title: str
    meta: dict = slot_field(default_factory=dict)


# 故意不带 `from __future__ import annotations`——这是 PEP 649 的真实形态。
_NO_FUTURE_SRC = """\
import sys
sys.path.insert(0, {scripts!r})
from search_types import slot_record, slot_field

@slot_record
class NoFuture:
    title: str
    score: float = 0.5
    meta: dict = slot_field(default_factory=dict)
"""


def _load_no_future_module(tmp_path: Path, name: str = "argo_slot_nofuture"):
    """把一段不带 future import 的源码当模块加载进来。"""
    mod_path = tmp_path / f"{name}.py"
    mod_path.write_text(_NO_FUTURE_SRC.format(scripts=str(SCRIPTS)), encoding="utf-8")
    sys.modules.pop(name, None)
    spec = importlib.util.spec_from_file_location(name, mod_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


class TestSlotFields:
    def test_fields_read_with_future_import(self):
        assert _Plain._slot_fields == ("title", "meta")

    def test_fields_read_without_future_import(self):
        """PEP 649 惰性注解：`__annotations__` 不在类字典里，仍必须读到。"""
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            mod = _load_no_future_module(Path(d))
            try:
                assert mod.NoFuture._slot_fields == ("title", "score", "meta"), (
                    "PEP 649 下注解读到空——cls.__dict__ 直取的老写法复发")
                inst = mod.NoFuture(title="x")
                assert inst.title == "x"
                assert inst.score == 0.5
                assert inst.meta == {}
            finally:
                sys.modules.pop("argo_slot_nofuture", None)

    def test_annotations_helper(self):
        assert search_types._class_annotations(_Plain) == {
            "title": str, "meta": dict,
        } or set(search_types._class_annotations(_Plain)) == {"title", "meta"}


class TestStdlibCompat:
    """标准库 dataclasses 对 slot_record 实例必须照常工作。"""

    def test_is_dataclass_on_class_and_instance(self):
        assert dataclasses.is_dataclass(_Plain)
        assert dataclasses.is_dataclass(_Plain(title="x"))

    def test_replace(self):
        r = _Plain(title="x")
        assert dataclasses.replace(r, title="y").title == "y"
        assert r.title == "x"          # 不改原对象

    def test_fields_lists_every_field(self):
        """曾返回 `()`：`_field_type` 写死 None，被 fields() 的过滤条件滤光。"""
        names = [f.name for f in dataclasses.fields(_Plain(title="x"))]
        assert names == ["title", "meta"], (
            f"dataclasses.fields 漏字段（_field_type 未惰性解析）：{names}")

    def test_slot_replace(self):
        r = _Plain(title="x")
        assert slot_replace(r, title="z").title == "z"
        assert slot_replace(r).title == "x"


class TestBehaviour(unittest.TestCase):
    def test_default_factory_not_shared(self):
        assert _Plain(title="a").meta is not _Plain(title="b").meta

    def test_positional_and_keyword_mixed(self):
        assert _Plain("x", {"k": 1}).meta == {"k": 1}

    def test_missing_required_raises(self):
        with self.assertRaises(TypeError):
            _Plain()

    def test_unexpected_kwarg_raises(self):
        with self.assertRaises(TypeError):
            _Plain(title="x", nope=1)

    def test_too_many_positional_raises(self):
        with self.assertRaises(TypeError):
            _Plain("x", {}, "extra")

    def test_frozen_rejects_write(self):
        @slot_record(frozen=True)
        class F:
            x: int
        f = F(x=1)
        with self.assertRaises(AttributeError):
            f.x = 2


class TestGateTeeth:
    """门禁有牙：把注解读取换回旧写法，PEP 649 那条必须失败。"""

    @pytest.mark.skipif(
        sys.version_info < (3, 14),
        reason="PEP 649 是 3.14 语义：3.12 上旧写法本来就能读到注解，这条门禁无从成立",
    )
    def test_reverting_annotation_read_breaks_pep649(self):
        original = search_types._class_annotations
        try:
            # 旧写法：直取类字典（PEP 649 下取不到）
            search_types._class_annotations = (
                lambda cls: cls.__dict__.get("__annotations__", {}) or {})
            import tempfile
            with tempfile.TemporaryDirectory() as d:
                mod = _load_no_future_module(Path(d))
                try:
                    assert mod.NoFuture._slot_fields == (), (
                        "旧写法竟然还能读到注解——门禁失去意义")
                finally:
                    sys.modules.pop("argo_slot_nofuture", None)
        finally:
            search_types._class_annotations = original


if __name__ == "__main__":
    unittest.main()
