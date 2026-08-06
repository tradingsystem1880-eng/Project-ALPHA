"""Shared heavyweight command classification."""

from __future__ import annotations

import pytest

from alpha_cli.job_capacity import HEAVYWEIGHT_JOB_KINDS, heavyweight_job_kind_for_command


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        (["forecast", "run", "SPY"], "kronos_forecast"),
        (["forecast", "eval", "SPY"], "kronos_evaluate"),
        (["ml", "train", "exchange"], "ml_train"),
        (["backtest", "run", "SPY", "--strategy", "kronos"], "kronos_strategy"),
        (["validate", "SPY", "--strategy", "kronos"], "kronos_strategy"),
        (["optim", "grid", "SPY", "--strategy", "kronos"], "kronos_strategy"),
        (["backtest", "run", "SPY", "--strategy=kronos"], "kronos_strategy"),
        (
            ["validate", "SPY", "--strategy", "mean_reversion", "--strategy=kronos"],
            "kronos_strategy",
        ),
        (["backtest", "run", "SPY", "--strategy", "mean_reversion"], None),
        (["research", "run", "pilot", "project-id"], "research:event-study"),
    ],
)
def test_heavyweight_command_classification(args: list[str], expected: str | None) -> None:
    assert heavyweight_job_kind_for_command(args) == expected


def test_research_compute_jobs_share_the_capacity_one_class() -> None:
    assert "research:event-study" in HEAVYWEIGHT_JOB_KINDS
    assert "research:ml" in HEAVYWEIGHT_JOB_KINDS
    assert "research:acquire" not in HEAVYWEIGHT_JOB_KINDS
