"""Figure builders: curves."""

from __future__ import annotations

from alpha_cli.figures import _sources as src
from alpha_cli.figures._common import _MONTHS, BuildContext, _truncation, pct
from alpha_core import DataError
from alpha_research.figures import (
    FigureSpec,
    HeatmapMark,
    LineMark,
    Panel,
)


# --------------------------------------------------------------------------- performance
def equity_underwater(ctx: BuildContext) -> FigureSpec:
    """One builder for every run: labels from the full series (``rule_periods``)."""
    from alpha_cli.figures import rule_periods

    return rule_periods.build(ctx, "equity_underwater", None)


def equity_vs_passive(ctx: BuildContext) -> FigureSpec:
    """Growth ratio to buy and hold in the caption, end label and lower panel alike."""
    from alpha_cli.figures import rule_periods

    return rule_periods.build(ctx, "equity_vs_passive", None)


def rolling_risk(ctx: BuildContext) -> FigureSpec:
    frame = src.require(ctx.rdir, "rolling_metrics.parquet", "ts")
    picked = src.sample(frame.height)
    view = frame[picked]
    ts = src.epochs(view["ts"])
    window = int(view["window"].to_list()[0])
    returns = src.floats(view["return_value"], name="return_value")
    vol = src.floats(view["volatility"], name="volatility")
    sharpe_raw = src.optional_floats(view["sharpe"])
    defined = [(t, s) for t, s in zip(ts, sharpe_raw, strict=True) if s is not None]
    if not defined:
        raise DataError("rolling Sharpe is undefined across the whole window")
    sharpe_ts = tuple(item[0] for item in defined)
    sharpe = tuple(float(item[1]) for item in defined)
    positive = sum(1 for value in sharpe if value > 0) / len(sharpe)
    return ctx.spec(
        "rolling_risk",
        x_label="Date (UTC)",
        artifacts=("rolling_metrics.parquet",),
        truncation=_truncation(frame.height, len(picked), "windows"),
        answer=(
            f"Rolling {window}-session Sharpe was positive in {pct(positive, 0)} of windows, "
            f"ending at {sharpe[-1]:.2f} with {pct(vol[-1])} annualised volatility."
        ),
        panels=(
            Panel(
                panel_id="sharpe",
                y_label=f"Sharpe ({window}d)",
                y_unit="sharpe",
                y_zero_rule=True,
                legend=False,
                marks=(LineMark(x=sharpe_ts, y=sharpe, role="subject"),),
            ),
            Panel(
                panel_id="vol",
                y_label="Volatility (%, ann.)",
                y_unit="percent",
                y_percent=True,
                legend=False,
                marks=(LineMark(x=ts, y=vol, role="subject"),),
            ),
            Panel(
                panel_id="return",
                y_label=f"Return (%, {window}d)",
                y_unit="percent",
                y_percent=True,
                y_zero_rule=True,
                legend=False,
                marks=(LineMark(x=ts, y=returns, role="subject"),),
            ),
        ),
    )


def monthly_heatmap(ctx: BuildContext) -> FigureSpec:
    frame = src.require(ctx.rdir, "calendar_returns.parquet")
    months = frame.filter(frame["period_type"] == "month").sort(["year", "month"])
    years_frame = frame.filter(frame["period_type"] == "year").sort("year")
    if months.is_empty():
        raise DataError("no monthly returns stored for this run")
    grid: dict[int, list[float | None]] = {}
    for year, month, value in zip(
        months["year"].to_list(),
        months["month"].to_list(),
        months["return_value"].to_list(),
        strict=True,
    ):
        row = grid.setdefault(int(year), [None] * 12)
        row[int(month) - 1] = float(value)
    annual = {
        int(year): float(value)
        for year, value in zip(
            years_frame["year"].to_list(), years_frame["return_value"].to_list(), strict=True
        )
    }
    ordered = sorted(grid)
    rows = tuple(str(year) for year in ordered)
    # The annual total is deliberately excluded from the colour scale: a +9.7% year on the
    # same ramp as monthly returns saturates it and flattens every month into one shade.
    # It keeps its number and sits on the neutral background, which also reads correctly
    # as "this column is a summary, not a thirteenth month".
    values = tuple(tuple([*grid[year], None]) for year in ordered)
    cell_text = tuple(
        tuple(
            [
                *("" if cell is None else f"{cell * 100:.1f}" for cell in grid[year]),
                "" if annual.get(year) is None else f"{annual[year] * 100:.1f}",
            ]
        )
        for year in ordered
    )
    flat = [cell for row in values for cell in row[:12] if cell is not None]
    best, worst = max(flat), min(flat)
    return ctx.spec(
        "monthly_heatmap",
        x_label="Calendar month",
        x_kind="category",
        x_categories=(*_MONTHS, "Year"),
        artifacts=("calendar_returns.parquet",),
        answer=(
            f"Across {len(ordered)} calendar years the best month returned {pct(best)} and the "
            f"worst {pct(worst)}."
        ),
        panels=(
            Panel(
                panel_id="calendar",
                y_label="Year",
                y_unit="category",
                legend=False,
                marks=(
                    HeatmapMark(
                        rows=rows,
                        columns=(*_MONTHS, "Year"),
                        values=values,
                        cell_text=cell_text,
                        colorbar_label="Return (%)",
                        diverging_center=0.0,
                    ),
                ),
            ),
        ),
    )
