"""Task plans keep a machine-readable state and the live work folder holds only live work.

* Every plan, archived or not, has exactly one ``**Delivery state:**`` line in its first 12
  lines using the fixed vocabulary.
* Every live plan, ``docs/work/<task>/02-plan.md``, passes ``plan_check``
  (``scripts/harness_models.py::FeaturePlan``) and is not finished.
* Finished plans live under ``docs/work/archive/YYYY-MM/`` (month of the task name): a single
  ``<task>.md`` file (plans archived before 2026-11-14) or a ``<task>/02-plan.md`` folder.
"""

from __future__ import annotations

import re
from pathlib import Path

import harness_awareness
import pytest

ROOT = Path(__file__).parents[2]
WORK = ROOT / "docs" / "work"
ARCHIVE = WORK / "archive"
PLAN = "02-plan.md"

STATE = re.compile(
    r"^\*\*Delivery state:\*\* "
    r"(?P<state>Completed|Implemented – qualification pending|In progress|Blocked|Planned"
    r"|Superseded by \S+)"
    r"(?=$|\s—|\s\(|\.|;|,|\s\d{4}-)"
)
FINISHED = ("Completed", "Superseded by ")


def _live() -> list[Path]:
    return sorted(p for p in WORK.glob(f"*/{PLAN}") if p.parent.name != ARCHIVE.name)


def _archived() -> list[Path]:
    return sorted([*ARCHIVE.glob("*/*.md"), *ARCHIVE.glob(f"*/*/{PLAN}")])


def _task(path: Path) -> str:
    """The task name: the folder of a ``02-plan.md``, or the stem of a legacy single file."""
    return path.parent.name if path.name == PLAN else path.stem


def _state(path: Path) -> str:
    head = path.read_text(encoding="utf-8").splitlines()[:12]
    lines = [line for line in head if line.startswith("**Delivery state:**")]
    assert len(lines) == 1, f"{_task(path)}: expected one Delivery state line in lines 1-12"
    match = STATE.match(lines[0])
    assert match, f"{_task(path)}: state outside the vocabulary: {lines[0]!r}"
    return match.group("state")


def test_plan_folders_are_populated() -> None:
    assert _live(), "no live plans found"
    assert _archived(), "no archived plans found"


@pytest.mark.parametrize("path", _live() + _archived(), ids=_task)
def test_every_plan_has_one_vocabulary_state_line(path: Path) -> None:
    _state(path)


@pytest.mark.parametrize("path", _live(), ids=_task)
def test_live_plans_pass_plan_check(path: Path) -> None:
    ok, message = harness_awareness.plan_check(path)
    assert ok, message


def test_finished_plans_are_archived() -> None:
    misplaced = [_task(p) for p in _live() if _state(p).startswith(FINISHED)]
    assert misplaced == [], f"move these task folders under docs/work/archive/YYYY-MM/: {misplaced}"


@pytest.mark.parametrize("path", _archived(), ids=_task)
def test_archived_plans_are_finished_and_filed_by_month(path: Path) -> None:
    month = path.relative_to(ARCHIVE).parts[0]
    assert _state(path).startswith(FINISHED), f"{_task(path)} is not finished"
    assert re.fullmatch(r"\d{4}-\d{2}", month), month
    assert _task(path).startswith(month + "-"), f"{_task(path)} is in the wrong month"
