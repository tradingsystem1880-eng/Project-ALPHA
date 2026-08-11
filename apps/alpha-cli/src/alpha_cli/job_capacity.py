"""Lightweight public classification for the shared Qlib/Kronos capacity class."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

HEAVYWEIGHT_JOB_CAPACITY: Final = 1
# Both research kinds are RESERVED-FORWARD names (R-34). The classifier below maps
# `alpha research run` to "research:event-study", but no live surface routes governed
# research argv through the launchers that consult it (the generic web job route rejects
# governed research commands; the six research MCP tools use the projection path), so no
# executor creates either kind today. Reserving them now means generic durable-job
# creation already rejects the names, so a future caller cannot mint them outside
# governed research ownership. D0's live launch governance (three lifetime slots plus
# budget) is enforced separately in ControlStore.reserve_d0_research_launch.
HEAVYWEIGHT_JOB_KINDS: Final = frozenset(
    {
        "ml_train",
        "kronos_forecast",
        "kronos_evaluate",
        "kronos_strategy",
        "suite:qlib",
        "suite:kronos",
        "suite:monte_carlo",
        "research:event-study",
        "research:ml",
    }
)


def heavyweight_job_kind_for_command(args: Sequence[str]) -> str | None:
    """Classify direct CLI argv that consumes the shared heavyweight capacity class."""
    command = tuple(args[:2])
    if command == ("forecast", "run"):
        return "kronos_forecast"
    if command == ("forecast", "eval"):
        return "kronos_evaluate"
    if command == ("monte-carlo", "kronos"):
        return "kronos_strategy"
    if command == ("ml", "train"):
        return "ml_train"
    if command == ("research", "run"):
        return "research:event-study"
    for index, argument in enumerate(args):
        if argument == "--strategy=kronos":
            return "kronos_strategy"
        if argument == "--strategy" and index + 1 < len(args) and args[index + 1] == "kronos":
            return "kronos_strategy"
    return None
