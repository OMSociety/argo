#!/usr/bin/env python3
"""fetch_feishu.py — 飞书文档认证直取（fetch_v3 第零级前置短路）。

职责单一：给定 URL，判断它是不是飞书云文档；是则经 lark-cli 的认证通道取回
**原生 Markdown 正文**，其余一概返回 None。

从 fetch_v3 拆出，理由与 fetch_quality 同：让 fetch_v3 聚焦降级链调度，避免其
持续膨胀（拆前 1872 行）。本模块不构建结果 dict、不碰质量信号、不持有状态——
结果形态由调用方决定，所以 `fetch_text` 只交回正文文本。

为什么值得单开一条前置通道（实测）：
  飞书云文档 URL 走公开路径会逐级降级到 chrome_cdp（Chrome 冷启动），35s 后
  拿回登录页；而登录页的长度(231)与质量分(0.31)都能险过阈值，被当成功收下。
  经认证直取则一步拿到原生 Markdown——飞书文档本身就是 Markdown，无需
  HTML→Markdown 转换，结构保真 100%，且不消耗任何反爬预算。

纯增益前置：未装 lark-cli / 未登录 / 非文档 URL / 任何失败一律返回 None，
交回调用方的降级链，既有站点行为完全不变。
"""

from __future__ import annotations

import shutil
import subprocess
from urllib.parse import urlparse

try:
    from engine_env import env_flag
except ImportError:  # 独立运行时（测试/脚本）保底
    def env_flag(name: str, default: bool = True) -> bool:
        import os
        raw = os.environ.get(name)
        if raw is None:
            return default
        return str(raw).strip().lower() not in {"0", "false", "no", "off", ""}

# 飞书文档 URL 形态：<tenant>.feishu.cn/<type>/<token>，
# 同族还有 larksuite.com（国际版）与 larkoffice.com / feishu.net（别名域）。
_DOC_HOSTS = ("feishu.cn", "larksuite.com", "larkoffice.com", "feishu.net")
# 首段路径即对象类型；只认这些，避免把营销页/帮助中心（/content/...、/document/...）
# 也当成文档去打认证接口。
_DOC_PATH_TYPES = ("docx", "docs", "wiki", "sheets", "base", "slides",
                   "mindnotes", "file")

# 取回正文的长度地板：低于此视为空文档/权限页残留，交回降级链。
_MIN_CHARS = 200


def enabled() -> bool:
    """认证直取开关：ARGO_FETCH_FEISHU=0 关闭，默认开启。

    默认开是安全的：未装 lark-cli 时 shutil.which 直接返回 None，零开销。
    """
    return env_flag("ARGO_FETCH_FEISHU")


def matches(url: str) -> bool:
    """是否飞书云文档地址（排除营销页/帮助中心等非文档路径）。"""
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    host = (parsed.netloc or "").lower().split(":", 1)[0]
    if not any(host == h or host.endswith("." + h) for h in _DOC_HOSTS):
        return False
    parts = [p for p in (parsed.path or "").split("/") if p]
    return bool(parts) and parts[0].lower() in _DOC_PATH_TYPES


def fetch_text(url: str, timeout: float = 8.0) -> str | None:
    """经 lark-cli 认证直取飞书文档正文（原生 Markdown）；不适用返回 None。"""
    if not matches(url):
        return None
    exe = shutil.which("lark-cli")
    if not exe:
        return None
    try:
        r = subprocess.run(
            [exe, "docs", "+fetch", "--doc", url, "--as", "user",
             "--doc-format", "markdown", "--jq", ".data.document.content"],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=timeout)
    except Exception:
        return None
    # 非零退出 = 未授权/无权限/文档不存在。静默交回降级链，不猜正文——
    # 猜出来的「正文」比没有正文更坏（登录页当正文正是这么发生的）。
    if r.returncode != 0:
        return None
    text = (r.stdout or "").strip()
    return text if len(text) >= _MIN_CHARS else None
