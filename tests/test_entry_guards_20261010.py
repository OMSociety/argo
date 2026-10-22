"""入口级守卫回归（2026-10-10 方案甲）。

覆盖两处「失败伪装成空结果」类的收口：
  1. --engine 无效名在入口即报错（exit 2 + did-you-mean），不再产出
     status=completed/count=0 的假空——09-20 实踩、10-10 复测仍在的那类。
  2. serp_guard 整页误杀先入账本、search 层可 drain——诚实空不再不可见
     （搜狗跳转壳 10-06、百家号 10-08 两例复发的可见性补丁）。
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))


# ── 入口引擎名校验 ───────────────────────────────────────────────────────────

def _run_cli(*args: str, tmp_path: Path) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["ARGO_STATE_DIR"] = str(tmp_path / "state")  # 测试绝不写生产状态
    return subprocess.run(
        [sys.executable, str(REPO / "bin" / "argo"), "search", *args],
        capture_output=True, text=True, env=env, timeout=120)


def test_unknown_engine_fails_fast_at_entry(tmp_path):
    r = _run_cli("test", "--engine", "nosuchengine123", "--plan-only",
                 tmp_path=tmp_path)
    assert r.returncode == 2, f"应入口即败，实际 stdout={r.stdout[:200]}"
    assert "未知引擎" in r.stderr
    assert "nosuchengine123" in r.stderr


def test_unknown_engine_did_you_mean(tmp_path):
    r = _run_cli("test", "--engine", "bing", "--plan-only", tmp_path=tmp_path)
    assert r.returncode == 2
    # bing 不存在，但建议里必须出现真名（bing_rss / local_bing 一类）
    assert "bing_rss" in r.stderr or "local_bing" in r.stderr


def test_valid_engine_and_auto_unaffected(tmp_path):
    r = _run_cli("test", "--engine", "local_search", "--plan-only",
                 "--json", tmp_path=tmp_path)
    assert r.returncode == 0
    assert '"status"' in r.stdout
    r = _run_cli("test", "--plan-only", "--json", tmp_path=tmp_path)
    assert r.returncode == 0


# ── serp_guard 误杀账本 ──────────────────────────────────────────────────────

@pytest.fixture()
def _clean_kills():
    from serp_kill_log import drain_serp_guard_kills
    drain_serp_guard_kills()  # 清掉同进程此前用例的残留
    yield
    drain_serp_guard_kills()


def test_serp_kill_recorded_and_drainable(_clean_kills, monkeypatch):
    import engines_base
    import serp_guard
    import serp_kill_log
    monkeypatch.setattr(serp_guard, "is_junk_serp", lambda q, r: True)
    out = engines_base._serp_guard_apply(
        "local_bing", "q", [{"url": "https://x/a"}, {"url": "https://x/b"}])
    assert out == []  # 诚实空语义不变
    kills = serp_kill_log.drain_serp_guard_kills()
    assert kills == [{"engine": "local_bing", "results": 2}]
    assert serp_kill_log.drain_serp_guard_kills() == []  # drain 后清空


def test_serp_guard_pass_through_untouched(_clean_kills, monkeypatch):
    import engines_base
    import serp_guard
    import serp_kill_log
    monkeypatch.setattr(serp_guard, "is_junk_serp", lambda q, r: False)
    rows = [{"url": "https://x/a"}]
    assert engines_base._serp_guard_apply("local_bing", "q", rows) is rows
    assert serp_kill_log.drain_serp_guard_kills() == []


def test_serp_guard_only_guards_own_engines(_clean_kills, monkeypatch):
    import engines_base
    import serp_guard
    monkeypatch.setattr(serp_guard, "is_junk_serp",
                        lambda q, r: pytest.fail("不该对非守卫引擎调用判垃圾"))
    rows = [{"url": "https://x/a"}]
    assert engines_base._serp_guard_apply("anysearch", "q", rows) is rows


def test_recovery_limitation_distinguishes_outcomes():
    """「触发但无策略可用」与「恢复成功」在局限声明里必须可区分。"""
    from search_attribution import zero_result_recovery_note

    def _lim(recovery, outcomes=None):
        return zero_result_recovery_note(recovery, outcomes) or ""

    assert "no usable strategy" in _lim(
        {"triggered": True, "recovered": False, "note": "无可用恢复策略"})
    # 恢复成功的那半句由 search.py 的 elif 分支产出，helper 只负责失败分支
    assert _lim({"triggered": True, "recovered": True}) == ""
    assert _lim(None) == ""
    # 2026-10-22：空结果来自「跳过/鉴权失败」时，必须点名源，而不是说 no recall
    skipped = _lim(
        {"triggered": True, "recovered": False, "note": "无可用恢复策略"},
        [{"engine": "bocha", "status": "skipped-quota-exhausted"}])
    assert "bocha" in skipped and "no-recall" in skipped
    # 源码里两个分支都要在（判据在 search_attribution，措辞在 search.py）
    src = (REPO / "scripts" / "search_attribution.py").read_text(encoding="utf-8")
    assert "recovery triggered but no usable strategy" in src
    src_search = (REPO / "scripts" / "search.py").read_text(encoding="utf-8")
    assert "recovery used; engine fallback may differ" in src_search
