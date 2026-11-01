"""Run the paid media agent directly.

    # one-off question (live LLM; needs FIREWORKS_API_KEY)
    python -m pmf_agent "How did Google spend move last week vs the week before?"

    # interactive session
    python -m pmf_agent

    # pick the architecture and entry point
    python -m pmf_agent --arch hierarchical "Which platform gained spend share?"
    python -m pmf_agent --entry-point scheduled "Produce the weekly report"

Flags:
    --entry-point  slack | scheduled (capability profile; default slack)
    --arch         folded | hierarchical (default folded)
    --routed       enable Decisions-backed intent routing (Stage 2 middleware)
    --no-stream    print only the final answer (tests); default streams turns
"""

from __future__ import annotations

import argparse
import sys
import uuid

from .agent import ENTRY_POINTS
from .adapter import extract_text, extract_tool_calls, extract_usage
from .fw import estimate_cost_usd

_ARCHS = ("folded", "hierarchical")

_BANNER = """pmf_agent — paid media analyst (folded single loop)
type a question, or :quit / Ctrl-D to exit
"""


def _build_agent(
    entry_point: str = "slack",
    arch: str = "folded",
    routed: bool = False,
    skills_root: str | None = "workspace",
    model=None,
    tools_surface: str = "core",
):
    """Build the deepagents graph for the selected architecture.

    tools_surface: "core" (4 tools) or "full50" (the 50-tool GTM-scale catalog).
    """
    tools_override = None
    if tools_surface == "full50":
        from .catalog50 import build_catalog_50

        tools_override = build_catalog_50()
    if arch == "hierarchical":
        from .subagent_arch import create_hierarchical_agent

        return create_hierarchical_agent(entry_point, model=model, skills_root=skills_root)
    if routed:
        from .agent import create_agent
        from .routing import tool_selection_middleware

        return create_agent(
            entry_point,
            model=model,
            skills_root=skills_root,
            middleware=[tool_selection_middleware()],
            tools_override=tools_override,
        )
    from .agent import create_agent

    return create_agent(entry_point, model=model, skills_root=skills_root, tools_override=tools_override)


def _print_turn(text: str, tool_calls: list[str], usage: dict, cost: float) -> None:
    if tool_calls:
        print(f"  [tools] {', '.join(tool_calls)}")
    print(text)
    print(f"  — {usage['input_tokens']} in / {usage['output_tokens']} out, ~${cost:.4f}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pmf_agent", description="Run the paid media agent.")
    parser.add_argument("prompt", nargs="*", help="one-off question; omit for interactive mode")
    parser.add_argument("--entry-point", choices=ENTRY_POINTS, default="slack")
    parser.add_argument("--arch", choices=_ARCHS, default="folded")
    parser.add_argument("--routed", action="store_true", help="Decisions-backed tool routing")
    parser.add_argument("--skills-root", default="workspace")
    parser.add_argument("--tools", dest="tools_surface", choices=["core", "full50"], default="core")
    parser.add_argument("--thread-id", default=None, help="conversation thread (interactive keeps one)")
    parser.add_argument("--no-stream", action="store_true", help="print only the final answer")
    args = parser.parse_args(argv)

    agent = _build_agent(
        entry_point=args.entry_point,
        arch=args.arch,
        routed=args.routed,
        skills_root=args.skills_root,
        tools_surface=args.tools_surface,
    )
    thread = {"configurable": {"thread_id": args.thread_id or f"cli-{uuid.uuid4().hex[:8]}"}}

    def _ask(question: str) -> None:
        result = agent.invoke({"messages": [{"role": "user", "content": question}]}, config=thread)
        messages = result["messages"]
        usage = extract_usage(messages)
        _print_turn(
            extract_text(messages),
            extract_tool_calls(messages),
            usage,
            estimate_cost_usd(usage["input_tokens"], usage["output_tokens"]),
        )

    if args.prompt:
        _ask(" ".join(args.prompt))
        return 0

    # interactive REPL: one thread, multi-turn context
    print(_BANNER)
    try:
        while True:
            try:
                question = input("you> ").strip()
            except EOFError:
                break
            if not question or question in (":quit", ":q", "exit"):
                break
            _ask(question)
    except KeyboardInterrupt:
        print()
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
