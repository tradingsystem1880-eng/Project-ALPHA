"""Figure builders: mlskill."""

from __future__ import annotations

from alpha_cli.figures import _sources as src
from alpha_cli.figures._common import BuildContext, pct
from alpha_research.figures import (
    FigureSpec,
    LineMark,
    Panel,
    ScatterMark,
    TableMark,
)


def state_conditioned_performance(ctx: BuildContext) -> FigureSpec:
    frame = src.require(ctx.rdir, "state_performance.parquet", "state_key")
    categories = tuple(f"State {index + 1}" for index in range(frame.height))
    x = tuple(float(index) for index in range(frame.height))
    raw = src.floats(frame["raw_crps"], name="raw_crps")
    calibrated = src.floats(frame["calibrated_crps"], name="calibrated_crps")
    fallback = tuple(bool(value) for value in frame["used_pooled_fallback"].to_list())
    rows = tuple(
        (
            categories[index],
            str(frame["state_key"][index]),
            str(frame["sample_count"][index]),
            "pooled" if fallback[index] else "state-specific",
        )
        for index in range(frame.height)
    )
    improved = sum(after < before for before, after in zip(raw, calibrated, strict=True))
    return ctx.spec(
        "state_conditioned_performance",
        x_label="Frozen market state",
        x_kind="category",
        x_categories=categories,
        artifacts=("state_performance.parquet",),
        answer=f"Calibration lowered CRPS in {improved} of {len(raw)} reported states.",
        panels=(
            Panel(
                panel_id="state_loss",
                y_label="Mean CRPS (ratio)",
                y_unit="ratio",
                marks=(
                    ScatterMark(x=x, y=raw, role="neutral", marker="o", label="Raw"),
                    ScatterMark(x=x, y=calibrated, role="subject", marker="D", label="Calibrated"),
                ),
            ),
            Panel(
                panel_id="state_table",
                y_label="State diagnostics (count)",
                y_unit="count",
                legend=False,
                marks=(
                    TableMark(
                        columns=("State", "Frozen labels", "OOS n", "Estimate"),
                        rows=rows,
                    ),
                ),
            ),
        ),
    )


def calibrated_reliability(ctx: BuildContext) -> FigureSpec:
    frame = src.require(ctx.rdir, "calibration_reliability.parquet")
    splits = src.strings(frame["split"])
    x = tuple(float(index) for index in range(frame.height))
    raw_crps = src.floats(frame["raw_crps"], name="raw_crps")
    calibrated_crps = src.floats(frame["calibrated_crps"], name="calibrated_crps")
    nominal = src.floats(frame["nominal_coverage"], name="nominal_coverage")
    raw_coverage = src.floats(frame["raw_coverage"], name="raw_coverage")
    calibrated_coverage = src.floats(frame["calibrated_coverage"], name="calibrated_coverage")
    oos = splits.index("oos") if "oos" in splits else len(splits) - 1
    return ctx.spec(
        "calibrated_reliability",
        x_label="Frozen evaluation split",
        x_kind="category",
        x_categories=splits,
        artifacts=("calibration_reliability.parquet",),
        answer=(
            f"OOS calibrated CRPS was {calibrated_crps[oos]:.4f} versus "
            f"{raw_crps[oos]:.4f} raw; coverage was {pct(calibrated_coverage[oos])}."
        ),
        panels=(
            Panel(
                panel_id="calibration_loss",
                y_label="CRPS (ratio)",
                y_unit="ratio",
                marks=(
                    ScatterMark(x=x, y=raw_crps, role="neutral", label="Raw"),
                    ScatterMark(x=x, y=calibrated_crps, role="subject", label="Calibrated"),
                ),
            ),
            Panel(
                panel_id="calibration_coverage",
                y_label="Coverage (probability)",
                y_unit="probability",
                y_limits=(0.0, 1.0),
                marks=(
                    LineMark(x=x, y=nominal, role="reference", dashed=True, label="Nominal"),
                    ScatterMark(x=x, y=raw_coverage, role="neutral", label="Raw"),
                    ScatterMark(
                        x=x,
                        y=calibrated_coverage,
                        role="subject",
                        marker="D",
                        label="Calibrated",
                    ),
                ),
            ),
        ),
    )


def forecast_abstention(ctx: BuildContext) -> FigureSpec:
    frame = src.require(ctx.rdir, "calibrated_origins.parquet", "origin_ts")
    ts = src.epochs(frame["origin_ts"])
    candidates = frame["candidate"].to_list()
    signals = tuple(
        float(signal) if candidate is not None and signal is not None else 0.0
        for candidate, signal in zip(candidates, frame["signal"].to_list(), strict=True)
    )
    emitted = sum(candidate is not None for candidate in candidates)
    blocker_counts: dict[str, int] = {}
    for blockers in frame["blocker_codes"].to_list():
        for blocker in blockers or ():
            blocker_counts[str(blocker)] = blocker_counts.get(str(blocker), 0) + 1
    rows = tuple(
        (blocker, f"{count}")
        for blocker, count in sorted(blocker_counts.items(), key=lambda item: (-item[1], item[0]))
    ) or (("NO_BLOCKERS", "0"),)
    return ctx.spec(
        "forecast_abstention",
        x_label="OOS forecast origin (UTC)",
        artifacts=("calibrated_origins.parquet",),
        answer=(
            f"The candidate emitted at {emitted} of {len(candidates)} OOS origins and abstained "
            f"at {len(candidates) - emitted}."
        ),
        panels=(
            Panel(
                panel_id="candidate_signal",
                y_label="Candidate signal (index)",
                y_unit="index",
                y_zero_rule=True,
                marks=(ScatterMark(x=ts, y=signals, role="subject", marker="o", size=24.0),),
            ),
            Panel(
                panel_id="abstention_reasons",
                y_label="Blocked origins (count)",
                y_unit="count",
                legend=False,
                marks=(TableMark(columns=("Blocker", "Origins"), rows=rows),),
            ),
        ),
    )
