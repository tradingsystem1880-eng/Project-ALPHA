"""Figure builders: forecast."""

from __future__ import annotations

from alpha_cli.figures import _sources as src
from alpha_cli.figures._common import BuildContext, pct
from alpha_core import DataError
from alpha_research.figures import (
    BandMark,
    FigureSpec,
    LineMark,
    Mark,
    Panel,
    RuleMark,
    ScatterMark,
    ValueLabel,
    ZoneMark,
)


# --------------------------------------------------------------------------- forecast
def forecast_fan(ctx: BuildContext) -> FigureSpec:
    quantiles = src.require(ctx.rdir, "quantiles.parquet", "ts")
    history = src.require(ctx.rdir, "history.parquet", "ts")
    h_ts = src.epochs(history["ts"])
    h_close = src.floats(history["close"], name="close")
    q_ts = src.epochs(quantiles["ts"])
    q05 = src.floats(quantiles["q05"], name="q05")
    q25 = src.floats(quantiles["q25"], name="q25")
    q50 = src.floats(quantiles["q50"], name="q50")
    q75 = src.floats(quantiles["q75"], name="q75")
    q95 = src.floats(quantiles["q95"], name="q95")
    origin = h_ts[-1]
    move = q50[-1] / h_close[-1] - 1.0
    width = (q95[-1] - q05[-1]) / h_close[-1]
    return ctx.spec(
        "forecast_fan",
        x_label="Date (UTC)",
        artifacts=("quantiles.parquet", "history.parquet"),
        answer=(
            f"The median path ends {pct(move)} from the last close, with a 90% interval "
            f"spanning {pct(width)} of price."
        ),
        panels=(
            Panel(
                panel_id="cone",
                y_label="Close (native quote)",
                y_unit="price",
                marks=(
                    BandMark(
                        x=q_ts,
                        lower=q05,
                        upper=q95,
                        role="subject",
                        alpha=0.14,
                        label="90% interval",
                    ),
                    BandMark(
                        x=q_ts,
                        lower=q25,
                        upper=q75,
                        role="subject",
                        alpha=0.26,
                        label="50% interval",
                    ),
                    LineMark(x=h_ts, y=h_close, role="substrate", label="History", width=1.1),
                    LineMark(
                        x=q_ts,
                        y=q50,
                        role="feature",
                        dashed=True,
                        label="Median",
                        end_label=ValueLabel(text=f"{q50[-1]:.2f}"),
                    ),
                    RuleMark(
                        orientation="vertical",
                        position=origin,
                        role="reference",
                        width=1.0,
                        label="Forecast origin",
                    ),
                ),
            ),
        ),
    )


def forecast_skill(ctx: BuildContext) -> FigureSpec:
    frame = src.require(ctx.rdir, "origins.parquet", "origin_ts")
    ts = src.epochs(frame["origin_ts"])
    crps = src.floats(frame["crps"], name="crps")
    rw = src.floats(frame["crps_rw"], name="crps_rw")
    boot = src.floats(frame["crps_bootstrap"], name="crps_bootstrap")
    pre = [bool(value) for value in frame["pre_cutoff"].to_list()]
    skill = tuple(1.0 - c / b if b else 0.0 for c, b in zip(crps, rw, strict=True))
    beat = sum(1 for value in skill if value > 0)
    marks: list[Mark] = [
        LineMark(x=ts, y=crps, role="categorical", palette_index=0, label="Model", width=1.5),
        LineMark(x=ts, y=rw, role="categorical", palette_index=1, label="Random walk", width=1.2),
        LineMark(x=ts, y=boot, role="categorical", palette_index=2, label="Bootstrap", width=1.2),
    ]
    if any(pre) and not all(pre):
        boundary = next(t for t, flag in zip(ts, pre, strict=True) if not flag)
        marks.append(
            ZoneMark(
                x0=ts[0],
                x1=boundary,
                role="feature",
                alpha=0.08,
                label="Pre-cutoff (may be in training)",
            )
        )
    return ctx.spec(
        "forecast_skill",
        x_label="Forecast origin (UTC)",
        artifacts=("origins.parquet",),
        answer=(
            f"The model beat the random-walk baseline at {beat} of {len(skill)} origins "
            f"({pct(beat / len(skill), 0)})."
        ),
        panels=(
            Panel(
                panel_id="crps",
                y_label="CRPS (lower is better)",
                y_unit="ratio",
                height_ratio=1.6,
                marks=tuple(marks),
            ),
            Panel(
                panel_id="skill",
                y_label="Skill vs random walk",
                y_unit="ratio",
                y_zero_rule=True,
                legend=False,
                marks=(LineMark(x=ts, y=skill, role="subject", fill_to=0.0),),
            ),
        ),
    )


def forecast_calibration(ctx: BuildContext) -> FigureSpec:
    frame = src.require(ctx.rdir, "origins.parquet", "origin_ts")
    levels = ((0.5, "cover50"), (0.8, "cover80"), (0.9, "cover90"))
    nominal: list[float] = []
    realised: list[float] = []
    for level, column in levels:
        flags = [bool(value) for value in frame[column].to_list()]
        if not flags:
            continue
        nominal.append(level)
        realised.append(sum(1 for flag in flags if flag) / len(flags))
    if not nominal:
        raise DataError("no coverage columns stored for this run")
    gaps = [abs(r - n) for n, r in zip(nominal, realised, strict=True)]
    return ctx.spec(
        "forecast_calibration",
        x_label="Nominal coverage (probability)",
        x_kind="numeric",
        artifacts=("origins.parquet",),
        answer=(
            f"Realised coverage differs from nominal by up to {pct(max(gaps))} across the "
            f"{len(nominal)} stored levels."
        ),
        panels=(
            Panel(
                panel_id="calibration",
                y_label="Realised coverage (probability)",
                y_unit="probability",
                y_limits=(0.0, 1.0),
                marks=(
                    LineMark(
                        x=(0.0, 1.0),
                        y=(0.0, 1.0),
                        role="reference",
                        dashed=True,
                        label="Perfect calibration",
                    ),
                    ScatterMark(
                        x=tuple(nominal),
                        y=tuple(realised),
                        role="subject",
                        size=48.0,
                        label="Observed",
                    ),
                ),
            ),
        ),
    )
