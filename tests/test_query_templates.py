#!/usr/bin/env python3
"""tests/test_query_templates.py — 查询模板注册表（加载/合并/展开）+ argo template CLI。

离线必过：CLI 的转发用 mock subprocess 拦下，绝不真跑搜索。

覆盖：
  - 随包注册表：schema 合法（id/command 白名单/query 非空）、条目数与分组
  - 合并：用户表新增 / 覆盖 / disabled 停用；白名单外的 command 被拒
  - 展开：模板 query + --add 追加词（空追加不产生多余空格）
  - get_template：未知 id 抛 TemplateError 且带 did-you-mean
  - CLI：--list（人读/JSON）、--dry-run（人读/JSON）、转发参数与默认参数
"""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
import contextlib
from pathlib import Path
from unittest.mock import Mock, patch

SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPT_DIR = SKILL_DIR / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import query_templates as qt  # noqa: E402
import template_cli as tc  # noqa: E402


def _write_yaml(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


class TestShippedRegistry(unittest.TestCase):
    def setUp(self):
        self.reg = qt.load_templates(include_user=False)

    def test_shipped_loads_and_nonempty(self):
        self.assertGreaterEqual(len(self.reg), 10)
        self.assertIn("ai_model_release", self.reg)
        self.assertIn("ai_zh", self.reg)

    def test_every_entry_is_valid(self):
        for tid, t in self.reg.items():
            self.assertRegex(tid, r"^[a-z0-9][a-z0-9_]*$")
            self.assertIn(t["command"], qt.COMMANDS, tid)
            self.assertTrue(t["query"].strip(), tid)
            self.assertTrue(t["description"], tid)
            self.assertTrue(t["category"], tid)

    def test_x_templates_carry_retweet_filter(self):
        """随包 X 模板统一带 -is:retweet（去转发）——方法论硬约束。"""
        for tid, t in self.reg.items():
            if t["command"] == "x-search":
                self.assertIn("-is:retweet", t["query"], tid)


class TestMerge(unittest.TestCase):
    def _user(self, text: str) -> Path:
        d = tempfile.mkdtemp(prefix="argo-tpl-")
        p = Path(d) / "query-templates.yaml"
        _write_yaml(p, text)
        return p

    def test_user_adds_new_template(self):
        up = self._user("version: 1\ntemplates:\n  my_thing:\n"
                        "    description: d\n    category: c\n"
                        "    command: search\n    query: 'hello world'\n")
        reg = qt.load_templates(include_user=True, user=up)
        self.assertIn("my_thing", reg)
        self.assertEqual(reg["my_thing"]["command"], "search")

    def test_user_overrides_shipped(self):
        up = self._user("version: 1\ntemplates:\n  ai_zh:\n"
                        "    description: 覆盖\n    command: search\n"
                        "    query: 'overridden'\n")
        reg = qt.load_templates(include_user=True, user=up)
        self.assertEqual(reg["ai_zh"]["query"], "overridden")
        self.assertEqual(reg["ai_zh"]["command"], "search")

    def test_user_can_disable_shipped(self):
        up = self._user("version: 1\ntemplates:\n  ai_zh:\n    disabled: true\n")
        reg = qt.load_templates(include_user=True, user=up)
        self.assertNotIn("ai_zh", reg)
        self.assertIn("ai_model_release", reg)  # 其余不受影响

    def test_command_whitelist_enforced(self):
        up = self._user("version: 1\ntemplates:\n  evil:\n"
                        "    description: d\n    command: rm\n    query: 'x'\n")
        with self.assertRaises(qt.TemplateError):
            qt.load_templates(include_user=True, user=up)

    def test_missing_query_rejected(self):
        up = self._user("version: 1\ntemplates:\n  bad:\n    description: d\n")
        with self.assertRaises(qt.TemplateError):
            qt.load_templates(include_user=True, user=up)


class TestExpand(unittest.TestCase):
    def test_append_words(self):
        t = {"query": "a b"}
        self.assertEqual(qt.expand(t, ["c", "d"]), "a b c d")

    def test_no_adds(self):
        self.assertEqual(qt.expand({"query": "a b"}, []), "a b")
        self.assertEqual(qt.expand({"query": "a b"}, None), "a b")

    def test_blank_adds_dropped(self):
        self.assertEqual(qt.expand({"query": "a b"}, ["", "  ", "c"]), "a b c")


class TestGetTemplate(unittest.TestCase):
    def test_unknown_raises_with_hint(self):
        reg = {"ai_model_release": {"id": "ai_model_release", "query": "x"}}
        with self.assertRaises(qt.TemplateError) as cm:
            qt.get_template(reg, "ai_model_releas")
        self.assertIn("未知模板", str(cm.exception))
        self.assertIn("ai_model_release", str(cm.exception))


def _run_cli(argv, *, subprocess_side=None):
    """跑 template_cli.main()，返回 (code, stdout)。"""
    env = {"ARGO_TEMPLATES_FILE": os.path.join(tempfile.gettempdir(),
                                               "argo-no-such-tpl.yaml")}
    buf = io.StringIO()
    patches = [patch.dict(os.environ, env)]
    if subprocess_side is not None:
        patches.append(patch.object(tc.subprocess, "run", side_effect=subprocess_side))
    for p in patches:
        p.start()
    try:
        with contextlib.redirect_stdout(buf):
            code = tc.main(argv)
    finally:
        for p in reversed(patches):
            p.stop()
    return code, buf.getvalue()


class TestCli(unittest.TestCase):
    def test_list_human(self):
        code, out = _run_cli(["--list"])
        self.assertEqual(code, 0)
        self.assertIn("ai_model_release", out)
        self.assertIn("AI 模型", out)

    def test_list_json(self):
        code, out = _run_cli(["--list", "--json"])
        self.assertEqual(code, 0)
        rows = json.loads(out)
        ids = {r["id"] for r in rows}
        self.assertIn("ai_zh", ids)

    def test_dry_run_human(self):
        code, out = _run_cli(["ai_model_release", "--add", "GPT-5", "--dry-run"])
        self.assertEqual(code, 0)
        self.assertIn("x-search", out)
        self.assertIn("GPT-5", out)
        self.assertIn("-is:retweet", out)

    def test_dry_run_json(self):
        code, out = _run_cli(["ai_zh", "--dry-run", "--json"])
        self.assertEqual(code, 0)
        d = json.loads(out)
        self.assertEqual(d["command"], "x-search")
        self.assertEqual(d["script"], "x_search.py")
        self.assertIn("lang:zh", d["query"])

    def test_unknown_template_exit1(self):
        code, out = _run_cli(["nope", "--dry-run"])
        self.assertEqual(code, 1)

    def test_forwarding_builds_argv(self):
        """转发：默认参数 + 展开 query + 透传开关，且顺序正确。"""
        captured = {}

        def fake_run(argv, **kw):
            captured["argv"] = argv
            m = Mock()
            m.returncode = 0
            return m

        code, _ = _run_cli(["ai_model_release", "--add", "GPT-5", "-n", "20",
                            "--json"], subprocess_side=fake_run)
        self.assertEqual(code, 0)
        argv = captured["argv"]
        self.assertEqual(argv[1], str(SCRIPT_DIR / "x_search.py"))
        # query 紧跟脚本（x-search 无默认参数）
        self.assertIn("GPT-5", argv[2])
        self.assertIn("-is:retweet", argv[2])
        self.assertIn("-n", argv)
        self.assertIn("--json", argv)

    def test_search_command_gets_json_default(self):
        """command: search 的模板转发时应带默认 --json（与 bin/argo 一致）。"""
        captured = {}

        def fake_run(argv, **kw):
            captured["argv"] = argv
            m = Mock()
            m.returncode = 0
            return m

        # 造一个 search 模板的用户注册表
        d = tempfile.mkdtemp(prefix="argo-tpl-")
        p = Path(d) / "query-templates.yaml"
        _write_yaml(p, "version: 1\ntemplates:\n  web_thing:\n"
                       "    description: d\n    command: search\n    query: 'hello'\n")
        buf = io.StringIO()
        with patch.dict(os.environ, {"ARGO_TEMPLATES_FILE": str(p)}), \
             patch.object(tc.subprocess, "run", side_effect=fake_run), \
             contextlib.redirect_stdout(buf):
            code = tc.main(["web_thing"])
        self.assertEqual(code, 0)
        self.assertEqual(captured["argv"][1], str(SCRIPT_DIR / "search.py"))
        self.assertIn("--json", captured["argv"])


if __name__ == "__main__":
    unittest.main()
