#!/usr/bin/env python3
"""test_jump_resolver_bing.py — Bing ck/a 跳转壳的离线还原（零网络）。

## 守的是什么缺陷

local_bing 的英文结果常是 `https://www.bing.com/ck/a?...&u=a1<base64url>`，
真实落点就编码在 `u` 参数里。此前：

  - `jump_resolver.JUMP_MARKERS` 不认 bing；
  - `local_bing` 没有声明 `resolve_redirects`；
  - 聚合层 P0 把 bing.com URL 当搜索页整批滤掉。

于是引擎交 10 条、聚合层拿 0 条，状态记成 no-results（近 7 天 271 次调用、
40.2% 空结果）。修复是离线解码：不发请求、不依赖引擎声明。

本文件锁四条：
  1. 正常壳能解出真实 URL；
  2. 非 Bing / 非法 base64 / 同源弹回返回空串；
  3. `is_jump_url` 认得 bing 壳；
  4. `resolve_jump_url` 对 Bing 壳**不发起网络请求**。
"""

from __future__ import annotations

import base64
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

from jump_resolver import (  # noqa: E402
    is_jump_url,
    resolve_jump_url,
    unwrap_offline_url,
)

_TARGET = "https://realpython.com/async-io-python/"


def _bing_url(target: str) -> str:
    encoded = base64.urlsafe_b64encode(target.encode()).decode().rstrip("=")
    return ("https://www.bing.com/ck/a?!&&p=abc&ptn=3&ver=2&hsh=4"
            f"&fclid=xyz&u=a1{encoded}&ntb=1")


class TestOfflineUnwrap(unittest.TestCase):
    def test_decodes_bing_wrapper(self):
        self.assertEqual(unwrap_offline_url(_bing_url(_TARGET)), _TARGET)

    def test_non_bing_url_is_untouched(self):
        self.assertEqual(unwrap_offline_url("https://example.com/a"), "")
        self.assertEqual(unwrap_offline_url(""), "")

    def test_invalid_base64_returns_empty(self):
        bad = "https://www.bing.com/ck/a?u=a1!!!not-base64!!!"
        self.assertEqual(unwrap_offline_url(bad), "")

    def test_same_origin_target_rejected(self):
        self.assertEqual(
            unwrap_offline_url(_bing_url("https://www.bing.com/search?q=x")), "")

    def test_is_jump_url_recognizes_bing(self):
        self.assertTrue(is_jump_url(_bing_url(_TARGET)))
        self.assertFalse(is_jump_url("https://example.com/a"))


class TestNoNetworkForOfflineForms(unittest.TestCase):
    def test_resolve_does_not_issue_request(self):
        with patch("jump_resolver._resolve_core") as core:
            got = resolve_jump_url(_bing_url(_TARGET))
            core.assert_not_called()
        self.assertEqual(got, _TARGET)


if __name__ == "__main__":
    unittest.main()
