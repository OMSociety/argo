#!/usr/bin/env python3
"""test_tail_completion.py — 早停后台补全的契约（2026-10-25）。

  1. 宽限内完成的弃置引擎：学习器记真实成绩（含场景标签），交付合并写
     L2 缓存（URL 去重、追加在既有结果之后）；
  2. 宽限耗尽：标 expired，不记分不写缓存；
  3. ARGO_TAIL_COMPLETE_S=0：整个机制禁用，hand_off 直接返回；
  4. skip_cache：只记学习器，不碰缓存；
  5. 主响应不变量：engine_dispatch 早停路径照记 cancelled outcome
     （stranded 只是额外携带 holder，不改变既有记账）。
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

SCRIPT_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import tail_completion


@pytest.fixture(autouse=True)
def _reset_module_state():
    """每用例复位模块级队列/线程/注册标记（进程级状态，与 conftest 的
    _isolate_measure_clock 同一理由）。"""
    tail_completion._JOBS.clear()
    tail_completion._WORKER = None
    tail_completion._ATEXIT_REGISTERED = False
    for k in list(tail_completion._STATS):
        tail_completion._STATS[k] = 0
    yield
    tail_completion._JOBS.clear()
    tail_completion._WORKER = None
    tail_completion._ATEXIT_REGISTERED = False


def _holder_with(results, t0_offset=0.0):
    """伪造已完成的 holder（engine_dispatch._daemon_start 的产出形态）。"""
    return {"t0": time.time() - t0_offset, "r": ("eng", results, {}, 0)}


class _FakeLearner:
    def __init__(self):
        self.calls = []

    def record(self, eng, **kw):
        self.calls.append((eng, kw))


class _FakeCache:
    """SearchCache 的最小替身：get/set 形态与 finalize 用法一致。"""

    def __init__(self, payload):
        self.payload = payload
        self.set_calls = []

    def get(self, query, engine, max_results, **kw):
        return self.payload

    def set(self, query, engine, max_results, results, **kw):
        self.set_calls.append((query, engine, results))


def _job_kwargs(cache, query="新结果 旧结果"):
    return dict(query=query, cache_engine_key="auto", max_results=8,
                domain="general_search", mode="auto", depth="fast",
                decision={"domain": "general_search",
                          "features": {"primary_lang": "zh"}},
                cache_instance=cache)


def test_salvaged_records_and_merges(monkeypatch, tmp_path):
    """宽限内完成：学习器记真实成绩（含场景标签），缓存合并去重追加。"""
    monkeypatch.setenv("ARGO_TAIL_COMPLETE_S", "2")
    monkeypatch.setenv("ARGO_STATE_DIR", str(tmp_path))
    holder = _holder_with([
        {"title": "新结果", "url": "https://new.example/1", "snippet": "s"},
        {"title": "重复", "url": "https://old.example/1", "snippet": "s"},
    ])
    fake_learner = _FakeLearner()
    fake_cache = _FakeCache({
        "results": [{"title": "旧结果", "url": "https://old.example/1",
                     "score": 0.9}],
        "engines_used": ["octen"],
    })
    monkeypatch.setattr("adaptive.get_learner", lambda: fake_learner)

    tail_completion.hand_off([("anysearch", holder, time.time)],
                             **_job_kwargs(fake_cache))
    tail_completion.wait_for_completion(timeout_s=3)

    assert tail_completion.stats()["salvaged"] == 1
    # 学习器：真实成绩（success、quality、场景标签）
    assert len(fake_learner.calls) == 1
    eng, kw = fake_learner.calls[0]
    assert eng == "anysearch" and kw["success"] is True
    assert kw["quality"] is not None
    assert kw["domain"] == "general_search" and kw["lang"] == "zh"
    # 缓存：URL 去重后只追加新条目，engines_used 增补
    assert len(fake_cache.set_calls) == 1
    payload = fake_cache.set_calls[0][2]
    urls = [r["url"] for r in payload["results"]]
    assert urls == ["https://old.example/1", "https://new.example/1"]
    assert "anysearch" in payload["engines_used"]
    assert payload["results"][1]["score"] > 0  # score 缺省由词面相关度补


def test_expired_when_grace_runs_out(monkeypatch, tmp_path):
    """宽限耗尽：expired，不记分不写缓存。"""
    monkeypatch.setenv("ARGO_TAIL_COMPLETE_S", "0.15")
    monkeypatch.setenv("ARGO_STATE_DIR", str(tmp_path))
    never_done = {"t0": time.time()}  # r 永不出现
    fake_learner = _FakeLearner()
    fake_cache = _FakeCache({"results": [], "engines_used": []})
    monkeypatch.setattr("adaptive.get_learner", lambda: fake_learner)

    tail_completion.hand_off([("slow", never_done, time.time)],
                             **_job_kwargs(fake_cache))
    tail_completion.wait_for_completion(timeout_s=3)

    st = tail_completion.stats()
    assert st["expired"] == 1 and st["salvaged"] == 0
    assert fake_learner.calls == [] and fake_cache.set_calls == []


def test_grace_zero_disables(monkeypatch):
    """ARGO_TAIL_COMPLETE_S=0：hand_off 直接返回，不起线程不注册 atexit。"""
    monkeypatch.setenv("ARGO_TAIL_COMPLETE_S", "0")
    tail_completion.hand_off([("e", _holder_with([]), time.time)],
                             **_job_kwargs(_FakeCache(None)))
    assert tail_completion._JOBS == []
    assert tail_completion._WORKER is None
    assert tail_completion._ATEXIT_REGISTERED is False


def test_no_cache_instance_records_only(monkeypatch, tmp_path):
    """cache_instance 缺位：学习器照记，缓存不碰（skip_cache 语义）。"""
    monkeypatch.setenv("ARGO_TAIL_COMPLETE_S", "2")
    monkeypatch.setenv("ARGO_STATE_DIR", str(tmp_path))
    fake_learner = _FakeLearner()
    monkeypatch.setattr("adaptive.get_learner", lambda: fake_learner)

    tail_completion.hand_off(
        [("anysearch", _holder_with([{"url": "https://x/1"}]), time.time)],
        **{**_job_kwargs(None)})
    tail_completion.wait_for_completion(timeout_s=3)

    assert len(fake_learner.calls) == 1


def test_empty_goods_recorded_as_empty(monkeypatch, tmp_path):
    """引擎正常返回但无结果：success=False、empty=True（不毒化成功率）。"""
    monkeypatch.setenv("ARGO_TAIL_COMPLETE_S", "2")
    monkeypatch.setenv("ARGO_STATE_DIR", str(tmp_path))
    fake_learner = _FakeLearner()
    fake_cache = _FakeCache({"results": [], "engines_used": []})
    monkeypatch.setattr("adaptive.get_learner", lambda: fake_learner)

    tail_completion.hand_off([("e", _holder_with([]), time.time)],
                             **_job_kwargs(fake_cache))
    tail_completion.wait_for_completion(timeout_s=3)

    eng, kw = fake_learner.calls[0]
    assert kw["success"] is False and kw["empty"] is True
    assert fake_cache.set_calls == []  # 无新条目可合并，不空写


def test_worker_is_daemon_and_single_registration(monkeypatch, tmp_path):
    """收割线程是 daemon（不阻塞进程退出）；worker 与 atexit 都只注册一次。"""
    monkeypatch.setenv("ARGO_TAIL_COMPLETE_S", "1")
    monkeypatch.setenv("ARGO_STATE_DIR", str(tmp_path))
    monkeypatch.setattr("adaptive.get_learner", lambda: _FakeLearner())

    tail_completion.hand_off([("e1", _holder_with([]), time.time)],
                             **_job_kwargs(None))
    first_thread = tail_completion._WORKER
    assert first_thread.daemon is True
    assert tail_completion._ATEXIT_REGISTERED is True
    tail_completion.hand_off([("e2", _holder_with([]), time.time)],
                             **_job_kwargs(None))
    assert tail_completion._WORKER is first_thread  # 单 worker 复用
    tail_completion.wait_for_completion(timeout_s=3)


class _AllowAllBreaker:
    def allow(self, *_a, **_k):
        return True, ""

    def get_negative(self, *_a, **_k):
        return None

    def status(self, *_a, **_k):
        return {"state": "closed"}

    def record_success(self, *_a, **_k):
        pass

    def record_failure(self, *_a, **_k):
        pass

    def record_note(self, *_a, **_k):
        pass

    def set_negative(self, *_a, **_k):
        pass

    def clear_negative(self, *_a, **_k):
        pass


def test_execute_search_hands_off_stranded(tmp_path, monkeypatch):
    """集成：快源够数早停后，慢源进 stranded 交给收割，主响应不变。

    主响应不变量：early_stopped=True、慢源 outcome 记 cancelled（空列表，
    不进 errors[]）；新增量：finalize 把携带慢源 holder 的 stranded 交给
    tail_completion.hand_off。
    """
    from contextlib import ExitStack
    from unittest.mock import MagicMock, patch

    import search
    from cache import SearchCache

    monkeypatch.setenv("ARGO_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("ARGO_TAIL_COMPLETE_S", "6")
    hands = []
    monkeypatch.setattr(tail_completion, "hand_off",
                        lambda stranded, **kw: hands.append((list(stranded), kw)))

    def fake(_q, eng, **_kw):
        if eng == "fast_primary":
            # 超过宽限窗（search._PRIMARY_GRACE_S=0.8s）才合格：backup 已按
            # stagger 起跑，早停发生在「backup 在跑」时——stranded 要收的场景
            time.sleep(1.0)
            return [{"title": f"f{i}", "url": f"https://fast/{i}",
                     "snippet": "s"} for i in range(3)]
        if eng == "slow_backup":
            time.sleep(2.5)
            return [{"title": f"s{i}", "url": f"https://slow/{i}",
                     "snippet": "s"} for i in range(3)]
        return []

    decision = {"engines_combo": ["fast_primary", "slow_backup"],
                "engines": ["fast_primary", "slow_backup"],
                "parallel": True, "domain": "macro_data",
                "engine": "fast_primary", "early_stop_min_results": 1,
                "no_early_stop": False}
    with ExitStack() as stack:
        for p in (
            patch("search.engine_search", side_effect=fake),
            patch("circuit_breaker.get_breaker",
                  return_value=_AllowAllBreaker()),
            patch("quota.get_quota_manager", return_value=MagicMock()),
        ):
            stack.enter_context(p)
        out = search.execute_search(
            "中国 通胀率", decision, max_results=5, timeout=10,
            depth="fast", cache=SearchCache(db_path=":memory:"),
            skip_cache=True, mode="fast")

    assert out.get("early_stopped") is True
    outcomes = {o.get("engine"): o.get("status")
                for o in out.get("engine_outcomes", [])}
    assert outcomes.get("slow_backup") == "cancelled"
    assert hands, "finalize 应把 stranded 交给 tail_completion.hand_off"
    stranded, kw = hands[0]
    assert [e for e, _h, _n in stranded] == ["slow_backup"]
    holder = stranded[0][1]
    assert "t0" in holder  # holder 形态正确（收割线程按 r 键等完成）
