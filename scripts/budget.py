#!/usr/bin/env python3
"""budget.py — 按引擎的月度预算（原生币种）。

为什么需要（2026-10-21）：`quota.py` 的额度是**次数**（limit/used），而付费引擎
（DeepSeek、Tavily 等）的真实约束是**钱**。按次数换算会在单价变化时失真，也会
把「失败调用」算成花费（DeepSeek 只对成功请求计费）。本模块只做三件事：

1. 读取预算（默认 → 共享文件 → env 覆盖），不碰配额状态；
2. 把预算挂到 `quota.py` 的 profile 上（budget_amount / budget_currency / period）；
3. 提供 `argo budget set|list|unset` 的存储原语。

存储位置：`~/.config/argo/budgets.json`（POSIX）或 `%APPDATA%\\argo\\budgets.json`
（Windows），与 `~/.config/argo/env` 同根；`ARGO_BUDGET_FILE` 可覆盖（测试/多环境）。
格式：

    {"deepseek_search": {"amount": 5.0, "currency": "CNY", "period": "month"}}

env 覆盖（优先级高于文件，便于插件/临时实验）：
  - `ARGO_BUDGETS_JSON`：整份 JSON（最高）
  - `ARGO_BUDGET_<ENGINE>`：单引擎金额（币种按引擎 cost_unit，缺省 CNY；周期 month）

默认只给 DeepSeek 一个月度体验额度（¥5 ≈ 1000 次成功调用）；其他引擎默认不设，
沿用各自 quota_profiles.json 里的既有额度，符合「其他默认不改」。
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

__all__ = [
    "DEFAULT_BUDGETS",
    "budget_file",
    "load_budgets",
    "budget_for",
    "apply_to_profiles",
    "set_budget",
    "unset_budget",
]

# 默认预算：只覆盖 DeepSeek。金额按人民币；折算依据是官方 5 元/千次成功请求。
DEFAULT_BUDGETS: dict[str, dict[str, Any]] = {
    "deepseek_search": {"amount": 5.0, "currency": "CNY", "period": "month"},
}

_ENV_JSON = "ARGO_BUDGETS_JSON"
_ENV_FILE = "ARGO_BUDGET_FILE"
_ENV_PREFIX = "ARGO_" + "BUDGET_"


def budget_file() -> Path:
    """预算文件路径（不保证存在）。"""
    override = (os.environ.get(_ENV_FILE) or "").strip()
    if override:
        return Path(os.path.expanduser(override))
    if os.name == "nt":
        base = (os.environ.get("APPDATA") or "").strip() or os.path.expanduser("~")
    else:
        base = (os.environ.get("XDG_CONFIG_HOME") or "").strip() or os.path.expanduser("~/.config")
    return Path(base) / "argo" / "budgets.json"


def _valid(entry: Any) -> dict[str, Any] | None:
    """校验并归一一条预算；坏条目返回 None（不阻断其他引擎）。"""
    if not isinstance(entry, dict):
        return None
    try:
        amount = float(entry.get("amount"))
    except (TypeError, ValueError):
        return None
    if amount < 0:
        return None
    currency = str(entry.get("currency") or "CNY").strip().upper() or "CNY"
    period = str(entry.get("period") or "month").strip().lower()
    if period not in ("day", "month"):
        period = "month"
    return {"amount": amount, "currency": currency, "period": period}


def _read_file() -> dict[str, dict[str, Any]]:
    try:
        raw = json.loads(budget_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(raw, dict):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for engine, entry in raw.items():
        if str(engine).startswith("_"):
            continue
        norm = _valid(entry)
        if norm is not None:
            out[str(engine)] = norm
    return out


def _read_env() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    raw = (os.environ.get(_ENV_JSON) or "").strip()
    if raw:
        try:
            parsed = json.loads(raw)
        except ValueError:
            parsed = None
        if isinstance(parsed, dict):
            for engine, entry in parsed.items():
                norm = _valid(entry)
                if norm is not None:
                    out[str(engine)] = norm
    # 单引擎便捷覆盖："ARGO_BUDGET_DEEPSEEK_SEARCH"=5 → deepseek_search 5 CNY/月。
    # 同族命名 ARGO_BUDGET_<ENGINE> 由下面按前缀解析；字面量保留给插件门禁对拍。
    # 只认「大写化后能在默认/文件里找到的引擎」太窄；这里按环境变量名反推引擎名，
    # 由调用方（quota）决定是否真的存在该引擎，避免拼错静默生效。
    for key, value in os.environ.items():
        if not key.startswith(_ENV_PREFIX) or key in (_ENV_JSON, _ENV_FILE):
            continue
        engine = key[len(_ENV_PREFIX):].strip().lower()
        if not engine:
            continue
        try:
            amount = float(str(value).strip())
        except (TypeError, ValueError):
            continue
        if amount < 0:
            continue
        entry = {"amount": amount, "currency": "CNY", "period": "month"}
        if engine in out and out[engine].get("currency"):
            entry["currency"] = out[engine]["currency"]
        out[engine] = entry
    return out


def load_budgets() -> dict[str, dict[str, Any]]:
    """默认 → 文件 → env，逐层覆盖。"""
    merged: dict[str, dict[str, Any]] = {k: dict(v) for k, v in DEFAULT_BUDGETS.items()}
    merged.update(_read_file())
    merged.update(_read_env())
    return merged


def budget_for(engine: str) -> dict[str, Any] | None:
    return load_budgets().get(str(engine))


def apply_to_profiles(profiles: dict[str, dict[str, Any]]) -> None:
    """把预算挂到 quota profile（就地）。只覆盖存在的引擎，拼错不生效。"""
    for engine, entry in load_budgets().items():
        spec = profiles.get(engine)
        if not isinstance(spec, dict):
            continue
        spec["budget_amount"] = entry["amount"]
        spec["budget_currency"] = entry["currency"]
        # 预算周期即重置周期；与 limit 共用同一条 `period`，避免两套时钟。
        spec["period"] = entry["period"]


def _write(data: dict[str, Any]) -> None:
    path = budget_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                   encoding="utf-8")
    os.replace(tmp, path)


def over_budget_error(engine: str) -> str | None:
    """预算耗尽时返回可行动错误文本；未耗尽/未配预算/读失败返回 None。

    放在 budget.py 而不是 dispatch：engine_dispatch 有行数门禁，预算检查是
    「读状态 + 拼一句话」的纯策略，搬出来也让显式/自动路径共用同一文案。
    """
    if (os.environ.get("ARGO_PAID_BUDGET_BYPASS", "").strip().lower()
            in ("1", "true", "yes", "on")):
        return None
    try:
        from quota import get_quota_manager
        qm = get_quota_manager()
        # 只认真正的 True：测试常把 quota manager 打成 MagicMock，属性调用
        # 会返回真值 mock——不能把「mock 存在」当成预算耗尽。
        if qm.is_over_budget(engine) is not True:
            return None
        st = qm.get_stats().get(engine) or {}
        return (f"本月预算已用完（{st.get('cost_used', 0)}/{st.get('budget')} "
                f"{st.get('budget_currency') or ''}）；"
                f"可用 ARGO_PAID_BUDGET_BYPASS=1 单次放行")
    except Exception:
        return None


def set_budget(engine: str, amount: float, *, currency: str = "CNY",
               period: str = "month") -> dict[str, Any]:
    """写入一条预算（保留文件里其他引擎）。返回归一后的条目。"""
    norm = _valid({"amount": amount, "currency": currency, "period": period})
    if norm is None:
        raise ValueError("预算金额必须是非负数")
    data = _read_file()
    data[str(engine)] = norm
    _write(data)
    return norm


def unset_budget(engine: str) -> bool:
    """删除一条预算；返回是否真的删了。"""
    data = _read_file()
    if engine not in data:
        return False
    data.pop(engine, None)
    _write(data)
    return True
