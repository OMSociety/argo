#!/usr/bin/env python3
"""test_dispatch_retry_policy — 重试按失败类别区分的门禁（2026-10-21）。

## 背景

`execution.retry_count=1` 一直存在，但它是**无差别重试**：配额耗尽、鉴权
失败、反爬拦截都会再发一次请求。这三类都是**源端状态**——配额重试仍是
耗尽、鉴权重试仍是 401、反爬重试仍撞同一堵墙。代价是多烧一次调用，并
推迟切备选源（那一次备选本来可能已经给出答案）。

dsh-free-search 的 failure-aware fallback 是同一判断：quota/auth 冷却到
会话结束、bot-wall 短退避，只有 transient（超时/限流/网络）才重试一次。

## 锁什么

1. `classify_error_status`：错误文本 → 类别，且**重试判据与归因判据同源**
   （两处各写一套词表会让「什么算配额耗尽」有两种说法）。
2. `is_retryable_failure`：确定性失败返回 False，transient 与空结果返回 True。
3. 行为：配额引擎只被调用一次；超时机引擎被调用两次。
4. 记账：outcome 带 `attempts`，如实反映发了几次请求。
5. 门禁有牙：把 `_NON_RETRYABLE_STATUS` 改空，第 2 条必须失败。
"""
from __future__ import annotations

import sys
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import engine_dispatch  # noqa: E402
import retry_policy  # noqa: E402
import search  # noqa: E402
from engine_dispatch import (  # noqa: E402
    classify_engine_outcome,
    classify_error_status,
    is_retryable_failure,
)
from cache import SearchCache  # noqa: E402

QUERY = "retry policy probe query"


class _AllowAllBreaker:
    """关闭熔断/负缓存干扰（与 test_race_fast_budget_0906 同款）。"""

    def allow(self, eng):
        return True, "closed"

    def get_negative(self, *a, **k):
        return None

    def status(self, eng):
        return {"state": "closed"}

    def record_success(self, *a, **k):
        pass

    def record_failure(self, *a, **k):
        pass

    def record_note(self, *a, **k):
        pass

    def set_negative(self, *a, **k):
        pass

    def clear_negative(self, *a, **k):
        pass


class TestClassifyErrorStatus:
    """错误文本 → 类别：优先级顺序即语义强弱。"""

    def test_timeout_wins_over_quota(self):
        # 「quota」与「timeout」同时出现时，超时更具体：它描述的是这次
        # 调用的形态，配额是原因，而重试判据关心的是形态。
        assert classify_error_status("request timeout after quota check") == "timeout"

    def test_quota_keywords(self):
        # 词表真源是 cache_guard._QUOTA_ERROR_KEYWORDS（唯一来源），
        # 这里逐条钉住它当前收录的措辞——新增码只改那一处。
        for msg in ("quota exceeded", "insufficient balance", "10406",
                    "insufficient funds", "not enough money",
                    "余额不足", "额度不足", "配额耗尽"):
            assert classify_error_status(msg) == "quota-exhausted", msg

    def test_rate_limit(self):
        for msg in ("429 too many requests", "rate limit exceeded"):
            assert classify_error_status(msg) == "rate-limited", msg

    def test_blocked(self):
        for msg in ("Just a moment...", "cf-browser-verification",
                    "安全验证", "access denied"):
            assert classify_error_status(msg) == "blocked", msg

    def test_auth(self):
        # 401/403 与裸 "auth" 是词表收录的鉴权措辞；"invalid api key"
        # 不在表内（归 error），这里不替它加词——改词表会同时改动熔断
        # 记账，是另一个决定。
        for msg in ("401 unauthorized", "403 forbidden", "auth failed"):
            assert classify_error_status(msg) == "auth-failed", msg

    def test_unknown_falls_to_error(self):
        assert classify_error_status("something odd") == "error"
        assert classify_error_status("") == "error"
        assert classify_error_status(None) == "error"

    def test_case_insensitive(self):
        assert classify_error_status("TIMEOUT") == "timeout"
        assert classify_error_status("Quota Exceeded") == "quota-exhausted"


class TestIsRetryableFailure:
    """确定性失败不重试；transient 与空结果沿用既有重试语义。"""

    def test_deterministic_failures_not_retried(self):
        for status in ("quota-exhausted", "auth-failed", "blocked"):
            msg = {
                "quota-exhausted": "quota exceeded",
                "auth-failed": "401 unauthorized",
                "blocked": "just a moment...",
            }[status]
            res = [{"error": msg, "source": "e"}]
            assert is_retryable_failure(res) is False, status

    def test_transient_retried(self):
        for msg in ("request timeout", "429 too many requests",
                    "connection reset by peer", "something odd"):
            assert is_retryable_failure([{"error": msg}]) is True, msg

    def test_empty_result_still_retried(self):
        """空结果沿用既有「重试一次」语义——本次只收紧确定性失败。"""
        assert is_retryable_failure([]) is True
        assert is_retryable_failure(None) is True

    def test_mirrors_classify_engine_outcome(self):
        """重试判据与归因判据必须同源：同一文本给出的类别一致。

        这是本文件最重要的一条——两处各写一套词表时，测试可以各自通过，
        而线上对同一次失败会给出两个不同判断。
        """
        samples = ["quota exceeded", "401 unauthorized", "just a moment...",
                   "request timeout", "429 too many requests", "weird failure"]
        for msg in samples:
            res = [{"error": msg}]
            outcome_status = classify_engine_outcome("e", res, 1)["status"]
            assert classify_error_status(msg) == outcome_status, msg

    def test_gate_has_teeth(self):
        """把「不重试」集合清空，第 2 条必须失败——否则门禁是摆设。"""
        original = retry_policy.NON_RETRYABLE_STATUS
        try:
            retry_policy.NON_RETRYABLE_STATUS = frozenset()
            assert is_retryable_failure([{"error": "quota exceeded"}]) is True
        finally:
            retry_policy.NON_RETRYABLE_STATUS = original


class TestRetryBehaviour:
    """行为：确定性失败只发一次，transient 发两次。"""

    def _execute(self, eng: str, fake):
        calls: list[int] = []

        def _spy(query_: str, engine: str, **kwargs):
            calls.append(1)
            return fake(query_, engine)

        decision = {"engines_combo": [eng], "engines": [eng], "parallel": False,
                    "domain": "general_search", "engine": eng}
        cache = SearchCache(db_path=":memory:")
        with ExitStack() as stack:
            for p in (
                patch("search.engine_search", side_effect=_spy),
                patch("circuit_breaker.get_breaker", return_value=_AllowAllBreaker()),
                patch("quota.get_quota_manager", return_value=MagicMock()),
            ):
                stack.enter_context(p)
            out = search.execute_search(
                QUERY, decision, max_results=5, timeout=10, depth="fast",
                cache=cache, skip_cache=True, mode="auto")
        return out, len(calls)

    def _outcome(self, out: dict) -> dict:
        outcomes = out.get("engine_outcomes") or []
        assert outcomes, "应有一条 outcome"
        return outcomes[0]

    def test_quota_failure_not_retried(self):
        out, n = self._execute("quota_eng",
                               lambda *a: [{"error": "quota exceeded"}])
        assert n == 1, f"配额耗尽是确定性失败，不该重试：实际 {n} 次"
        assert self._outcome(out)["status"] == "quota-exhausted"

    def test_auth_failure_not_retried(self):
        out, n = self._execute("auth_eng",
                               lambda *a: [{"error": "401 unauthorized"}])
        assert n == 1, f"鉴权失败是确定性失败，不该重试：实际 {n} 次"

    def test_blocked_not_retried(self):
        out, n = self._execute("blocked_eng",
                               lambda *a: [{"error": "just a moment..."}])
        assert n == 1, f"反爬拦截是确定性失败，不该重试：实际 {n} 次"

    def test_timeout_retried_once(self):
        """transient 走既有重试链：2 次同深尝试 + 1 次 balanced 补跑。

        后一次是既有的「balanced 补跑」（depth != balanced 时），不是本次
        新增的机制；`attempts` 如实把它计入，因为那确实是一次网络请求。
        """
        out, n = self._execute("slow_eng",
                               lambda *a: [{"error": "request timeout"}])
        assert n == 3, f"超时应走完整重试链：实际 {n} 次"
        assert self._outcome(out)["attempts"] == 3

    def test_empty_result_still_retried_once(self):
        out, n = self._execute("empty_eng", lambda *a: [])
        assert n == 3, f"空结果沿用既有重试语义：实际 {n} 次"

    def test_first_attempt_success_sends_exactly_one(self):
        good = [{"title": "t", "snippet": "s", "url": "https://e.com/1"}]
        out, n = self._execute("ok_eng", lambda *a: good)
        assert n == 1
        assert self._outcome(out)["attempts"] == 1

    def test_attempts_recorded_on_success_too(self):
        """记账要如实：成功的调用也报 1，而不是缺字段让调用方以为没记。"""
        good = [{"title": "t", "snippet": "s", "url": "https://e.com/1"}]
        out, _ = self._execute("ok_eng2", lambda *a: good)
        assert self._outcome(out)["attempts"] == 1


if __name__ == "__main__":
    unittest.main()
