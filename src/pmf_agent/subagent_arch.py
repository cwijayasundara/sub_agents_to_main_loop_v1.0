"""The hierarchical architecture: parent + one subagent per platform.

The PMA's production choice, rebuilt for the A/B. The parent holds intent-level
tools (discovery, writes) and delegates platform analysis through `task`;
each subagent gets platform-scoped read tools, the skills library, and returns
its synthesized findings. Isolation is engineered: scoped tools, scoped prompt,
scoped response.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from langchain_core.tools import tool

from .agent import ENTRY_POINTS, create_agent
from .fw import chat_model
from .tools import PLATFORMS, _platform_window_totals

PLATFORM_SUBAGENTS = {
    "google_ads": "google-ads-specialist",
    "meta_ads": "meta-ads-specialist",
    "reddit_ads": "reddit-ads-specialist",
}


def platform_read_tools(platform: str) -> list:
    """Read tools pre-bound to one platform — the subagent cannot see others."""
    if platform not in PLATFORMS:
        raise ValueError(f"unknown platform {platform!r}; known: {', '.join(sorted(PLATFORMS))}")

    @tool
    def check_performance(window: str) -> dict[str, Any]:
        """Check this platform's performance (spend, conversions, CPA) over a window.

        Args:
            window: one of last_week, prior_week, last_30d
        """
        return _platform_window_totals(platform, window)

    @tool
    def compare_windows(metric: str, window_a: str, window_b: str) -> dict[str, Any]:
        """Compare one metric across two windows for this platform.

        Args:
            metric: one of spend, conversions, cpa
            window_a: recent window (last_week, prior_week, last_30d)
            window_b: baseline window
        """
        a = _platform_window_totals(platform, window_a)
        b = _platform_window_totals(platform, window_b)
        if "error" in a or "error" in b:
            return {"error": a.get("error") or b.get("error")}
        va, vb = a["totals"][metric], b["totals"][metric]
        if va is None or vb is None or not vb:
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
        }

    @tool
    def read_context() -> dict[str, Any]:
        """Read this platform's context: data anchor, source-of-truth reminder."""
        from pmf_evals.fixtures import anchor

        return {
            "platform": platform,
            "anchor": anchor().isoformat(),
            "source": "ad platform (fixture)",
            "reminder": "media metrics never come from the warehouse",
        }

    return [check_performance, compare_windows, read_context]


_SUBAGENT_PROMPT = (
    "You are the {platform} specialist. Check this platform's performance with "
    "your tools, compare last_week vs prior_week, and return a compact synthesis: "
    "absolute figures for both windows, the change, the likely driver, and caveats "
    "(data completeness, small volumes). You only know this platform."
)


def create_hierarchical_agent(
    entry_point: str, model=None, middleware=None, skills_root: str | None = None
):
    """PMA-style parent + per-platform subagents. Same model, same skills."""
    if entry_point not in ENTRY_POINTS:
        raise ValueError(f"entry_point must be one of {ENTRY_POINTS}, got {entry_point!r}")
    from deepagents import create_deep_agent

    parent_tools_spec = None  # (unused placeholder removed)
    if entry_point == "slack":
        from .tools import _tool_registry

        parent_tool_objs = [_tool_registry["list_platforms"], _tool_registry["propose_campaign_change"]]
    else:
        from .tools import _tool_registry

        parent_tool_objs = [_tool_registry["list_platforms"]]

    subagent_specs = []
    for platform, name in PLATFORM_SUBAGENTS.items():
        spec: dict = {
            "name": name,
            "description": f"Read-only analyst for {platform} performance. Delegates platform analysis.",
            "system_prompt": _SUBAGENT_PROMPT.format(platform=platform),
            "tools": platform_read_tools(platform),
        }
        if skills_root is not None:
            spec["skills"] = ["/skills"]
        subagent_specs.append(spec)

    kwargs: dict = {}
    if skills_root is not None:
        from deepagents.backends import FilesystemBackend

        kwargs["backend"] = FilesystemBackend(root_dir=skills_root)
        kwargs["skills"] = ["/skills"]

    agent = create_deep_agent(
        model=model if model is not None else chat_model(),
        tools=parent_tool_objs,
        subagents=subagent_specs,
        middleware=list(middleware or []),
        **kwargs,
    )
    agent.pmf_tools = parent_tool_objs
    agent.pmf_middleware = list(middleware or [])
    agent.pmf_subagents = {spec["name"]: spec for spec in subagent_specs}
    return agent
