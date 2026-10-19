#!/usr/bin/env python3
"""seek_frecency.py — local-seek 的访问频次信号（zoxide 式 frecency，opt-in）。

默认**关闭**（ARGO_SEEK_FRECENCY=1 才启用）：local-seek 的排序契约是确定性
（tests/test_determinism_20261006.py），使用信号会让同一查询在不同机器/
不同历史下给出不同次序——这与工具的「可复现」定位冲突。故 frecency 只作为
显式开启的实验项：开启后记录每次搜索命中的 top 路径（频次 + 最近时间），
并在文件名评分与内容重排上加一个**有上限的小加成**。

算法（zoxide Wiki「Algorithm」的裁剪版）：
  boost = min(√count, 3) × recency_mult
  recency_mult: 1 小时内 ×2 / 当天内 ×1.5 / 当周内 ×1 / 更早 ×0.5
  上限 ≈ 6 分——对 BM25F 分数（典型 5-40）是温和 nudging，不是主导项；
  对 fzf V2 分数（典型 30-200）只够做并列裁决。zoxide 的 _ZO_MAXAGE 老化
  在这里换成硬上限条目数（1000 条，超出按 last_ts 淘汰最旧）——本地搜索
  的「访问」就是「被搜到」，没有 cd 那样的高频信号，老化意义有限。

状态文件：$ARGO_SEEK_FRECENCY_DB 覆盖，默认 ~/.cache/local-seek/frecency.json。
读写全部 fail-soft：任何 IO/解析异常静默跳过，绝不影响搜索主流程。
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path

_MAX_ENTRIES = 1000
_RECORD_TOP = 10          # 每次搜索只记录前 N 条命中路径
_TRUTHY = ("1", "on", "yes", "true", "enable", "enabled")


def enabled() -> bool:
    return (os.environ.get("ARGO_SEEK_FRECENCY", "").strip().lower()
            in _TRUTHY)


def _state_path() -> Path:
    custom = os.environ.get("ARGO_SEEK_FRECENCY_DB", "").strip()
    if custom:
        return Path(custom)
    cache_root = os.environ.get("XDG_CACHE_HOME") or str(
        Path.home() / ".cache")
    return Path(cache_root) / "local-seek" / "frecency.json"


_MEMO: tuple[str, int, int, dict[str, list[float]]] | None = None


def _load() -> dict[str, list[float]]:
    global _MEMO
    try:
        path = _state_path()
        p_str = str(path)
        try:
            st = path.stat()
        except OSError:
            _MEMO = (p_str, -1, -1, {})
            return {}
        if (_MEMO is not None and _MEMO[0] == p_str
                and _MEMO[1] == st.st_mtime_ns and _MEMO[2] == st.st_size):
            return _MEMO[3]
        raw = json.loads(path.read_text(encoding="utf-8"))
        data = raw if isinstance(raw, dict) else {}
        _MEMO = (p_str, st.st_mtime_ns, st.st_size, data)
        return data
    except Exception:
        return {}


def _save(data: dict[str, list[float]]) -> None:
    global _MEMO
    try:
        path = _state_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(tmp, path)
        try:
            st = path.stat()
            _MEMO = (str(path), st.st_mtime_ns, st.st_size, data)
        except OSError:
            _MEMO = None
    except Exception:
        pass  # frecency 是增益信号，写失败静默


def record(paths: list[str], now: float | None = None) -> None:
    """记录一次搜索命中的 top 路径（频次 +1、时间刷新）。"""
    if not paths:
        return
    now = now if now is not None else time.time()
    data = _load()
    for fp in paths[:_RECORD_TOP]:
        entry = data.get(fp)
        if entry and isinstance(entry, list) and len(entry) == 2:
            entry[0] = float(entry[0]) + 1.0
            entry[1] = now
        else:
            data[fp] = [1.0, now]
    if len(data) > _MAX_ENTRIES:
        keep = sorted(data.items(), key=lambda kv: -kv[1][1])[:_MAX_ENTRIES]
        data = dict(keep)
    _save(data)


def boost(fp: str, now: float | None = None) -> float:
    """该路径的 frecency 加成（0 = 无记录/未启用）。"""
    entry = _load().get(fp)
    if not entry or not isinstance(entry, list) or len(entry) != 2:
        return 0.0
    now = now if now is not None else time.time()
    count = max(0.0, float(entry[0]))
    age = now - float(entry[1])
    if age <= 3600:
        mult = 2.0
    elif age <= 86400:
        mult = 1.5
    elif age <= 7 * 86400:
        mult = 1.0
    else:
        mult = 0.5
    return round(min(count ** 0.5, 3.0) * mult, 3)
