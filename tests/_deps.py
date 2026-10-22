#!/usr/bin/env python3
"""可选依赖的测试守卫：缺件时跳过并说明原因，而不是抛 ImportError。

## 为什么要这个文件

`curl_cffi` 是可选依赖（运行期惰性导入），但有一批用例用 mock 替换
`curl_cffi.requests.get` 来验证 TLS 指纹、429 停止轮换等逻辑——**打补丁要求
目标模块真实存在**。缺件时这些用例不是「测出产品坏了」，而是环境没装全：
21 条会一起红，报错是 `ModuleNotFoundError`，看不出「该装什么」。

2026-10-22 第一次把全量用例搬到干净环境（只有 pytest + PyYAML）时踩到：
21 条一起红，全在 7 个文件里。修法是两条并行：CI 的 unit 作业装上测试真正
需要的三件（`curl_cffi` / `bs4` / `lxml`，见 requirements-dev.txt），让这些
用例真的跑到；同时加这道守卫，让任何更瘦的环境拿到「skip + 原因」，而不是
一屏 import 错误。九件全装的档由 CI 的 extras 作业负责。

## 为什么不写在 conftest

`tests/` 不是包，conftest 只能自动作用于 fixture，不能被 unittest 文件导入。
这里用显式 import，谁需要谁引，保持「依赖关系写在 import 行上」。
"""

from __future__ import annotations

import importlib.util

import pytest

CURL_CFFI_MISSING = importlib.util.find_spec("curl_cffi") is None

needs_curl_cffi = pytest.mark.skipif(
    CURL_CFFI_MISSING,
    reason=(
        "可选依赖 curl_cffi 未安装：本用例用 mock 替换 curl_cffi.requests，"
        "补丁目标必须真实存在。装全后可跑（见 requirements-optional.txt）"
    ),
)
