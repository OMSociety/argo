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
