"""Tear-sheet report schema + rendering (spec §8 reporting, §11.2).

Pure assembly: these frozen dataclasses hold the already-computed gauntlet results, and the
(later) ``report_to_manifest`` / ``render_tearsheet_html`` helpers turn a ``GauntletReport`` into a
byte-stable JSON manifest and a quantstats HTML tear sheet. This module runs no engine and knows
nothing about nautilus — it imports only ``alpha_core`` plus the pandas/quantstats rendering edge —
so ``alpha_validation`` keeps its core-only dependency footprint. The richer report lives here (not
in ``alpha_core``) and *contains* ``alpha_core.ValidationOutcome``s so the shared contract is
honored without growing the dependency-free core.
"""

from __future__ import annotations

import dataclasses
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from alpha_core import ValidationOutcome

_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class FoldSummary:
    """One walk-forward fold: index bounds into the return series + its OOS performance."""

    index: int
    train_start: int
    train_end: int  # exclusive
    test_start: int
    test_end: int  # exclusive
    n_test: int
    oos_return: float
    oos_sharpe: float  # NaN when the fold held a zero-variance (flat) position
    oos_cagr: float


@dataclass(frozen=True)
class NullSummary:
    """Where the observed statistic falls in one tier of the randomized-price null."""

    tier: str  # "returns_level" (Tier 1) | "full_engine" (Tier 2)
    observed: float
    percentile: float
    p_value: float
    threshold: float
    passed: bool
    n_paths: int


@dataclass(frozen=True)
class CISummary:
    """A block-bootstrap BCa confidence interval for one headline metric."""

    metric: str  # "sharpe" | "cagr"
    point: float
    lower: float
    upper: float
    confidence: float


@dataclass(frozen=True)
class RunMetadata:
    """Everything needed to attribute and reproduce a run (the manifest's provenance block)."""

    run_id: str
    symbol: str
    snapshot_id: str | None
    seed: int
    periods_per_year: int
    fee_bps: float
    slippage_bps: float
    starting_cash: float
    lookback: int
    skip: int
    vol_window: int
    target_vol: float
    rebalance_every: int
    max_leverage: float
    allow_short: bool
    train_size: int
    test_size: int
    embargo: int
    anchored: bool
    n_bars: int
    first_ts: str  # ISO; provenance only
    last_ts: str
    quantstats_version: str


@dataclass(frozen=True)
class GauntletReport:
    """The full validation result for one run — the single object the renderer consumes."""

    metadata: RunMetadata
    oos_metrics: Mapping[str, float]  # engine OOS: sharpe, cagr, annualized_vol, max_drawdown, ...
    folds: tuple[FoldSummary, ...]
    nulls: tuple[NullSummary, ...]  # returns_level + full_engine
    cis: tuple[CISummary, ...]  # sharpe + cagr
    outcomes: tuple[ValidationOutcome, ...]  # one per gate (the alpha_core contract)
    passed: bool  # all gates passed


def build_outcomes(
    *,
    oos_metrics: Mapping[str, float],
    nulls: Sequence[NullSummary],
    cis: Sequence[CISummary],
) -> tuple[ValidationOutcome, ...]:
    """Map the gauntlet gates to ``alpha_core.ValidationOutcome``s (spec §8 gates 2–4).

    - ``walk_forward_oos`` (gate 2): passes when a finite OOS Sharpe was produced.
    - ``randomized_price_null`` (gate 3): passes only when the observed statistic beats the
      threshold percentile in *every* tier (conservative — Tier-1 returns-level AND Tier-2
      full-engine).
    - ``bootstrap_ci`` (gate 4): passes when the Sharpe BCa interval's lower bound clears zero (the
      risk-adjusted edge is bounded away from zero); the interval itself is always reported.
    """
    sharpe = float(oos_metrics.get("sharpe", math.nan))
    walk_forward = ValidationOutcome(
        name="walk_forward_oos",
        passed=math.isfinite(sharpe),
        detail={k: v for k, v in oos_metrics.items() if math.isfinite(v)},
    )

    null_detail: dict[str, float] = {}
    for n in nulls:
        null_detail[f"{n.tier}_percentile"] = n.percentile
        null_detail[f"{n.tier}_p_value"] = n.p_value
    null = ValidationOutcome(
        name="randomized_price_null",
        passed=len(nulls) > 0 and all(n.passed for n in nulls),
        detail=null_detail,
    )

    sharpe_ci = next((c for c in cis if c.metric == "sharpe"), None)
    ci_detail: dict[str, float] = (
        {}
        if sharpe_ci is None
        else {
            "sharpe_lower": sharpe_ci.lower,
            "sharpe_point": sharpe_ci.point,
            "sharpe_upper": sharpe_ci.upper,
        }
    )
    bootstrap_ci = ValidationOutcome(
        name="bootstrap_ci",
        passed=sharpe_ci is not None and sharpe_ci.lower > 0.0,
        detail=ci_detail,
    )
    return (walk_forward, null, bootstrap_ci)


def _sanitize(obj: Any) -> Any:
    """Recursively replace non-finite floats with ``None`` so the manifest is strict-JSON valid."""
    if isinstance(obj, bool):  # bool is an int subclass; keep it a JSON boolean
        return obj
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, Mapping):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list | tuple):
        return [_sanitize(v) for v in obj]
    return obj


def report_to_manifest(report: GauntletReport) -> dict[str, Any]:
    """Serialize a ``GauntletReport`` to a deterministic, strict-JSON-valid manifest dict.

    Sorted-key serialization (by the writer) over this dict is byte-identical for identical runs
    (spec §11.4); ``NaN``/``inf`` become ``null`` so the manifest is valid JSON. The raw equity and
    trade series are written separately as Parquet, not embedded here.
    """
    manifest: dict[str, Any] = {
        "schema_version": _SCHEMA_VERSION,
        "run_id": report.metadata.run_id,
        "metadata": dataclasses.asdict(report.metadata),
        "oos_metrics": dict(report.oos_metrics),
        "folds": [dataclasses.asdict(f) for f in report.folds],
        "nulls": [dataclasses.asdict(n) for n in report.nulls],
        "cis": [dataclasses.asdict(c) for c in report.cis],
        "outcomes": [
            {"name": o.name, "passed": o.passed, "detail": dict(o.detail)} for o in report.outcomes
        ],
        "passed": report.passed,
    }
    return {k: _sanitize(v) for k, v in manifest.items()}
