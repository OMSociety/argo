#!/usr/bin/env python3
"""ab_eval — 交错 A/B 实测（逐对随机化运行顺序，防顺序偏差）。

为什么存在（2026-10-07 教训）：非交错基准里，暖连接红利让「后跑的一组」
系统性变慢/变快，造出过 37% 的假阳性——本仓历史同类假阳性至少三次
（roundtrip 第三次假阳性、benchmark 阈值改旗标、10-07 事件化证伪轮）。
本工具把正确测量固化成可复用能力：**逐对抛硬币定运行序**，逐对差值出
统计量（中位差、A 胜率、精确二项符号检验），单次快慢不作数。

与 ab_eval_p0p1.py 的分工：那是 P0/P1 优化轮的一次性验收脚本（固定场景
清单）；本工具是通用 A/B 测量器——两条带 {query} 占位符的命令即可对测
（不同引擎组合、开关、参数档）。

用法：
  python3 scripts/ab_eval.py --pairs 10 \
    --cmd-a "python3 scripts/search.py {query} --json --fields agent" \
    --cmd-b "python3 scripts/search.py {query} --json --fields agent --verify 2" \
    --query "蓝牙耳机推荐"

子进程默认注入 ARGO_USAGE_LOG=0：A/B 用的是合成查询对，不进生产使用账本
（口径同 10-10 评测隔离原则）；--usage-log 保留写入。

输出 stdout 单个 JSON：per_pair（含当对运行序）+ stats。exit 恒 0（测量
工具不是门禁）；质量守卫字段 count_median_a/b 供人工判断结果数回退。
"""
from __future__ import annotations

import argparse
import json
import os
import random
import shlex
import statistics
import subprocess
import sys
import time

_RUN_TIMEOUT_S = 120


def _run_once(cmd: str, query: str, keep_usage: bool) -> dict:
    # {query} 由本函数负责加引号（shlex.quote）：含空格查询此前会把命令拆成
    # 多个 argv，argparse 直接 rc=2——占位符两侧不要再自行加引号。
    substituted = cmd.replace("{query}", shlex.quote(query))
    env = dict(os.environ)
    if not keep_usage:
        env["ARGO_USAGE_LOG"] = "0"
    t0 = time.monotonic()
    try:
        proc = subprocess.run(substituted, shell=True, capture_output=True,
                              text=True, encoding="utf-8", errors="replace",
                              timeout=_RUN_TIMEOUT_S, env=env)
    except subprocess.TimeoutExpired:
        return {"ok": False, "reason": f"timeout>{_RUN_TIMEOUT_S}s"}
    wall_ms = round((time.monotonic() - t0) * 1000)
    if proc.returncode != 0:
        return {"ok": False, "reason": f"rc={proc.returncode}",
                "stderr_tail": proc.stderr[-200:], "wall_ms": wall_ms}
    try:
        d = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"ok": False, "reason": "stdout 非 JSON", "wall_ms": wall_ms,
                "stdout_head": proc.stdout[:120]}
    timing = d.get("timing") or {}
    return {"ok": True, "elapsed_ms": timing.get("elapsed_ms", wall_ms),
            "count": d.get("count"), "wall_ms": wall_ms}


def _sign_test_p(wins: int, losses: int) -> float:
    """精确二项双尾符号检验（无平局计入 n）。"""
    n = wins + losses
    if n == 0:
        return 1.0
    k = min(wins, losses)
    tail = sum(_comb(n, i) for i in range(0, k + 1)) / (2 ** n)
    return min(1.0, 2 * tail)


def _comb(n: int, k: int) -> float:
    from math import comb
    return comb(n, k)


def evaluate(cmd_a: str, cmd_b: str, query: str, pairs: int, seed: int | None,
             keep_usage: bool) -> dict:
    rng = random.Random(seed)
    per_pair = []
    for i in range(pairs):
        a_first = rng.random() < 0.5
        runs = {}
        for label in (("a", "b") if a_first else ("b", "a")):
            cmd = cmd_a if label == "a" else cmd_b
            runs[label] = _run_once(cmd, query, keep_usage)
        per_pair.append({"pair": i + 1, "a_first": a_first,
                         "a": runs["a"], "b": runs["b"]})
    diffs, a_wins, b_wins, ties = [], 0, 0, 0
    for r in per_pair:
        a, b = r["a"], r["b"]
        if not (a.get("ok") and b.get("ok")):
            continue  # 失败对不进统计，账面保留
        d = a["elapsed_ms"] - b["elapsed_ms"]
        diffs.append(d)
        if d < 0:
            a_wins += 1
        elif d > 0:
            b_wins += 1
        else:
            ties += 1
    counts_a = [r["a"]["count"] for r in per_pair
                if r["a"].get("ok") and r["a"].get("count") is not None]
    counts_b = [r["b"]["count"] for r in per_pair
                if r["b"].get("ok") and r["b"].get("count") is not None]
    stats = {
        "valid_pairs": len(diffs),
        "failed_pairs": pairs - len(diffs),
        "median_diff_ms": statistics.median(diffs) if diffs else None,
        "mean_diff_ms": round(statistics.fmean(diffs), 1) if diffs else None,
        "a_wins": a_wins, "b_wins": b_wins, "ties": ties,
        "sign_test_p": round(_sign_test_p(a_wins, b_wins), 4),
        "count_median_a": statistics.median(counts_a) if counts_a else None,
        "count_median_b": statistics.median(counts_b) if counts_b else None,
    }
    return {"query": query, "pairs": pairs, "seed": seed,
            "order": "逐对随机（a_first 字段记录当对顺序）",
            "per_pair": per_pair, "stats": stats}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="交错 A/B 实测（随机化逐对顺序）")
    ap.add_argument("--cmd-a", required=True, help="A 变体命令，含 {query} 占位")
    ap.add_argument("--cmd-b", required=True, help="B 变体命令，含 {query} 占位")
    ap.add_argument("--query", required=True)
    ap.add_argument("--pairs", type=int, default=10)
    ap.add_argument("--seed", type=int, default=None,
                    help="固定种子可复现当轮运行序")
    ap.add_argument("--usage-log", action="store_true",
                    help="子进程查询写入生产使用账本（默认不写）")
    args = ap.parse_args(argv)
    report = evaluate(args.cmd_a, args.cmd_b, args.query, args.pairs,
                      args.seed, args.usage_log)
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
