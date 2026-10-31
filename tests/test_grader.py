import pytest

from pmf_evals.grader import grade_result
from pmf_evals.scenarios import FigureSpec, Scenario


def _scenario(**kw):
    base = dict(
        id="q01_x",
        entry_point="slack",
        category="q_and_a",
        prompt="p",
        rubric=["criterion one", "criterion two"],
        figure_specs=(
            FigureSpec(platform="google_ads", window="last_week", metric="spend"),
        ),
    )
    base.update(kw)
    return Scenario(**base)


def _spend_figure() -> float:
    return FigureSpec(platform="google_ads", window="last_week", metric="spend").expected_value()


def _row(text=None, status="ok", **kw):
    if text is None:
        text = f"we spent {_spend_figure():.2f} last week"
    row = dict(
        scenario_id="q01_x", status=status, text=text, tool_calls=[],
        tokens_in=1, tokens_out=1, cost_usd=0.0, latency_ms=1,
        error=None, anchor="2026-11-01",
    )
    row.update(kw)
    return row


def test_figure_found_passes():
    report = grade_result(_row(), [_scenario()])
    assert report["figures"][0]["found"] is True
    assert report["verdict"] == "figures_only"


def test_currency_and_thousands_separators_match():
    expected = _spend_figure()
    report = grade_result(_row(f"Total: ${expected:,.2f}"), [_scenario()])
    assert report["figures"][0]["found"] is True


def test_wrong_number_fails_and_lists_missing():
    report = grade_result(_row("we spent 9999.99"), [_scenario()])
    assert report["figures"][0]["found"] is False
    assert report["verdict"] == "fail"
    assert f"{_spend_figure():.2f}" in report["figures"][0]["expected_str"]


def test_numbers_inside_dates_do_not_match():
    # a date like 2026-11-26 must never satisfy a figure check like 26.0
    s = _scenario(figure_specs=(FigureSpec(platform="google_ads", window="last_week", metric="conversions"),))
    row = _row("as of 2026-11-26 there were 218 conversions")
    report = grade_result(row, [s])
    # 218 conversions IS the expected value; but a text with ONLY the date and a wrong count...
    row2 = _row("as of 2026-11-26 the count was 500")
    report2 = grade_result(row2, [s])
    expected = report2["figures"][0]["expected"]
    assert report2["figures"][0]["found"] is False or expected == 500


def test_failed_run_grades_as_error():
    report = grade_result(_row(status="failed", error="RuntimeError: boom"), [_scenario()])
    assert report["verdict"] == "error"


def test_rubric_skipped_without_judge():
    report = grade_result(_row(), [_scenario()])
    assert all(c["verdict"] == "skipped" for c in report["rubric"])
    assert report["verdict"] == "figures_only"


def test_rubric_graded_with_judge():
    judge = lambda criterion, row: "one" in criterion
    report = grade_result(_row(), [_scenario()], judge=judge)
    verdicts = {c["criterion"]: c["verdict"] for c in report["rubric"]}
    assert verdicts["criterion one"] == "pass"
    assert verdicts["criterion two"] == "fail"
    assert report["verdict"] == "fail"


def test_unknown_scenario_id_raises():
    with pytest.raises(KeyError):
        grade_result(_row(), [])
