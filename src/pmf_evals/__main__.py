"""CLI: run scenarios against an agent, grade results, compare two runs.

    python -m pmf_evals run --agent echo --out results.jsonl
    python -m pmf_evals grade --results results.jsonl --out graded.json
    python -m pmf_evals compare run_a.jsonl run_b.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .echo_agent import EchoAgent
from .grader import grade_result
from .report import compare
from .runner import run_suite
from .scenarios import GOLDEN_PATH, load_scenarios


def _fireworks_agent(
    routed: bool = False, skills_root: str | None = None, arch: str = "folded",
    tools_surface: str = "core", llm_selector: bool = False,
):
    """Lazily import pmf_agent so the CLI loads without the agent stack."""
    from pmf_agent.adapter import FireworksAgentUnderTest

    return FireworksAgentUnderTest(
        entry_point="slack",
        routed=routed,
        skills_root=skills_root,
        arch=arch,
        tools_surface=tools_surface,
        llm_selector=llm_selector,
    )


_AGENTS = {
    "echo": EchoAgent,
    "fireworks": lambda: _fireworks_agent(),
    "fireworks-routed": lambda: _fireworks_agent(routed=True),
    "fireworks-skills": lambda: _fireworks_agent(skills_root="workspace"),
    "fireworks-hierarchical": lambda: _fireworks_agent(skills_root="workspace", arch="hierarchical"),
    "fireworks-50": lambda: _fireworks_agent(skills_root="workspace", tools_surface="full50"),
    "fireworks-50-routed": lambda: _fireworks_agent(
        skills_root="workspace", tools_surface="full50", llm_selector=True
    ),
}


def _cmd_run(args: argparse.Namespace) -> int:
    scenarios = load_scenarios(args.scenarios or GOLDEN_PATH)
    agent = _AGENTS[args.agent]()
    rows = run_suite(agent, scenarios, args.out, trace_dir=args.trace_dir)
    print(f"ran {len(rows)} scenarios -> {args.out}")
    if args.trace_dir:
        print(f"traces -> {args.trace_dir}")
    return 0


def _cmd_grade(args: argparse.Namespace) -> int:
    scenarios = load_scenarios(args.scenarios or GOLDEN_PATH)
    reports = []
    for line in Path(args.results).read_text().splitlines():
        row = json.loads(line)
        reports.append(grade_result(row, scenarios, arch=args.arch))
    out = {"results": str(args.results), "arch": args.arch, "reports": reports}
    if args.out:
        Path(args.out).write_text(json.dumps(out, indent=2))
    errors = sum(1 for r in reports if r["verdict"] == "error")
    fails = sum(1 for r in reports if r["verdict"] == "fail")
    print(f"graded {len(reports)}: {fails} fail, {errors} error")
    return 0


def _cmd_compare(args: argparse.Namespace) -> int:
    def load_graded(path: str) -> list[dict]:
        scenarios = load_scenarios(GOLDEN_PATH)
        rows = [json.loads(l) for l in Path(path).read_text().splitlines()]
        return [grade_result(r, scenarios) | {"latency_ms": r["latency_ms"], "cost_usd": r["cost_usd"]} for r in rows]

    report = compare(load_graded(args.run_a), load_graded(args.run_b))
    print(json.dumps(report, indent=2))
    return 0


def _cmd_report(args: argparse.Namespace) -> int:
    from .comparison_page import open_page

    path = open_page()
    print(f"comparison page -> {path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pmf_evals")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run")
    p_run.add_argument("--agent", choices=sorted(_AGENTS), default="echo")
    p_run.add_argument("--out", default="results.jsonl")
    p_run.add_argument("--scenarios")
    p_run.add_argument("--trace-dir", help="write one transcript log per scenario here")
    p_run.set_defaults(func=_cmd_run)

    p_grade = sub.add_parser("grade")
    p_grade.add_argument("--results", required=True)
    p_grade.add_argument("--out")
    p_grade.add_argument("--scenarios")
    p_grade.add_argument("--arch", choices=["folded", "hierarchical"], default="folded")
    p_grade.set_defaults(func=_cmd_grade)

    p_cmp = sub.add_parser("compare")
    p_cmp.add_argument("run_a")
    p_cmp.add_argument("run_b")
    p_cmp.set_defaults(func=_cmd_compare)

    sub.add_parser("report", help="build + open the architecture comparison page").set_defaults(func=_cmd_report)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
