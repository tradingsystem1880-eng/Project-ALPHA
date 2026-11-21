"""Figure builders: nulls."""

from __future__ import annotations

import math

import numpy as np

from alpha_cli.figures import _sources as src
from alpha_cli.figures._common import BuildContext, _hist, _observed_label, pct
from alpha_core import DataError
from alpha_research.figures import (
    BarMark,
    ErrorBarMark,
    FigureSpec,
    HistogramMark,
    Mark,
    Panel,
    RuleMark,
    ScatterMark,
    ValueLabel,
)


# --------------------------------------------------------------------------- robustness
def null_distribution(ctx: BuildContext) -> FigureSpec:
    frame = src.require(ctx.rdir, "nulls.parquet", "tier", "path_index")
    tiers = ctx.manifest.get("nulls")
    summary = (
        {str(item.get("tier")): item for item in tiers if isinstance(item, dict)}
        if isinstance(tiers, list)
        else {}
    )
    panels: list[Panel] = []
    verdicts: list[str] = []
    for tier in ("returns_level", "full_engine", "bar_permutation"):
        subset = frame.filter(frame["tier"] == tier)
        if subset.is_empty():
            continue
        values = src.floats(subset["statistic"], name="statistic")
        low, high = min(values), max(values)
        span = (high - low) or 1.0
        bins = 41
        edges = tuple(low + span * index / bins for index in range(bins + 1))
        counts = [0.0] * bins
        for value in values:
            counts[min(bins - 1, int((value - low) / span * bins))] += 1
        info = summary.get(tier, {})
        observed = info.get("observed")
        percentile = info.get("percentile")
        marks: list[Mark] = [
            HistogramMark(
                edges=edges,
                counts=tuple(counts),
                role="substrate",
                alpha=0.9,
                label=f"{len(values):,} no-edge paths",
            )
        ]
        if isinstance(observed, int | float):
            marks.append(
                RuleMark(
                    orientation="vertical",
                    position=float(observed),
                    role="feature",
                    width=1.6,
                    dashed=False,
                    label="Observed",
                    annotate=ValueLabel(text=_observed_label(float(observed), percentile)),
                )
            )
            if isinstance(percentile, int | float):
                verdicts.append(f"{tier} {pct(float(percentile), 0)}")
        panels.append(
            Panel(
                panel_id=tier,
                y_label=f"{tier.replace('_', '-').capitalize()} paths (n)",
                y_unit="count",
                marks=tuple(marks),
            )
        )
    if not panels:
        raise DataError("no null tiers stored for this run")
    return ctx.spec(
        "null_distribution",
        x_label="Out-of-sample Sharpe of a no-edge path (sharpe)",
        x_kind="numeric",
        artifacts=("nulls.parquet",),
        answer=(
            "Observed result sits at " + ", ".join(verdicts) + " of the no-edge distribution."
            if verdicts
            else "Null distributions are stored but the manifest records no observed percentile."
        ),
        panels=tuple(panels),
    )


def fold_sharpe(ctx: BuildContext) -> FigureSpec:
    folds = ctx.manifest.get("folds")
    if not isinstance(folds, list) or not folds:
        raise DataError("this run records no walk-forward folds")
    index: list[float] = []
    sharpe: list[float] = []
    degenerate: list[float] = []
    returns: list[float] = []
    for position, fold in enumerate(folds):
        if not isinstance(fold, dict):
            continue
        raw = fold.get("oos_sharpe")
        value = float(raw) if isinstance(raw, int | float) and math.isfinite(float(raw)) else None
        index.append(float(position))
        returns.append(float(fold.get("oos_return") or 0.0))
        if value is None:
            degenerate.append(float(position))
            sharpe.append(0.0)
        else:
            sharpe.append(value)
    if not index:
        raise DataError("fold records are malformed")
    defined = [value for position, value in enumerate(sharpe) if float(position) not in degenerate]
    mean = sum(defined) / len(defined) if defined else 0.0
    positive = sum(1 for value in defined if value > 0)
    marks: list[Mark] = [
        BarMark(x=tuple(index), y=tuple(sharpe), signed_colour=True, width=0.6),
        RuleMark(
            orientation="horizontal",
            position=mean,
            role="feature",
            width=1.2,
            annotate=ValueLabel(text=f"mean {mean:.2f}", ha="right", dx_pt=-6.0),
        ),
    ]
    if degenerate:
        marks.append(
            ScatterMark(
                x=tuple(degenerate),
                y=tuple(0.0 for _ in degenerate),
                hollow=True,
                role="neutral",
                size=40.0,
                label="Degenerate (flat fold)",
            )
        )
    return ctx.spec(
        "fold_sharpe",
        x_label="Walk-forward fold",
        x_kind="numeric",
        artifacts=("manifest.json",),
        answer=(
            f"{positive} of {len(defined)} folds with a defined Sharpe were positive, averaging "
            f"{mean:.2f}"
            + (
                f"; {len(degenerate)} fold(s) were flat and are shown hollow."
                if degenerate
                else "."
            )
        ),
        panels=(
            Panel(
                panel_id="sharpe",
                y_label="Fold OOS Sharpe (sharpe)",
                y_unit="sharpe",
                y_zero_rule=True,
                marks=tuple(marks),
            ),
            Panel(
                panel_id="return",
                y_label="Fold OOS return (%)",
                y_unit="percent",
                y_percent=True,
                y_zero_rule=True,
                legend=False,
                marks=(BarMark(x=tuple(index), y=tuple(returns), signed_colour=True, width=0.6),),
            ),
        ),
    )


def confidence_intervals(ctx: BuildContext) -> FigureSpec:
    cis = ctx.manifest.get("cis")
    if not isinstance(cis, list) or not cis:
        raise DataError("this run records no bootstrap confidence intervals")
    names: list[str] = []
    point: list[float] = []
    lower: list[float] = []
    upper: list[float] = []
    for item in cis:
        if not isinstance(item, dict):
            continue
        try:
            low = float(item["lower"])
            high = float(item["upper"])
            mid = float(item.get("point", (low + high) / 2))
        except (KeyError, TypeError, ValueError) as error:
            raise DataError(f"malformed confidence interval {item!r}") from error
        names.append(str(item.get("metric") or item.get("statistic") or item.get("name") or "?"))
        lower.append(low)
        upper.append(high)
        point.append(mid)
    straddling = [n for n, low, high in zip(names, lower, upper, strict=True) if low <= 0 <= high]
    return ctx.spec(
        "confidence_intervals",
        x_label="Estimate with 95% bootstrap interval",
        x_kind="numeric",
        artifacts=("manifest.json",),
        answer=(
            f"{len(straddling)} of {len(names)} intervals straddle zero"
            + (f" ({', '.join(straddling)})." if straddling else ", so every metric clears zero.")
        ),
        panels=(
            Panel(
                panel_id="forest",
                y_label="Metric",
                y_unit="category",
                legend=False,
                marks=(
                    ErrorBarMark(
                        categories=tuple(names),
                        point=tuple(point),
                        lower=tuple(lower),
                        upper=tuple(upper),
                    ),
                    RuleMark(orientation="vertical", position=0.0, role="reference", width=1.0),
                ),
            ),
        ),
    )


def mcpt_null_histogram(ctx: BuildContext) -> FigureSpec:
    """Best in-sample score per bar permutation, with the observed best marked."""
    frame = src.require(ctx.rdir, "mcpt_null.parquet", "path_index")
    values = src.floats(frame["statistic"], name="statistic")
    edges, counts = _hist(np.asarray(values, dtype=np.float64))
    observed = ctx.manifest.get("observed")
    stat = observed.get("statistic") if isinstance(observed, dict) else None
    percentile = ctx.manifest.get("percentile")
    p_value = ctx.manifest.get("p_value")
    marks: list[Mark] = [
        HistogramMark(
            edges=edges,
            counts=counts,
            role="substrate",
            alpha=0.9,
            label=f"{len(values):,} re-optimised permutations",
        )
    ]
    if isinstance(stat, int | float):
        marks.append(
            RuleMark(
                orientation="vertical",
                position=float(stat),
                role="feature",
                width=1.6,
                dashed=False,
                label="Observed best",
                annotate=ValueLabel(text=_observed_label(float(stat), percentile)),
            )
        )
    verdict = "The manifest records no observed percentile for the permutation bests"
    if (
        isinstance(percentile, int | float)
        and isinstance(p_value, int | float)
        and not isinstance(percentile, bool)
        and not isinstance(p_value, bool)
    ):
        verdict = (
            f"The observed best in-sample Sharpe beats {pct(float(percentile), 0)} of the "
            f"permutation bests (p = {float(p_value):.3f})"
        )
    return ctx.spec(
        "mcpt_null_histogram",
        x_label="Best in-sample Sharpe over the grid (sharpe)",
        x_kind="numeric",
        artifacts=("mcpt_null.parquet",),
        answer=f"{verdict}; an optimisation-overfit check, not out-of-sample evidence.",
        panels=(
            Panel(
                panel_id="permutations",
                y_label="Permutations (n)",
                y_unit="count",
                marks=tuple(marks),
            ),
        ),
    )
