#!/usr/bin/env python3
"""test_yuanbao_engine — 腾讯元宝搜索接入的门禁（2026-10-21）。

## 背景

元宝（POST api.wsa.cloud.tencent.com/SearchPro）有四个与 argo 既有 http
引擎不同的地方，每一条都是「声明式配置表达不了、只能写 builder」的理由：

1. `Pages` 是 **JSON 字符串数组**，要二次解析
2. **错误走 HTTP 200**（`Response.Error`）——鉴权失败/欠费/限流都是 200
3. `date` 是 `YYYY/MM/DD HH:MM:SS`（东八区），不是 argo 的 ISO 约定
4. `Cnt` 只接受 10/20/30/50，其余值上游回 `illegal Cnt` 且 0 结果

第 2 条最要命：不留痕的话，整条链会把「key 错了」上报成 `no-results`，
调用方（Agent）据此判定「网上没有这个信息」并停止追问——与 2026-09-15
`--engine you` 的 SSL 超时上报成 `completed, count=0, errors=[]` 同族。

## 锁什么

1. 二次解析：`Pages` 是字符串时能解，是对象时也认（上游改形态不炸）
2. 错误映射：六个错误码 → argo 失败类别，且**必须留痕**（note_failure）
3. 日期归一：斜杠格式 → 东八区 ISO；无法解析交空串而不是原样字符串
4. Cnt 夹取：任何 n 都落在 {10,20,30,50}
5. 字段契约：title/url/snippet/source 必有，空 url/空 title 的条目丢弃
6. 门禁有牙：清空 `_ERROR_MAP`，第 2 条必须失败

全部离线（解析层是纯函数，不发网络）。
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import engines_base  # noqa: E402
import engines_builders_batch15 as yb  # noqa: E402


def _page(**kw) -> str:
    row = {
        "title": "三星堆名字的由来",
        "url": "https://www.163.com/dy/article/X.html",
        "passage": "三星堆遗址位于四川省广汉市西北部……",
        "content": "更长的正文……",
        "date": "2024-06-07 19:00:51",
        "site": "网易",
        "score": 0.8978,
    }
    row.update(kw)
    return json.dumps(row, ensure_ascii=False)


def _payload(*pages: str, error: dict | None = None) -> dict:
    resp: dict = {"RequestId": "r-1", "Query": "三星堆的由来", "Version": "standard"}
    if error is not None:
        resp["Error"] = error
    else:
        resp["Pages"] = list(pages)
    return {"Response": resp}


class TestParse:
    def test_二次解析字符串页(self):
        out = yb.parse_yuanbao_payload(_payload(_page()), 5)
        assert len(out) == 1
        r = out[0]
        assert r["title"] == "三星堆名字的由来"
        assert r["url"] == "https://www.163.com/dy/article/X.html"
        assert r["source"] == "yuanbao"
        assert r["site_name"] == "网易"
        assert r["snippet"].startswith("三星堆遗址")

    def test_兼容对象形态的页(self):
        """上游若把 Pages 改成对象数组，不该整源失效。"""
        payload = _payload()
        payload["Response"]["Pages"] = [json.loads(_page())]
        assert len(yb.parse_yuanbao_payload(payload, 5)) == 1

    def test_n_截断(self):
        payload = _payload(*[_page(url=f"https://e.com/{i}") for i in range(5)])
        assert len(yb.parse_yuanbao_payload(payload, 2)) == 2

    def test_丢弃空_url_与空_title(self):
        payload = _payload(_page(url=""), _page(title=""), _page())
        out = yb.parse_yuanbao_payload(payload, 5)
        assert len(out) == 1

    def test_坏_json_页跳过不炸(self):
        assert yb.parse_yuanbao_payload(_payload("{不是 json"), 5) == []

    def test_snippet_优先_passage(self):
        out = yb.parse_yuanbao_payload(_payload(_page(passage="摘要", content="正文")), 5)
        assert out[0]["snippet"].startswith("摘要")

    def test_passage_缺失时回落_content(self):
        out = yb.parse_yuanbao_payload(_payload(_page(passage="", content="正文内容")), 5)
        assert out[0]["snippet"].startswith("正文内容")

    def test_剥离_html_标签(self):
        out = yb.parse_yuanbao_payload(
            _payload(_page(title="<strong>三星堆</strong>的由来")), 5)
        assert "<strong>" not in out[0]["title"]


class TestErrorPath:
    """HTTP 200 上的错误必须变成可行动的失败，而不是 no-results。"""

    def setUp(self):
        engines_base._FAIL_NOTES.clear()

    def test_鉴权错误映射为_auth_并留痕(self):
        yb.parse_yuanbao_payload(
            _payload(error={"Code": "UnauthorizedOperation", "Message": "未授权操作。"}),
            5)
        note = engines_base.pop_failure_note("yuanbao")
        assert note is not None, "错误现场没留痕——会被上报成 no-results"
        assert note["category"] == "auth"
        assert "UnauthorizedOperation" in note["detail"]

    def test_六个错误码的类别(self):
        expect = {
            "UnauthorizedOperation": "auth",
            "ResourceNotFound": "auth",
            "ResourceUnavailable": "quota_exhausted",
            "RequestLimitExceeded": "rate_limited",
            "InvalidParameter": "upstream",
            "InternalError": "unknown",
        }
        for code, cat in expect.items():
            engines_base._FAIL_NOTES.clear()
            yb.parse_yuanbao_payload(_payload(error={"Code": code, "Message": "x"}), 5)
            note = engines_base.pop_failure_note("yuanbao")
            assert note and note["category"] == cat, f"{code} → {note}"

    def test_未知错误码归_unknown_但仍留痕(self):
        yb.parse_yuanbao_payload(_payload(error={"Code": "BrandNew", "Message": "?"}), 5)
        note = engines_base.pop_failure_note("yuanbao")
        assert note and note["category"] == "unknown"

    def test_无_Response_键也留痕(self):
        yb.parse_yuanbao_payload({"Oops": 1}, 5)
        assert engines_base.pop_failure_note("yuanbao") is not None

    def test_错误时返回空列表(self):
        assert yb.parse_yuanbao_payload(
            _payload(error={"Code": "UnauthorizedOperation", "Message": "x"}), 5) == []

    def test_门禁有牙(self):
        """清空错误码表，鉴权错误必须退化成 unknown（证明映射真在起作用）。"""
        original = yb._ERROR_MAP
        try:
            yb._ERROR_MAP = {}
            engines_base._FAIL_NOTES.clear()
            yb.parse_yuanbao_payload(
                _payload(error={"Code": "UnauthorizedOperation", "Message": "x"}), 5)
            note = engines_base.pop_failure_note("yuanbao")
            assert note and note["category"] == "unknown"
        finally:
            yb._ERROR_MAP = original


class TestNormDate:
    def test_斜杠格式转东八区_iso(self):
        assert yb._norm_date("2024-06-07 19:00:51") == "2024-06-07T19:00:51+08:00"
        assert yb._norm_date("2023/06/08 00:00:00") == "2023-06-08T00:00:00+08:00"

    def test_只给日期(self):
        assert yb._norm_date("2023/06/08") == "2023-06-08T00:00:00+08:00"

    def test_无法解析交空串(self):
        """空串而不是原样字符串：原样交出去会落到「有字段但读不出日期」。"""
        assert yb._norm_date("未知") == ""
        assert yb._norm_date("") == ""
        assert yb._norm_date(None) == ""


class TestCnt:
    def test_夹到合法档(self):
        for n in range(-5, 120):
            assert yb.yuanbao_cnt(n) in yb._CNT_ALLOWED, n

    def test_取能覆盖的最小档(self):
        assert yb.yuanbao_cnt(1) == 10
        assert yb.yuanbao_cnt(10) == 10
        assert yb.yuanbao_cnt(11) == 20
        assert yb.yuanbao_cnt(21) == 30
        assert yb.yuanbao_cnt(31) == 50
        assert yb.yuanbao_cnt(999) == 50

    def test_非法输入不抛(self):
        for v in (None, "abc", 0, -1):
            assert yb.yuanbao_cnt(v) == 10


class TestKeyChain:
    def test_候选链含官方名(self):
        """腾讯文档用的名字是 TENCENTCLOUD_WSA_APIKEY，必须被识别。"""
        assert "TENCENTCLOUD_WSA_APIKEY" in yb._KEY_ENV
        assert yb._KEY_ENV[0].startswith("ARGO_")

    def test_与_engine_env_别名表一致(self):
        from engine_env import KNOWN_ENV_ALIASES
        assert set(yb._KEY_ENV) == set(KNOWN_ENV_ALIASES["yuanbao"])


class TestQuota:
    """按次的月度额度（不是金额预算）——用完即全模式排除。"""

    def _profile(self):
        import json
        root = Path(__file__).resolve().parent.parent
        return json.loads(
            (root / "backends" / "quota_profiles.json").read_text("utf-8"))["yuanbao"]

    def test_派生件是计数档不是金额档(self):
        p = self._profile()
        assert p["limit"] == 6000, "月度调用额度应为 6000 次"
        assert p["period"] == "month", "period 是额度重置周期（month→30 天）"
        # 金额档的两个字段都不该有值——有值就会被 budget.py 接管
        assert not p.get("budget_amount")

    def test_额度耗尽即全模式排除(self):
        """used >= limit → is_hard_down，路由组合层全模式排除该引擎。"""
        import os
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            old = os.environ.get("ARGO_STATE_DIR")
            os.environ["ARGO_STATE_DIR"] = d
            try:
                import importlib
                import quota as quota_mod
                importlib.reload(quota_mod)
                qm = quota_mod.get_quota_manager()
                qm._profiles["yuanbao"]["limit"] = 3
                qm.record_many([("yuanbao", True)] * 3)
                assert qm.is_hard_down("yuanbao") is True
                # 计数额度不走金额预算路径，两者不能混
                assert qm.is_over_budget("yuanbao") is False
            finally:
                if old is None:
                    os.environ.pop("ARGO_STATE_DIR", None)
                else:
                    os.environ["ARGO_STATE_DIR"] = old
                importlib.reload(quota_mod)

    def test_qps_与额度周期解耦(self):
        """period=month 只改额度重置跨度，限频窗口固定 60 秒（不能联动）。"""
        p = self._profile()
        assert p["qps"] == 2
        src = (Path(__file__).resolve().parent.parent
               / "scripts" / "quota.py").read_text("utf-8")
        assert "now - t < 60" in src, "限频窗口应固定 60 秒，与 period 无关"


if __name__ == "__main__":
    unittest.main()
