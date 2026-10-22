#!/usr/bin/env python3
"""CI 工作流的形状门禁：锁住「为什么这样分作业」，而不是锁住每一行。

## 为什么需要

工作流是唯一一处「改错了没人报错」的配置：YAML 语法对、键名写错、作业被
误删、`paths-ignore` 把测试目录也忽略掉——都不影响本地任何测试，只在你推
上去之后才发现（或者更糟：一直静默不跑，你以为它在跑）。2026-10-22 第一次
上 CI 时，自己就在 smoke 步骤里写过一条根本不存在的子命令；这类错误本地跑
不出来，只能靠这道门。

## 只锁四件会被无声破坏的事

1. 文件能解析（YAML 语法错误 = 整条流水线消失，GitHub 不会红给你看）；
2. 作业还在（gates/unit/extras/smoke；nightly 三件 + notify）；
3. PR 不跑 live、不跑 nightly、`pull_request_target` 不出现（fork 提权的经典口子）；
4. 分片参数与耗时表还在（`--splits 4 --group`、`--durations-path tests/.test_durations`），
   否则「分片」退化成「四份全量」，分钟数悄悄乘四。
"""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"


def _load(name: str) -> dict:
    path = WORKFLOWS / name
    assert path.exists(), f"工作流不见了：{path}"
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(doc, dict), f"{name} 不是映射"
    return doc


def _triggers(doc: dict) -> dict:
    # PyYAML 按 YAML 1.1 把裸 on 解析成布尔 True；GitHub 按 1.2 当字符串。
    trig = doc.get("on", doc.get(True))
    assert trig, "缺 on: 触发条件"
    return trig


def _steps_text(job: dict) -> str:
    return "\n".join(str(step.get("run", "")) + str(step.get("uses", ""))
                     for step in job.get("steps") or [])


def test_both_workflows_parse():
    for name in ("ci.yml", "nightly.yml"):
        assert _load(name)["jobs"], f"{name} 没有作业"


def test_ci_has_the_four_jobs():
    jobs = _load("ci.yml")["jobs"]
    assert set(jobs) == {"gates", "unit", "extras", "smoke"}, sorted(jobs)
    # gates 必须复用本地那套，不能在 CI 里另写一套判断
    assert "scripts/pre-commit" in _steps_text(jobs["gates"])


def test_unit_is_sharded_with_durations():
    unit = _load("ci.yml")["jobs"]["unit"]
    assert (unit.get("strategy") or {}).get("matrix", {}).get("group") == [1, 2, 3, 4]
    text = _steps_text(unit)
    assert "--splits 4" in text and "--group" in text
    assert "--durations-path tests/.test_durations" in text
    # 耗时表必须真的在仓库里，否则切片会退化成按名字糊切
    assert (ROOT / "tests" / ".test_durations").exists()


def test_pr_does_not_run_live_or_nightly():
    ci = _load("ci.yml")
    trig = _triggers(ci)
    assert "pull_request" in trig
    assert "pull_request_target" not in trig, "pull_request_target 会拿到写权限的 token"
    text = "\n".join(_steps_text(j) for j in ci["jobs"].values())
    assert "replay_eval.py --record" not in text, "录制会联网，不能进 PR"
    assert "-m live" not in text


def test_nightly_is_scheduled_and_reports():
    doc = _load("nightly.yml")
    trig = _triggers(doc)
    assert "schedule" in trig and "workflow_dispatch" in trig
    jobs = doc["jobs"]
    assert {"replay", "drift", "ledger", "notify"} <= set(jobs), sorted(jobs)
    # 漂移要看基线，基线丢了就变成「只记录不判断」
    drift = _steps_text(jobs["drift"])
    assert "tests/golden/drift_baseline_report.json" in drift
    assert "scripts/ci_drift_gate.py" in drift
    assert (ROOT / "tests" / "golden" / "drift_baseline_report.json").exists()
    assert jobs["notify"].get("if") == "failure()"


def test_requirements_files_exist_and_are_wired():
    dev = (ROOT / "requirements-dev.txt").read_text(encoding="utf-8")
    assert "pytest-split" in dev, "分片插件不能只写在 workflow 里"
    for dep in ("curl_cffi", "beautifulsoup4", "lxml"):
        assert dep in dev, f"测试真正要用的 {dep} 不在 requirements-dev"
    opt = (ROOT / "requirements-optional.txt").read_text(encoding="utf-8")
    assert "curl_cffi" in opt and "rapidocr" in opt
