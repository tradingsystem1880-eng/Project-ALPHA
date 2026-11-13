"""Feature plans keep a machine-readable state and the flat folder holds only live work.

* Every plan, archived or not, has exactly one ``**Delivery state:**`` line in its first 12
  lines using the fixed vocabulary.
* Every plan in the flat ``docs/superpowers/plans/`` folder passes ``plan_check``
  (``scripts/harness_models.py::FeaturePlan``), except the legacy allowlist below.
* Completed and superseded plans live in ``archive/YYYY-MM/`` (month of the filename date),
  except the pinned plans below, whose paths are referenced from files that cannot move them.
"""

from __future__ import annotations

import re
from pathlib import Path

import harness_awareness
import pytest

ROOT = Path(__file__).parents[2]
PLANS = ROOT / "docs" / "superpowers" / "plans"
ARCHIVE = PLANS / "archive"

STATE = re.compile(
    r"^\*\*Delivery state:\*\* "
    r"(?P<state>Completed|Implemented – qualification pending|In progress|Blocked|Planned"
    r"|Superseded by \S+)"
    r"(?=$|\s—|\s\(|\.|;|,|\s\d{4}-)"
)
FINISHED = ("Completed", "Superseded by ")

# Live plans that predate the FeaturePlan schema and cannot be brought to it truthfully.
# Key: plan filename; value: why it is exempt. Keep this empty unless there is no honest fix.
LEGACY_SCHEMA_EXCEPTIONS: dict[str, str] = {}

# Finished plans that stay in the flat folder because a file this repository must not rewrite
# names their path. Mirrored in docs/superpowers/plans/archive/README.md.
PINNED_FLAT: dict[str, str] = {
    "2026-09-11-edge-first-phase-c-screening-lane.md": "named in alpha_research/panel.py (hashed)",
    "2026-09-16-agent-neutral-reproducible-research.md": "linked from AGENTS.md (byte cap)",
    "2026-09-17-cancellation-and-research-walkthrough.md": "named in alpha_research/panel.py",
    "2026-09-30-edge-workspace.md": "linked from CLAUDE.md (byte cap)",
    "2026-09-30-research-workflow-completion.md": "path in captured alpha-eval evidence",
    "2026-10-26-native-rule-authority.md": "linked from CLAUDE.md (byte cap)",
    "2026-10-31-clean-rdagent-bootstrap.md": "linked from README.md",
}


def _flat() -> list[Path]:
    return sorted(PLANS.glob("*.md"))


def _archived() -> list[Path]:
    return sorted(p for p in ARCHIVE.glob("*/*.md"))


def _state(path: Path) -> str:
    head = path.read_text(encoding="utf-8").splitlines()[:12]
    lines = [line for line in head if line.startswith("**Delivery state:**")]
    assert len(lines) == 1, f"{path.name}: expected one Delivery state line in lines 1-12"
    match = STATE.match(lines[0])
    assert match, f"{path.name}: state outside the vocabulary: {lines[0]!r}"
    return match.group("state")


def test_plan_folders_are_populated() -> None:
    assert _flat(), "no live plans found"
    assert _archived(), "no archived plans found"


@pytest.mark.parametrize("path", _flat() + _archived(), ids=lambda p: p.name)
def test_every_plan_has_one_vocabulary_state_line(path: Path) -> None:
    _state(path)


@pytest.mark.parametrize("path", _flat(), ids=lambda p: p.name)
def test_live_plans_pass_plan_check(path: Path) -> None:
    if path.name in LEGACY_SCHEMA_EXCEPTIONS:
        pytest.skip(LEGACY_SCHEMA_EXCEPTIONS[path.name])
    ok, message = harness_awareness.plan_check(path)
    assert ok, message


def test_finished_plans_are_archived_unless_pinned() -> None:
    misplaced = [
        p.name for p in _flat() if _state(p).startswith(FINISHED) and p.name not in PINNED_FLAT
    ]
    assert misplaced == [], f"archive these under archive/YYYY-MM/: {misplaced}"
    stale_pins = [name for name in PINNED_FLAT if not (PLANS / name).is_file()]
    assert stale_pins == [], f"pinned plans missing from the flat folder: {stale_pins}"


@pytest.mark.parametrize("path", _archived(), ids=lambda p: p.name)
def test_archived_plans_are_finished_and_filed_by_month(path: Path) -> None:
    assert _state(path).startswith(FINISHED), f"{path.name} is not finished"
    assert re.fullmatch(r"\d{4}-\d{2}", path.parent.name), path.parent.name
    assert path.name.startswith(path.parent.name + "-"), f"{path.name} is in the wrong month"
