"""Figure builders: mcpaths."""

from __future__ import annotations

from typing import Any

import numpy as np

from alpha_cli.figures import _sources as src
from alpha_cli.figures._common import BuildContext, _hist, pct
from alpha_research.figures import (
    BandMark,
    FigureSpec,
    HistogramMark,
    LineMark,
    Panel,
    RuleMark,
    ValueLabel,
)

# --------------------------------------------------------------------------- Monte Carlo
_MONTE_CARLO_LABELS = {
    "iid_empirical": "IID empirical",
    "regime_switching": "Causal regime Markov",
    "student_t": "Student-t",
    "kronos_synthetic": "Kronos synthetic OHLCV",
}


_MONTE_CARLO_ASSUMPTIONS = {
    "iid_empirical": "IID draws with replacement from OOS account returns",
    "regime_switching": "two-state first-order Markov chain with empirical state emissions",
    "student_t": "IID Student-t log-account returns mapped back to simple returns",
    "kronos_synthetic": "pinned autoregressive OHLCV generation plus fresh full-engine replay",
}


def _mc_families(frame: Any) -> tuple[str, ...]:
    available = {str(value) for value in frame["family"].unique().to_list()}
    return tuple(family for family in _MONTE_CARLO_LABELS if family in available)


def _mc_path_count(ctx: BuildContext) -> int:
    value = ctx.field("paths")
    return int(value) if isinstance(value, int | float) else 0


def monte_carlo_equity_fans(ctx: BuildContext) -> FigureSpec:
    frame = src.require(ctx.rdir, "paths.parquet", "family", "path_index", "step")
    observed = src.require(ctx.rdir, "observed_oos.parquet", "step")
    observed_x = tuple(float(value) for value in observed["step"].to_list())
    observed_equity = src.floats(observed["equity"], name="observed equity")
    panels: list[Panel] = []
    total_paths = 0
    for family in _mc_families(frame):
        rows = frame.filter(frame["family"] == family).sort("path_index", "step")
        n_paths = int(rows["path_index"].n_unique())
        horizon = int(rows["step"].n_unique())
        matrix = np.asarray(rows["account_return"].to_list(), dtype=np.float64).reshape(
            n_paths, horizon
        )
        equity = np.concatenate((np.ones((n_paths, 1)), np.cumprod(1.0 + matrix, axis=1)), axis=1)
        x = tuple(float(value) for value in range(horizon + 1))
        q05, q25, q50, q75, q95 = np.quantile(equity, (0.05, 0.25, 0.5, 0.75, 0.95), axis=0)
        panels.append(
            Panel(
                panel_id=f"fan_{family}",
                y_label=f"{_MONTE_CARLO_LABELS[family]} equity (x)",
                y_unit="multiple",
                note=_MONTE_CARLO_ASSUMPTIONS[family],
                marks=(
                    BandMark(
                        x=x,
                        lower=tuple(q05),
                        upper=tuple(q95),
                        role="substrate",
                        alpha=0.35,
                        label="5-95%",
                    ),
                    BandMark(
                        x=x,
                        lower=tuple(q25),
                        upper=tuple(q75),
                        role="neutral",
                        alpha=0.45,
                        label="25-75%",
                    ),
                    LineMark(x=x, y=tuple(q50), role="subject", label="Median"),
                    LineMark(
                        x=observed_x,
                        y=observed_equity,
                        role="feature",
                        label="Observed OOS",
                    ),
                ),
            )
        )
        total_paths += n_paths
    return ctx.spec(
        "monte_carlo_equity_fans",
        x_label="OOS account-return step",
        x_kind="numeric",
        artifacts=("paths.parquet", "observed_oos.parquet"),
        answer=(
            f"This run contributes {len(panels)} of four required family panels and "
            f"contains {total_paths:,} simulated account paths; observed OOS equity is overlaid."
        ),
        panels=tuple(panels),
    )


def monte_carlo_terminal_returns(ctx: BuildContext) -> FigureSpec:
    frame = src.require(ctx.rdir, "path_metrics.parquet", "family", "path_index")
    panels: list[Panel] = []
    medians: list[float] = []
    families = _mc_families(frame)
    for family in families:
        values = np.asarray(
            frame.filter(frame["family"] == family)["terminal_return"].to_list(),
            dtype=np.float64,
        )
        edges, counts = _hist(values)
        median = float(np.median(values))
        medians.append(median)
        panels.append(
            Panel(
                panel_id=f"terminal_{family}",
                y_label=f"{_MONTE_CARLO_LABELS[family]} paths",
                y_unit="count",
                note=f"{len(values):,} paths · {_MONTE_CARLO_ASSUMPTIONS[family]}",
                marks=(
                    HistogramMark(edges=edges, counts=counts, role="subject", alpha=0.8),
                    RuleMark(
                        orientation="vertical",
                        position=0.0,
                        role="reference",
                        annotate=ValueLabel(text="break-even"),
                    ),
                    RuleMark(
                        orientation="vertical",
                        position=median,
                        role="feature",
                        annotate=ValueLabel(text=f"median {pct(median)}"),
                    ),
                ),
            )
        )
    return ctx.spec(
        "monte_carlo_terminal_returns",
        x_label="Terminal account return",
        x_kind="numeric",
        artifacts=("path_metrics.parquet",),
        answer="; ".join(
            f"{_MONTE_CARLO_LABELS[family]} median {pct(median)}"
            for family, median in zip(families, medians, strict=True)
        )
        + f" across {frame['path_index'].n_unique():,} paths per available family.",
        panels=tuple(panels),
    )


def monte_carlo_drawdown_ruin(ctx: BuildContext) -> FigureSpec:
    frame = src.require(ctx.rdir, "path_metrics.parquet", "family", "path_index")
    panels: list[Panel] = []
    ruin_rates: list[float] = []
    families = _mc_families(frame)
    for family in families:
        rows = frame.filter(frame["family"] == family)
        values = np.asarray(rows["maximum_drawdown"].to_list(), dtype=np.float64)
        ruined = [bool(value) for value in rows["ruined"].to_list()]
        ruin_rate = sum(ruined) / len(ruined)
        ruin_rates.append(ruin_rate)
        edges, counts = _hist(values)
        panels.append(
            Panel(
                panel_id=f"drawdown_{family}",
                y_label=f"{_MONTE_CARLO_LABELS[family]} paths",
                y_unit="count",
                note=(
                    f"{len(values):,} paths · 50% drawdown ruin rate {pct(ruin_rate)} · "
                    f"{_MONTE_CARLO_ASSUMPTIONS[family]}"
                ),
                marks=(
                    HistogramMark(edges=edges, counts=counts, role="down", alpha=0.8),
                    RuleMark(
                        orientation="vertical",
                        position=0.5,
                        role="feature",
                        annotate=ValueLabel(text="50% ruin boundary"),
                    ),
                ),
            )
        )
    return ctx.spec(
        "monte_carlo_drawdown_ruin",
        x_label="Maximum peak-to-trough account drawdown",
        x_kind="numeric",
        artifacts=("path_metrics.parquet",),
        answer="; ".join(
            f"{_MONTE_CARLO_LABELS[family]} ruin {pct(rate)}"
            for family, rate in zip(families, ruin_rates, strict=True)
        )
        + ".",
        panels=tuple(panels),
    )
