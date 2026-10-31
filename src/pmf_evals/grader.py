"""Grade a result row: deterministic figure checks first, then rubric flags.

Deterministic checks compare the answer text against exact fixture ground
truth (FigureSpec). Rubric criteria need a Judge callable (LLM or human); the
offline default marks them `skipped` rather than scoring 0.
"""

from __future__ import annotations

import re
from typing import Callable

# date-like tokens are stripped before number extraction so "2026-11-26"
# can never satisfy a figure check
_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
# $1,234.56 | $1234.56 | 1234.56 | 1,234
_NUMBER_RE = re.compile(r"\$?\d{1,3}(?:,\d{3})+(?:\.\d+)?|\$?\d+(?:\.\d+)?")


def _extract_numbers(text: str) -> list[float]:
    cleaned = _DATE_RE.sub(" ", text)
    values = []
    for m in _NUMBER_RE.finditer(cleaned):
        raw = m.group(0).replace("$", "").replace(",", "")
        try:
            values.append(float(raw))
        except ValueError:  # pragma: no cover - regex guarantees parseable
            continue
    return values


def _matches(expected: float, found: list[float]) -> bool:
    tolerance = max(0.01, abs(expected) * 0.01)
    return any(abs(v - expected) <= tolerance for v in found)


def grade_result(row: dict, scenarios: list[Scenario], judge: Callable[[str, dict], bool] | None = None) -> dict:
    """Grade one runner row against its scenario.

    judge: optional callable(criterion, row) -> bool, applied per rubric criterion.
    """
    scenario = next((s for s in scenarios if s.id == row["scenario_id"]), None)
    if scenario is None:
        raise KeyError(f"no scenario with id {row['scenario_id']!r}")

    if row.get("status") == "failed":
        return {
            "scenario_id": row["scenario_id"],
            "verdict": "error",
            "figures": [],
            "rubric": [],
            "error": row.get("error"),
        }

    found_numbers = _extract_numbers(row.get("text", ""))

    figures = []
    for spec in scenario.figure_specs:
        expected = spec.expected_value()
        figures.append(
            {
                "platform": spec.platform,
                "window": spec.window,
                "metric": spec.metric,
                "expected": expected,
                "expected_str": f"{expected:.2f}",
                "found": expected is not None and _matches(expected, found_numbers),
            }
        )
    figures_ok = all(f["found"] for f in figures)

    rubric = []
    for criterion in scenario.rubric:
        if judge is None:
            rubric.append({"criterion": criterion, "verdict": "skipped"})
        else:
            rubric.append(
                {"criterion": criterion, "verdict": "pass" if judge(criterion, row) else "fail"}
            )

    if figures and not figures_ok:
        verdict = "fail"
    elif any(c["verdict"] == "fail" for c in rubric):
        verdict = "fail"
    elif rubric and all(c["verdict"] == "pass" for c in rubric):
        verdict = "pass"
    else:
        # no rubric judged (skipped) -> deterministic evidence only
        verdict = "figures_only"

    return {
        "scenario_id": row["scenario_id"],
        "verdict": verdict,
        "figures": figures,
        "rubric": rubric,
        "error": None,
    }
