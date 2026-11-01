"""A 50-tool catalog at GTM-agent scale, for measuring the tool-selection ceiling.

Composition: the 4 core tools (identical names/descriptions to the small
catalog), ~10 useful fixture-backed reads, and ~36 plausible marketing-ops
distractors with real schemas but stub behavior. The degradation under test is
context/discrimination load, so distractors must look real.
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool, tool

from pmf_evals.fixtures import (
    PLATFORMS,
    anchor,
    load_dataset,
    shift_dataset,
    shipped_offset,
    window_totals,
)

from .tools import _tool_registry, check_platform_performance, compare_platform_windows

# (name, description, params, behavior)
# behavior: "daily" = fixture daily rows, "totals" = fixture window totals,
# "stub" = plausible no-op for a fixture deployment.
_SPEC: list[tuple[str, str, list[tuple[str, str, str]], str]] = [
    # --- useful fixture-backed reads ---
    ("get_spend_daily", "Get the daily spend breakdown for one platform over a window. Use when you need day-by-day granularity, not just totals.", [("platform", "str", "one of google_ads, meta_ads, reddit_ads"), ("window", "str", "last_week, prior_week, last_30d")], "daily"),
    ("get_clicks_daily", "Get the daily clicks breakdown for one platform over a window. Use for traffic-level day analysis.", [("platform", "str", "one of google_ads, meta_ads, reddit_ads"), ("window", "str", "last_week, prior_week, last_30d")], "daily"),
    ("get_conversions_daily", "Get the daily conversion counts for one platform over a window.", [("platform", "str", "one of google_ads, meta_ads, reddit_ads"), ("window", "str", "last_week, prior_week, last_30d")], "daily"),
    ("compare_all_platforms", "Compare one metric across ALL platforms for a window in one call. Use for share-of-spend or ranking questions.", [("metric", "str", "spend, conversions, cpa"), ("window", "str", "last_week, prior_week, last_30d")], "totals"),
    ("get_metric_totals", "Get totals for one metric on one platform over a window. Simple single-number lookup.", [("platform", "str", "one of google_ads, meta_ads, reddit_ads"), ("metric", "str", "spend, conversions, cpa"), ("window", "str", "last_week, prior_week, last_30d")], "totals"),
    ("list_campaigns", "List the campaigns running on a platform with their goals. Use before proposing campaign-scoped changes.", [("platform", "str", "one of google_ads, meta_ads, reddit_ads")], "campaigns"),
    ("get_account_summary", "One-paragraph summary of an ad account: platforms active, anchor date, data completeness.", [("platform", "str", "one of google_ads, meta_ads, reddit_ads")], "totals"),
    ("get_weekly_digest", "Pre-aggregated weekly digest for a platform: totals, direction, and flags. Fast path for recurring Monday questions.", [("platform", "str", "one of google_ads, meta_ads, reddit_ads"), ("window", "str", "last_week, prior_week")], "totals"),
    ("get_metric_momentum", "Direction and magnitude of change for a metric between two windows, normalized. Use for trend-ranking.", [("platform", "str", "one of google_ads, meta_ads, reddit_ads"), ("metric", "str", "spend, conversions, cpa"), ("window_a", "str", "recent window"), ("window_b", "str", "baseline window")], "totals"),
    ("get_platform_caveats", "Data-quality caveats for a platform: completeness, known join limitations, attribution notes.", [("platform", "str", "one of google_ads, meta_ads, reddit_ads")], "caveats"),
    # --- plausible GTM / marketing-ops distractors (stub behavior) ---
    ("create_campaign", "Create a new advertising campaign on a platform with budget, goal, and schedule.", [("platform", "str", "target platform"), ("name", "str", "campaign name"), ("budget", "str", "weekly budget"), ("goal", "str", "campaign objective")], "stub"),
    ("pause_campaign", "Pause an existing campaign by name on a platform.", [("platform", "str", "target platform"), ("campaign_name", "str", "campaign to pause")], "stub"),
    ("resume_campaign", "Resume a paused campaign by name on a platform.", [("platform", "str", "target platform"), ("campaign_name", "str", "campaign to resume")], "stub"),
    ("archive_campaign", "Archive a completed campaign so it stops consuming management attention.", [("platform", "str", "target platform"), ("campaign_name", "str", "campaign to archive")], "stub"),
    ("duplicate_campaign", "Duplicate an existing campaign with a new name for testing variations.", [("platform", "str", "target platform"), ("campaign_name", "str", "source campaign"), ("new_name", "str", "duplicate name")], "stub"),
    ("set_campaign_budget", "Set the weekly budget of an existing campaign directly (requires separate approval from proposals).", [("platform", "str", "target platform"), ("campaign_name", "str", "campaign"), ("budget", "str", "new weekly budget")], "stub"),
    ("set_bid_strategy", "Switch the bid strategy of a campaign (e.g. target CPA, maximize clicks).", [("platform", "str", "target platform"), ("campaign_name", "str", "campaign"), ("strategy", "str", "bid strategy name")], "stub"),
    ("set_ad_schedule", "Configure dayparting: which hours and days a campaign serves ads.", [("platform", "str", "target platform"), ("campaign_name", "str", "campaign"), ("schedule", "str", "schedule spec")], "stub"),
    ("set_geo_targeting", "Replace the geographic targeting of a campaign with a new list of regions.", [("platform", "str", "target platform"), ("campaign_name", "str", "campaign"), ("regions", "str", "comma-separated regions")], "stub"),
    ("exclude_geo", "Exclude regions from a campaign's targeting.", [("platform", "str", "target platform"), ("campaign_name", "str", "campaign"), ("regions", "str", "regions to exclude")], "stub"),
    ("add_audience", "Add an audience segment to a campaign's targeting.", [("platform", "str", "target platform"), ("campaign_name", "str", "campaign"), ("audience", "str", "audience definition")], "stub"),
    ("create_lookalike_audience", "Create a lookalike audience from a seed audience on a platform.", [("platform", "str", "target platform"), ("seed_audience", "str", "seed audience name"), ("size", "str", "lookalike size 1-10")], "stub"),
    ("list_remarketing_lists", "List the remarketing audiences available on a platform with sizes.", [("platform", "str", "target platform")], "stub"),
    ("list_keywords", "List keywords of a search campaign with their match types and status.", [("platform", "str", "target platform"), ("campaign_name", "str", "campaign")], "stub"),
    ("add_negative_keywords", "Add negative keywords to a search campaign to stop irrelevant queries.", [("platform", "str", "target platform"), ("campaign_name", "str", "campaign"), ("keywords", "str", "keywords to exclude")], "stub"),
    ("get_auction_insights", "Get auction-insight competitors and impression share for a search campaign.", [("platform", "str", "target platform"), ("campaign_name", "str", "campaign")], "stub"),
    ("get_impression_share", "Get impression share and lost-IS reasons for a campaign over a window.", [("platform", "str", "target platform"), ("campaign_name", "str", "campaign"), ("window", "str", "reporting window")], "stub"),
    ("list_creatives", "List the ad creatives attached to a campaign with their status.", [("platform", "str", "target platform"), ("campaign_name", "str", "campaign")], "stub"),
    ("upload_creative", "Upload a new creative (image or video URL) to a campaign.", [("platform", "str", "target platform"), ("campaign_name", "str", "campaign"), ("url", "str", "creative asset URL")], "stub"),
    ("generate_ad_copy", "Generate ad copy variants for a campaign following the brand voice.", [("platform", "str", "target platform"), ("theme", "str", "copy theme"), ("variants", "str", "number of variants")], "stub"),
    ("translate_ad_copy", "Translate existing ad copy into target languages.", [("copy", "str", "copy to translate"), ("languages", "str", "target languages")], "stub"),
    ("check_brand_safety", "Check a campaign's placements against the brand-safety blocklist.", [("platform", "str", "target platform"), ("campaign_name", "str", "campaign")], "stub"),
    ("list_placements", "List the placements a campaign is serving on with performance.", [("platform", "str", "target platform"), ("campaign_name", "str", "campaign")], "stub"),
    ("list_devices", "Break down campaign performance by device class.", [("platform", "str", "target platform"), ("campaign_name", "str", "campaign")], "stub"),
    ("get_demographics", "Get the demographic breakdown (age, gender) of a campaign's audience.", [("platform", "str", "target platform"), ("campaign_name", "str", "campaign")], "stub"),
    ("create_experiment", "Create an A/B experiment between two campaign variants.", [("platform", "str", "target platform"), ("variant_a", "str", "control campaign"), ("variant_b", "str", "challenger campaign")], "stub"),
    ("get_experiment_results", "Read the results and significance of a running or finished experiment.", [("platform", "str", "target platform"), ("experiment_name", "str", "experiment")], "stub"),
    ("export_report", "Export a performance report as a file attachment for sharing.", [("platform", "str", "target platform"), ("window", "str", "reporting window"), ("format", "str", "csv or pdf")], "stub"),
    ("schedule_report", "Schedule a recurring report delivery to a channel.", [("platform", "str", "target platform"), ("window", "str", "reporting window"), ("channel", "str", "delivery channel")], "stub"),
    ("send_slack_alert", "Send a custom Slack alert about campaign performance to a channel.", [("channel", "str", "Slack channel"), ("message", "str", "alert text")], "stub"),
    ("get_billing_summary", "Get the billing summary and payment status of an ad account.", [("platform", "str", "target platform")], "stub"),
    ("get_account_structure", "Get the account hierarchy: account, campaigns, ad groups, ads.", [("platform", "str", "target platform")], "stub"),
    ("list_pixels", "List tracking pixels / conversion APIs configured on a platform account.", [("platform", "str", "target platform")], "stub"),
    ("create_conversion_event", "Define a new conversion event on a platform tracking setup.", [("platform", "str", "target platform"), ("event_name", "str", "event to track")], "stub"),
    ("get_attribution_settings", "Read the attribution model and window configured on a platform account.", [("platform", "str", "target platform")], "stub"),
    ("add_utm_template", "Set or update the UTM tracking template for a platform account.", [("platform", "str", "target platform"), ("template", "str", "UTM template")], "stub"),
]


def _make_tool(spec: tuple) -> BaseTool:
    name, description, params, behavior = spec

    if behavior == "daily":
        metric_key = name.split("_")[1]  # get_spend_daily -> spend

        def fn(**kwargs) -> dict[str, Any]:
            if kwargs.get("platform") not in PLATFORMS:
                return {"error": f"unknown platform {kwargs.get('platform')!r}"}
            shifted = shift_dataset(load_dataset(), shipped_offset())
            rows = [r for r in shifted[kwargs["platform"]] if r["date"].isoformat() <= anchor().isoformat()][-7 if kwargs.get("window") == "last_week" else -30:]
            return {
                "platform": kwargs["platform"],
                "window": kwargs.get("window"),
                "daily": [{"date": r["date"].isoformat(), metric_key: r[metric_key]} for r in rows],
            }
    elif behavior == "totals":
        def fn(**kwargs) -> dict[str, Any]:
            if kwargs.get("platform") not in PLATFORMS:
                return {"error": f"unknown platform {kwargs.get('platform')!r}"}
            from pmf_agent.tools import WINDOWS, _resolve_window
            win = _resolve_window(kwargs.get("window", "last_week"))
            if win is None:
                return {"error": f"unknown window {kwargs.get('window')!r}"}
            metric = kwargs.get("metric", "spend")
            totals = window_totals(shift_dataset(load_dataset(), shipped_offset()), kwargs["platform"], win)
            value = totals.get(metric) if metric in ("spend", "conversions", "cpa") else None
            return {"platform": kwargs["platform"], "metric": metric, "window": kwargs.get("window"), "value": value}
    elif behavior == "campaigns":
        def fn(**kwargs) -> dict[str, Any]:
            return {
                "platform": kwargs.get("platform"),
                "campaigns": [
                    {"name": "Search - product terms", "goal": "qualified_leads"},
                    {"name": "Brand awareness video", "goal": "awareness"},
                    {"name": "Community boost", "goal": "content_downloads"},
                ],
                "note": "fixture campaign list",
            }
    elif behavior == "caveats":
        def fn(**kwargs) -> dict[str, Any]:
            return {
                "platform": kwargs.get("platform"),
                "caveats": [
                    "video campaigns may not join to warehouse (keyword-less)",
                    "platform conversion definitions differ from warehouse outcomes",
                ],
            }
    else:  # stub
        def fn(**kwargs) -> dict[str, Any]:
            return {
                "status": "not_applied",
                "fixture_stub": True,
                "note": "available in production deployment; fixture mode does not execute this action",
                "received": kwargs,
            }

    return fn


def _typed_tool(spec: tuple) -> BaseTool:
    """Build a tool with an explicit typed schema from the spec row."""
    name, description, params, behavior = spec
    plain = _make_tool(spec)

    # Build a typed function dynamically so @tool generates a real schema.
    import textwrap

    args_sig = ", ".join(f"{n}: str" for n, _, _ in params)
    args_doc = "\n".join(f"        {n}: {d}" for n, _, d in params)
    kwargs_map = ", ".join(f"'{n}': {n}" for n, _, _ in params)
    body = f"""
    def {name}({args_sig}) -> dict:
        \"\"\"{description}

        Args:
{args_doc}
        \"\"\"
        return _make_tool(_SPEC_BY_NAME[{name!r}])(**{{{kwargs_map}}})
    """
    ns: dict = {"_make_tool": _make_tool, "_SPEC_BY_NAME": _SPEC_BY_NAME}
    exec(textwrap.dedent(body), ns)
    return tool(ns[name])


_SPEC_BY_NAME = {s[0]: s for s in _SPEC}


def build_catalog_50() -> list[BaseTool]:
    """Exactly 50 tools: the 4 core + fixture-backed reads + marketing-ops distractors."""
    core = [
        _tool_registry["list_platforms"],
        check_platform_performance,
        compare_platform_windows,
        _tool_registry["propose_campaign_change"],
    ]
    built: dict[str, BaseTool] = {}
    for spec in _SPEC:
        t = _typed_tool(spec)
        built[t.name] = t
    return [*core, *built.values()]
