#!/usr/bin/env python3
"""tests/test_wechat_article.py — 微信文章多级降级抓取单元测试

覆盖：URL 验证、降级链编排、各通道成功/失败场景、输出格式。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

from wechat_article import fetch_wechat_article, _http_fetch, _cdp_fetch


# ── URL 验证 ───────────────────────────────────────────────────────────────

def test_non_wechat_url_rejected():
    """非微信域名应被拒绝。"""
    result = fetch_wechat_article("https://example.com/article")
    assert not result["ok"]
    assert "仅支持 mp.weixin.qq.com" in result["error"]


def test_non_http_url_rejected():
    """非 http(s) URL 应被拒绝。"""
    result = fetch_wechat_article("ftp://mp.weixin.qq.com/s/xxx")
    assert not result["ok"]


# ── 通道1: HTTP 直取 ───────────────────────────────────────────────────────

def test_http_fetch_success():
    """HTTP 直取成功时返回结构化结果。"""
    mock_result = {
        "ok": True,
        "url": "https://mp.weixin.qq.com/s/abc",
        "title": "测试文章",
        "author": "作者",
        "content": "正文内容",
        "char_count": 4,
    }
    with patch("wechat_article.fetch_article", return_value=mock_result):
        result = _http_fetch("https://mp.weixin.qq.com/s/abc")
        assert result["ok"]
        assert result["title"] == "测试文章"


def test_http_fetch_failure():
    """HTTP 直取失败时返回错误。"""
    with patch("wechat_article.fetch_article", side_effect=Exception("robots.txt 拦截")):
        result = _http_fetch("https://mp.weixin.qq.com/s/abc")
        assert not result["ok"]
        assert "HTTP 直取失败" in result["error"]


# ── 通道2: CDP 浏览器 ──────────────────────────────────────────────────────

def test_cdp_fetch_success():
    """CDP 抓取成功时返回结构化结果。"""
    mock_browser_result = {
        "success": True,
        "content": "这是正文内容",
        "title": "文章标题",
        "html": '<div id="js_name">作者名</div><div id="publish_time">2026-10-11</div>'
                  '<img data-src="https://mmbiz.qpic.cn/img1.jpg">',
    }
    with patch("wechat_article.browser_fetch", return_value=mock_browser_result):
        result = _cdp_fetch("https://mp.weixin.qq.com/s/abc")
        assert result["ok"]
        assert result["title"] == "文章标题"
        assert result["author"] == "作者名"
        assert result["publish_time"] == "2026-10-11"
        assert result["fetch_method"] == "chrome_cdp"
        assert len(result["images"]) == 1


def test_cdp_fetch_failure():
    """CDP 抓取失败时返回错误。"""
    with patch("wechat_article.browser_fetch", return_value={
        "success": False, "error": "Chrome failed to start"
    }):
        result = _cdp_fetch("https://mp.weixin.qq.com/s/abc")
        assert not result["ok"]
        assert "Chrome failed to start" in result["error"]


# ── 降级链编排 ─────────────────────────────────────────────────────────────

def test_fallback_to_cdp_when_http_fails():
    """HTTP 失败时应降级到 CDP。"""
    with patch("wechat_article._http_fetch", return_value={"ok": False, "error": "拦截"}):
        with patch("wechat_article._cdp_fetch", return_value={
                "ok": True, "title": "CDP 文章", "content": "内容", "fetch_method": "chrome_cdp"
        }):
            with patch("wechat_article._sogou_fallback") as mock_sogou:
                result = fetch_wechat_article("https://mp.weixin.qq.com/s/abc")
                assert result["ok"]
                assert result["title"] == "CDP 文章"
                mock_sogou.assert_not_called()


def test_fallback_to_sogou_when_cdp_fails():
    """CDP 失败时应降级到搜狗。"""
    with patch("wechat_article._http_fetch", return_value={"ok": False, "error": "拦截"}):
        with patch("wechat_article._cdp_fetch", return_value={"ok": False, "error": "CDP 失败"}):
            with patch("wechat_article._sogou_fallback", return_value={
                "ok": True, "title": "搜狗文章", "content": "摘要", "fetch_method": "sogou_fallback"
            }):
                result = fetch_wechat_article("https://mp.weixin.qq.com/s/abc")
                assert result["ok"]
                assert result["title"] == "搜狗文章"


def test_all_channels_fail():
    """所有通道都失败时返回结构化错误。"""
    with patch("wechat_article._http_fetch", return_value={"ok": False, "error": "拦截"}):
        with patch("wechat_article._cdp_fetch", return_value={"ok": False, "error": "CDP 失败"}):
            with patch("wechat_article._sogou_fallback", return_value={"ok": False, "error": "搜狗失败"}):
                result = fetch_wechat_article("https://mp.weixin.qq.com/s/abc")
                assert not result["ok"]
                assert "所有通道均失败" in result["error"]


# ── 输出格式 ───────────────────────────────────────────────────────────────

def test_output_contains_required_fields():
    """输出应包含必要字段。"""
    with patch("wechat_article._http_fetch", return_value={
        "ok": True, "url": "https://mp.weixin.qq.com/s/abc", "title": "标题", "author": "作者", "publish_time": "2026-10-11",
        "content": "正文", "char_count": 2, "image_count": 0, "images": [],
        "fetch_method": "http_direct",
    }):
        result = fetch_wechat_article("https://mp.weixin.qq.com/s/abc")
        for field in ["ok", "url", "title", "author", "content", "fetch_method"]:
            assert field in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
