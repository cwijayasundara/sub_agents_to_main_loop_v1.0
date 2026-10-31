"""Intent-grouped tools over the fixture data — the agent's whole tool surface.

Grouped by user intent, not per-API (Anthropic doctrine): one performance
tool, one comparison tool, one discovery tool, one proposal tool. The write
gate is structural: proposals can be *created* but no tool that applies them
exists in this process, so the model cannot bypass approval.
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from langchain_core.tools import tool

from pmf_evals.fixtures import PLATFORMS, anchor, load_dataset, shift_dataset, shipped_offset, window_totals

WINDOWS = {
    "last_week": lambda a: (a - dt.timedelta(days=6), a),
    "prior_week": lambda a: (a - dt.timedelta(days=13), a - dt.timedelta(days=7)),
    "last_30d": lambda a: (a - dt.timedelta(days=29), a),
}
METRICS = ("spend", "conversions", "cpa")

# proposals live in-process; a real deployment persists these behind the approval server
_PROPOSALS: list[dict] = []


def _resolve_window(name: str) -> tuple[dt.date, dt.date] | None:
    fn = WINDOWS.get(name)
    return fn(anchor()) if fn else None


def _shifted():
    return shift_dataset(load_dataset(), shipped_offset())


@tool
def list_platforms() -> dict[str, Any]:
    """Discover which ad platforms and metrics are available, and the data anchor date."""
    return {
        "platforms": list(PLATFORMS),
        "metrics": list(METRICS),
        "anchor": anchor().isoformat(),
        "windows": sorted(WINDOWS),
    }


@tool
def check_platform_performance(platform: str, window: str) -> dict[str, Any]:
    """Check one ad platform's performance (spend, conversions, CPA) over a window.

    Use for "how much did we spend / how did X do" questions about a single platform.

    Args:
        platform: one of google_ads, meta_ads, reddit_ads
        window: one of last_week, prior_week, last_30d
    """
    if platform not in PLATFORMS:
        return {
            "error": f"unknown platform {platform!r}; known platforms: {', '.join(sorted(PLATFORMS))}",
            "known_platforms": sorted(PLATFORMS),
        }
    win = _resolve_window(window)
    if win is None:
        return {
            "error": f"unknown window {window!r}; known windows: {', '.join(sorted(WINDOWS))}",
            "known_windows": sorted(WINDOWS),
        }
    totals = window_totals(_shifted(), platform, win)
    return {
        "platform": platform,
        "window": window,
        "window_start": win[0].isoformat(),
        "window_end": win[1].isoformat(),
        "totals": totals,
        "source": "ad platform (fixture)",  # source-of-truth rule: media metrics live with the ad platform
        "data_complete_through": anchor().isoformat(),
    }


@tool
def compare_platform_windows(platform: str, metric: str, window_a: str, window_b: str) -> dict[str, Any]:
    """Compare one metric for one platform across two windows (e.g. last_week vs prior_week).

    Use for trend, week-over-week, and "did it get better or worse" questions.

    Args:
        platform: one of google_ads, meta_ads, reddit_ads
        metric: one of spend, conversions, cpa
        window_a: the recent window (last_week, prior_week, last_30d)
        window_b: the baseline window
    """
    if metric not in METRICS:
        return {"error": f"unknown metric {metric!r}; known metrics: {', '.join(METRICS)}"}
    a = check_platform_performance.invoke({"platform": platform, "window": window_a})
    b = check_platform_performance.invoke({"platform": platform, "window": window_b})
    if "error" in a:
        return a
    if "error" in b:
        return b
    va, vb = a["totals"][metric], b["totals"][metric]
    if va is None or vb is None or vb == 0:
        direction = "flat"
    elif abs(va - vb) / abs(vb) < 0.005:
        direction = "flat"
    else:
        direction = "up" if va > vb else "down"
    return {
        "platform": platform,
        "metric": metric,
        "window_a": window_a,
        "window_a_total": va,
        "window_b": window_b,
        "window_b_total": vb,
        "direction": direction,
        "pct_change": round((va - vb) / vb * 100, 1) if vb else None,
    }


@tool
def propose_campaign_change(
    platform: str, change_type: str, details: str, rationale: str
) -> dict[str, Any]:
    """Propose a campaign change (keywords, budget, targeting, copy) for human approval.

    The proposal is created in `pending` state only. It is NEVER applied by the
    agent — a human approves it and code applies it.

    Args:
        platform: one of google_ads, meta_ads, reddit_ads
        change_type: e.g. add_keywords, update_budget, update_targeting, update_copy
        details: the exact proposed change (keywords with match types, before/after values, etc.)
        rationale: why, grounded in the performance data just observed
    """
    proposal = {
        "proposal_id": f"prop-{uuid.uuid4().hex[:8]}",
        "status": "pending",
        "platform": platform,
        "change_type": change_type,
        "details": details,
        "rationale": rationale,
        "note": "pending human approval; the agent cannot apply changes",
    }
    _PROPOSALS.append(proposal)
    return proposal


ALL_TOOL_NAMES = (
    "list_platforms",
    "check_platform_performance",
    "compare_platform_windows",
    "propose_campaign_change",
)

READ_TOOL_NAMES = tuple(n for n in ALL_TOOL_NAMES if n != "propose_campaign_change")
