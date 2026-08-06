"""Lightweight public classification for the shared Qlib/Kronos capacity class."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

HEAVYWEIGHT_JOB_CAPACITY: Final = 1
# "research:event-study" classifies `alpha research run` today (the D0 pilot occupies the
# shared slot conservatively). "research:ml" is a RESERVED-FORWARD name for the unshipped
# empirical research workers (R-34): reserving it now means generic durable-job creation
# already rejects it, so no future caller can mint the kind outside governed research
# ownership. No executor creates it yet by design.
HEAVYWEIGHT_JOB_KINDS: Final = frozenset(
    {
        "ml_train",
        "kronos_forecast",
        "kronos_evaluate",
        "kronos_strategy",
        "suite:qlib",
        "suite:kronos",
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
