"""ab_eval 单元测试：随机化顺序、统计量、usage-log 隔离注入。"""
import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import ab_eval  # noqa: E402

_FAKE = ("python3 -c \"import json;print(json.dumps({"
         "'count': 5, 'timing': {'elapsed_ms': %d}}))\"")


def _fake_cmd(ms: int, extra_env_probe: bool = False) -> str:
    """extra_env_probe=True 时把 ARGO_USAGE_LOG 的可见值塞进 count。

    为什么塞 count 而不是自加一个键：_run_once 只透传 elapsed_ms/count/wall_ms
    到结果里，自加键会被丢掉——旧用例就是因此没牙（断言了 elapsed_ms，从未
    看到注入值）。count 是既有透传通道，用它才能形成真断言。
    """
    body = _FAKE % ms
    if extra_env_probe:
        body = body.replace(
            "'count': 5,",
            "'count': __import__('os').environ.get('ARGO_USAGE_LOG', 'unset'),")
    return body


def test_stats_with_deterministic_fake():
    report = ab_eval.evaluate(_fake_cmd(100), _fake_cmd(300), "测试查询",
                              pairs=4, seed=1, keep_usage=False)
    s = report["stats"]
    assert s["valid_pairs"] == 4 and s["failed_pairs"] == 0
    assert s["a_wins"] == 4 and s["b_wins"] == 0
    assert s["median_diff_ms"] == -200  # A 快 200ms
    assert s["count_median_a"] == 5 and s["count_median_b"] == 5
    assert 0.0 <= s["sign_test_p"] <= 1.0


def test_pair_order_randomized_and_recorded():
    report = ab_eval.evaluate(_fake_cmd(1), _fake_cmd(1), "q", pairs=8,
                              seed=42, keep_usage=False)
    flags = {r["a_first"] for r in report["per_pair"]}
    assert flags == {True, False}  # 两种顺序都出现（seed=42 下 8 对必混合）


def test_usage_log_suppressed_by_default():
    """keep_usage=False 时子进程必须看到 ARGO_USAGE_LOG=0（真断言到注入值）。"""
    report = ab_eval.evaluate(_fake_cmd(5, extra_env_probe=True),
                              _fake_cmd(6, extra_env_probe=True), "q",
                              pairs=1, seed=1, keep_usage=False)
    assert report["per_pair"][0]["a"]["count"] == "0", \
        "ab_eval 必须给子进程注入 ARGO_USAGE_LOG=0（防基准污染生产日志）"
    assert report["per_pair"][0]["a"].get("elapsed_ms") == 5


def test_usage_log_kept_when_requested(monkeypatch):
    """keep_usage=True 时不注入 =0（对比档要真实记日志）。

    先清掉套件级 ARGO_USAGE_LOG=0（conftest 全局设的），否则子进程无论如何
    都看到 "0"，测不出「不注入」这一行为。
    """
    monkeypatch.delenv("ARGO_USAGE_LOG", raising=False)
    report = ab_eval.evaluate(_fake_cmd(5, extra_env_probe=True),
                              _fake_cmd(6, extra_env_probe=True), "q",
                              pairs=1, seed=1, keep_usage=True)
    assert report["per_pair"][0]["a"]["count"] == "unset"


def test_failed_pair_excluded_but_accounted():
    report = ab_eval.evaluate(_fake_cmd(10),
                              "python3 -c \"import sys;sys.exit(3)\"",
                              "q", pairs=2, seed=1, keep_usage=False)
    s = report["stats"]
    assert s["valid_pairs"] == 0 and s["failed_pairs"] == 2


def test_spaced_query_reaches_cmd_as_single_arg():
    # 回归（2026-10-11）：{query} 替换须整体加引号——含空格查询此前被
    # shell 拆成多个 argv，argparse rc=2，全部 pair 失败。
    probe = ("python3 -c \"import json,sys;print(json.dumps("
             "{'count': len(sys.argv)-1, 'argv': sys.argv[1:], "
             "'timing': {'elapsed_ms': 1}}))\" {query}")
    report = ab_eval.evaluate(probe, probe, "webassembly 性能对比",
                              pairs=1, seed=1, keep_usage=False)
    pair = report["per_pair"][0]
    assert pair["a"]["ok"] and pair["b"]["ok"], (pair["a"], pair["b"])
    assert pair["a"]["count"] == 1  # 完整查询串是唯一 argv，未被拆散


# ── 尾判据（B-4）：p90 / max，而不是中位 ────────────────────────────────────
#
# 为什么必须补这一档：中位由最快的那个引擎决定，把并发从 3 提到 6 只可能动
# 尾部。中位纹丝不动而 p90 翻倍的改动，只看 median_diff / 符号检验会被放行。

def test_percentile_nearest_rank_takes_observed_sample():
    assert ab_eval.percentile_nearest_rank(list(range(1, 11)), 0.9) == 9
    assert ab_eval.percentile_nearest_rank(list(range(1, 11)), 0.5) == 5
    assert ab_eval.percentile_nearest_rank([42.0], 0.9) == 42.0
    assert ab_eval.percentile_nearest_rank([], 0.9) is None
    # 最近秩只取**真实观测到的样本**，不做插值：n=10 时 statistics.quantiles
    # 的 p90 会插出 370 这种从未出现过的值，而 400 是 max 不是 p90。
    assert ab_eval.percentile_nearest_rank([100] * 9 + [400], 0.9) == 100


def test_tail_verdict_passes_small_noise():
    a = [100] * 10
    b = [100] * 9 + [120]        # 唯一一个极值 +20%，p90 未动
    v = ab_eval.tail_verdict(a, b)
    assert v["passed"] is True, v["reason"]
    assert v["p90_a_ms"] == 100 and v["p90_b_ms"] == 100
    assert v["max_ratio"] == 1.2


def test_tail_verdict_flags_p90_regression_only():
    a = [100] * 10
    b = [100] * 8 + [115, 115]   # p90 +15%（超 10% 容忍），max 仍在 25% 内
    v = ab_eval.tail_verdict(a, b)
    assert v["passed"] is False
    assert "p90" in v["reason"] and "max" not in v["reason"]
    assert v["p90_ratio"] == 1.15 and v["max_ratio"] == 1.15


def test_tail_verdict_flags_max_regression():
    a = [100] * 10
    b = [100] * 9 + [900]        # 尾点：p90=100 未动，max ×9
    v = ab_eval.tail_verdict(a, b)
    assert v["passed"] is False
    assert "max" in v["reason"]
    assert v["p90_ratio"] == 1.0


def test_tail_verdict_needs_samples():
    v = ab_eval.tail_verdict([], [])
    assert v["passed"] is False
    assert "样本不足" in v["reason"]


def test_evaluate_stats_expose_tail_fields():
    report = ab_eval.evaluate(_fake_cmd(100), _fake_cmd(300), "q",
                              pairs=3, seed=1, keep_usage=False)
    s = report["stats"]
    assert s["p90_a_ms"] == 100 and s["p90_b_ms"] == 300
    assert s["max_a_ms"] == 100 and s["max_b_ms"] == 300
    assert s["p90_ratio"] == 3.0
    assert s["tail_verdict"]["passed"] is False  # B 慢 3 倍，尾判据必须拦住
