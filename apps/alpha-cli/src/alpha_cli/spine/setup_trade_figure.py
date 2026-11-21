"""Pure deterministic trade figure and plain-language command presentation."""

from __future__ import annotations

from io import BytesIO
from typing import Any

from alpha_cli.figures import direct_notes as notes
from alpha_cli.spine.setup_reading import owner_lines


def draw_trades(
    *,
    rows: list[dict[str, Any]],
    primary: dict[str, Any],
    title: str,
    direction: str = "long",
    variant: str = "plain",
) -> bytes:
    """The standard white sheet; ``variant="annotated"`` adds callouts and a reading box."""
    import matplotlib

    matplotlib.use("Agg", force=True)
    from matplotlib import rc_context
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    from matplotlib.patches import Patch
    from matplotlib.ticker import PercentFormatter

    # Losses red, gains green: the owner reads the colour before the key.
    palette = {
        "stop": "C3",
        "target": "C2",
        "time": "C0",
        "opposite": "C1",
        "open-at-end": "0.6",
    }
    names = {
        "stop": "Stop exit (incl. gaps through the stop)",
        "target": "Target exit",
        "time": "Time exit",
        "opposite": "Opposite-condition exit",
        "open-at-end": "Still open at the end (marked only, not in the mean)",
    }
    done = sorted(
        (r for r in rows if r["net_return"] is not None),
        key=lambda r: (r["entry_ts"], r["asset"], r["candidate_id"]),
    )
    sentences = notes.trade_sentences(done, primary, direction)
    extra = notes.extra_height(variant, sentences)
    place = notes.layout(extra)
    with rc_context(dict(matplotlib.rcParamsDefault.items())):
        figure = Figure(figsize=(16, notes.BASE_HEIGHT_IN + extra), dpi=100, facecolor="white")
        FigureCanvasAgg(figure)
        grid = figure.add_gridspec(2, 2, height_ratios=[3, 2], width_ratios=[3, 2])
        top = figure.add_subplot(grid[0, :])
        bottom = figure.add_subplot(grid[1, 0])
        hist = figure.add_subplot(grid[1, 1])
        groups = [
            {"stop-gap": "stop", "max-hold": "time"}.get(r["reason"], r["reason"]) for r in done
        ]
        top.bar(
            range(len(done)), [r["net_return"] for r in done], color=[palette[g] for g in groups]
        )
        if done:
            top.scatter(
                range(len(done)),
                [0] * len(done),
                color="black",
                marker="v" if direction == "short" else "^",
                s=18,
                label=f"{direction.title()} entry",
            )
            top.legend(
                handles=[
                    top.collections[-1],
                    *[
                        Patch(color=palette[k], label=f"{names[k]}: {groups.count(k)}")
                        for k in palette
                        if k in groups
                    ],
                ],
                loc="upper left",
            )
        ticks = _year_ticks([r["entry_ts"] for r in done])
        if ticks:
            top.set_xticks([i for i, _ in ticks], [label for _, label in ticks])
        top.set_xlim(-1, max(len(done), 1))
        top.set_xlabel("Each bar is one trade, in entry-date order (year of entry below)")
        top.set_ylabel("Trade return after costs")
        _controls_panel(bottom, primary)
        multiples = [
            r["r_multiple"] for r in done if r["complete"] and r.get("r_multiple") is not None
        ]
        if multiples:
            hist.hist(multiples, bins="auto", color="C0")
        else:
            hist.text(0.5, 0.5, "R not recorded", ha="center", transform=hist.transAxes)
        hist.set_xlabel("Net return in initial risk units (R)")
        hist.set_ylabel("Completed trades")
        for axes in (top, bottom):
            axes.axhline(0, color="black", linewidth=0.8)
            axes.yaxis.set_major_formatter(PercentFormatter(1))
            axes.grid(alpha=0.3)
            axes.set_axisbelow(True)
        figure.subplots_adjust(
            left=0.09, right=0.97, top=place["top"], bottom=place["bottom"], hspace=0.35
        )
        if variant == "annotated":
            notes.mark_extremes(top, [float(r["net_return"]) for r in done], "trade")
            notes.add_box(figure, sentences)
        figure.text(0.05, place["title_y"], title, fontsize=16, va="top")
        figure.text(
            0.05,
            place["foot_y"],
            f"{direction.title()} trades after costs. Open-at-end trades excluded from the mean. "
            "One counted exploratory test; not confirmed on reserved data.",
            fontsize=11,
        )
        buffer = BytesIO()
        figure.savefig(buffer, format="png", dpi=100, metadata={"Software": None})
        figure.clear()
        return buffer.getvalue()


def _year_ticks(stamps: list[Any]) -> list[tuple[int, str]]:
    """First trade of each entry year, thinned to at most twelve labels."""
    firsts: list[tuple[int, str]] = []
    for i, stamp in enumerate(stamps):
        year = getattr(stamp, "year", None)
        if year is None:
            return []
        if not firsts or firsts[-1][1] != str(year):
            firsts.append((i, str(year)))
    step = -(-len(firsts) // 12) if firsts else 1
    return firsts[::step]


def _controls_panel(axes: Any, primary: dict[str, Any]) -> None:
    low, high, drift, mean = (
        primary[k] for k in ("random_date_5", "random_date_95", "drift_mean", "mean")
    )
    if low is not None and high is not None:
        axes.axhspan(
            low,
            high,
            facecolor="0.85",
            edgecolor="0.6",
            label=f"Random dates, middle 90% of their averages: {low:.2%} to {high:.2%}",
        )
    if drift is not None:
        axes.axhline(
            drift,
            color="black",
            linestyle="--",
            label=f"Same exits started on any day: {drift:.2%}",
        )
    if mean is None:
        axes.text(
            0.5,
            0.5,
            "No completed trades; nothing to compare",
            ha="center",
            transform=axes.transAxes,
        )
    else:
        axes.plot(
            [0],
            [mean],
            "o",
            color="C1",
            markersize=12,
            label=f"Average completed trade after this setup: {mean:.2%}",
        )
        axes.annotate(
            f"{primary['trades']} trades, {primary['hit_rate']:.1%} of them gained",
            (0, mean),
            xytext=(18, 14),
            textcoords="offset points",
        )
        axes.legend(loc="upper left")
    values = [v for v in (low, high, drift, mean, 0.0) if v is not None]
    span = max(values) - min(values) or 0.01
    axes.set_ylim(min(values) - 0.15 * span, max(values) + 0.6 * span)
    axes.set_xlim(-1, 1)
    axes.set_xticks([])
    axes.set_ylabel("Average net return per trade")


def trade_text(output: dict[str, Any]) -> str:
    row = output["pooled"]
    lines = [output["reading"], *owner_lines(output), output.get("basis", ""), "measure\tvalue"]
    for title, field, percent in (
        ("trades", "trades", False),
        ("mean", "mean", True),
        ("median", "median", True),
        ("hit rate", "hit_rate", True),
        ("bars held", "mean_bars_held", False),
        ("drift", "drift_mean", True),
        ("excess", "excess", True),
        ("random-date p", "random_date_p", True),
    ):
        value = row[field]
        text = (
            "unavailable"
            if value is None
            else f"{value:.2%}"
            if percent
            else f"{value:.1f}"
            if isinstance(value, float)
            else str(value)
        )
        lines.append(f"{title}\t{text}")
    for label, key in (
        ("Mean R", "mean_r"),
        ("Median R", "median_r"),
        ("Share above 0 R", "share_above_zero_r"),
        ("Expectancy per trade in R", "expectancy_r"),
    ):
        value = row.get(key)
        displayed = (
            "not recorded"
            if value is None
            else (f"{value:.2%}" if key == "share_above_zero_r" else f"{value:.2f} R")
        )
        lines.append(f"{label}\t{displayed}")
    control = output.get("controls", {}).get("opposite_direction")
    if control:
        net, mean_r = control["mean_net_return"], control["mean_r"]
        lines.extend(
            [
                f"{control['label']} · {control['direction']}",
                "Mean net return\t" + ("not recorded" if net is None else f"{net:.2%}"),
                "Mean R\t" + ("not recorded" if mean_r is None else f"{mean_r:.2f} R"),
            ]
        )
    if "risk_explanation" in output:
        lines.append(output["risk_explanation"])
    lines.extend(
        [
            "by reason\t" + ", ".join(f"{k}: {v}" for k, v in row["by_reason"].items()),
            "Labels: " + ", ".join(label.replace("-", " ") for label in output["labels"]),
            *([output["reserve_sentence"]] if output.get("reserve_sentence") else []),
            output["folder"],
            f"Next: alpha results cite {output['trade_id']} setup_trade_mean_net_return",
        ]
    )
    return "\n".join(lines)


def study_text(output: dict[str, Any]) -> str:
    lines = [output["reading"], *owner_lines(output)]
    primary = str(output["primary_horizon"])
    for group, keys in (
        ("Primary horizon", [primary]),
        ("Also looked at, not tested", [k for k in output["horizons"] if k != primary]),
    ):
        if not keys:
            continue
        lines.extend([group.lower(), "bars\toccurrences\tmean\tmedian\thit rate\tdrift\texcess"])
        for key in keys:
            row = output["horizons"][key]["pooled"]
            values = [
                "unavailable" if row[k] is None else f"{row[k]:.2%}"
                for k in ("mean", "median", "hit_rate", "drift_mean", "excess")
            ]
            lines.append(
                "\t".join(
                    [
                        key + (" (primary)" if key == primary else ""),
                        str(row["occurrences"]),
                        *values,
                    ]
                )
            )
    lines.extend(
        [
            "Labels: " + ", ".join(label.replace("-", " ") for label in output["labels"]),
            *([output["reserve_sentence"]] if output.get("reserve_sentence") else []),
            output["folder"],
            f"Next: alpha results cite {output['study_id']} setup_mean_net_return",
        ]
    )
    return "\n".join(lines)
