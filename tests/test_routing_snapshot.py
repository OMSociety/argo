#!/usr/bin/env python3
"""test_routing_snapshot.py — 路由决策快照对账门（离线、确定性）。

## 这道门在治什么

近 90 天 `fix(route)` 13 次：每次动域正则都可能碰翻另一条查询的路由，
而既有防线只有手工维护的 ~100 条标注用例（ROUTE_MATRIX + precision 测试），
没有「这次改动翻转了哪些查询」的总视图——修 A 坏 B 的回归只能靠人撞。

本门把路由决策变成可 diff 的快照（tests/golden/routing_snapshot.json）：
语料 = 三处标注集并集（116 条），比对键 = domain + kind（regex/tfidf）。
引擎组合**不比对**——它随熔断/配额/健康态波动，参与比对会让门禁被环境
噪声天天假红，直到被人 --no-verify，那比没有门禁更坏。

## 工作流

改路由后：`python3 scripts/gen_routing_snapshot.py` 重新生成 → review diff
→ 提交（快照随改动一起）。本测试调 `--check`：有漂移即红，并给出「哪条
查询、哪个键、从什么变成什么、期望域是什么」的可读 diff。

运行：
    python3 -m pytest tests/test_routing_snapshot.py -v
"""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GEN = ROOT / "scripts" / "gen_routing_snapshot.py"


class TestRoutingSnapshot(unittest.TestCase):
    def test_snapshot_up_to_date(self):
        """当前路由决策必须与已提交快照逐条一致（domain + kind）。"""
        r = subprocess.run([sys.executable, str(GEN), "--check"],
                           capture_output=True, text=True, timeout=300, cwd=str(ROOT))
        self.assertEqual(r.returncode, 0,
                         f"路由快照漂移（改路由请重新生成并 review diff）：\n"
                         f"{r.stdout}{r.stderr}")

    def test_generator_reports_usage_log_locally(self):
        """--local 观察窗：真实查询过一遍路由，不入快照（本机无日志时空跑）。"""
        r = subprocess.run([sys.executable, str(GEN), "--local", "10"],
                           capture_output=True, text=True, timeout=300, cwd=str(ROOT))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("usage_log", r.stdout)


if __name__ == "__main__":
    unittest.main()
