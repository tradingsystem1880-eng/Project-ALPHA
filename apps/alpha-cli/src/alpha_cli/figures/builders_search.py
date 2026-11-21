"""Figure builders: search."""

from __future__ import annotations

import json
from datetime import datetime

from alpha_cli.figures import _sources as src
from alpha_cli.figures._common import BuildContext, _truncation, mult
from alpha_core import DataError
from alpha_research.figures import (
    FigureSpec,
    HeatmapMark,
    LineMark,
    Mark,
    Panel,
    TableMark,
)


# --------------------------------------------------------------------------- optimisation
def optim_trials(ctx: BuildContext) -> FigureSpec:
    frame = src.require(ctx.rdir, "trials.parquet", "trial", "step")
    groups = frame.partition_by("trial", maintain_order=True)
    best_trial = ctx.manifest.get("best_trial")
    marks: list[Mark] = []
    finals: list[float] = []
    for group in groups[:400]:
        trial = int(group["trial"].to_list()[0])
        returns = src.floats(group["oos_return"], name="oos_return")
        equity, value = [], 1.0
        for step in returns:
            value *= 1.0 + step
            equity.append(value)
        finals.append(value)
        chosen = best_trial is not None and trial == best_trial
        marks.append(
            LineMark(
                x=tuple(float(i) for i in range(len(equity))),
                y=tuple(equity),
                role="feature" if chosen else "substrate",
                alpha=1.0 if chosen else 0.5,
                label="Selected configuration" if chosen else None,
                z=2 if chosen else 0,
            )
        )
    if not marks:
        raise DataError("no trials stored for this run")
    return ctx.spec(
        "optim_trials",
        x_label="Out-of-sample step",
        x_kind="numeric",
        artifacts=("trials.parquet",),
        truncation=_truncation(len(groups), len(marks), "trials"),
        answer=(
            f"{len(groups):,} configurations were tried; their final equity ranged from "
            f"{mult(min(finals))} to {mult(max(finals))}."
        ),
        panels=(
            Panel(
                panel_id="trials",
                y_label="Growth of 1 (x initial)",
                y_unit="multiple",
                marks=tuple(marks),
            ),
        ),
    )


def optim_surface(ctx: BuildContext) -> FigureSpec:
    import json

    frame = src.require(ctx.rdir, "trial_ledger.parquet", "trial")
    # The ledger stores each config as ordered [key, value] pairs, not an object.
    configs = [dict(json.loads(value)) for value in frame["config_json"].to_list()]
    status = src.strings(frame["status"])
    sharpe = src.optional_floats(frame["annualized_sharpe"])
    varying = sorted(
        {
            key
            for key in {k for config in configs for k in config}
            if len({json.dumps(config.get(key), sort_keys=True) for config in configs}) > 1
        }
    )
    if not varying:
        raise DataError("no parameter varied across this sweep")
    x_key = varying[0]
    y_key = varying[1] if len(varying) > 1 else None
    columns = sorted({_axis_value(config.get(x_key)) for config in configs}, key=_numeric_key)
    rows = (
        sorted({str(config.get(y_key)) for config in configs}, key=_numeric_key) if y_key else ["-"]
    )
    grid: dict[tuple[str, str], float | None] = {}
    failed: set[tuple[str, str]] = set()
    for config, state, value in zip(configs, status, sharpe, strict=True):
        cell = (_axis_value(config.get(y_key)) if y_key else "-", _axis_value(config.get(x_key)))
        if state != "passed" or value is None:
            failed.add(cell)
            grid.setdefault(cell, None)
        else:
            grid[cell] = value
    values = tuple(tuple(grid.get((row, column)) for column in columns) for row in rows)
    text = tuple(tuple(_cell_text(grid, failed, row, col) for col in columns) for row in rows)
    ok = [value for value in grid.values() if value is not None]
    return ctx.spec(
        "optim_surface",
        x_label=f"{x_key}",
        x_kind="category",
        x_categories=tuple(columns),
        artifacts=("trial_ledger.parquet",),
        answer=(
            f"{len(ok)} of {len(configs)} configurations completed; out-of-sample Sharpe ranged "
            f"from {min(ok):.2f} to {max(ok):.2f}."
            if ok
            else f"None of the {len(configs)} configurations completed successfully."
        ),
        panels=(
            Panel(
                panel_id="surface",
                y_label=f"{y_key or 'configuration'}",
                y_unit="category",
                legend=False,
                marks=(
                    HeatmapMark(
                        rows=tuple(rows),
                        columns=tuple(columns),
                        values=values,
                        cell_text=text,
                        colorbar_label="OOS Sharpe (sharpe)",
                        diverging_center=0.0,
                    ),
                ),
            ),
        ),
    )


def _cell_text(
    grid: dict[tuple[str, str], float | None],
    failed: set[tuple[str, str]],
    row: str,
    column: str,
) -> str:
    """A failed configuration reads as an explicit x, never as an empty cell."""
    if (row, column) in failed:
        return "x"
    value = grid.get((row, column))
    return "" if value is None else f"{value:.2f}"


def _axis_value(value: object) -> str:
    """Render a swept parameter as an axis tick.

    Grid values arrive as floats even when the parameter is a lookback in sessions, and
    a tick reading "63.0" claims a precision the sweep never had.
    """
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _numeric_key(value: str) -> tuple[int, float, str]:
    try:
        return (0, float(value), "")
    except ValueError:
        return (1, 0.0, value)


def research_discovery_trace(ctx: BuildContext) -> FigureSpec:
    """Render the immutable D1 chart artifact without recomputing research statistics."""
    path = ctx.rdir / "chart-data.json"
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 16 * 1024 * 1024:
        raise DataError("chart-data.json is missing, unsafe, or exceeds 16 MiB")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DataError("chart-data.json is not valid bounded JSON") from exc
    if not isinstance(document, dict):
        raise DataError("chart-data.json must contain one object")
    raw_series = document.get("series")
    if not isinstance(raw_series, list) or not raw_series:
        raise DataError("chart-data.json requires at least one recorded series")

    marks: list[Mark] = []
    returned = 0
    original = 0
    for index, raw in enumerate(raw_series):
        if not isinstance(raw, dict) or not isinstance(raw.get("points"), list):
            raise DataError("chart-data.json series must contain points")
        points = raw["points"]
        original = max(original, len(points))
        picked = src.sample(len(points))
        x: list[float] = []
        y: list[float] = []
        for point_index in picked:
            point = points[point_index]
            if not isinstance(point, dict):
                raise DataError("chart-data.json contains a malformed point")
            stamp = point.get("ts")
            value = point.get("value")
            if (
                not isinstance(stamp, str)
                or isinstance(value, bool)
                or not isinstance(value, int | float)
            ):
                raise DataError("chart-data.json point requires an ISO timestamp and value")
            try:
                parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            except ValueError as exc:
                raise DataError("chart-data.json contains an invalid timestamp") from exc
            if parsed.tzinfo is None:
                raise DataError("chart-data.json timestamps must be timezone-aware")
            x.append(parsed.timestamp())
            y.append(float(value))
        returned = max(returned, len(picked))
        label = raw.get("label")
        marks.append(
            LineMark(
                x=tuple(x),
                y=tuple(y),
                role="categorical",
                palette_index=index,
                label=label if isinstance(label, str) and label else f"Series {index + 1}",
            )
        )

    sample_size = document.get("sample_size")
    effective = document.get("effective_sample_size")
    answer = document.get("plain_language_answer")
    if (
        isinstance(sample_size, bool)
        or not isinstance(sample_size, int)
        or isinstance(effective, bool)
        or not isinstance(effective, int | float)
        or not isinstance(answer, str)
        or not answer.strip()
    ):
        raise DataError("chart-data.json has invalid sample or answer metadata")
    rows = (
        ("Sample observations", f"{sample_size:,}"),
        ("Effective event sample", f"{float(effective):.1f}"),
        ("Evidence phase", str(document.get("evidence_phase", "unknown")).upper()),
        ("Watermark", str(document.get("watermark", "EXPLORATORY"))),
        ("Dataset SHA-256", str(document.get("dataset_sha256", ""))[:16] + "…"),
        ("Protocol SHA-256", str(document.get("protocol_sha256", ""))[:16] + "…"),
    )
    return ctx.spec(
        "research_discovery_trace",
        x_label="Bar end (UTC)",
        artifacts=("chart-data.json",),
        answer=answer,
        truncation=_truncation(original, returned, "chart points"),
        panels=(
            Panel(
                panel_id="discovery_trace",
                y_label=str(document.get("y_label", "Recorded value")),
                y_unit="price",
                height_ratio=2.0,
                marks=tuple(marks),
            ),
            Panel(
                panel_id="evidence_table",
                y_label="Evidence record (count)",
                y_unit="count",
                legend=False,
                marks=(
                    TableMark(
                        columns=("Recorded field", "Value"),
                        rows=rows,
                        align=("left", "right"),
                    ),
                ),
            ),
        ),
    )
