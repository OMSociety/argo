#!/usr/bin/env python3
"""漂移阈值判定：把夜间「重录 vs 基线」的比较结果变成退出码。

## 为什么单独成文件

判定逻辑原来写在 nightly.yml 的 heredoc 里：语法对错只能在推上去之后知道，
阈值改松改紧也没人测。抽出来后有两个好处——本地能跑同一套判定，用例能锁住
「跌多少算跌」这条契约（tests/test_ci_workflows.py）。

## 判什么、为什么只判这两样

- **结果条数**：少 1 条允许（工具源单条抖动很常见），少 2 条以上算漂移；
- **输出体积**：超过基线 20% 算漂移（体积是 Agent 真金白银付的上下文）。

`not_recorded`（重放时要了一个当时没调过的引擎）**不计入**：录制只保留真正
被调到的引擎，而重放是瞬时完成，早停时机与真跑不同，这是录制机制的正常边界，
当成回归报会制造长期噪音。它仍然会打印出来，供人看。

用法：
    python3 scripts/ci_drift_gate.py --baseline 基线报告.json --current 本次报告.json
退出码：0 通过；1 有漂移；2 输入缺失/格式不对（这两件事必须分开，混在一起
会让人以为「红了=质量掉了」）。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

KEPT_SLACK = 1          # 允许少 1 条
BYTES_GROWTH = 1.2      # 体积上限 = 基线 × 1.2


def _load(path: Path) -> dict[str, Any]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    # save_baseline 存的是 {"_meta":…, "report":{…}}；evaluate_all 直接给报告本体
    return doc.get("report", doc)


def violations(base: dict[str, Any], cur: dict[str, Any]) -> list[str]:
    by_id = {c.get("id"): c for c in (base.get("cases") or [])}
    cur_ids = {c.get("id") for c in (cur.get("cases") or [])}
    out: list[str] = []
    for case in cur.get("cases") or []:
        old = by_id.get(case.get("id"))
        if not old:
            continue  # 新增的用例没有基线，不算漂移
        cid = case.get("id")
        kept, old_kept = case.get("kept", 0), old.get("kept", 0)
        if kept < old_kept - KEPT_SLACK:
            out.append(f"{cid}: 结果 {kept} 条，基线 {old_kept} 条")
        old_bytes = old.get("bytes", 0)
        if old_bytes and case.get("bytes", 0) > old_bytes * BYTES_GROWTH:
            out.append(
                f"{cid}: 输出 {case.get('bytes')}B，超过基线 {old_bytes}B×{BYTES_GROWTH}")
    # 基线里有、本次没有：不是「通过」，是这条根本没被录到（查询集被改、
    # 或录制整条失败）。2026-10-22 本地实跑踩过：只剩 1 条时判定照样退 0。
    for cid in by_id:
        if cid and cid not in cur_ids:
            out.append(f"{cid}: 本次报告里没有这条（查询集被改了，还是录制失败？）")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="夜间漂移阈值判定")
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--current", required=True)
    args = ap.parse_args()

    try:
        base = _load(Path(args.baseline))
        cur = _load(Path(args.current))
    except (OSError, json.JSONDecodeError) as e:
        print(f"读不到报告：{type(e).__name__}: {e}", file=sys.stderr)
        return 2

    bad = violations(base, cur)
    if bad:
        print("\n".join(bad), file=sys.stderr)
        return 1
    print(f"通过：{len(cur.get('cases') or [])} 条，漏录 "
          f"{cur.get('total_missing', 0)} 个引擎（信息项，不算漂移）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
