"""Figure builders: portfolio."""

from __future__ import annotations

import math

from alpha_cli.figures import _sources as src
from alpha_cli.figures._common import BuildContext, _truncation, money, pct
from alpha_research.figures import (
    BandMark,
    FigureSpec,
    HeatmapMark,
    HistogramMark,
    LineMark,
    Mark,
    Panel,
    RuleMark,
    ValueLabel,
)


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
