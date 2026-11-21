"""Figure builders: mcregimes."""

from __future__ import annotations

import numpy as np

from alpha_cli.figures import _sources as src
from alpha_cli.figures._common import BuildContext, pct
from alpha_cli.figures.builders_mcpaths import _mc_path_count
from alpha_research.figures import (
    FigureSpec,
    HeatmapMark,
    HistogramMark,
    LineMark,
    Mark,
    Panel,
    ScatterMark,
)


def monte_carlo_regimes(ctx: BuildContext) -> FigureSpec:
    emissions = src.require(ctx.rdir, "regime_emissions.parquet", "step")
    diagnostics = src.require(ctx.rdir, "regime_diagnostics.parquet", "from_state", "to_state")
    all_returns = np.asarray(emissions["account_return"].to_list(), dtype=np.float64)
    edges = np.histogram_bin_edges(all_returns, bins=31)
    emission_marks: list[Mark] = []
    labels = ("Calm", "Volatile")
    for state, label in enumerate(labels):
        values = np.asarray(
            emissions.filter(emissions["state"] == state)["account_return"].to_list(),
            dtype=np.float64,
        )
        counts, _ = np.histogram(values, bins=edges)
        emission_marks.append(
            HistogramMark(
                edges=tuple(float(value) for value in edges),
                counts=tuple(float(value) for value in counts),
                role="categorical",
                palette_index=state,
                alpha=0.55,
                label=label,
            )
        )
    matrix = [[0.0, 0.0], [0.0, 0.0]]
    for row in diagnostics.iter_rows(named=True):
        probability = row["transition_probability"]
        matrix[int(row["from_state"])][int(row["to_state"])] = (
            0.0 if probability is None else float(probability)
        )
    return ctx.spec(
        "monte_carlo_regimes",
        x_label="Account return (emissions) / destination state (matrix)",
        x_kind="numeric",
        artifacts=("regime_emissions.parquet", "regime_diagnostics.parquet"),
        answer=(
            f"The frozen causal classifier assigned {(emissions['state'] == 0).sum()} calm and "
            f"{(emissions['state'] == 1).sum()} volatile OOS observations; the linked run "
            f"simulates {_mc_path_count(ctx):,} first-order Markov paths."
        ),
        panels=(
            Panel(
                panel_id="emissions",
                y_label="OOS observations",
                y_unit="count",
                note="Trailing volatility is prior-known; the state boundary is training-frozen.",
                marks=tuple(emission_marks),
            ),
            Panel(
                panel_id="transition_matrix",
                y_label="Origin state",
                y_unit="category",
                note="Rows are origin states; each row sums to one when estimable.",
                marks=(
                    HeatmapMark(
                        rows=labels,
                        columns=labels,
                        values=tuple(tuple(row) for row in matrix),
                        cell_text=tuple(tuple(f"{value:.2f}" for value in row) for row in matrix),
                        colorbar_label="Transition probability",
                    ),
                ),
            ),
        ),
    )


def kronos_monte_carlo_calibration(ctx: BuildContext) -> FigureSpec:
    frame = src.require(ctx.rdir, "calibration_origins.parquet", "origin_index")
    x = tuple(float(value) for value in frame["origin_index"].to_list())
    crps = src.floats(frame["crps"], name="Kronos CRPS")
    crps_rw = src.floats(frame["crps_rw"], name="random-walk CRPS")
    crps_bootstrap = src.floats(frame["crps_bootstrap"], name="bootstrap CRPS")
    nominal = (0.5, 0.8, 0.9)
    realised = tuple(
        sum(bool(value) for value in frame[column].to_list()) / frame.height
        for column in ("cover50", "cover80", "cover90")
    )
    return ctx.spec(
        "kronos_monte_carlo_calibration",
        x_label="Rolling origin index / nominal coverage",
        x_kind="numeric",
        artifacts=("calibration_origins.parquet",),
        answer=(
            f"Mean Kronos CRPS is {sum(crps) / len(crps):.4f} versus random-walk "
            f"{sum(crps_rw) / len(crps_rw):.4f} and bootstrap "
            f"{sum(crps_bootstrap) / len(crps_bootstrap):.4f}; realised 80% coverage is "
            f"{pct(realised[1])} across {frame.height:,} rolling origins and "
            f"{_mc_path_count(ctx):,} synthetic full-engine paths."
        ),
        panels=(
            Panel(
                panel_id="crps_skill",
                y_label="CRPS (lower is better)",
                y_unit="ratio",
                note="Pinned Kronos samples versus random-walk and stationary-bootstrap baselines.",
                marks=(
                    LineMark(x=x, y=crps, role="subject", label="Kronos"),
                    LineMark(x=x, y=crps_rw, role="neutral", label="Random walk"),
                    LineMark(
                        x=x,
                        y=crps_bootstrap,
                        role="reference",
                        label="Stationary bootstrap",
                    ),
                ),
            ),
            Panel(
                panel_id="coverage",
                y_label="Realised coverage",
                y_unit="probability",
                y_limits=(0.0, 1.0),
                note="Empirical coverage is calibration evidence, not a guarantee of future paths.",
                marks=(
                    LineMark(
                        x=(0.0, 1.0),
                        y=(0.0, 1.0),
                        role="reference",
                        dashed=True,
                        label="Perfect calibration",
                    ),
                    ScatterMark(
                        x=nominal,
                        y=realised,
                        role="subject",
                        size=48.0,
                        label="Observed",
                    ),
                ),
            ),
        ),
    )
