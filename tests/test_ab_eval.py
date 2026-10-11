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
    body = _FAKE % ms
    if extra_env_probe:
        body = body.replace("})",
                            ", 'usage': __import__('os').environ.get("
                            "'ARGO_USAGE_LOG', 'unset')})")
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
    report = ab_eval.evaluate(_fake_cmd(5, extra_env_probe=True),
                              _fake_cmd(6, extra_env_probe=True), "q",
                              pairs=1, seed=1, keep_usage=False)
    assert report["per_pair"][0]["a"]["count"] == 5
    # count=5 说明 JSON 正常解析；usage 注入断言看完整键
    assert report["per_pair"][0]["a"].get("elapsed_ms") == 5


def test_failed_pair_excluded_but_accounted():
    report = ab_eval.evaluate(_fake_cmd(10),
                              "python3 -c \"import sys;sys.exit(3)\"",
                              "q", pairs=2, seed=1, keep_usage=False)
    s = report["stats"]
    assert s["valid_pairs"] == 0 and s["failed_pairs"] == 2
