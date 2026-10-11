#!/usr/bin/env python3
"""wechat_article.py — 微信公众号文章多级降级抓取。

用法: argo wx <url> [--json]
      argo wx <url> --json > article.json

降级链（按速度优先）：
  1. HTTP 直取（article.py 解析逻辑，5s 超时）
  2. Chrome CDP 浏览器（复用 fetch_browser.browser_fetch）
  3. 搜狗微信搜索兜底（通过标题间接获取）

输出: 标题 / 作者 / 发布时间 / 正文纯文本 / 图片 URL 列表
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
import html as htmllib
from typing import Optional

# 复用 article.py 的解析逻辑
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from article import strip_tags, fetch_article

# 复用 fetch_browser.py 的 CDP 通道
from fetch_browser import browser_fetch

# urllib 出口唯一入口（issue #13）：代理解析集中在一处；YAML 解析同理
from net_proxy import open_url
from yaml_load import loads

# 本脚本所在目录：子进程脚本路径必须绝对（本模块可能从任意 CWD 调起）
_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))


def _http_fetch(url: str, timeout: int = 5) -> dict:
    """通道1: HTTP 直取（article.py 逻辑，短超时快速失败）。"""
    try:
        return fetch_article(url, timeout=timeout)
    except Exception as e:
        return {"ok": False, "error": f"HTTP 直取失败: {e}"}


def _cdp_fetch(url: str, timeout: int = 15) -> dict:
    """通道2: Chrome CDP 浏览器抓取。"""
    try:
        result = browser_fetch(url, max_chars=20000, timeout=timeout)
        if not result.get("success"):
            return {"ok": False, "error": result.get("error", "CDP 抓取失败")}

        content = result.get("content", "")
        title = result.get("title", "")

        html = result.get("html", "")
        author = ""
        pubtime = ""
        if html:
            m = re.search(r'id="js_name"[^>]*>([^<]+)<', html)
            if m:
                author = m.group(1).strip()
            m = re.search(r'id="publish_time"[^>]*>([^<]+)<', html)
            if m:
                pubtime = m.group(1).strip()

        imgs = []
        if html:
            imgs = re.findall(r'data-src="(https://mmbiz\.qpic\.cn/[^"]+)"', html)
            if not imgs:
                imgs = re.findall(r'src="(https://mmbiz\.qpic\.cn/[^"]+)"', html)

        return {
            "ok": True,
            "url": url,
            "title": title,
            "author": author,
            "publish_time": pubtime,
            "char_count": len(content),
            "image_count": len(imgs),
            "images": imgs,
            "content": content,
            "fetch_method": "chrome_cdp",
        }
    except Exception as e:
        return {"ok": False, "error": f"CDP 通道异常: {e}"}


def _sogou_cmd(title: str) -> list:
    """搜狗兜底的子进程命令——脚本路径绝对化，与调用方 CWD 无关。"""
    return [sys.executable, os.path.join(_SCRIPTS_DIR, "sogou_weixin_browser.py"),
            title, "--n", "3"]


def _sogou_fallback(url: str) -> dict:
    """通道3: 搜狗微信搜索兜底（通过标题间接获取）。"""
    try:
        title = ""
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                              "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
            })
            with open_url(req, timeout=5) as r:
                raw = r.read().decode("utf-8", errors="ignore")
                m = re.search(r'<meta property="og:title" content="([^"]+)"', raw)
                if m:
                    title = m.group(1).strip()
        except Exception:
            pass

        if not title:
            return {"ok": False, "error": "无法获取标题，搜狗兜底失败"}

        result = subprocess.run(
            _sogou_cmd(title),
            capture_output=True, text=True, timeout=30,
            encoding="utf-8", errors="replace"
        )
        if result.returncode != 0:
            return {"ok": False, "error": f"搜狗搜索失败: {result.stderr[:200]}"}

        try:
            items = loads(result.stdout)
        except Exception:
            return {"ok": False, "error": "搜狗搜索结果解析失败"}

        if not items:
            return {"ok": False, "error": "搜狗搜索无结果"}

        best = items[0]
        return {
            "ok": True,
            "url": best.get("url", url),
            "title": best.get("title", title),
            "author": "",
            "publish_time": best.get("published_at", ""),
            "char_count": len(best.get("snippet", "")),
            "image_count": 0,
            "images": [],
            "content": best.get("snippet", ""),
            "fetch_method": "sogou_fallback",
            "note": "通过搜狗搜索间接获取，内容可能不完整",
        }
    except Exception as e:
        return {"ok": False, "error": f"搜狗兜底异常: {e}"}


def fetch_wechat_article(url: str) -> dict:
    """多级降级链主函数。"""
    if not re.match(r"https?://mp\.weixin\.qq\.com/", url):
        return {"ok": False, "error": "仅支持 mp.weixin.qq.com 链接"}

    # 通道1: HTTP 直取（快速失败）
    result = _http_fetch(url, timeout=5)
    if result.get("ok"):
        result["fetch_method"] = "http_direct"
        return result

    # 通道2: Chrome CDP 浏览器
    result = _cdp_fetch(url, timeout=15)
    if result.get("ok"):
        return result

    # 通道3: 搜狗搜索兜底
    result = _sogou_fallback(url)
    if result.get("ok"):
        return result

    # 全部失败
    return {
        "ok": False,
        "error": "所有通道均失败。建议：1) 稍后重试 2) 用浏览器手动打开",
        "url": url,
    }


def main():
    ap = argparse.ArgumentParser(description="微信公众号文章多级降级抓取")
    ap.add_argument("url", help="mp.weixin.qq.com 文章链接")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args()

    out = fetch_wechat_article(args.url)

    if args.json:
        from cli_io import dumps
        print(dumps(out))
    else:
        if not out["ok"]:
            print(f"抓取失败: {out['error']}", file=sys.stderr)
            sys.exit(1)
        print(f"标题: {out.get('title', '')}")
        print(f"作者: {out.get('author', '')}  时间: {out.get('publish_time', '')}  "
              f"正文 {out.get('char_count', 0)} 字 / {out.get('image_count', 0)} 图")
        print(f"通道: {out.get('fetch_method', '')}")
        print("---")
        print(out.get("content", ""))
        if out.get("images"):
            print("---")
            for i, u in enumerate(out["images"], 1):
                print(f"[图{i}] {u}")


if __name__ == "__main__":
    main()
