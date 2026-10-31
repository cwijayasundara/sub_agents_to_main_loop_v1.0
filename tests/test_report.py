import pytest

from pmf_evals.report import compare


def _row(sid, verdict, latency=100, cost=0.01):
    return {
        "scenario_id": sid,
        "verdict": verdict,
        "latency_ms": latency,
        "cost_usd": cost,
    }


def test_compare_lists_flipped_tasks():
    a = [_row("q01", "pass"), _row("q02", "fail"), _row("q03", "pass")]
    b = [_row("q01", "fail"), _row("q02", "pass"), _row("q03", "pass")]
    report = compare(a, b)
    assert report["flipped"] == {
        "q01": "pass->fail",
        "q02": "fail->pass",
    }
    assert report["verdicts"]["a"] == {"q01": "pass", "q02": "fail", "q03": "pass"}
    assert report["verdicts"]["b"]["q03"] == "pass"


def test_compare_aggregates_latency_and_cost():
    a = [_row("q01", "pass", latency=100, cost=0.01), _row("q02", "pass", latency=300, cost=0.03)]
    b = [_row("q01", "pass", latency=50, cost=0.005), _row("q02", "pass", latency=50, cost=0.005)]
    report = compare(a, b)
    assert report["summary"]["a"]["mean_latency_ms"] == 200
    assert report["summary"]["b"]["mean_cost_usd"] == pytest.approx(0.005)
    assert report["summary"]["b"]["pass_rate"] == pytest.approx(1.0)


def test_compare_rejects_mismatched_scenarios():
    a = [_row("q01", "pass")]
    b = [_row("q01", "pass"), _row("q09", "pass")]
    with pytest.raises(ValueError, match="mismatch"):
        compare(a, b)


def test_error_verdicts_count_as_fail():
    a = [_row("q01", "error")]
    b = [_row("q01", "pass")]
    report = compare(a, b)
    assert report["flipped"] == {"q01": "error->pass"}
    assert report["summary"]["a"]["pass_rate"] == 0.0
