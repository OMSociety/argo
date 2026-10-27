#!/usr/bin/env python3
"""test_python_probe.py — bin/argo 的解释器探测契约（回归门）。

两个真实缺陷在这里被钉住，起因都不是「写错了一个字」，而是「写了一个看起来
在检查、实际什么都没检查的表达式」：

1. **严格档是死代码**（2026-10-21 定位）。旧写法：
       "import sys; sys.exit(0 if sys.version_info >= (3,9,) else 1); import yaml"
   `sys.exit(...)` 在版本判据成立的那一刻就终止进程，`import yaml` 永不执行。
   于是严格档与廉价档的唯一区别（真 import）被自己吃掉，两档退化成同一个判据；
   结果 macOS 自带 python3.9（无 PyYAML）通过探测、被写进
   `~/.cache/unified-search/.argo_python`，此后每个 `type: cli` 引擎都在子进程里
   ModuleNotFoundError —— 实测 weather 单次 5.8s traceback 且 0 条结果、
   weather_query 域 p50 被抬到 3071ms（本机最慢域）。

2. **候选链只查 PATH**（同日定位）。`/opt/homebrew/bin` 在非交互式 shell 里
   常常不在 PATH 上，`shutil.which("python3.14")` 一律落空 → 回落到
   sys.executable=3.9。现在经 `_which_python` 在 which 落空后按惯例前缀再找一遍。

## 怎么在不装/不卸 PyYAML 的前提下测「依赖真的被 import 了」

往 `sys.modules['yaml']` 塞 `None`：CPython 对 `import x` 遇到
`sys.modules[x] is None` 会立刻抛 ImportError（"import of yaml halted; None in
sys.modules"）。这让我们能在**任何**解释器上构造「依赖不可用」这一态，而不必
真的卸载包——判据于是变成可重复的：可用 → rc 0，不可用 → rc 非 0。

旧实现对这个构造返回 0（因为它根本没 import），新实现返回非 0。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
ARGO_BIN = SKILL_DIR / "bin" / "argo"

# 判据与 bin/argo 的 _PY_*_CHECK 共用同一构造手段。`sys.modules['yaml'] = None`
# 必须在被测代码之前执行，且被测代码自己开头的 `import sys` 不受影响。
_POISON_YAML = "import sys; sys.modules['yaml'] = None\n"


def _load_entry_module():
    """把 bin/argo 当普通模块执行一遍，拿到它的常量与助手。

    bin/argo 是脚本（末尾 `if __name__ == "__main__": main()`），用
    `__name__` 非 `__main__` 执行即可只取定义、不触发主流程。
    """
    namespace = {"__file__": str(ARGO_BIN), "__name__": "argo_entry_under_test"}
    source = ARGO_BIN.read_text(encoding="utf-8")
    exec(compile(source, str(ARGO_BIN), "exec"), namespace)  # noqa: S102 — 本地可信源
    return namespace


class TestProbeChecksActuallyCheck(unittest.TestCase):
    """两个探测脚本都必须真的验证「版本 + 依赖」，且不能有不可达代码。"""

    @classmethod
    def setUpClass(cls):
        cls.entry = _load_entry_module()

    def _run(self, code: str) -> int:
        return subprocess.run([sys.executable, "-c", code],
                              capture_output=True, timeout=30).returncode

    def test_strict_check_fails_when_yaml_is_unavailable(self):
        """核心回归：yaml 不可用时严格档必须失败。

        旧实现（exit 在前、import 在后）恒返回 0 —— 这条断言就是它的尸检报告。
        """
        code = self.entry["_PY_STRICT_CHECK"]
        self.assertNotEqual(
            self._run(_POISON_YAML + code), 0,
            "严格档在 yaml 不可用时仍返回 0：`import yaml` 没有真正执行"
            "（历史 bug：sys.exit() 提前终止，import 成了死代码）",
        )

    def test_cheap_check_fails_when_yaml_is_unavailable(self):
        """廉价档同判据（find_spec 视角），两档不得一宽一严。"""
        code = self.entry["_PY_CHEAP_CHECK"]
        self.assertNotEqual(self._run(_POISON_YAML + code), 0)

    def test_strict_check_passes_when_yaml_is_available(self):
        """依赖可用时必须放行——否则会把好解释器一并拒掉，退化成「每次重选」。"""
        try:
            import yaml  # noqa: F401
        except ImportError:
            self.skipTest("本解释器没有 PyYAML，无法构造「可用」一侧")
        self.assertEqual(self._run(self.entry["_PY_STRICT_CHECK"]), 0)

    def test_both_checks_agree_on_version_gate(self):
        """版本判据必须同源：两档对「版本不达标」给出一致的拒绝。

        把门槛临时抬到当前解释器达不到的高度，两档都应返回非 0。这条防的是
        「一档写了版本判据、另一档漏了」——2026-09-16 踩过同形态的坑
        （当时 strict 只有 import、没有版本，3.9 被选中固化进缓存）。
        """
        too_new = (sys.version_info[0] + 1, 0)
        min_ver = "%d,%d" % too_new
        for key in ("_PY_STRICT_CHECK", "_PY_CHEAP_CHECK"):
            code = self.entry[key].replace(
                ",".join(str(p) for p in self.entry["MIN_PYTHON"]), min_ver)
            self.assertNotEqual(
                self._run(code), 0,
                f"{key} 未拦截不达标版本（版本判据可能与另一档不同源）",
            )


class TestKnownPrefixFallback(unittest.TestCase):
    """`_which_python`：PATH 优先，落空才按惯例前缀找。"""

    @classmethod
    def setUpClass(cls):
        cls.entry = _load_entry_module()

    def setUp(self):
        self._orig_which = self.entry["shutil"].which
        self._orig_prefixes = self.entry["_KNOWN_PY_PREFIXES"]
        self.tmp = tempfile.mkdtemp(prefix="argo-pyprobe-")

    def tearDown(self):
        self.entry["shutil"].which = self._orig_which
        self.entry["_KNOWN_PY_PREFIXES"] = self._orig_prefixes
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _plant(self, name: str) -> str:
        path = os.path.join(self.tmp, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("#!/bin/sh\nexit 0\n")
        os.chmod(path, 0o755)
        return path

    def test_path_wins_over_known_prefixes(self):
        """PATH 上能解析到就是用户的显式选择，不得被惯例前缀盖掉。"""
        self._plant("python9.9")
        self.entry["_KNOWN_PY_PREFIXES"] = (self.tmp,)
        self.entry["shutil"].which = lambda name: "/from/path/" + name
        self.assertEqual(self.entry["_which_python"]("python9.9"),
                         "/from/path/python9.9")

    def test_falls_back_to_known_prefix_when_which_misses(self):
        """which 落空 → 惯例前缀兜底。这正是本机 /opt/homebrew/bin 的场景。"""
        planted = self._plant("python9.9")
        self.entry["_KNOWN_PY_PREFIXES"] = (self.tmp,)
        self.entry["shutil"].which = lambda name: None
        self.assertEqual(self.entry["_which_python"]("python9.9"), planted)

    def test_returns_empty_when_nowhere(self):
        self.entry["_KNOWN_PY_PREFIXES"] = (self.tmp,)
        self.entry["shutil"].which = lambda name: None
        self.assertEqual(self.entry["_which_python"]("python9.9"), "")


class TestVenvInterpreter(unittest.TestCase):
    """`_venv_python`：安装器建的 .venv 解释器发现（PEP 668 场景的唯一落点）。

    背景：PEP 668 环境（Homebrew、Debian 12+）下 pip 的 --user 与全局安装
    都会被拒，旧安装脚本三段回落全败 → 机器上没有任何带 PyYAML 的解释器。
    install.sh 自 2026-10-27 起在 $INSTALL_DIR/.venv 装依赖，入口候选链
    靠本函数发现它。这里钉住两条契约：不存在时返回空串（不白付探测子进程）、
    存在时返回绝对路径。
    """

    @classmethod
    def setUpClass(cls):
        cls.entry = _load_entry_module()

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="argo-venv-")
        # 造一个假的检出目录：<tmp>/root/bin/argo（内容无关，只借 __file__
        # 推导 ARGO_HOME），exec 一份源文件拿到该检出下的命名空间。
        self.root = os.path.join(self.tmp, "root")
        os.makedirs(os.path.join(self.root, "bin"))
        fake_bin = os.path.join(self.root, "bin", "argo")
        with open(fake_bin, "w", encoding="utf-8") as fh:
            fh.write("# placeholder\n")
        source = ARGO_BIN.read_text(encoding="utf-8")
        self.ns = {"__file__": fake_bin, "__name__": "argo_entry_venv_under_test"}
        exec(compile(source, fake_bin, "exec"), self.ns)  # noqa: S102 — 本地可信源
        self.home = self.ns["ARGO_HOME"]

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_empty_when_venv_absent(self):
        """没有 .venv 时返回空串：候选链原样跳过，不额外起探测进程。"""
        self.assertEqual(self.ns["_venv_python"](), "")

    def test_returns_venv_absolute_path_when_present(self):
        """venv 在时返回其解释器绝对路径（_pick_python 只认单个绝对路径）。"""
        sub = ("Scripts", "python.exe") if os.name == "nt" else ("bin", "python")
        venv_dir = os.path.join(self.home, ".venv", *sub[:-1])
        os.makedirs(venv_dir)
        venv_py = os.path.join(venv_dir, sub[-1])
        with open(venv_py, "w", encoding="utf-8") as fh:
            fh.write("#!/bin/sh\nexit 0\n")
        os.chmod(venv_py, 0o755)
        self.assertEqual(self.ns["_venv_python"](), venv_py)
        self.assertTrue(os.path.isabs(self.ns["_venv_python"]()))

    def test_pick_python_falls_back_to_venv_when_others_fail(self):
        """所有系统解释器都没有 PyYAML 时，venv 必须能接管。

        这就是 PEP 668 机器的真实处境：安装器的三段 pip 回落全败，机器上
        只有 .venv 里那份依赖是齐的。把 _probe_python 换成「只认 venv」，
        _pick_python 的选择结果必须落到 venv 解释器上。
        """
        sub = ("Scripts", "python.exe") if os.name == "nt" else ("bin", "python")
        venv_dir = os.path.join(self.home, ".venv", *sub[:-1])
        os.makedirs(venv_dir)
        venv_py = os.path.join(venv_dir, sub[-1])
        with open(venv_py, "w", encoding="utf-8") as fh:
            fh.write("#!/bin/sh\nexit 0\n")
        os.chmod(venv_py, 0o755)

        ns = self.ns
        ns["_cached_python"] = lambda: ""
        ns["_remember_python"] = lambda p: None
        ns["_probe_python"] = lambda py, strict: (
            os.path.realpath(py) == os.path.realpath(venv_py))
        old_env = os.environ.pop("ARGO_PYTHON", None)
        try:
            picked = ns["_pick_python"]()
        finally:
            if old_env is not None:
                os.environ["ARGO_PYTHON"] = old_env
        self.assertEqual(os.path.realpath(picked), os.path.realpath(venv_py))


if __name__ == "__main__":
    unittest.main()
