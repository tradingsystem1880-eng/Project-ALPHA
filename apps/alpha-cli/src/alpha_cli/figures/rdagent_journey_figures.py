"""Display transformations of recorded evidence and its annotated white PNGs."""

from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from io import BytesIO
from itertools import accumulate
from operator import mul
from pathlib import Path
from typing import Any

import polars as pl

from alpha_cli.rdagent_journey_words import CLOCK, display, pass_line
from alpha_cli.toolbox.reserve import RESERVED_DAY
from alpha_research.figures.theme import Theme, load_theme

Data = dict[str, Any]


def table(path: Path, columns: list[str], clock: str | None = None) -> pl.DataFrame | None:
    if not path.is_file():
        return None
    frame = pl.scan_parquet(path, glob=False)
    schema = frame.collect_schema()
    if any(name not in schema for name in columns):
        return None
    if "date" in columns:
        frame = frame.filter(pl.col("date") < RESERVED_DAY).with_columns(
            pl.col("date").cast(pl.Date)
        )
    if clock is not None:
        if "clock" not in schema:
            return None
        frame = frame.filter(pl.col("clock") == clock)
    result = frame.select(columns).collect()
    return None if result.is_empty() else result


def _unique(frame: pl.DataFrame, keys: list[str]) -> pl.DataFrame:
    if frame.select(keys).is_duplicated().any():
        raise ValueError(f"Duplicate plotted observation for {keys}")
    return frame.sort(keys)


def signal_data(values: Path, panel: Path, name: str, label: str | None = None) -> Data | None:
    prices = table(panel, ["date", "instrument", "close"])
    factors = table(values, ["date", "instrument", name])
    if prices is None or factors is None:
        return None
    scores = _unique(factors, ["date", "instrument"]).rename({name: "score"})
    scores = scores.with_columns(pl.when(pl.col("score").is_finite()).then("score").alias("score"))
    prices = _unique(prices, ["date", "instrument"])
    joined = prices.join(scores, on=["date", "instrument"], how="left")
    names = sorted(joined.drop_nulls()["instrument"].unique().to_list())
    if not names:
        return None
    symbol = next((s for s in names if s.startswith("BTC")), names[0])
    band = scores.group_by("date").agg(
        pl.col("score").quantile(0.1, interpolation="linear").alias("low"),
        pl.col("score").quantile(0.9, interpolation="linear").alias("high"),
    )
    chosen = (
        joined.filter(pl.col("instrument") == symbol).join(band, on="date", how="left").sort("date")
    )
    return {
        "instrument": symbol,
        "label": label or name,
        **chosen.drop("instrument")
        .with_columns(pl.col("date").cast(pl.String))
        .to_dict(as_series=False),
    }


def quick_data(totals: Path, dated: Path, clock: str) -> Data | None:
    overall = table(totals, ["bucket", "mean_outcome"], clock)
    days = table(dated, ["date", "bucket", "mean_outcome"], clock)
    if overall is None or days is None:
        return None
    overall = _unique(overall, ["bucket"])
    days = _unique(days, ["date", "bucket"])
    if overall["bucket"].to_list() != [1, 2, 3] or overall["mean_outcome"].null_count():
        return None
    years = (
        days.with_columns(pl.col("date").dt.year().alias("year"))
        .group_by("year", "bucket")
        .agg(pl.col("mean_outcome").mean())
    )
    by_year = {}
    for group in years.sort(["year", "bucket"]).partition_by("year"):
        by_bucket = dict(group.select("bucket", "mean_outcome").iter_rows())
        by_year[str(group["year"][0])] = [by_bucket.get(i) for i in (1, 2, 3)]
    return {"overall": overall["mean_outcome"].to_list(), "by_year": by_year, "clock": clock}


def trading_data(path: Path, clock: str, stats: Data) -> Data | None:
    """Growth of 100 for the replayed selection and the basket, from the stored per-period rows."""
    columns = ["target_ts", "net_return", "gross_return", "benchmark_return", "turnover"]
    if not path.is_file():
        return None
    frame = pl.scan_parquet(path, glob=False)
    schema = frame.collect_schema()
    if any(name not in schema for name in [*columns, "clock"]):
        return None
    rows = (
        frame.filter(pl.col("clock") == clock)
        .select(columns)
        .with_columns(pl.col("target_ts").dt.date().alias("date"))
        .filter(pl.col("date") < RESERVED_DAY)
        .collect()
    )
    if rows.is_empty() or rows.drop_nulls().height != rows.height:
        return None
    rows = _unique(rows, ["date"])

    def growth(column: str) -> list[float]:
        return [100 * v for v in accumulate((1 + r for r in rows[column].to_list()), mul)]

    return {
        "date": rows["date"].cast(pl.String).to_list(),
        "after": growth("net_return"),
        "before": growth("gross_return"),
        "basket": growth("benchmark_return"),
        "annual_cost": stats.get("annual_cost"),
        "mean_turnover": stats.get("mean_turnover"),
        "clock": clock,
    }


def timeline_data(path: Path, clock: str, sign: int | None) -> Data | None:
    if sign is None:
        return None
    if sign not in (-1, 1):
        raise ValueError("Invalid declared direction")
    data = table(path, ["date", "rank_ic"], clock)
    if data is None or data["rank_ic"].drop_nulls().is_empty():
        return None
    frame = _unique(data, ["date"]).with_columns((pl.col("rank_ic") * sign).alias("score"))
    means = (
        frame.group_by(pl.col("date").dt.year().alias("year"))
        .agg(pl.col("score").mean())
        .sort("year")
    )
    scores = frame["score"].to_list()
    totals = iter(accumulate(s for s in scores if s is not None))
    return {
        "date": frame["date"].cast(pl.String).to_list(),
        "signed": scores,
        "clock": clock,
        "cumulative": [next(totals) if s is not None else None for s in scores],
        "year_means": {str(year): mean for year, mean in means.iter_rows() if mean is not None},
    }


def looks_data(row: Data, ledger: list[Data]) -> Data | None:
    cutoff = pass_line(row)
    if cutoff is None or not row.get("panel_sha256"):
        return None
    scores: list[float] = []
    indices: list[int] = []
    selected = None
    for look in ledger:
        if (
            look.get("panel_sha256") != row["panel_sha256"]
            or look.get("screen_rule") != row["screen_rule"]
        ):
            continue
        if look.get("stage") not in {"screen", "replay"}:
            continue
        sc = look.get("clocks", {}).get(look.get("primary_clock"), {}).get("screen", {})
        if sc.get("status") != "OK" or sc.get("p") is None:
            continue
        if all(row.get(k) == look.get(k) for k in ("run_id", "iteration", "name", "code_sha256")):
            if selected is not None:
                raise ValueError("Duplicate idea in the trial ledger")
            selected = len(scores)
            if sc["p"] != row["clocks"][row["primary_clock"]]["screen"]["p"]:
                raise ValueError("Ledger and evaluation screen scores disagree")
        scores.append(sc["p"])
        indices.append(look["trial_index"])
    return (
        None
        if selected is None
        else {
            "p": scores,
            "trial": indices,
            "selected": selected,
            "pass_line": cutoff,
            "counted": row.get("screen_m"),
        }
    )


def figure_theme(dark: bool) -> Theme:
    """The one white standard look; ``dark`` is accepted for old callers and changes nothing.

    Colours are matplotlib's own defaults (tab blue, orange, green, red) on a white face.
    """
    return replace(
        load_theme("alpha-dark"),
        theme_id="plain-notebook",
        bg="#ffffff",
        panel="#ffffff",
        ink="#000000",
        ink_dim="#444444",
        accent="#1f77b4",
        grid="#e0e0e0",
        faint="#999999",
        muted="#666666",
        gold="#ff7f0e",
        up="#2ca02c",
        down="#d62728",
    )


def _style(theme: Theme) -> dict[Any, Any]:
    import matplotlib

    return {
        **dict(matplotlib.rcParamsDefault.items()),
        "figure.facecolor": theme.bg,
        "axes.facecolor": theme.panel,
    }


def _note(
    ax: Any,
    x: Any,
    y: float,
    text: str,
    theme: Theme,
    *,
    above: bool,
    frac: float = 0.5,
    reach: int = 32,
) -> None:
    """A label placed beside the point it names, on the side with free room."""
    ax.annotate(
        text,
        (x, y),
        xytext=(-14 if frac > 0.7 else 14 if frac < 0.3 else 0, reach if above else -reach - 4),
        textcoords="offset points",
        ha="right" if frac > 0.7 else "left" if frac < 0.3 else "center",
        fontsize=9,
        color=theme.ink,
        bbox={"facecolor": theme.panel, "edgecolor": theme.grid, "alpha": 0.95, "pad": 2.5},
        arrowprops={"arrowstyle": "->", "color": theme.muted},
        zorder=6,
    )


def _month(day: date) -> str:
    return day.strftime("%b %Y")


def _lock(ax: Any, first: date, theme: Theme) -> None:
    width = max(200, (RESERVED_DAY - first).days // 4)
    end = RESERVED_DAY + timedelta(days=width)
    ax.axvspan(RESERVED_DAY, end, hatch="///", facecolor=theme.grid, edgecolor=theme.faint, lw=0)
    ax.text(
        RESERVED_DAY + timedelta(days=width // 2),
        0.5,
        "LOCKED\n2024 onward",
        transform=ax.get_xaxis_transform(),
        ha="center",
        va="center",
        color=theme.ink_dim,
        fontsize=8,
        fontweight="bold",
        bbox={"facecolor": theme.panel, "edgecolor": theme.faint, "boxstyle": "round,pad=0.4"},
    )
    ax.set_xlim(first - timedelta(days=1), end)


def _years(ax: Any, first: date) -> None:
    ticks = [date(y, 1, 1) for y in range(first.year, RESERVED_DAY.year + 1)]
    ticks = [t for t in ticks if t >= first]
    ax.set_xticks(ticks, [str(t.year) for t in ticks])


def _heading(fig: Any, title: str, sub: str, theme: Theme) -> None:
    fig.text(0.01, 0.985, title, fontsize=15, fontweight="bold", va="top", color=theme.ink)
    fig.text(0.01, 0.925, sub, fontsize=9.5, va="top", color=theme.ink_dim, wrap=True)


def _signal(fig: Any, data: Data, theme: Theme) -> None:
    from matplotlib.ticker import FuncFormatter

    upper, lower = fig.subplots(2, 1, sharex=True, height_ratios=[1, 1])
    dates = [date.fromisoformat(d) for d in data["date"]]
    score = data["score"]
    name = data["instrument"]
    _heading(
        fig,
        f"What RD-Agent's number looked like for {name}",
        f"Top: {name}'s price. Bottom: the number the AI's code gave it each day (blue), "
        "against the middle 80% of all coins (grey band).",
        theme,
    )
    upper.plot(dates, data["close"], color=theme.ink_dim, lw=1.3)
    upper.set_ylabel(f"{name} price (USD)")
    upper.set_ylim(bottom=0)
    upper.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v / 1000:g}k" if v else "0"))
    nan = float("nan")
    lower.fill_between(
        dates,
        [nan if v is None else v for v in data["low"]],
        [nan if v is None else v for v in data["high"]],
        color=theme.faint,
        alpha=0.35,
        lw=0,
    )
    lower.plot(dates, score, color=theme.accent, lw=1.5, zorder=4)
    lower.set_ylabel("RD-Agent's number")
    valid = [i for i, v in enumerate(score) if v is not None]
    if valid:
        first = dates[valid[0]]
        if (first - dates[0]).days > 60:
            for a in (upper, lower):
                a.axvspan(dates[0], first, color=theme.grid, alpha=0.6, lw=0)
            lower.text(
                dates[0],
                0.04,
                " history,\n no number yet",
                transform=lower.get_xaxis_transform(),
                fontsize=8,
                color=theme.muted,
                va="bottom",
            )
        for pick, word, above in ((max, "Highest", True), (min, "Lowest", False)):
            i = pick(valid, key=score.__getitem__)
            frac = (dates[i] - dates[0]).days / max(1, (dates[-1] - dates[0]).days)
            _note(
                lower,
                dates[i],
                score[i],
                f"{word}: {_month(dates[i])}, {display(score[i])}",
                theme,
                above=above,
                frac=frac,
            )
    for a in (upper, lower):
        _lock(a, dates[0], theme)
    _years(lower, dates[0])


def _pct_points(value: float) -> str:
    return f"{value * 100:.3g}"


def _quick(fig: Any, data: Data, theme: Theme) -> None:
    from matplotlib.ticker import PercentFormatter

    upper, lower = fig.subplots(2, 1, height_ratios=[1, 1])
    totals, years = data["overall"], data["by_year"]
    span = CLOCK.get(data["clock"], data["clock"])
    gap = totals[2] - totals[0]
    verb = "more" if gap > 0 else "less"
    _heading(
        fig,
        f"The top third earned {verb} than the bottom third"
        if gap
        else "The top and bottom thirds earned the same",
        f"Each period the coins were sorted by RD-Agent's number into three equal groups; "
        f"bars show the average return over the following {span}.",
        theme,
    )
    names = ["Bottom third\n(lowest numbers)", "Middle third", "Top third\n(highest numbers)"]
    upper.bar(range(3), totals, color=[theme.muted, theme.faint, theme.accent], width=0.55)
    for i, v in enumerate(totals):
        upper.annotate(
            display(v, True),
            (i, v),
            xytext=(0, 4 if v >= 0 else -4),
            textcoords="offset points",
            ha="center",
            va="bottom" if v >= 0 else "top",
            fontsize=10,
            fontweight="bold",
            color=theme.ink,
        )
    upper.text(
        0.02,
        0.97,
        f"Top minus bottom:\n{_pct_points(gap)} percentage points",
        transform=upper.transAxes,
        ha="left",
        va="top",
        fontsize=9.5,
        color=theme.ink,
        bbox={"facecolor": theme.panel, "edgecolor": theme.grid, "pad": 3},
    )
    upper.set_xticks(range(3), names)
    upper.set_ylabel(f"Average return, next {span}")
    wins = sum(1 for v in years.values() if None not in (v[0], v[2]) and v[2] > v[0])
    for i, (year, values) in enumerate(years.items()):
        colour = theme.series_colour(i)
        lower.plot(range(3), values, marker="o", color=colour, lw=1.6)
        for x, align in ((2, "left"), (0, "right")):
            if values[x] is not None:
                lower.annotate(
                    year,
                    (x, values[x]),
                    xytext=(7 if x else -7, 0),
                    textcoords="offset points",
                    ha=align,
                    va="center",
                    fontsize=9,
                    color=colour,
                    fontweight="bold",
                )
    lower.set_xticks(range(3), names)
    lower.set_xlim(-0.5, 2.5)
    lower.set_ylabel(f"Average return, next {span}")
    lower.set_title(
        f"Same chart, year by year: the top third beat the bottom in {wins} of {len(years)} years",
        fontsize=10,
        color=theme.ink_dim,
        loc="left",
    )
    for a in (upper, lower):
        a.yaxis.set_major_formatter(PercentFormatter(1))
        a.axhline(0, color=theme.muted, lw=0.8)


def _over_time(fig: Any, data: Data, theme: Theme) -> None:
    upper, lower = fig.subplots(2, 1, sharex=True, height_ratios=[3, 2])
    dates = [date.fromisoformat(d) for d in data["date"]]
    cum = data["cumulative"]
    means = data["year_means"]
    held = sum(1 for v in means.values() if v > 0)
    title = (
        f"The pattern held in all {len(means)} years"
        if held == len(means)
        else "The pattern did not hold in any year"
        if held == 0
        else f"The pattern held in {held} of {len(means)} years"
    )
    _heading(
        fig,
        title,
        "Each period: how well the ranks matched the next returns (rank correlation), signed so "
        "that up means the idea worked. A line that keeps climbing = it kept working.",
        theme,
    )
    upper.plot(dates, cum, color=theme.accent, lw=1.6)
    upper.axhline(0, lw=0.8, color=theme.muted)
    upper.set_ylabel("Running total of the score")
    valid = [i for i, v in enumerate(cum) if v is not None]
    if valid:
        i = valid[-1]
        _note(
            upper,
            dates[i],
            cum[i],
            f"Ended at {display(cum[i])} after {len(valid)} periods",
            theme,
            above=cum[i] < 0,
            frac=1.0,
            reach=95,
        )
    for year, mean in means.items():
        ds = [d for d in dates if d.year == int(year)]
        colour = theme.up if mean > 0 else theme.down
        lower.plot([ds[0], ds[-1]], [mean, mean], color=colour, lw=2.5)
        lower.annotate(
            f"{year}: {display(mean)}",
            (ds[len(ds) // 2], mean),
            xytext=(0, 6 if mean >= 0 else -6),
            textcoords="offset points",
            ha="center",
            va="bottom" if mean >= 0 else "top",
            color=colour,
            fontweight="bold",
            fontsize=9.5,
        )
    lower.axhline(0, lw=0.8, color=theme.muted)
    lower.set_ylabel("Average score\nin that year")
    for a in (upper, lower):
        _lock(a, dates[0], theme)
    lower.margins(y=0.3)
    _years(lower, dates[0])


def _trading(fig: Any, data: Data, theme: Theme) -> None:
    from matplotlib.ticker import FuncFormatter

    upper, lower = fig.subplots(2, 1, sharex=True, height_ratios=[3, 2])
    dates = [date.fromisoformat(d) for d in data["date"]]
    after, before, basket = data["after"], data["before"], data["basket"]
    ahead_after, ahead_before = after[-1] > basket[-1], before[-1] > basket[-1]
    title = (
        "Trading costs turned an edge into a loss"
        if ahead_before and not ahead_after
        else "After costs, the idea ended ahead of the basket"
        if ahead_after
        else "After costs, the idea ended behind the basket"
    )
    _heading(
        fig,
        title,
        "Hold the top-ranked third of coins, paying the trading costs ALPHA assumes, and compare "
        "with holding every coin in equal parts (the basket). Starts at $100.",
        theme,
    )
    upper.plot(
        dates,
        before,
        color=theme.accent,
        ls="--",
        lw=1.4,
        label=f"idea, before costs: ${before[-1]:.3g}",
    )
    upper.plot(
        dates, basket, color=theme.faint, lw=1.6, label=f"basket of all coins: ${basket[-1]:.3g}"
    )
    upper.plot(
        dates, after, color=theme.accent, lw=2.2, label=f"idea, after costs: ${after[-1]:.3g}"
    )
    upper.set_yscale("log")
    upper.set_ylabel("$100 grows to... (log scale)")
    upper.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"${v:g}"))
    upper.legend(loc="lower left", bbox_to_anchor=(0.3, 0.02), fontsize=9, frameon=False)
    for series, colour, style in ((before, theme.accent, "--"), (after, theme.accent, "-")):
        lower.plot(
            dates,
            [100 * (a / b - 1) for a, b in zip(series, basket, strict=True)],
            color=colour,
            ls=style,
            lw=1.4,
        )
    for series, word, rise in ((before, "before costs", 6), (after, "after costs", -24)):
        lower.annotate(
            word,
            (dates[-1], 100 * (series[-1] / basket[-1] - 1)),
            xytext=(-4, rise),
            textcoords="offset points",
            ha="right",
            fontsize=8.5,
            color=theme.accent,
        )
    lower.fill_between(
        dates,
        [100 * (a / b - 1) for a, b in zip(before, basket, strict=True)],
        [100 * (a / b - 1) for a, b in zip(after, basket, strict=True)],
        color=theme.down,
        alpha=0.12,
        lw=0,
    )
    lower.axhline(0, lw=0.8, color=theme.muted)
    lower.set_ylabel("Ahead of / behind\nthe basket (%)")
    cost, turnover = data["annual_cost"], data["mean_turnover"]
    if cost is not None and turnover is not None:
        lower.text(
            0.02,
            0.97,
            f"Shaded gap = trading costs: about {display(cost, True)} a year,\n"
            f"because about {display(turnover, True)} of the portfolio is traded each period.",
            transform=lower.transAxes,
            fontsize=9,
            color=theme.down,
            va="top",
        )
    for a in (upper, lower):
        _lock(a, dates[0], theme)
    _years(lower, dates[0])


def _looks(fig: Any, data: Data, theme: Theme) -> None:
    from matplotlib.ticker import FuncFormatter, MaxNLocator

    ax = fig.add_subplot(111)
    i, line = data["selected"], data["pass_line"]
    scores = [max(v, 1e-12) for v in data["p"]]
    mine = scores[i]
    verdict = "reached" if mine <= line else "did not reach"
    counted = f"; the judge counted {data['counted']} in all" if data.get("counted") else ""
    _heading(
        fig,
        f"This idea {verdict} the pass line",
        "Each dot is one look at an idea on the same data and test (lower = less likely to be "
        f"luck). {len(scores)} looks are drawn{counted}.",
        theme,
    )
    ax.scatter(data["trial"], scores, color=theme.muted, s=40, zorder=3)
    ax.scatter([data["trial"][i]], [mine], color=theme.accent, s=90, zorder=4)
    ax.axhline(line, color=theme.gold, ls="--", lw=1.4)
    ax.set_yscale("log")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v * 100:g}%"))
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.set_xlabel("Order in which the looks were recorded")
    ax.set_ylabel("Chance score (log scale; lower is better)")
    trials = data["trial"]
    frac = (trials[i] - min(trials)) / max(1, max(trials) - min(trials))
    _note(
        ax,
        trials[i],
        mine,
        f"This idea: {display(mine, True)}",
        theme,
        above=mine < line * 30,
        frac=frac,
    )
    ax.text(
        0.99,
        line,
        f"pass line {display(line, True)}",
        transform=ax.get_yaxis_transform(),
        ha="right",
        va="bottom",
        fontsize=9,
        color=theme.gold,
    )


def draw(name: str, data: Data, dark: bool) -> bytes:
    from matplotlib import rc_context
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    from matplotlib.layout_engine import ConstrainedLayoutEngine

    theme = figure_theme(dark)
    painters = {
        "signal": _signal,
        "quick-test": _quick,
        "over-time": _over_time,
        "trading-test": _trading,
        "how-many-ideas": _looks,
    }
    with rc_context(_style(theme)):
        fig = Figure(figsize=(8, 6.4))
        fig.set_layout_engine(ConstrainedLayoutEngine(rect=(0, 0, 1, 0.84)))
        FigureCanvasAgg(fig)
        painters[name](fig, data, theme)
        for a in fig.axes:
            a.grid(axis="y", color=theme.grid, linewidth=0.6)
            a.set_axisbelow(True)
            a.margins(y=0.2)
        buffer = BytesIO()
        fig.savefig(buffer, format="png", dpi=200, metadata={"Software": None})
        return buffer.getvalue()
