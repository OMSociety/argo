#!/usr/bin/env python3
"""test_dsh_plugin_env_gate.py — DSH 插件 argoEnv 白名单与 argo 源码的对拍门禁。

packages/dsh-plugin/dsh/index.js 的 ARGO_ENV_SPECS 是「面板可露出的 argo
环境变量开关」白名单：apply 期对白名单外的名字 loud fail。本测试保证白名单
里每个名字都在 argo 源码（scripts/ 与 bin/）有真实读取点——拼错或抄了个
不存在的名字，此处必须红，而不是等用户在面板上配了不生效。

反向（argo 新增了环境变量但面板没露出）不设失败： curated 是渐进过程，
新增开关要不要进面板是产品决策；这里只把增量打印出来，提醒同步。
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_INDEX = ROOT / "packages" / "dsh-plugin" / "dsh" / "index.js"


def _plugin_allowlist() -> set[str]:
    src = PLUGIN_INDEX.read_text(encoding="utf-8")
    m = re.search(r"export const ARGO_ENV_SPECS = Object\.freeze\(\[(.*?)\n\]\)", src, re.S)
    assert m, "index.js 缺少 ARGO_ENV_SPECS 导出"
    return set(re.findall(r"name: '(ARGO_[A-Z0-9_]+)'", m.group(1)))


def _argo_source_env_names() -> set[str]:
    names: set[str] = set()
    for base in (ROOT / "scripts", ROOT / "bin"):
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if path.suffix not in (".py", ".js") or "__pycache__" in path.parts:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            names.update(re.findall(r"ARGO_[A-Z][A-Z0-9_]*", text))
    return names


def test_allowlist_names_exist_in_argo_source():
    allowlist = _plugin_allowlist()
    assert allowlist, "白名单解析为空：正则或导出形状变了？"
    source_names = _argo_source_env_names()
    phantom = sorted(allowlist - source_names)
    assert not phantom, (
        f"白名单里的名字在 argo 源码没有读取点（拼错或已删除）: {phantom}"
    )


def test_allowlist_delta_is_reported(capsys):
    """argo 源码里有、白名单没有的增量只打印不失败（curated 是渐进过程）。"""
    allowlist = _plugin_allowlist()
    delta = sorted(_argo_source_env_names() - allowlist)
    with capsys.disabled():
        print(f"[argoEnv] allowlist={len(allowlist)} names, "
              f"argo-source-only={len(delta)}: {delta}")
