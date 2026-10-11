#!/usr/bin/env python3
"""digup_bridge：digup 结果行 → argo 契约的映射边界测试（全离线，无模型）。

覆盖：
  - 位置后缀与 URL fragment（PDF 页 / 音视频时刻）——fragment 同时承担
    「同文件不同页/时刻不被 url 去重合并」
  - excerpt 高亮记号 «» 剥除；无 excerpt 时回退 snippet 永不为空
  - published_at：digup --json 不带 modified，桥内 os.stat 取 mtime
    （文件消失时不硬造日期）
  - resolve_bin 定位顺序（显式 > DIGUP_BIN > PATH > App Helpers）
  - main() 端到端：假 digup 可执行 → {"results": [...]} 单 JSON
"""

from __future__ import annotations

import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import digup_bridge  # noqa: E402


class MapRowTests(unittest.TestCase):
    def test_pdf_page_hit(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "行政处罚法.pdf"
            f.write_bytes(b"%PDF-1.4 fake")
            row = {"path": str(f), "kind": "pdf", "segment": "page", "loc": 13.0,
                   "score": 3.1, "excerpt": "«罚款»、没收的违法所得必须上缴国库"}
            r = digup_bridge.map_row(row, 0)
        self.assertEqual(r["title"], "行政处罚法.pdf · 第13页")
        self.assertTrue(r["url"].startswith("file://") and "#page=13" in r["url"])
        self.assertNotIn("«", r["snippet"])
        self.assertIn("罚款", r["snippet"])
        self.assertEqual(r["source"], "digup")
        self.assertRegex(r["published_at"], r"^\d{4}-\d{2}-\d{2}$")
        self.assertEqual(r["score"], 1.0)

    def test_audio_moment_hit(self):
        row = {"path": "/a/talk.m4a", "kind": "audio", "segment": "audio",
               "loc": 125.0, "loc_end": 150.0, "modified": 1760000000.0}
        r = digup_bridge.map_row(row, 1)
        self.assertIn("2:05（声音）", r["title"])
        self.assertTrue(r["url"].endswith("#t=125,150"))
        self.assertEqual(r["score"], 0.9)

    def test_image_no_excerpt_snippet_never_empty(self):
        home = os.path.expanduser("~")
        row = {"path": f"{home}/Pics/shot.png", "kind": "screenshot",
               "segment": "name", "score": 4.0, "modified": 0}
        r = digup_bridge.map_row(row, 2)
        self.assertIn("截图", r["snippet"])
        self.assertIn("~/Pics", r["snippet"])
        self.assertNotIn("published_at", r)   # mtime 缺失不硬造日期

    def test_lines_hit(self):
        row = {"path": "/repo/x.py", "kind": "doc", "segment": "lines",
               "loc": 10.0, "loc_end": 24.0}
        r = digup_bridge.map_row(row, 0)
        self.assertEqual(r["title"], "x.py · 第10–24行")

    def test_duration_passthrough_ignores_junk(self):
        # digup --json 不带 modified/info，桥内 os.stat 取 mtime
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "v.mp4"
            f.write_bytes(b"x")
            ok = digup_bridge.map_row({"path": str(f), "kind": "video"}, 0)
            self.assertRegex(ok["published_at"], r"^\d{4}-\d{2}-\d{2}$")
            gone = digup_bridge.map_row({"path": str(Path(d) / "nope.mp4"), "kind": "video"}, 0)
            self.assertNotIn("published_at", gone)   # 文件没了不硬造日期


class ResolveBinTests(unittest.TestCase):
    @staticmethod
    def _fake_bin(path: Path) -> str:
        path.write_text("#!/bin/sh\n")
        path.chmod(path.stat().st_mode | stat.S_IEXEC)
        return str(path)

    def test_explicit_wins(self):
        with tempfile.TemporaryDirectory() as d:
            fake = self._fake_bin(Path(d) / "digup")
            self.assertEqual(digup_bridge.resolve_bin(fake), fake)

    def test_env_beats_which(self):
        with tempfile.TemporaryDirectory() as d:
            fake = self._fake_bin(Path(d) / "digup")
            with patch.object(digup_bridge.shutil, "which", return_value="/path/which-digup"):
                self.assertEqual(digup_bridge.resolve_bin(), "/path/which-digup")
                with patch.dict(os.environ, {"DIGUP_BIN": fake}):
                    self.assertEqual(digup_bridge.resolve_bin(), fake)

    def test_app_helper_fallback(self):
        with tempfile.TemporaryDirectory() as d:
            helper = Path(d) / "digup"
            helper.write_text("#!/bin/sh\n")
            helper.chmod(helper.stat().st_mode | stat.S_IEXEC)
            with patch.dict(os.environ, {"DIGUP_BIN": ""}), \
                 patch.object(digup_bridge.shutil, "which", return_value=None), \
                 patch.object(digup_bridge, "_APP_HELPERS", [str(helper)]):
                self.assertEqual(digup_bridge.resolve_bin(), str(helper))

    def test_missing_returns_empty(self):
        with patch.dict(os.environ, {"DIGUP_BIN": ""}), \
             patch.object(digup_bridge.shutil, "which", return_value=None), \
             patch.object(digup_bridge, "_APP_HELPERS", ()):
            self.assertEqual(digup_bridge.resolve_bin(), "")


class MainTests(unittest.TestCase):
    def test_end_to_end_with_fake_digup(self):
        with tempfile.TemporaryDirectory() as d:
            fake = Path(d) / "digup"
            rows = [{"path": "/Users/me/a.pdf", "kind": "pdf", "segment": "page",
                     "loc": 3.0, "excerpt": "«backoff» retry", "modified": 1760000000.0}]
            fake.write_text(f"#!/bin/sh\nprintf '%s' '{json.dumps(rows)}'\n")
            fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
            out = json.loads(_capture(
                lambda: digup_bridge.main(["backoff", "-n", "3", "--bin", str(fake)])))
            self.assertEqual(len(out["results"]), 1)
            self.assertEqual(out["results"][0]["title"], "a.pdf · 第3页")

    def test_missing_bin_yields_empty_results(self):
        with patch.dict(os.environ, {"DIGUP_BIN": ""}), \
             patch.object(digup_bridge.shutil, "which", return_value=None), \
             patch.object(digup_bridge, "_APP_HELPERS", ()):
            out = _capture(lambda: digup_bridge.main([" anything "]))
            self.assertEqual(json.loads(out)["results"], [])


def _capture(fn) -> str:
    """捕获 main() 的 stdout JSON（main 返回码恒 0，不 sys.exit）。"""
    import io
    import contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        fn()
    return buf.getvalue()


if __name__ == "__main__":
    unittest.main()
