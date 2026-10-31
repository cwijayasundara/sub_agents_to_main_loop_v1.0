"""Scenario schema and golden-set loader.

Scenarios are data (JSON), never code. Each names its entry point (capability
profile), a category, the user prompt, rubric criteria (judged), and optional
`figure_specs` — (platform, window, metric) triples whose exact values the
deterministic grader can compute from the fixture ground truth.
"""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass, field
from pathlib import Path

from .fixtures import load_dataset, shift_dataset, shipped_offset, window_totals

GOLDEN_PATH = Path(__file__).resolve().parents[2] / "evals" / "scenarios" / "golden.json"

ENTRY_POINTS = ("slack", "scheduled")
CATEGORIES = ("weekly_report", "q_and_a", "write_proposal", "cross_platform")

WINDOWS = {
    "last_week": lambda a: (a - dt.timedelta(days=6), a),
    "prior_week": lambda a: (a - dt.timedelta(days=13), a - dt.timedelta(days=7)),
    "last_30d": lambda a: (a - dt.timedelta(days=29), a),
}


@dataclass(frozen=True)
class FigureSpec:
    """A deterministic figure the answer must contain, computed from fixtures."""

    platform: str
    window: str  # key into WINDOWS
    metric: str  # spend | conversions | cpa

    def totals(self) -> dict[str, float | None]:
        shifted = shift_dataset(load_dataset(), shipped_offset())
        anchor_date = shifted[self.platform][-1]["date"]
        start, end = WINDOWS[self.window](anchor_date)
        return window_totals(shifted, self.platform, (start, end))

    def expected_value(self) -> float | None:
        return self.totals().get(self.metric)


@dataclass(frozen=True)
class Scenario:
    id: str
    entry_point: str
    category: str
    prompt: str
    rubric: list[str] = field(default_factory=list)
    figure_specs: tuple[FigureSpec, ...] = ()

    def __post_init__(self) -> None:
        if self.entry_point not in ENTRY_POINTS:
            raise ValueError(f"entry_point must be one of {ENTRY_POINTS}, got {self.entry_point!r}")
        if self.category not in CATEGORIES:
            raise ValueError(f"category must be one of {CATEGORIES}, got {self.category!r}")

    def window_dates(self) -> tuple[dt.date, dt.date] | None:
        """The window implied by the first figure spec, resolved to the runtime anchor."""
        if not self.figure_specs:
            return None
        shifted = shift_dataset(load_dataset(), shipped_offset())
        anchor_date = shifted[self.figure_specs[0].platform][-1]["date"]
        return WINDOWS[self.figure_specs[0].window](anchor_date)


def _parse(data: dict) -> Scenario:
    specs = tuple(
        FigureSpec(platform=s["platform"], window=s["window"], metric=s["metric"])
        for s in data.get("figure_specs", [])
    )
    return Scenario(
        id=data["id"],
        entry_point=data["entry_point"],
        category=data["category"],
        prompt=data["prompt"],
        rubric=list(data.get("rubric", [])),
        figure_specs=specs,
    )


def load_scenarios_from_list(items: list[Scenario]) -> list[Scenario]:
    ids = [s.id for s in items]
    if len(ids) != len(set(ids)):
        raise ValueError("scenario ids must be unique")
    return items


def load_scenarios(path: str | Path = GOLDEN_PATH) -> list[Scenario]:
    """Load and validate scenarios from a JSON file; ids must be unique."""
    raw = json.loads(Path(path).read_text())
    return load_scenarios_from_list([_parse(d) for d in raw])
