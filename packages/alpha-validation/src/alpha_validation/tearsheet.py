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
from alpha_validation.verdict import VerdictSummary

_SCHEMA_VERSION = 2  # 2: null tiers carry convention_divergence / flagged_low_fidelity


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
    # Tier-1 only: |Sharpe(close-fill) - Sharpe(t+1-open-fill)| of the SAME surrogate weights on
    # the observed OOS window. Large values mark the close-fill convention as structurally
    # low-fidelity for this strategy (high signal-correlated turnover) - see
    # docs/investigations/2026-06-23-tier1-surrogate-crediting-bias.md.
    convention_divergence: float | None = None
    # True when this tier FAILED but was demoted to advisory: the divergence exceeded tolerance
    # while the faithful full-engine tier passed, so the fail is a surrogate-fidelity artifact.
    flagged_low_fidelity: bool = False


@dataclass(frozen=True)
class CISummary:
    """A block-bootstrap BCa confidence interval for one headline metric."""

    metric: str  # "sharpe" | "cagr"
    point: float
    lower: float
    upper: float
    confidence: float


@dataclass(frozen=True)
class DSRSummary:
    """Probabilistic + Deflated Sharpe verdict for the OOS returns (skew/kurtosis/length aware)."""

    sharpe: float  # per-observation OOS Sharpe
    psr: float  # P(true SR > 0)
    dsr: float  # PSR deflated against the expected-max Sharpe over n_trials
    expected_max_sharpe: float
    n_trials: int
    threshold: float
    passed: bool  # dsr >= threshold


@dataclass(frozen=True)
class CPCVSummary:
    """Distribution of OOS Sharpe across combinatorial purged cross-validation folds."""

    n_folds: int
    mean_sharpe: float
    std_sharpe: float
    frac_positive: float  # share of folds with a positive OOS Sharpe
    passed: bool  # mean OOS Sharpe across folds is positive


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
    strategy_name: str = "ts_momentum"
    strategy_params: tuple[tuple[str, float], ...] = ()  # per-strategy params, for full provenance


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
    dsr: DSRSummary | None = None  # probabilistic/deflated Sharpe (optional, back-compat default)
    cpcv: CPCVSummary | None = None  # combinatorial purged CV OOS distribution (optional)
    verdict: VerdictSummary | None = None  # A-F grade (a headline summary, not a pass/fail gate)


def build_outcomes(
    *,
    oos_metrics: Mapping[str, float],
    nulls: Sequence[NullSummary],
    cis: Sequence[CISummary],
    dsr: DSRSummary | None = None,
    cpcv: CPCVSummary | None = None,
) -> tuple[ValidationOutcome, ...]:
    """Map the gauntlet gates to ``alpha_core.ValidationOutcome``s (spec §8 gates 2–4 + extensions).

    - ``walk_forward_oos`` (gate 2): passes when a finite OOS Sharpe was produced.
    - ``randomized_price_null`` (gate 3): passes only when the observed statistic beats the
      threshold percentile in *every* tier (conservative — Tier-1 returns-level AND Tier-2
      full-engine). A tier marked ``flagged_low_fidelity`` counts as advisory: its FAIL is a
      documented surrogate-convention artifact (the faithful tier passed and the convention
      divergence exceeded tolerance), so it reports but does not veto.
    - ``bootstrap_ci`` (gate 4): passes when the Sharpe BCa interval's lower bound clears zero (the
      risk-adjusted edge is bounded away from zero); the interval itself is always reported.
    - ``deflated_sharpe`` (when provided): passes when the deflated Sharpe clears its threshold.
    - ``cpcv_oos`` (when provided): passes when the mean OOS Sharpe across CPCV folds is positive.

    The two trailing gates are appended only when their summaries are supplied, so the core
    three-gate contract is unchanged for callers that don't compute them.
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
        if n.convention_divergence is not None:
            null_detail[f"{n.tier}_convention_divergence"] = n.convention_divergence
        if n.flagged_low_fidelity:
            null_detail[f"{n.tier}_flagged_low_fidelity"] = 1.0
    null = ValidationOutcome(
        name="randomized_price_null",
        passed=len(nulls) > 0 and all(n.passed or n.flagged_low_fidelity for n in nulls),
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
    outcomes = [walk_forward, null, bootstrap_ci]

    if dsr is not None:
        outcomes.append(
            ValidationOutcome(
                name="deflated_sharpe",
                passed=dsr.passed,
                detail={"psr": dsr.psr, "dsr": dsr.dsr, "n_trials": float(dsr.n_trials)},
            )
        )
    if cpcv is not None:
        outcomes.append(
            ValidationOutcome(
                name="cpcv_oos",
                passed=cpcv.passed,
                detail={
                    "mean_sharpe": cpcv.mean_sharpe,
                    "std_sharpe": cpcv.std_sharpe,
                    "frac_positive": cpcv.frac_positive,
                },
            )
        )
    return tuple(outcomes)


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
        "dsr": dataclasses.asdict(report.dsr) if report.dsr is not None else None,
        "cpcv": dataclasses.asdict(report.cpcv) if report.cpcv is not None else None,
        "verdict": dataclasses.asdict(report.verdict) if report.verdict is not None else None,
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
  {_verdict_html(report)}
  {_dsr_cpcv_html(report)}
</section>
"""


# (oos_metrics key, human label) for the risk-metrics table, in display order.
_RISK_METRIC_LABELS: tuple[tuple[str, str], ...] = (
    ("value_at_risk", "Value-at-Risk (95%)"),
    ("expected_shortfall", "Expected Shortfall (95%)"),
    ("risk_of_ruin", "Risk of Ruin"),
    ("max_drawdown", "Max Drawdown"),
)


def _verdict_html(report: GauntletReport) -> str:
    """The A-F Verdict grade table + the tail-risk metrics table (QuantPad-style headline)."""
    parts: list[str] = []
    if report.verdict is not None:
        v = report.verdict
        parts.append(
            "<h3>Verdict</h3>"
            '<table border="1" cellpadding="4" cellspacing="0">'
            "<tr><th>Edge</th><th>Robustness</th><th>Risk</th><th>Sample</th><th>Overall</th></tr>"
            f"<tr><td>{html.escape(v.edge)}</td><td>{html.escape(v.robustness)}</td>"
            f"<td>{html.escape(v.risk)}</td><td>{html.escape(v.sample)}</td>"
            f"<td><b>{html.escape(v.overall)}</b></td></tr></table>"
        )
    risk_rows = "".join(
        f"<tr><td>{label}</td><td>{_fmt(report.oos_metrics[key])}</td></tr>"
        for key, label in _RISK_METRIC_LABELS
        if key in report.oos_metrics
    )
    if risk_rows:
        parts.append(
            "<h3>Risk Metrics</h3>"
            '<table border="1" cellpadding="4" cellspacing="0">'
            "<tr><th>Metric</th><th>Value</th></tr>"
            f"{risk_rows}</table>"
        )
    return "\n".join(parts)


def _dsr_cpcv_html(report: GauntletReport) -> str:
    """The Deflated-Sharpe + CPCV tables, rendered only when those gates were computed."""
    parts: list[str] = []
    if report.dsr is not None:
        d = report.dsr
        parts.append(
            "<h3>Deflated / Probabilistic Sharpe</h3>"
            '<table border="1" cellpadding="4" cellspacing="0">'
            "<tr><th>PSR</th><th>DSR</th><th>E[max SR]</th><th>Trials</th>"
            "<th>Threshold</th><th>Result</th></tr>"
            f"<tr><td>{_fmt(d.psr)}</td><td>{_fmt(d.dsr)}</td>"
            f"<td>{_fmt(d.expected_max_sharpe)}</td><td>{d.n_trials}</td>"
            f"<td>{_fmt(d.threshold)}</td><td>{'PASS' if d.passed else 'FAIL'}</td></tr></table>"
        )
    if report.cpcv is not None:
        c = report.cpcv
        parts.append(
            "<h3>Combinatorial Purged Cross-Validation (OOS Sharpe)</h3>"
            '<table border="1" cellpadding="4" cellspacing="0">'
            "<tr><th>Folds</th><th>Mean Sharpe</th><th>Std Sharpe</th>"
            "<th>Frac &gt; 0</th><th>Result</th></tr>"
            f"<tr><td>{c.n_folds}</td><td>{_fmt(c.mean_sharpe)}</td><td>{_fmt(c.std_sharpe)}</td>"
            f"<td>{_fmt(c.frac_positive)}</td>"
            f"<td>{'PASS' if c.passed else 'FAIL'}</td></tr></table>"
        )
    return "\n".join(parts)


def _render_with_section(
    returns: FloatArray,
    timestamps: Sequence[datetime],
    *,
    title: str,
    section_html: str,
    output_path: Path,
    periods_per_year: int,
) -> None:
    """Write a quantstats HTML report for ``returns`` and inject a custom section near the end.

    The heavy rendering stack (matplotlib/quantstats) is imported lazily so merely importing
    ``alpha_validation`` stays cheap. ``periods_per_year`` is passed through explicitly because
    quantstats defaults to 365 (calendar) — our daily convention is 252. The HTML carries volatile
    fields (timestamps, fonts) and is deliberately outside the byte-identity guarantee (spec §11.4).
    """
    if len(returns) != len(timestamps):
        raise DataError(
            f"returns ({len(returns)}) and timestamps ({len(timestamps)}) must align one-to-one"
        )
    import logging

    import matplotlib

    matplotlib.use("Agg")  # headless: no display needed/available in CI
    logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)  # silence font fallbacks
    import pandas as pd
    import quantstats_lumi as qs

    index = pd.DatetimeIndex(list(timestamps))
    if index.tz is not None:
        index = index.tz_localize(None)  # quantstats works on naive daily dates
    series = pd.Series(returns, index=index, name="strategy")

    qs.reports.html(series, output=str(output_path), title=title, periods_per_year=periods_per_year)
    rendered = output_path.read_text(encoding="utf-8")
    marker = "</body>"
    injected = (
        rendered.replace(marker, section_html + marker, 1)
        if marker in rendered
        else rendered + section_html
    )
    output_path.write_text(injected, encoding="utf-8")


def render_tearsheet_html(
    report: GauntletReport,
    *,
    oos_returns: FloatArray,
    oos_timestamps: Sequence[datetime],
    output_path: Path,
    periods_per_year: int = 252,
) -> None:
    """Render the quantstats HTML tear sheet for the OOS returns + the gauntlet section."""
    _render_with_section(
        oos_returns,
        oos_timestamps,
        title=f"ALPHA OOS — {report.metadata.symbol}",
        section_html=_validation_section_html(report),
        output_path=output_path,
        periods_per_year=periods_per_year,
    )


def render_returns_tearsheet(
    returns: FloatArray,
    timestamps: Sequence[datetime],
    *,
    title: str,
    summary_rows: Sequence[tuple[str, str]],
    output_path: Path,
    periods_per_year: int = 252,
) -> None:
    """Render a quantstats tear sheet for an arbitrary return stream + a key/value summary table.

    Used by the portfolio and cross-sectional commands (which have no single-run ``GauntletReport``)
    to reach reporting parity with ``alpha validate``. ``summary_rows`` are ``(label, value)`` pairs
    shown above the quantstats body.
    """
    rows = "".join(
        f"<tr><td><b>{html.escape(label)}</b></td><td>{html.escape(value)}</td></tr>"
        for label, value in summary_rows
    )
    section = (
        '<section style="font-family: Arial, sans-serif; margin: 24px; max-width: 960px;">'
        f"<h2>{html.escape(title)}</h2>"
        '<table border="1" cellpadding="4" cellspacing="0">'
        f"{rows}</table></section>"
    )
    _render_with_section(
        returns,
        timestamps,
        title=title,
        section_html=section,
        output_path=output_path,
        periods_per_year=periods_per_year,
    )
