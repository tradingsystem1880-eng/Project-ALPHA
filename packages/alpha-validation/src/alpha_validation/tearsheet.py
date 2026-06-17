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
import html
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from alpha_core import DataError, ValidationOutcome
from alpha_validation.metrics import FloatArray

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


def _fmt(x: float) -> str:
    """Human-readable float for the HTML tables; non-finite renders as ``n/a``."""
    return f"{x:.4f}" if math.isfinite(x) else "n/a"


def _validation_section_html(report: GauntletReport) -> str:
    """The custom gauntlet section injected into the quantstats tear sheet.

    Carries what quantstats does not: the walk-forward fold table, both randomized-null tiers, the
    block-bootstrap BCa intervals, and the overall PASS/FAIL verdict.
    """
    verdict = "PASS" if report.passed else "FAIL"
    colour = "#1a7f37" if report.passed else "#cf222e"

    fold_rows = "".join(
        f"<tr><td>{f.index}</td><td>{f.test_start}:{f.test_end}</td><td>{f.n_test}</td>"
        f"<td>{_fmt(f.oos_return)}</td><td>{_fmt(f.oos_sharpe)}</td><td>{_fmt(f.oos_cagr)}</td></tr>"
        for f in report.folds
    )
    null_rows = "".join(
        f"<tr><td>{html.escape(n.tier)}</td><td>{_fmt(n.observed)}</td><td>{_fmt(n.percentile)}</td>"
        f"<td>{_fmt(n.p_value)}</td><td>{_fmt(n.threshold)}</td>"
        f"<td>{'PASS' if n.passed else 'FAIL'}</td><td>{n.n_paths}</td></tr>"
        for n in report.nulls
    )
    ci_rows = "".join(
        f"<tr><td>{html.escape(c.metric)}</td><td>{_fmt(c.point)}</td><td>{_fmt(c.lower)}</td>"
        f"<td>{_fmt(c.upper)}</td><td>{_fmt(c.confidence)}</td></tr>"
        for c in report.cis
    )
    return f"""
<section style="font-family: Arial, sans-serif; margin: 24px; max-width: 960px;">
  <h2>Validation Gauntlet</h2>
  <p style="font-size: 18px;">Overall verdict:
     <b style="color: {colour};">{verdict}</b>
     &nbsp;<span style="color:#57606a;">({html.escape(report.metadata.symbol)},
     run {html.escape(report.metadata.run_id)}, seed {report.metadata.seed})</span></p>
  <h3>Walk-Forward OOS</h3>
  <table border="1" cellpadding="4" cellspacing="0">
    <tr><th>Fold</th><th>Test window</th><th>n</th><th>Return</th><th>Sharpe</th><th>CAGR</th></tr>
    {fold_rows}
  </table>
  <h3>Randomized-Price Null</h3>
  <table border="1" cellpadding="4" cellspacing="0">
    <tr><th>Tier</th><th>Observed</th><th>Percentile</th><th>p-value</th>
        <th>Threshold</th><th>Result</th><th>Paths</th></tr>
    {null_rows}
  </table>
  <h3>Block-Bootstrap BCa Confidence Intervals</h3>
  <table border="1" cellpadding="4" cellspacing="0">
    <tr><th>Metric</th><th>Point</th><th>Lower</th><th>Upper</th><th>Confidence</th></tr>
    {ci_rows}
  </table>
</section>
"""


def render_tearsheet_html(
    report: GauntletReport,
    *,
    oos_returns: FloatArray,
    oos_timestamps: Sequence[datetime],
    output_path: Path,
    periods_per_year: int = 252,
) -> None:
    """Render the quantstats HTML tear sheet for the OOS returns + the gauntlet section.

    The heavy rendering stack (matplotlib/quantstats) is imported lazily so merely importing
    ``alpha_validation`` stays cheap. ``periods_per_year`` is passed through explicitly because
    quantstats defaults to 365 (calendar) — our daily convention is 252, and the tear sheet must
    agree with the manifest. The HTML carries volatile fields (timestamps, fonts) and is therefore
    deliberately outside the byte-identity guarantee (spec §11.4).
    """
    if len(oos_returns) != len(oos_timestamps):
        raise DataError(
            f"oos_returns ({len(oos_returns)}) and oos_timestamps ({len(oos_timestamps)}) "
            "must align one-to-one"
        )
    import logging

    import matplotlib

    matplotlib.use("Agg")  # headless: no display needed/available in CI
    logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)  # silence font fallbacks
    import pandas as pd
    import quantstats_lumi as qs

    index = pd.DatetimeIndex(list(oos_timestamps))
    if index.tz is not None:
        index = index.tz_localize(None)  # quantstats works on naive daily dates
    series = pd.Series(oos_returns, index=index, name="strategy")

    qs.reports.html(
        series,
        output=str(output_path),
        title=f"ALPHA OOS — {report.metadata.symbol}",
        periods_per_year=periods_per_year,
    )
    rendered = output_path.read_text(encoding="utf-8")
    section = _validation_section_html(report)
    marker = "</body>"
    if marker in rendered:
        injected = rendered.replace(marker, section + marker, 1)
    else:
        injected = rendered + section
    output_path.write_text(injected, encoding="utf-8")
