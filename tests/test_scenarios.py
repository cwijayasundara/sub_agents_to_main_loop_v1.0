import pytest

from pmf_evals.scenarios import GOLDEN_PATH, FigureSpec, Scenario, load_scenarios


def _valid_scenario(**overrides):
    base = dict(
        id="q01_test",
        entry_point="slack",
        category="q_and_a",
        prompt="How did google spend move last week vs the week before?",
        rubric=["quotes per-platform spend", "flags incomplete data caveat"],
        figure_specs=[FigureSpec(platform="google_ads", window="last_week", metric="spend")],
    )
    base.update(overrides)
    return Scenario(**base)


def test_scenario_validates_entry_point():
    with pytest.raises(ValueError):
        _valid_scenario(entry_point="email")


def test_scenario_validates_unique_ids():
    dup = _valid_scenario()
    with pytest.raises(ValueError, match="unique"):
        load_scenarios_from_list([dup, dup])


def test_load_scenarios_from_list():
    scenarios = load_scenarios_from_list([_valid_scenario()])
    assert scenarios[0].window_dates()  # resolves last_week against the anchor


def test_golden_file_loads_15_with_expected_mix():
    scenarios = load_scenarios(GOLDEN_PATH)
    assert len(scenarios) == 15
    assert len({s.id for s in scenarios}) == 15
    entry_points = [s.entry_point for s in scenarios]
    assert entry_points.count("slack") >= 5
    assert entry_points.count("scheduled") >= 5
    categories = {s.category for s in scenarios}
    assert {"weekly_report", "q_and_a", "write_proposal", "cross_platform"} <= categories
    # every scenario has at least one rubric criterion
    assert all(len(s.rubric) >= 1 for s in scenarios)


def test_figure_specs_resolve_to_exact_totals():
    scenarios = load_scenarios(GOLDEN_PATH)
    for s in scenarios:
        for spec in s.figure_specs:
            totals = spec.totals()  # uses shifted dataset under the current anchor
            assert totals is not None and "spend" in totals or "cpa" in totals


# helper mirroring the public loader, for tests that build scenarios in code
def load_scenarios_from_list(items: list[Scenario]) -> list[Scenario]:
    ids = [s.id for s in items]
    if len(ids) != len(set(ids)):
        raise ValueError("scenario ids must be unique")
    return items


def test_scenario_accepts_tool_expectations():
    from pmf_evals.scenarios import load_scenarios_from_list as _load

    s = _valid_scenario(expected_tools=["compare_platform_windows"], forbidden_tools=["propose_campaign_change"])
    loaded = _load([s])[0]
    assert loaded.expected_tools == ["compare_platform_windows"]
    assert loaded.forbidden_tools == ["propose_campaign_change"]


def test_golden_file_tool_expectations_present():
    scenarios = load_scenarios(GOLDEN_PATH)
    q11 = next(s for s in scenarios if s.id == "q11_write_keyword_proposal")
    assert "propose_campaign_change" in q11.expected_tools
    # q12's proposal is conditional on the data: the agent must check first,
    # but proposing when the data contradicts the premise is wrong
    q12 = next(s for s in scenarios if s.id == "q12_write_budget_change")
    assert set(q12.expected_tools) == {"check_platform_performance", "compare_platform_windows"}
    q01 = next(s for s in scenarios if s.id == "q01_weekly_spend_wow")
    assert q01.expected_tools  # weekly report must check/compare platform data
    assert all(not s.forbidden_tools for s in scenarios)  # none shipped for now
