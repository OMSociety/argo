#!/usr/bin/env python3
"""query_operators.py — 查询级操作符契约层（2026-10-17，借鉴 DeepSeek Search）。

## 解决什么问题

Google 风格查询里的操作符（site:/-site:/-词/-"短语"/lang:/after:/before:）
此前散落四处：引号短语走 phrase_filter、-词走 query_understanding 的否定、
after/before 只认 CLI flag、lang 靠自动检测、site: 更是只以「域正则触发词」
的形态存在——结果是一条 `DeepSeek site:github.com` 把路由锁死进 code_search，
而引擎侧拿到的还是含字面 site: 的脏查询（2026-10-17 实测：github 引擎返回
GitHub Pages 通用页）。同一能力五种形态、没有一处是契约。

## 本层的契约（对照 DeepSeek Search 的透传语义）

Argo 侧选择**解析而非透传**：DeepSeek 把操作符原样甩给上游搜索服务，Argo 的
上游是 260 个异构引擎（多数不认识这些语法），原样透传=把字面 site: 喂给
不认识它的引擎。故本层抽取为结构化 operators，路由/缓存/查询理解只认
clean_query（剥掉指令后的意图核心），operators 走三个既有消费点：

  - langs     → route 的语言偏好覆盖（替代自动检测的选择）
  - after/before → 时间窗归一化（--since/--until 的同一判据；CLI flag 优先）
  - exclude_terms → query_understanding 的排除项汇合（融合后过滤）
  - sites/exclude_sites/phrases → v1 只记录可观测（results 的 limitations 提示
    未下推），不污染检索词；按引擎能力下推是后续增量（extra_params 的查询级
    覆盖机制已就位）

## 语法（与 DeepSeek 对齐的子集）

  site:github.com / -site:x.com   站点限定/排除（多个空格分隔按 OR 语义记录）
  -词 / -"短语"                   排除关键词/短语
  "短语"                          精确短语（保留在 clean_query——它是意图
                                  本体不是指令，phrase_filter 照常提取）
  lang:zh,en                      语言限定（逗号分隔）
  after:2026 / after:2026-01-01   发布时间下界
  before:2026 / before:2026-06-01 发布时间上界

纯函数、零依赖、无全局状态。用法：
  from query_operators import parse_query_operators
  clean, ops = parse_query_operators('DeepSeek site:github.com lang:zh after:2026')
  # clean == 'DeepSeek'；ops['sites'] == ['github.com']；ops['langs'] == ['zh']
"""
from __future__ import annotations

import re
from typing import Any

# site: 的值：域名形态（字母数字点连字符），到空白/引号/结尾收边
# site: 值；尾部 OR 连接词仅在「后面还跟 site:」时消费（DeepSeek 文档的
# 多站点 OR 语义），否则查询里的裸 OR 原样保留。
_SITE_RE = re.compile(r"(?<![\w-])(-?)site:([a-zA-Z0-9.\-]+)(?:\s+OR(?=\s+site:))?")
# lang: 的值：逗号分隔的语言代码
_LANG_RE = re.compile(r"(?<![\w-])lang:([a-zA-Z,]+)")
# after:/before: 的值：年份或 YYYY-MM-DD
_DATE_RE = re.compile(r"(?<![\w-])(after|before):(\d{4}(?:-\d{2}-\d{2})?)")
# 排除短语：-"..."（先于单词排除处理）
_EXCL_PHRASE_RE = re.compile(r'-\s*"([^"]+)"')
# 排除单词：-词（字母数字或 CJK 串；连字符后紧跟非空白非连字符）
_EXCL_TERM_RE = re.compile(r"(?<![\w\"])-(\S+)")


def parse_query_operators(query: str) -> tuple[str, dict[str, Any]]:
    """抽取查询操作符 → (clean_query, operators)。

    clean_query 剥掉全部指令（site/-site/-词/-"短语"/lang/after/before），
    保留精确短语 "..."（它是意图本体）。operators 字段：
      sites / exclude_sites: list[str]
      exclude_terms: list[str]（-词 与 -"短语" 合并，供排除过滤）
      langs: list[str]
      after / before: str | None
      dropped: list[str]（原操作符文本，可观测/limitations 提示用）
    """
    if not query or not isinstance(query, str):
        return (query or ""), _empty_ops()

    ops = _empty_ops()
    text = query

    def _take(match: re.Match) -> str:
        ops["dropped"].append(match.group(0).strip())
        return " "

    # 1) 站点限定/排除
    def _site_sub(m: re.Match) -> str:
        (ops["exclude_sites"] if m.group(1) else ops["sites"]).append(m.group(2))
        return _take(m)
    text = _SITE_RE.sub(_site_sub, text)

    # 2) 语言
    def _lang_sub(m: re.Match) -> str:
        langs = [x.strip() for x in m.group(1).split(",") if x.strip()]
        ops["langs"].extend(langs)
        return _take(m)
    text = _LANG_RE.sub(_lang_sub, text)

    # 3) 时间窗
    def _date_sub(m: re.Match) -> str:
        ops[m.group(1)] = m.group(2)
        return _take(m)
    text = _DATE_RE.sub(_date_sub, text)

    # 4) 排除短语（先于 -词，避免 " 被当词的一部分）
    def _excl_phrase_sub(m: re.Match) -> str:
        ops["exclude_terms"].append(m.group(1).strip())
        return _take(m)
    text = _EXCL_PHRASE_RE.sub(_excl_phrase_sub, text)

    # 5) 排除单词
    def _excl_term_sub(m: re.Match) -> str:
        term = m.group(1).strip()
        if term:
            ops["exclude_terms"].append(term)
        return _take(m)
    text = _EXCL_TERM_RE.sub(_excl_term_sub, text)

    clean = re.sub(r"\s+", " ", text).strip()
    return clean, ops


def _empty_ops() -> dict[str, Any]:
    return {
        "sites": [], "exclude_sites": [], "exclude_terms": [],
        "langs": [], "after": None, "before": None, "dropped": [],
    }
