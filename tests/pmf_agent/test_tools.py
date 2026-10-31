import datetime as dt

import pytest

from pmf_agent.tools import (
    ALL_TOOL_NAMES,
    check_platform_performance,
    compare_platform_windows,
    list_platforms,
    propose_campaign_change,
)


def test_performance_returns_totals_for_known_platform_and_window():
    result = check_platform_performance.invoke(
        {"platform": "google_ads", "window": "last_week"}
    )
    assert result["platform"] == "google_ads"
    assert result["window"] == "last_week"
    assert set(result["totals"]) == {"spend", "conversions", "cpa"}
    assert result["data_complete_through"]


def test_performance_unknown_platform_is_readable_error():
    result = check_platform_performance.invoke({"platform": "tiktok", "window": "last_week"})
    assert "error" in result
    assert "tiktok" in result["error"].lower()
    assert set(result["known_platforms"]) == {"google_ads", "meta_ads", "reddit_ads"}


def test_performance_unknown_window_is_readable_error():
    result = check_platform_performance.invoke({"platform": "google_ads", "window": "yesterdayish"})
    assert "error" in result
    assert "last_week" in result["error"]


def test_compare_returns_both_windows_and_direction():
    result = compare_platform_windows.invoke(
        {"platform": "google_ads", "metric": "spend", "window_a": "last_week", "window_b": "prior_week"}
    )
    assert result["window_a_total"] is not None and result["window_b_total"] is not None
    assert result["direction"] in ("up", "down", "flat")
    # google is a built-in mover: last week must be up
    assert result["direction"] == "up"


def test_compare_bad_metric_is_readable_error():
    result = compare_platform_windows.invoke(
        {"platform": "meta_ads", "metric": "roi", "window_a": "last_week", "window_b": "prior_week"}
    )
    assert "error" in result


def test_list_platforms_discovers():
    result = list_platforms.invoke({})
    assert len(result["platforms"]) == 3
    assert "anchor" in result


def test_propose_creates_pending_proposal_only():
    result = propose_campaign_change.invoke(
        {
            "platform": "google_ads",
            "change_type": "add_keywords",
            "details": "add: paid media analytics (phrase), ppc attribution (phrase), gtm tracking (exact)",
            "rationale": "top converting campaign, expanding coverage",
        }
    )
    assert result["status"] == "pending"
    assert result["proposal_id"]
    assert "apply" not in ALL_TOOL_NAMES  # the write gate is structural
