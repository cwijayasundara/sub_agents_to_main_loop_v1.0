import pytest


def test_catalog_has_exactly_50_unique_tools():
    from pmf_agent.catalog50 import build_catalog_50
    from pmf_agent.tools import ALL_TOOL_NAMES

    tools = build_catalog_50()
    names = [t.name for t in tools]
    assert len(tools) == 50
    assert len(set(names)) == 50
    assert set(ALL_TOOL_NAMES) <= set(names)  # core 4 present, unchanged


def test_distractor_tools_are_invocable():
    from pmf_agent.catalog50 import build_catalog_50

    tools = {t.name: t for t in build_catalog_50()}
    result = tools["pause_campaign"].invoke({"platform": "google_ads", "campaign_name": "Brand-Q3"})
    assert isinstance(result, dict)
    assert "error" not in result or result.get("fixture_stub")


def test_spend_daily_is_fixture_backed():
    from pmf_agent.catalog50 import build_catalog_50

    tools = {t.name: t for t in build_catalog_50()}
    result = tools["get_spend_daily"].invoke({"platform": "google_ads", "window": "last_week"})
    assert isinstance(result, dict)
    assert result["platform"] == "google_ads"
    assert len(result["daily"]) == 7  # real fixture rows, not a stub
