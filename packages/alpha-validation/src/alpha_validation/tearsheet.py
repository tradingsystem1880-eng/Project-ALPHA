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

from collections.abc import Mapping
from dataclasses import dataclass

from alpha_core import ValidationOutcome


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
