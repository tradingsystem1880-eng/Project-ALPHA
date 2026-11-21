"""Pure deterministic drawing of recorded event-study paths and controls."""

from __future__ import annotations

from io import BytesIO
from typing import Any

from alpha_cli.figures import direct_notes as notes

FOOTER = (
    "Returns after costs. Grey band: what random dates did. This is a counted look at outcomes."
)


def draw_event_study(
    *,
    paths: list[list[float | None]],
    mean: list[float | None],
    drift: list[float | None],
    lower: list[float | None],
    upper: list[float | None],
    horizons: list[int],
    primary: int,
    title: str,
    variant: str = "plain",
) -> bytes:
    """Missing endpoints are gaps, never zero returns; ``annotated`` adds a reading box."""
    import matplotlib
    import numpy as np

    matplotlib.use("Agg", force=True)
    from matplotlib import rc_context
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    from matplotlib.ticker import PercentFormatter

    style: dict[Any, Any] = dict(matplotlib.rcParamsDefault.items())
    sentences = notes.event_sentences(mean, drift, horizons, primary)
    extra = notes.extra_height(variant, sentences)
    place = notes.layout(extra)
    with rc_context(style):
        figure = Figure(figsize=(16, notes.BASE_HEIGHT_IN + extra), dpi=100, facecolor="white")
        FigureCanvasAgg(figure)
        # Top: every occurrence at full scale. Bottom: the same average zoomed in against
        # the controls, which are a few percent wide and vanish at the top panel's scale.
        top, bottom = figure.subplots(2, 1, sharex=True, height_ratios=[3, 2])
        x = list(range(len(mean)))
        for index, path in enumerate(paths):
            top.plot(
                np.asarray(path, dtype=float),
                color="0.6",
                alpha=0.35,
                linewidth=0.7,
                label="Each occurrence (one faint line each)" if index == 0 else None,
            )
        for axes in (top, bottom):
            axes.plot(
                x,
                np.asarray(mean, dtype=float),
                color="C0",
                linewidth=2.6,
                label="Average after this setup",
            )
        bottom.fill_between(
            x,
            np.asarray(lower, dtype=float),
            np.asarray(upper, dtype=float),
            color="0.5",
            alpha=0.25,
            linewidth=0,
            label="Random dates: middle 90% of their averages",
        )
        bottom.plot(
            x,
            np.asarray(drift, dtype=float),
            color="black",
            linewidth=1.4,
            linestyle="--",
            label="The asset on any day",
        )
        for axes in (top, bottom):
            for horizon in sorted(set(horizons)):
                axes.axvline(
                    horizon,
                    color="C1" if horizon == primary else "0.6",
                    linewidth=1.4 if horizon == primary else 0.9,
                    linestyle=":",
                )
            axes.axhline(0, color="black", linewidth=0.8)
            axes.yaxis.set_major_formatter(PercentFormatter(1, decimals=0))
            axes.grid(alpha=0.3)
            axes.set_axisbelow(True)
            axes.legend(loc="upper left")
        for horizon in sorted(set(horizons)):
            top.text(
                horizon,
                1.01,
                f"{horizon} bars (tested)" if horizon == primary else f"{horizon} bars",
                color="C1" if horizon == primary else "0.3",
                transform=top.get_xaxis_transform(),
                ha="center",
                va="bottom",
            )
        bottom.set_title(
            "Zoomed in: the average against random dates and the asset on any day",
            loc="right",
            color="0.3",
            fontsize=10,
        )
        bottom.set_xlim(0, max(horizons))
        step = 10 if max(horizons) > 20 else max(1, max(horizons) // 5)
        bottom.set_xticks(sorted({0, *horizons, *range(0, max(horizons) + 1, step)}))
        bottom.set_xlabel("Bars after entry")
        top.set_ylabel("Return since entry, after costs")
        bottom.set_ylabel("Average, after costs")
        figure.subplots_adjust(
            left=0.08, right=0.97, top=place["top"], bottom=place["bottom"], hspace=0.12
        )
        if variant == "annotated":
            notes.add_box(figure, sentences)
        figure.text(0.05, place["title_y"], title, fontsize=16, va="top")
        figure.text(0.05, place["foot_y"], FOOTER, fontsize=11)
        buffer = BytesIO()
        figure.savefig(buffer, format="png", dpi=100, metadata={"Software": None})
        figure.clear()
        return buffer.getvalue()
