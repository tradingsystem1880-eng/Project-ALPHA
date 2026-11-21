"""Figure builders: tradestats."""

from __future__ import annotations

from alpha_cli.figures import _sources as src
from alpha_cli.figures._common import BuildContext, money, pct
from alpha_core import DataError
from alpha_research.figures import (
    BarMark,
    FigureSpec,
    HistogramMark,
    LineMark,
    Mark,
    Panel,
    RuleMark,
    ValueLabel,
)


# --------------------------------------------------------------------------- trades
def trade_pnl(ctx: BuildContext) -> FigureSpec:
    frame = src.require(ctx.rdir, "trades.parquet", "entry_ts")
    pnl = src.floats(frame["realized_pnl"], name="realized_pnl")
    ordinal = tuple(float(index + 1) for index in range(len(pnl)))
    cumulative: list[float] = []
    total = 0.0
    for value in pnl:
        total += value
        cumulative.append(total)
    wins = sum(1 for value in pnl if value > 0)
    best, worst = max(pnl), min(pnl)
    share = abs(best) / sum(abs(value) for value in pnl) if any(pnl) else 0.0
    return ctx.spec(
        "trade_pnl",
        x_label="Trade (chronological)",
        x_kind="numeric",
        artifacts=("trades.parquet",),
        answer=(
            f"{len(pnl):,} closed trades, {wins:,} profitable ({pct(wins / len(pnl), 0)}); the "
            f"single best made {money(best)} and the worst lost {money(abs(worst))}, with the "
            f"best trade accounting for {pct(share, 0)} of gross P&L."
        ),
        panels=(
            Panel(
                panel_id="pnl",
                y_label="Realised P&L (account currency)",
                y_unit="account_currency",
                y_zero_rule=True,
                legend=False,
                marks=(BarMark(x=ordinal, y=pnl, signed_colour=True, width=0.8),),
            ),
            Panel(
                panel_id="cumulative",
                y_label="Cumulative P&L (account currency)",
                y_unit="account_currency",
                y_zero_rule=True,
                legend=False,
                marks=(
                    LineMark(
                        x=ordinal,
                        y=tuple(cumulative),
                        role="subject",
                        step=True,
                        end_label=ValueLabel(text=money(cumulative[-1])),
                    ),
                ),
            ),
        ),
    )


def holding_period(ctx: BuildContext) -> FigureSpec:
    frame = src.require(ctx.rdir, "trades.parquet", "entry_ts")
    entry = src.epochs(frame["entry_ts"])
    exit_ = src.epochs(frame["exit_ts"])
    pnl = src.floats(frame["realized_pnl"], name="realized_pnl")
    days = tuple((b - a) / 86400.0 for a, b in zip(entry, exit_, strict=True))
    if not days:
        raise DataError("no closed trades to measure")
    span = max(days) or 1.0
    # Fixed edges so the shape does not shift when the trade count changes.
    bin_count = 20
    edges = tuple(span * index / bin_count for index in range(bin_count + 1))

    def counts(subset: tuple[float, ...]) -> tuple[float, ...]:
        out = [0.0] * bin_count
        for value in subset:
            index = min(bin_count - 1, int(value / span * bin_count))
            out[index] += 1
        return tuple(out)

    winners = tuple(day for day, value in zip(days, pnl, strict=True) if value > 0)
    losers = tuple(day for day, value in zip(days, pnl, strict=True) if value <= 0)
    ordered = sorted(days)
    median = ordered[len(ordered) // 2]
    marks: list[Mark] = []
    if winners:
        marks.append(
            HistogramMark(
                edges=edges, counts=counts(winners), role="up", alpha=0.75, label="Profitable"
            )
        )
    if losers:
        marks.append(
            HistogramMark(
                edges=edges, counts=counts(losers), role="down", alpha=0.55, label="Unprofitable"
            )
        )
    marks.append(
        RuleMark(
            orientation="vertical",
            position=median,
            role="feature",
            width=1.2,
            annotate=ValueLabel(text=f"median {median:.0f}d"),
        )
    )
    return ctx.spec(
        "holding_period",
        x_label="Holding period (calendar days)",
        x_kind="numeric",
        artifacts=("trades.parquet",),
        answer=(
            f"The median trade was held {median:.0f} calendar days, ranging from "
            f"{min(days):.0f} to {max(days):.0f}."
        ),
        panels=(
            Panel(
                panel_id="holding",
                y_label="Trades (count)",
                y_unit="count",
                marks=tuple(marks),
            ),
        ),
    )


def trade_runs_test(ctx: BuildContext) -> FigureSpec:
    """Trade signs in entry order under the runs z-score the native tear sheet recorded."""
    trades = src.require(ctx.rdir, "trades.parquet", "entry_ts")
    pnl = src.floats(trades["realized_pnl"], name="realized_pnl")
    stats = src.require(ctx.rdir, "trade_statistics.parquet", "metric")
    row = stats.filter(stats["metric"] == "trade_runs_z")
    if row.is_empty():
        raise DataError("trade_statistics.parquet carries no trade_runs_z row")
    available = bool(row["available"][0])
    signs = tuple(1.0 if value > 0 else -1.0 if value < 0 else 0.0 for value in pnl)
    runs = 1 + sum(1 for a, b in zip(signs, signs[1:], strict=False) if a != b)
    ordinal = tuple(float(index + 1) for index in range(len(signs)))
    marks: list[Mark] = [BarMark(x=ordinal, y=signs, signed_colour=True, width=0.8)]
    if available:
        (z,) = src.floats(row["value"], name="trade_runs_z")
        reading = "clustered" if z < 0 else "alternating" if z > 0 else "exactly as expected"
        answer = (
            f"{len(signs):,} trades form {runs:,} runs of equal sign; the runs z-score is "
            f"{z:+.2f} ({reading} relative to independence)."
        )
        marks.append(
            RuleMark(
                orientation="horizontal",
                position=0.0,
                role="feature",
                width=0.8,
                annotate=ValueLabel(text=f"runs z = {z:+.2f}", dy_pt=8.0),
            )
        )
    else:
        reason = str(row["unavailable_reason"][0])
        answer = (
            f"{len(signs):,} trades form {runs:,} runs of equal sign; the runs test is "
            f"undefined here ({reason.replace('_', ' ')})."
        )
    return ctx.spec(
        "trade_runs_test",
        x_label="Trade (entry order)",
        x_kind="numeric",
        artifacts=("trades.parquet", "trade_statistics.parquet"),
        answer=answer,
        panels=(
            Panel(
                panel_id="signs",
                y_label="Trade sign (win +1 / loss -1)",
                y_unit="index",
                y_zero_rule=True,
                legend=False,
                marks=tuple(marks),
            ),
        ),
    )
