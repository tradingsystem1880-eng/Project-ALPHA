"""One builder per catalogue figure: immutable artifacts in, a FigureSpec out.

Builders own two things the renderer deliberately does not: which marks tell this
figure's story, and the run-specific one-line answer. Everything numeric is read from a
stored artifact or a stored manifest value -- nothing is recomputed here beyond trivial
presentation arithmetic (rebasing, cumulative products), so a figure can never disagree
with the tear sheet beside it.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from alpha_cli.figures import _sources as src
from alpha_core import DataError
from alpha_research.figures import (
    BandMark,
    BarMark,
    CandleMark,
    ErrorBarMark,
    FigureSpec,
    HeatmapMark,
    HistogramMark,
    LineMark,
    Mark,
    Panel,
    RuleMark,
    ScatterMark,
    TableMark,
    ValueLabel,
    ZoneMark,
    figure_definition,
)

_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


# --------------------------------------------------------------------------- formatting
def pct(value: float, places: int = 1) -> str:
    return f"{value * 100:.{places}f}%"


def mult(value: float) -> str:
    return f"{value:.2f}x"


def money(value: float) -> str:
    return f"{value:,.0f}"


def _day(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, tz=UTC).strftime("%Y-%m-%d")


class BuildContext:
    """Everything a builder is allowed to read."""

    def __init__(self, *, run_id: str, rdir: Path, manifest: dict[str, Any], data_dir: Path):
        self.run_id = run_id
        self.rdir = rdir
        self.manifest = manifest
        self.data_dir = data_dir

    def field(self, *names: str) -> object:
        """Read a manifest field from the top level or the metadata block.

        Run kinds disagree about where identity lives: a backtest puts `symbol` at the
        top level, a validate run nests it under `metadata`. Callers should not care.
        """
        metadata = self.manifest.get("metadata")
        nested = metadata if isinstance(metadata, dict) else {}
        for name in names:
            for source in (self.manifest, nested):
                value = source.get(name)
                if value not in (None, "", []):
                    return value
        return None

    @property
    def command(self) -> str:
        value = self.manifest.get("command")
        return value if isinstance(value, str) else "unknown"

    @property
    def symbol(self) -> str:
        value = self.field("symbol", "label")
        if isinstance(value, str):
            return value
        symbols = self.field("symbols")
        if isinstance(symbols, list) and symbols:
            return ", ".join(str(item) for item in symbols[:4])
        return "-"

    @property
    def strategy(self) -> str:
        value = self.field("strategy", "strategy_name")
        return value if isinstance(value, str) else self.command

    def subtitle(self, extra: str = "") -> str:
        parts = [self.symbol, self.strategy]
        window = self._window()
        if window:
            parts.append(window)
        if extra:
            parts.append(extra)
        return "  ·  ".join(parts)

    def _window(self) -> str:
        start = self.field("start", "first_ts")
        end = self.field("end", "last_ts")
        if isinstance(start, str) and isinstance(end, str):
            return f"{start[:10]} to {end[:10]}"
        return ""

    def caption(self, *artifacts: str) -> str:
        snapshot = self.field("snapshot_hash")
        short = snapshot[:8] if isinstance(snapshot, str) and snapshot else "no snapshot"
        version = self.manifest.get("artifact_contract_version", "-")
        sources = " ".join(sorted(artifacts))
        return f"run {self.run_id} · snapshot {short} · contract v{version} · UTC · {sources}"

    def spec(
        self,
        figure_id: str,
        *,
        panels: tuple[Panel, ...],
        x_label: str,
        x_kind: str = "time",
        answer: str,
        artifacts: tuple[str, ...],
        truncation: str | None = None,
        x_categories: tuple[str, ...] = (),
    ) -> FigureSpec:
        definition = figure_definition(figure_id)
        return FigureSpec(
            figure_id=figure_id,
            title=definition.title,
            subtitle=self.subtitle(),
            x_label=x_label,
            x_kind=x_kind,  # type: ignore[arg-type]
            x_categories=x_categories,
            panels=panels,
            question=definition.question,
            plain_language_answer=answer,
            uncertainty=definition.uncertainty,
            caveat=definition.caveat,
            caption=self.caption(*artifacts),
            source_artifacts=artifacts,
            truncation_note=truncation,
        )


def _truncation(original: int, returned: int, noun: str) -> str | None:
    """A figure must never lie by omission about how much it is showing."""
    if returned >= original:
        return None
    return f"showing {returned:,} of {original:,} {noun}"


# --------------------------------------------------------------------------- performance
def equity_underwater(ctx: BuildContext) -> FigureSpec:
    frame = src.require(ctx.rdir, "equity_curve.parquet", "ts")
    picked = src.sample(frame.height)
    view = frame[picked]
    ts = src.epochs(view["ts"])
    equity = src.rebase(src.floats(view["equity"], name="equity"))
    under = src.drawdown(equity)
    peaks: list[float] = []
    running = -math.inf
    for value in equity:
        running = max(running, value)
        peaks.append(running)
    worst = min(under)
    trough = ts[under.index(worst)]
    return ctx.spec(
        "equity_underwater",
        x_label="Date (UTC)",
        artifacts=("equity_curve.parquet",),
        truncation=_truncation(frame.height, len(picked), "sessions"),
        answer=(
            f"Capital ended at {mult(equity[-1])} of its start; the worst drawdown was "
            f"{pct(worst)} and troughed on {_day(trough)}."
        ),
        panels=(
            Panel(
                panel_id="equity",
                y_label="Growth of 1 (x initial)",
                y_unit="multiple",
                height_ratio=2.6,
                marks=(
                    LineMark(x=ts, y=tuple(peaks), role="substrate", label="Running peak"),
                    LineMark(
                        x=ts,
                        y=equity,
                        role="subject",
                        label="Equity",
                        end_label=ValueLabel(text=mult(equity[-1])),
                    ),
                ),
            ),
            Panel(
                panel_id="underwater",
                y_label="Drawdown (%)",
                y_unit="percent",
                y_percent=True,
                legend=False,
                marks=(
                    LineMark(x=ts, y=under, role="down", fill_to=0.0),
                    RuleMark(
                        orientation="horizontal",
                        position=worst,
                        role="feature",
                        width=1.0,
                        annotate=ValueLabel(text=f"worst {pct(worst)}", ha="right", dx_pt=-6.0),
                    ),
                ),
            ),
        ),
    )


def equity_vs_passive(ctx: BuildContext) -> FigureSpec:
    frame = src.require(ctx.rdir, "benchmark_comparison.parquet", "ts")
    available = frame["available"].to_list()
    if not any(bool(flag) for flag in available):
        reason = frame["unavailable_reason"].to_list()[0] or "benchmark_unavailable"
        raise DataError(f"no passive benchmark for this run ({reason})")
    picked = src.sample(frame.height)
    view = frame[picked]
    ts = src.epochs(view["ts"])
    strategy = src.rebase(src.floats(view["strategy_equity"], name="strategy_equity"))
    passive_raw = src.optional_floats(view["benchmark_equity"])
    if any(value is None for value in passive_raw):
        raise DataError("passive benchmark has gaps; refusing to interpolate a comparison")
    passive = src.rebase(tuple(float(value) for value in passive_raw if value is not None))
    excess: list[float] = []
    running = 1.0
    for index in range(len(strategy)):
        if index:
            s_ret = strategy[index] / strategy[index - 1] - 1.0
            b_ret = passive[index] / passive[index - 1] - 1.0
            running *= 1.0 + (s_ret - b_ret)
        excess.append(running - 1.0)
    if passive[-1] <= 0.0:
        # A passive index that ends at or below zero has no meaningful relative lead, and
        # dividing by it would abort the whole figure pack with a ZeroDivisionError.
        raise DataError("passive benchmark ends at or below zero; relative lead is undefined")
    lead = strategy[-1] - passive[-1]
    verdict = "ahead of" if lead > 0 else "behind"
    return ctx.spec(
        "equity_vs_passive",
        x_label="Date (UTC)",
        artifacts=("benchmark_comparison.parquet",),
        truncation=_truncation(frame.height, len(picked), "sessions"),
        answer=(
            f"Strategy finished at {mult(strategy[-1])} against {mult(passive[-1])} for the "
            f"passive price index -- {verdict} it by {pct(abs(lead) / passive[-1])}."
        ),
        panels=(
            Panel(
                panel_id="growth",
                y_label="Growth of 1 (x initial)",
                y_unit="multiple",
                height_ratio=2.2,
                marks=(
                    LineMark(
                        x=ts,
                        y=passive,
                        role="substrate",
                        label="Passive price index (no dividends)",
                    ),
                    LineMark(
                        x=ts,
                        y=strategy,
                        role="subject",
                        label="Strategy",
                        end_label=ValueLabel(text=mult(strategy[-1])),
                    ),
                ),
            ),
            Panel(
                panel_id="excess",
                y_label="Excess (%)",
                y_unit="percent",
                y_percent=True,
                y_zero_rule=True,
                legend=False,
                marks=(
                    LineMark(
                        x=ts,
                        y=tuple(excess),
                        role="feature" if excess[-1] > 0 else "down",
                        fill_to=0.0,
                        end_label=ValueLabel(text=pct(excess[-1])),
                    ),
                ),
            ),
        ),
    )


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


# --------------------------------------------------------------------------- signals
def price_signal(ctx: BuildContext) -> FigureSpec:
    rows, reason = src.bars(
        {
            "symbol": ctx.field("symbol"),
            "snapshot_id": ctx.field("snapshot_id"),
            "start": ctx.field("start"),
            "end": ctx.field("end"),
        },
        data_dir=ctx.data_dir,
    )
    if reason is not None or not rows:
        raise DataError(f"price bars unavailable for this run ({reason or 'no bars'})")
    ts = tuple(row["t"] for row in rows)
    marks: list[Mark] = [
        CandleMark(
            x=ts,
            open=tuple(row["o"] for row in rows),
            high=tuple(row["h"] for row in rows),
            low=tuple(row["l"] for row in rows),
            close=tuple(row["c"] for row in rows),
            alpha=0.85,
        )
        if len(rows) <= 400
        else LineMark(
            x=ts, y=tuple(row["c"] for row in rows), role="substrate", label="Close", width=1.0
        )
    ]

    annotations = src.frame(ctx.rdir, "chart_annotations.parquet", "annotation_id", "anchor_index")
    drawn, total = 0, 0
    if annotations is not None and not annotations.is_empty():
        groups = annotations.partition_by("annotation_id", maintain_order=True)
        total = len(groups)
        for group in groups[:40]:
            label = str(group["label"].to_list()[0])
            kind = str(group["kind"].to_list()[0])
            unit = str(group["unit"].to_list()[0])
            xs = src.epochs(group["ts"])
            ys = src.floats(group["value"], name="annotation value")
            if kind == "zone":
                marks.append(
                    ZoneMark(
                        x0=min(xs),
                        x1=max(xs),
                        role="feature",
                        alpha=0.12,
                        label=label if drawn == 0 else None,
                        corner_label=ValueLabel(text=label),
                    )
                )
            else:
                marks.append(
                    LineMark(
                        x=xs,
                        y=ys,
                        role="feature",
                        label=label if drawn == 0 else None,
                        end_label=ValueLabel(text=f"{label} {ys[-1]:.2f}{'' if unit else ''}"),
                    )
                )
            drawn += 1

    trace = src.frame(ctx.rdir, "execution_trace.parquet", "sequence_id")
    if trace is not None and not trace.is_empty():
        fills = trace.filter(trace["event_type"] == "fill")
        if not fills.is_empty():
            buys = fills.filter(fills["side"] == "BUY")
            sells = fills.filter(fills["side"] == "SELL")
            for subset, marker, role, label in (
                (buys, "^", "up", "Buy fill"),
                (sells, "v", "down", "Sell fill"),
            ):
                if subset.is_empty():
                    continue
                marks.append(
                    ScatterMark(
                        x=src.epochs(subset["ts"]),
                        y=src.floats(subset["price"], name="fill price"),
                        marker=marker,  # type: ignore[arg-type]
                        role=role,  # type: ignore[arg-type]
                        size=26.0,
                        label=label,
                    )
                )

    # Indicators are grouped by unit, not one panel each. A strategy that publishes three
    # price-unit series (two moving averages and the close it already draws) used to get
    # three near-identical panels whose rotated labels ran into each other, and the one
    # series that was NOT a price fell off the end of an alphabetical cap. Anything
    # measured in price belongs over the price -- which is exactly how a moving average is
    # read -- and each remaining unit gets one panel with the series named in its legend.
    indicators = src.frame(ctx.rdir, "indicator_series.parquet", "name", "ts")
    by_unit: dict[str, list[str]] = {}
    if indicators is not None and not indicators.is_empty():
        for name in sorted({str(value) for value in indicators["name"].to_list()}):
            subset = indicators.filter(indicators["name"] == name)
            unit = _indicator_unit(str(subset["unit"].to_list()[0]))
            # `close` restates the price line this figure already draws.
            if unit == "price" and name == "close":
                continue
            by_unit.setdefault(unit, []).append(name)

    def _indicator_marks(unit: str, names: tuple[str, ...], role: str) -> tuple[Mark, ...]:
        assert indicators is not None
        drawn_marks: list[Mark] = []
        for index, name in enumerate(names):
            subset = indicators.filter(indicators["name"] == name)
            values = src.floats(subset["value"], name=name)
            # One series wears the role's own colour. Several sharing a panel must be told
            # apart, and two gold lines over the same price are two lines you cannot read.
            categorical = len(names) > 1
            drawn_marks.append(
                LineMark(
                    x=src.epochs(subset["ts"]),
                    y=values,
                    role="categorical" if categorical else role,  # type: ignore[arg-type]
                    palette_index=index if categorical else None,
                    label=name,
                    width=1.2,
                    end_label=ValueLabel(text=f"{values[-1]:,.2f}"),
                )
            )
        return tuple(drawn_marks)

    price_overlays = tuple(by_unit.pop("price", [])[:3])
    if price_overlays:
        marks.extend(_indicator_marks("price", price_overlays, "feature"))

    panels: list[Panel] = [
        Panel(
            panel_id="price",
            y_label="Price (native quote)",
            y_unit="price",
            height_ratio=3.0,
            marks=tuple(marks),
            note=None if drawn else "the strategy emitted no chart annotations",
        )
    ]

    for index, (unit, names) in enumerate(sorted(by_unit.items())):
        capped = tuple(names[:3])
        panels.append(
            Panel(
                panel_id=f"indicator_{index}",
                y_label=_UNIT_LABELS.get(unit, unit.replace("_", " ").capitalize()),
                y_unit=unit,  # type: ignore[arg-type]
                marks=_indicator_marks(unit, capped, "subject"),
                note=(
                    None
                    if len(capped) == len(names)
                    else f"showing {len(capped)} of {len(names)} {unit} series"
                ),
            )
        )

    fills_count = 0 if trace is None else int((trace["event_type"] == "fill").sum())
    return ctx.spec(
        "price_signal",
        x_label="Date (UTC)",
        artifacts=(
            "execution_trace.parquet",
            "chart_annotations.parquet",
            "indicator_series.parquet",
        ),
        truncation=_truncation(total, drawn, "annotations") if total else None,
        answer=(
            f"{fills_count:,} fills over {len(rows):,} sessions, with {drawn} strategy-authored "
            f"annotation{'s' if drawn != 1 else ''} drawn on price."
        ),
        panels=tuple(panels),
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


# --------------------------------------------------------------------------- risk
def return_distribution(ctx: BuildContext) -> FigureSpec:
    frame = src.require(ctx.rdir, "return_distribution.parquet")
    hist = frame.filter(frame["kind"] == "histogram").sort("index")
    if hist.is_empty():
        raise DataError("no stored return histogram for this run")
    left = src.floats(hist["left"], name="left")
    right = src.floats(hist["right"], name="right")
    counts = src.floats(hist["count"], name="count")
    edges = (*left, right[-1])
    total = sum(counts)
    centres = [(a + b) / 2 for a, b in zip(left, right, strict=True)]
    mean = sum(c * n for c, n in zip(centres, counts, strict=True)) / total
    variance = sum(n * (c - mean) ** 2 for c, n in zip(centres, counts, strict=True)) / total
    sigma = math.sqrt(variance) or 1e-12
    width = right[0] - left[0]
    curve_x = tuple(left[0] + (edges[-1] - left[0]) * i / 200 for i in range(201))
    scale = total * width / (sigma * math.sqrt(2 * math.pi))
    curve_y = tuple(scale * math.exp(-0.5 * ((x - mean) / sigma) ** 2) for x in curve_x)
    return ctx.spec(
        "return_distribution",
        x_label="Daily return (ratio)",
        x_kind="numeric",
        artifacts=("return_distribution.parquet",),
        answer=(
            f"Daily returns averaged {pct(mean, 2)} with a {pct(sigma, 2)} standard deviation "
            f"across {int(total):,} sessions."
        ),
        panels=(
            Panel(
                panel_id="histogram",
                y_label="Sessions (count)",
                y_unit="count",
                marks=(
                    HistogramMark(
                        edges=edges, counts=counts, role="subject", alpha=0.8, label="Observed"
                    ),
                    LineMark(
                        x=curve_x,
                        y=curve_y,
                        role="reference",
                        dashed=True,
                        label="Normal reference",
                    ),
                    RuleMark(
                        orientation="vertical",
                        position=mean,
                        role="feature",
                        width=1.2,
                        annotate=ValueLabel(text=f"mean {pct(mean, 2)}"),
                    ),
                ),
            ),
        ),
    )


def qq_normal(ctx: BuildContext) -> FigureSpec:
    frame = src.require(ctx.rdir, "return_distribution.parquet")
    qq = frame.filter(frame["kind"] == "qq").sort("index")
    if qq.is_empty():
        raise DataError("no stored Q-Q points for this run")
    picked = src.sample(qq.height, 2000)
    view = qq[picked]
    theoretical = src.floats(view["theoretical"], name="theoretical")
    observed = src.floats(view["sample"], name="sample")
    slope = (
        sum(t * s for t, s in zip(theoretical, observed, strict=True))
        / sum(t * t for t in theoretical)
        if any(theoretical)
        else 1.0
    )
    reference = tuple(slope * value for value in theoretical)
    tail = max(abs(observed[0] - reference[0]), abs(observed[-1] - reference[-1]))
    return ctx.spec(
        "qq_normal",
        x_label="Normal quantile (z_score)",
        x_kind="numeric",
        artifacts=("return_distribution.parquet",),
        truncation=_truncation(qq.height, len(picked), "points"),
        answer=(
            f"The extreme tails depart from the normal reference by up to {pct(tail, 2)} of "
            "daily return, which is the usual signature of fat tails."
        ),
        panels=(
            Panel(
                panel_id="qq",
                y_label="Observed return (ratio)",
                y_unit="ratio",
                marks=(
                    LineMark(
                        x=theoretical,
                        y=reference,
                        role="reference",
                        dashed=True,
                        label="Normal reference",
                    ),
                    ScatterMark(
                        x=theoretical,
                        y=observed,
                        role="subject",
                        size=8.0,
                        label="Observed quantile",
                    ),
                ),
            ),
        ),
    )


def drawdown_episodes(ctx: BuildContext) -> FigureSpec:
    from alpha_validation import drawdown_episodes as compute

    frame = src.require(ctx.rdir, "equity_curve.parquet", "ts")
    ts = src.epochs(frame["ts"])
    equity = src.rebase(src.floats(frame["equity"], name="equity"))
    episodes = compute(equity, top=5)
    if not episodes:
        raise DataError("this run never drew down; there are no episodes to show")
    zones: list[Mark] = [LineMark(x=ts, y=equity, role="subject", label="Equity")]
    rows: list[tuple[str, ...]] = []
    for rank, episode in enumerate(episodes, start=1):
        end_index = episode.recovery_index if episode.recovery_index is not None else len(ts) - 1
        zones.append(
            ZoneMark(
                x0=ts[episode.peak_index],
                x1=ts[end_index],
                role="down",
                alpha=0.16,
                label="Drawdown window" if rank == 1 else None,
            )
        )
        rows.append(
            (
                str(rank),
                pct(episode.depth),
                _day(ts[episode.peak_index]),
                _day(ts[episode.trough_index]),
                _day(ts[episode.recovery_index]) if episode.recovery_index is not None else "open",
                f"{episode.length}",
                "-" if episode.recovery_length is None else f"{episode.recovery_length}",
            )
        )
    unrecovered = sum(1 for item in episodes if item.recovery_index is None)
    return ctx.spec(
        "drawdown_episodes",
        x_label="Date (UTC)",
        artifacts=("equity_curve.parquet",),
        answer=(
            f"The worst drawdown was {pct(episodes[0].depth)} over {episodes[0].length} sessions"
            + (
                "; it had not recovered by the end of the window."
                if unrecovered
                else f", recovering in {episodes[0].recovery_length} sessions."
            )
        ),
        panels=(
            Panel(
                panel_id="equity",
                y_label="Growth of 1 (x initial)",
                y_unit="multiple",
                height_ratio=2.0,
                marks=tuple(zones),
            ),
            Panel(
                panel_id="table",
                y_label="Episodes (count)",
                y_unit="count",
                legend=False,
                height_ratio=1.1,
                marks=(
                    TableMark(
                        columns=(
                            "#",
                            "Depth",
                            "Peak",
                            "Trough",
                            "Recovered",
                            "To trough",
                            "To recover",
                        ),
                        rows=tuple(rows),
                    ),
                ),
            ),
        ),
    )


def exposure_turnover(ctx: BuildContext) -> FigureSpec:
    frame = src.require(ctx.rdir, "exposure_turnover.parquet", "start_ts")
    picked = src.sample(frame.height)
    view = frame[picked]
    ts = src.epochs(view["start_ts"])
    exposure_ok = bool(view["exposure_available"].to_list()[0])
    turnover_ok = bool(view["turnover_available"].to_list()[0])
    if not exposure_ok and not turnover_ok:
        raise DataError("neither exposure nor turnover is available for this run")
    panels: list[Panel] = []
    if exposure_ok:
        gross = tuple(v or 0.0 for v in src.optional_floats(view["gross_exposure"]))
        net = tuple(v or 0.0 for v in src.optional_floats(view["net_exposure"]))
        panels.append(
            Panel(
                panel_id="exposure",
                y_label="Exposure (x net liquidation)",
                y_unit="ratio",
                y_zero_rule=True,
                marks=(
                    LineMark(x=ts, y=gross, role="subject", label="Gross"),
                    LineMark(x=ts, y=net, role="neutral", label="Net", fill_to=0.0),
                ),
            )
        )
    else:
        panels.append(
            Panel(
                panel_id="exposure",
                y_label="Exposure (x net liquidation)",
                y_unit="ratio",
                legend=False,
                note=str(
                    view["exposure_unavailable_reason"].to_list()[0] or "exposure unavailable"
                ),
                marks=(LineMark(x=ts, y=tuple(0.0 for _ in ts), role="substrate"),),
            )
        )
    if turnover_ok:
        turnover = tuple(v or 0.0 for v in src.optional_floats(view["turnover"]))
        panels.append(
            Panel(
                panel_id="turnover",
                y_label="Turnover (x net liquidation)",
                y_unit="ratio",
                legend=False,
                marks=(BarMark(x=ts, y=turnover, role="neutral", alpha=0.8),),
            )
        )
    else:
        panels.append(
            Panel(
                panel_id="turnover",
                y_label="Turnover (x net liquidation)",
                y_unit="ratio",
                legend=False,
                note=str(
                    view["turnover_unavailable_reason"].to_list()[0] or "turnover unavailable"
                ),
                marks=(LineMark(x=ts, y=tuple(0.0 for _ in ts), role="substrate"),),
            )
        )
    if exposure_ok:
        gross_values = [v or 0.0 for v in src.optional_floats(view["gross_exposure"])]
        peak = max(gross_values)
        answer = f"Gross exposure peaked at {peak:.2f}x net liquidation."
    else:
        answer = "Exposure is not recorded for this run type."
    return ctx.spec(
        "exposure_turnover",
        x_label="Date (UTC)",
        artifacts=("exposure_turnover.parquet",),
        truncation=_truncation(frame.height, len(picked), "sessions"),
        answer=answer,
        panels=tuple(panels),
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
    for tier in ("returns_level", "full_engine"):
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


_INDICATOR_UNITS = {
    "price",
    "ratio",
    "percent",
    "count",
    "days",
    "sharpe",
    "weight",
    "correlation",
    "probability",
    "z_score",
    "index",
    "seconds",
    "multiple",
    "account_currency",
}

#: An axis label must carry a unit a reader recognises, not the vocabulary token -- and it
#: must fit: these are budgeted for a short stacked panel, so every one stays under about
#: 22 characters rather than eliding into a shrug.
_UNIT_LABELS = {
    "account_currency": "Amount (account ccy)",
    "correlation": "Correlation (-1 to 1)",
    "count": "Count (n)",
    "days": "Duration (days)",
    "index": "Level (index points)",
    "multiple": "Multiple (x)",
    "percent": "Percent (%)",
    "price": "Price (native quote)",
    "probability": "Probability (0-1)",
    "ratio": "Ratio (unitless)",
    "seconds": "Duration (seconds)",
    "sharpe": "Sharpe (annualised)",
    "weight": "Weight (fraction)",
    "z_score": "Z-score (sigma)",
}


def _indicator_unit(raw: str) -> str:
    """Map a strategy-declared indicator unit onto the closed panel vocabulary.

    Strategies author their own unit strings; anything unrecognised is shown as a plain
    ratio rather than silently claiming to be a price.
    """
    return raw if raw in _INDICATOR_UNITS else "ratio"


def _observed_label(observed: float, percentile: object) -> str:
    text = f"observed {observed:.3f}"
    if isinstance(percentile, int | float) and not isinstance(percentile, bool):
        text += f" · {pct(float(percentile), 0)} pct"
    return text


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


BUILDERS: dict[str, Callable[[BuildContext], FigureSpec]] = {
    "equity_underwater": equity_underwater,
    "equity_vs_passive": equity_vs_passive,
    "rolling_risk": rolling_risk,
    "monthly_heatmap": monthly_heatmap,
    "price_signal": price_signal,
    "trade_pnl": trade_pnl,
    "holding_period": holding_period,
    "return_distribution": return_distribution,
    "qq_normal": qq_normal,
    "drawdown_episodes": drawdown_episodes,
    "exposure_turnover": exposure_turnover,
    "null_distribution": null_distribution,
    "fold_sharpe": fold_sharpe,
    "confidence_intervals": confidence_intervals,
    "optim_trials": optim_trials,
    "optim_surface": optim_surface,
}


# --------------------------------------------------------------------------- portfolio
def portfolio_weights(ctx: BuildContext) -> FigureSpec:
    from alpha_research.figures import CATEGORICAL_SLOTS

    frame = src.require(ctx.rdir, "portfolio_allocations.parquet", "ts", "symbol")
    symbols = sorted({str(value) for value in frame["symbol"].to_list()})
    stamps = sorted({value for value in frame["ts"].to_list()})
    picked = set(src.sample(len(stamps), 1500))
    kept = [stamps[index] for index in sorted(picked)]
    view = frame.filter(frame["ts"].is_in(kept))
    ts = tuple(sorted({v.timestamp() for v in kept}))

    # Rank sleeves by the capital they actually carried, so "other" is genuinely the tail.
    weight_by_symbol = {
        symbol: sum(
            abs(value)
            for value in view.filter(view["symbol"] == symbol)["weight"].to_list()
            if value is not None
        )
        for symbol in symbols
    }
    ranked = sorted(symbols, key=lambda s: -weight_by_symbol[s])
    named = ranked[: CATEGORICAL_SLOTS - 1] if len(ranked) > CATEGORICAL_SLOTS else ranked
    tail = [symbol for symbol in ranked if symbol not in named]

    series: dict[str, list[float]] = {name: [] for name in named}
    other: list[float] = []
    for stamp in kept:
        rows = view.filter(view["ts"] == stamp)
        lookup = {
            str(sym): float(w or 0.0)
            for sym, w in zip(rows["symbol"].to_list(), rows["weight"].to_list(), strict=True)
        }
        for name in named:
            series[name].append(lookup.get(name, 0.0))
        other.append(sum(lookup.get(name, 0.0) for name in tail))

    # Stacked bands, not overlaid lines. An equal-weight book puts every sleeve on exactly
    # the same value, so lines coincide perfectly and silently hide each other -- the reader
    # sees one series and concludes there is one holding. Stacking is also the encoding the
    # quantity deserves: these are shares of one book, and their sum is meaningful.
    marks: list[Mark] = []
    floor = [0.0] * len(ts)
    stack: list[tuple[str, list[float], int | None]] = [
        (name, series[name], index) for index, name in enumerate(named)
    ]
    if tail:
        stack.append((f"Other ({len(tail)} sleeves)", other, None))
    for label, values, slot in stack:
        ceiling = [base + value for base, value in zip(floor, values, strict=True)]
        marks.append(
            BandMark(
                x=ts,
                lower=tuple(floor),
                upper=tuple(ceiling),
                role="categorical" if slot is not None else "substrate",
                palette_index=slot,
                label=label,
                alpha=0.85,
            )
        )
        floor = ceiling

    gross = tuple(
        sum(abs(series[name][index]) for name in named) + abs(other[index])
        for index in range(len(ts))
    )
    return ctx.spec(
        "portfolio_weights",
        x_label="Date (UTC)",
        artifacts=("portfolio_allocations.parquet",),
        truncation=_truncation(len(stamps), len(kept), "rebalance dates"),
        answer=(
            f"{len(symbols)} sleeves, the largest being {ranked[0]}; combined gross weight "
            f"peaked at {max(gross):.2f}x."
            + (f" The smallest {len(tail)} are aggregated as 'other'." if tail else "")
        ),
        panels=(
            Panel(
                panel_id="weights",
                y_label="Sleeve weight (x net liq)",
                y_unit="weight",
                y_zero_rule=True,
                height_ratio=2.0,
                marks=tuple(marks),
            ),
            Panel(
                panel_id="gross",
                y_label="Combined gross (x net liq)",
                y_unit="ratio",
                legend=False,
                marks=(LineMark(x=ts, y=gross, role="subject", fill_to=0.0),),
            ),
        ),
    )


def portfolio_correlations(ctx: BuildContext) -> FigureSpec:
    frame = src.require(ctx.rdir, "correlations.parquet", "asset_a", "asset_b")
    assets = sorted({*frame["asset_a"].to_list(), *frame["asset_b"].to_list()})
    lookup: dict[tuple[str, str], float] = {}
    samples: dict[tuple[str, str], int] = {}
    for a, b, value, count in zip(
        frame["asset_a"].to_list(),
        frame["asset_b"].to_list(),
        frame["correlation"].to_list(),
        frame["sample_count"].to_list(),
        strict=True,
    ):
        if value is None:
            continue
        lookup[(str(a), str(b))] = float(value)
        lookup[(str(b), str(a))] = float(value)
        samples[(str(a), str(b))] = int(count or 0)
    values = tuple(tuple(lookup.get((row, column)) for column in assets) for row in assets)
    text = tuple(
        tuple(
            "" if lookup.get((row, col)) is None else f"{lookup[(row, col)]:.2f}" for col in assets
        )
        for row in assets
    )
    off_diagonal = [
        value for (a, b), value in lookup.items() if a != b and assets.index(a) < assets.index(b)
    ]
    worst = max(off_diagonal) if off_diagonal else 0.0
    return ctx.spec(
        "portfolio_correlations",
        x_label="Sleeve",
        x_kind="category",
        x_categories=tuple(assets),
        artifacts=("correlations.parquet",),
        answer=(
            f"The most correlated pair sits at {worst:.2f} over the aligned out-of-sample "
            f"window; association only, not causation."
        ),
        panels=(
            Panel(
                panel_id="correlation",
                y_label="Sleeve",
                y_unit="category",
                legend=False,
                marks=(
                    HeatmapMark(
                        rows=tuple(assets),
                        columns=tuple(assets),
                        values=values,
                        cell_text=text,
                        colorbar_label="Correlation (-1 to 1)",
                        diverging_center=0.0,
                    ),
                ),
            ),
        ),
    )


# --------------------------------------------------------------------------- prop firm
def propfirm_outcomes(ctx: BuildContext) -> FigureSpec:
    frame = src.require(ctx.rdir, "propfirm_paths.parquet", "path_index")
    passed = [bool(value) for value in frame["passed"].to_list()]
    payout = src.floats(frame["payout"], name="payout")
    raw_days = frame["days_to_pass"].to_list()
    days = [float(value) for value in raw_days if value is not None and math.isfinite(float(value))]
    excluded = len(raw_days) - len(days)
    panels: list[Panel] = []
    if days:
        low, high = min(days), max(days)
        span = (high - low) or 1.0
        bins = 31
        edges = tuple(low + span * index / bins for index in range(bins + 1))
        counts = [0.0] * bins
        for value in days:
            counts[min(bins - 1, int((value - low) / span * bins))] += 1
        panels.append(
            Panel(
                panel_id="days",
                y_label="Paths (count)",
                y_unit="count",
                marks=(
                    HistogramMark(
                        edges=edges,
                        counts=tuple(counts),
                        role="subject",
                        alpha=0.8,
                        label=f"{len(days):,} paths that cleared",
                    ),
                ),
                note=(
                    f"{excluded:,} path(s) never cleared and are excluded here"
                    if excluded
                    else None
                ),
            )
        )
    low_p, high_p = min(payout), max(payout)
    span_p = (high_p - low_p) or 1.0
    bins_p = 31
    edges_p = tuple(low_p + span_p * index / bins_p for index in range(bins_p + 1))
    counts_p = [0.0] * bins_p
    for value in payout:
        counts_p[min(bins_p - 1, int((value - low_p) / span_p * bins_p))] += 1
    expected = sum(payout) / len(payout)
    panels.append(
        Panel(
            panel_id="payout",
            y_label="Paths (count)",
            y_unit="count",
            marks=(
                HistogramMark(
                    edges=edges_p, counts=tuple(counts_p), role="up", alpha=0.75, label="Payout"
                ),
                RuleMark(
                    orientation="vertical",
                    position=expected,
                    role="feature",
                    width=1.4,
                    annotate=ValueLabel(text=f"expected {money(expected)}"),
                ),
            ),
        )
    )
    rate = sum(1 for value in passed if value) / len(passed)
    return ctx.spec(
        "propfirm_outcomes",
        x_label="Days to pass (left panel) / payout in account currency (right scale)",
        x_kind="numeric",
        artifacts=("propfirm_paths.parquet",),
        answer=(
            f"{pct(rate, 0)} of {len(passed):,} resampled paths cleared the evaluation, with an "
            f"expected payout of {money(expected)}."
        ),
        panels=tuple(panels),
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


BUILDERS.update(
    {
        "portfolio_weights": portfolio_weights,
        "portfolio_correlations": portfolio_correlations,
        "propfirm_outcomes": propfirm_outcomes,
        "forecast_fan": forecast_fan,
        "forecast_skill": forecast_skill,
        "forecast_calibration": forecast_calibration,
    }
)
