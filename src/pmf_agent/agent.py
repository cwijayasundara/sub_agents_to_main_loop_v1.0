"""Capability profiles for the single loop (Slack vs scheduled)."""

from __future__ import annotations

from .fw import chat_model
from .prompts import ENTRY_POINTS, system_prompt
from .tools import ALL_TOOL_NAMES, READ_TOOL_NAMES, _tool_registry


def profile_tools(entry_point: str) -> list:
    names = set(ALL_TOOL_NAMES if entry_point == "slack" else READ_TOOL_NAMES)
    return [_tool_registry[n] for n in ALL_TOOL_NAMES if n in names]


def create_agent(
    entry_point: str, model=None, middleware=None, skills_root: str | None = None
):
    """One model, one loop, no subagents; the entry point only changes capabilities.

    `middleware` (e.g. decision_harness ToolSelectionMiddleware) is appended to
    the deepagents middleware stack. `skills_root` points at a workspace
    directory containing `skills/` (progressively disclosed SKILL.md libraries)
    and `wiki/` (company reference pages); skills are then disclosed by name
    and read on demand through the filesystem backend.
    """
    if entry_point not in ENTRY_POINTS:
        raise ValueError(f"entry_point must be one of {ENTRY_POINTS}, got {entry_point!r}")
    from deepagents import create_deep_agent

    tools = profile_tools(entry_point)
    kwargs: dict = {}
    if skills_root is not None:
        from deepagents.backends import FilesystemBackend

        kwargs["backend"] = FilesystemBackend(root_dir=skills_root)
        kwargs["skills"] = ["/skills"]
    agent = create_deep_agent(
        model=model if model is not None else chat_model(),
        tools=tools,
        system_prompt=system_prompt(entry_point),
        middleware=list(middleware or []),
        **kwargs,
    )
    # expose the bound tool surface for introspection/tests (setattr verified safe)
    agent.pmf_tools = tools
    agent.pmf_middleware = list(middleware or [])
    return agent
