"""Figure builders: mlstability."""

from __future__ import annotations

from alpha_cli.figures import _sources as src
from alpha_cli.figures._common import BuildContext, _truncation, pct
from alpha_research.figures import (
    BarMark,
    FigureSpec,
    LineMark,
    Mark,
    Panel,
    ScatterMark,
    TableMark,
)


def ensemble_disagreement(ctx: BuildContext) -> FigureSpec:
    frame = src.require(ctx.rdir, "ensemble_diagnostics.parquet", "fold", "target_ts", "symbol")
    picked = src.sample(frame.height)
    view = frame[picked]
    lightgbm = src.floats(view["lightgbm_rank"], name="lightgbm_rank")
    ridge = src.floats(view["ridge_rank"], name="ridge_rank")
    disagreement = src.floats(view["disagreement"], name="disagreement")
    mean_disagreement = sum(disagreement) / len(disagreement)
    ordered = sorted(disagreement)
    q95 = ordered[round(0.95 * (len(ordered) - 1))]
    return ctx.spec(
        "ensemble_disagreement",
        x_label="LightGBM percentile rank",
        x_kind="numeric",
        artifacts=("ensemble_diagnostics.parquet",),
        truncation=_truncation(frame.height, len(picked), "predictions"),
        answer=f"Mean member rank disagreement was {mean_disagreement:.3f}.",
        panels=(
            Panel(
                panel_id="member_ranks",
                y_label="Ridge percentile rank (ratio)",
                y_unit="ratio",
                marks=(
                    LineMark(
                        x=(0.0, 1.0),
                        y=(0.0, 1.0),
                        role="reference",
                        dashed=True,
                        label="Agreement",
                    ),
                    ScatterMark(x=lightgbm, y=ridge, role="subject", size=12.0),
                ),
            ),
            Panel(
                panel_id="disagreement_summary",
                y_label="Disagreement summary (count)",
                y_unit="count",
                legend=False,
                marks=(
                    TableMark(
                        columns=("Diagnostic", "Value"),
                        rows=(
                            ("Predictions shown", f"{len(disagreement):,}"),
                            ("Mean absolute rank gap", f"{mean_disagreement:.4f}"),
                            ("95th percentile gap", f"{q95:.4f}"),
                            ("Maximum gap", f"{max(disagreement):.4f}"),
                        ),
                    ),
                ),
            ),
        ),
    )


def feature_stability(ctx: BuildContext) -> FigureSpec:
    frame = src.require(ctx.rdir, "ml_feature_stability.parquet", "feature", "fold")
    features = src.strings(frame["feature"])
    gains = src.floats(frame["gain"], name="gain")
    means: dict[str, list[float]] = {}
    for feature, gain in zip(features, gains, strict=True):
        means.setdefault(feature, []).append(gain)
    selected = sorted(
        means, key=lambda feature: (-sum(means[feature]) / len(means[feature]), feature)
    )[:8]
    marks: list[Mark] = []
    for index, feature in enumerate(selected):
        rows = frame.filter(frame["feature"] == feature).sort("fold")
        marks.append(
            LineMark(
                x=src.floats(rows["fold"], name="fold"),
                y=src.floats(rows["gain"], name="gain"),
                role="categorical",
                palette_index=index,
                label=feature,
            )
        )
    return ctx.spec(
        "feature_stability",
        x_label="Training fold",
        x_kind="numeric",
        artifacts=("ml_feature_stability.parquet",),
        answer=f"The chart follows the {len(selected)} highest mean-gain features across refits.",
        panels=(
            Panel(
                panel_id="feature_gain",
                y_label="LightGBM gain (ratio)",
                y_unit="ratio",
                marks=tuple(marks),
            ),
        ),
    )


def ml_cost_sensitivity(ctx: BuildContext) -> FigureSpec:
    frame = src.require(ctx.rdir, "ml_cost_sensitivity.parquet", "cost_multiplier")
    x = src.floats(frame["cost_multiplier"], name="cost_multiplier")
    returns = src.floats(frame["total_return"], name="total_return")
    turnover = src.floats(frame["mean_turnover"], name="mean_turnover")
    declared_index = x.index(1.0) if 1.0 in x else 0
    return ctx.spec(
        "ml_cost_sensitivity",
        x_label="Multiple of declared costs",
        x_kind="numeric",
        artifacts=("ml_cost_sensitivity.parquet",),
        answer=(
            f"At declared costs the canonical replay returned {pct(returns[declared_index])}; "
            f"at 2x costs it returned {pct(returns[-1])}."
        ),
        panels=(
            Panel(
                panel_id="cost_return",
                y_label="Total return (%)",
                y_unit="percent",
                y_percent=True,
                y_zero_rule=True,
                marks=(BarMark(x=x, y=returns, signed_colour=True, width=0.3),),
            ),
            Panel(
                panel_id="cost_turnover",
                y_label="Mean turnover (ratio)",
                y_unit="ratio",
                legend=False,
                marks=(LineMark(x=x, y=turnover, role="neutral"),),
            ),
        ),
    )
