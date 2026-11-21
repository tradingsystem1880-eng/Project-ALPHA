"""Recorded setup artifacts, with explicit absence rather than inferred results."""

from __future__ import annotations

from typing import Any

from alpha_web.api.models._base import StrictModel


class SetupRun(StrictModel):
    find_id: str
    description: str | None
    name: str | None
    recorded_at: str | None
    assets: list[dict[str, Any]] | None
    labels: list[str]


class SetupRunList(StrictModel):
    items: list[SetupRun]


class SetupFigure(StrictModel):
    name: str
    png: str | None
    # true when the picture was left out to keep the detail small; read it from the sheet route
    deferred: bool | None = None


class SetupReading(StrictModel):
    """How a stored study or trade reads: an evidence word and its place in the setup's family."""

    # one of three evidence words; null when the stored outcome word is not one this reads
    evidence: str | None
    # true when only the old outcome word was stored (its mapped phrase is shown as old wording)
    old_wording: bool
    # ledger rows of this kind on the same idea text, and this run's place among them
    family_position: int | None
    family_count: int | None


class SetupOutcome(StrictModel):
    run_id: str
    rule_version: str | None
    summary: dict[str, Any] | None
    rows: list[dict[str, Any]] | None
    figure: SetupFigure
    labels: list[str]
    trial_indices: list[int] | None
    trial_labels: dict[str, list[str]] | None = None
    reading: SetupReading | None = None


class SetupRunDetail(StrictModel):
    run: SetupRun
    summary: dict[str, Any] | None
    spec: dict[str, Any] | None
    candidates: list[dict[str, Any]] | None
    price_bars: None = None
    price_bars_reason: str
    sheets: list[SetupFigure] | None
    studies: list[SetupOutcome]
    trades: list[SetupOutcome]
    trial_indices: list[int] | None
    trial_labels: dict[str, list[str]] | None = None
    limits: list[str]
    label_explanations: dict[str, str]
