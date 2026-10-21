#!/usr/bin/env python3
"""search_types.py — 统一类型系统（已废弃，勿接入）

早期设计声明的统一 schema 层，从未被任何模块 import（grep 全仓库无引用）：
  - 引擎输出直接透传 dict，运行时防御在 engines_base/safe_search 与
    search.py 的 execute_search 里完成
  - 保留本文件仅避免旧版外部脚本 import 断裂；新代码禁止使用
"""
from __future__ import annotations

from enum import Enum
from typing import Any


class _FieldMeta:
    __slots__ = ("name", "init", "_field_type")

    def __init__(self, name: str) -> None:
        self.name = name
        self.init = True
        self._field_type = None


class _SlotField:
    __slots__ = ("factory",)

    def __init__(self, default_factory: Any) -> None:
        self.factory = default_factory


def slot_field(*, default_factory: Any) -> Any:
    """零依赖 field(default_factory=...) 替代。"""
    return _SlotField(default_factory)


def slot_record(_cls: Any = None, *, frozen: bool = False) -> Any:
    """零依赖 @dataclass 替代（省去 import dataclasses→inspect→tokenize→dis ~8ms）。

    挂上 `__dataclass_fields__` 兼容描述子，标准库 `dataclasses.replace` /
    `dataclasses.is_dataclass` 对实例照常工作，但热路径自身零导入。
    """
    def _wrap(cls: Any) -> Any:
        ann = list(cls.__dict__.get("__annotations__", {}).keys())
        defaults = {k: cls.__dict__[k] for k in ann if k in cls.__dict__}

        def __init__(self: Any, *args: Any, **kwargs: Any) -> None:
            if len(args) > len(ann):
                raise TypeError(f"{cls.__name__}.__init__() takes {len(ann)} positional arguments but {len(args)} were given")
            for i, val in enumerate(args):
                object.__setattr__(self, ann[i], val)
            for k in ann[len(args):]:
                if k in kwargs:
                    val = kwargs.pop(k)
                elif k in defaults:
                    d = defaults[k]
                    val = d.factory() if isinstance(d, _SlotField) else d
                else:
                    raise TypeError(f"{cls.__name__}.__init__() missing required argument: {k!r}")
                object.__setattr__(self, k, val)
            if kwargs:
                bad = next(iter(kwargs))
                raise TypeError(f"{cls.__name__}.__init__() got an unexpected keyword argument {bad!r}")

        cls._slot_fields = tuple(ann)
        cls.__dataclass_fields__ = {k: _FieldMeta(k) for k in ann}
        cls.__init__ = __init__
        if frozen:
            def __setattr__(self: Any, name: str, value: Any) -> None:
                raise AttributeError(f"cannot assign to field {name!r}")
            cls.__setattr__ = __setattr__
        return cls

    return _wrap if _cls is None else _wrap(_cls)


def slot_replace(obj: Any, **changes: Any) -> Any:
    """零依赖 replace(obj, **changes) 替代。"""
    kw = {k: getattr(obj, k) for k in obj._slot_fields}
    kw.update(changes)
    return type(obj)(**kw)


@slot_record
class SearchResult:
    """统一的搜索结果数据类。"""
    title: str
    url: str = ""
    snippet: str = ""
    score: float = 0.5
    source: str = ""
    metadata: dict = slot_field(default_factory=dict)
    social_meta: dict | None = None

    def to_dict(self) -> dict[str, Any]:
        """转为字典，省略空值/默认值字段。"""
        d: dict[str, Any] = {"title": self.title}
        if self.url:
            d["url"] = self.url
        if self.snippet:
            d["snippet"] = self.snippet[:300]
        if self.score != 0.5:
            d["score"] = round(self.score, 3)
        if self.source:
            d["source"] = self.source
        if self.metadata:
            d["metadata"] = self.metadata
        if self.social_meta:
            d["social_meta"] = self.social_meta
        return d


def normalize_result(item: dict, engine: str, default_score: float = 0.5) -> SearchResult:
    """将任意引擎输出统一为 SearchResult。

    处理字段名混乱（score/relevance_score/snippet/content/summary 混用）。
    """
    snippet = (
        item.get("snippet")
        or item.get("content")
        or item.get("summary")
        or item.get("description", "")
    )
    raw_score = item.get("score", item.get("relevance_score", default_score))
    try:
        score = float(raw_score) if isinstance(raw_score, (int, float, str)) else default_score
    except (ValueError, TypeError):
        score = default_score

    return SearchResult(
        title=item.get("title", "")[:200],
        url=item.get("url", ""),
        snippet=snippet[:300] if snippet else "",
        score=score,
        source=item.get("source", engine),
        metadata=item.get("metadata", {}),
        social_meta=item.get("social_meta"),
    )


class Stage(str, Enum):
    """进度回调的阶段名（on_progress 契约）。

    从 search.py 搬来这里：执行层与加工层（search_pipeline）都要发进度事件，
    枚举放在任何一侧都会让另一侧反向依赖；search_types 是本仓共享类型的家。
    """

    START = "start"
    CACHE_HIT = "cache_hit"
    ROUTING = "routing"
    SEARCHING = "searching"
    MERGING = "merging"
    DONE = "done"
    ERROR = "error"
