"""Shared pieces for the figures drawn straight onto matplotlib (trade and event-study sheets).

They follow the same standard look as every other figure: white face, matplotlib defaults.
The annotated variant adds callouts and a "How to read this chart" box whose sentences are
computed from the stored rows, never typed in.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final

import numpy as np

from alpha_cli.figures import plain_style as ps

if TYPE_CHECKING:
    from matplotlib.figure import Figure

BASE_HEIGHT_IN: Final = 9.0
_MARGIN_IN: Final = 1.08


def extra_height(variant: str, sentences: list[str]) -> float:
    """Inches added under the plot for the reading box; none for the plain chart."""
    return ps.box_height(sentences) + 0.3 if variant == "annotated" else 0.0


def layout(extra: float) -> dict[str, float]:
    """Figure fractions for a 16 x (9 + extra) inch sheet whose plot keeps its size."""
    total = BASE_HEIGHT_IN + extra
    return {
        "bottom": (_MARGIN_IN + extra) / total,
        "top": 1 - _MARGIN_IN / total,
        "title_y": 1 - 0.36 / total,
        "foot_y": (0.36 + extra) / total,
    }


def add_box(figure: Figure, sentences: list[str]) -> None:
    ps.how_to_read(figure, sentences, 0.1, width_chars=190)


def mark_extremes(axes: Any, values: list[float], label: str) -> None:
    """Callouts for the highest and lowest bar of a bar chart (x is the bar index)."""
    if len(values) < 2:
        return
    used: list[int] = []
    high, low = int(np.argmax(values)), int(np.argmin(values))
    ps.callout(axes, f"Best {label}: {ps.pct(values[high])}", (float(high), values[high]), used)
    if low != high:
        ps.callout(axes, f"Worst {label}: {ps.pct(values[low])}", (float(low), values[low]), used)


def trade_sentences(
    done: list[dict[str, Any]], primary: dict[str, Any], direction: str
) -> list[str]:
    """Reading of the trade sheet from its stored rows and pooled numbers."""
    returns = [float(r["net_return"]) for r in done]
    sentences = [
        "The top panel's horizontal axis is the trade number in entry order and its vertical "
        "axis is each trade's return after costs; the lower left panel compares the average "
        "trade with random dates; the lower right panel counts trades by result in units of "
        "the risk taken at entry (R).",
        "Each bar is one closed trade, coloured by how it ended: target, stop, time or "
        "opposite signal. The grey band is the middle 90% of averages from random dates, and "
        "the dashed line is the same exits started on any day.",
        "Look at whether a few tall bars carry the average, whether the dot sits outside the "
        "grey band, and how the R histogram leans.",
    ]
    if returns:
        gained = sum(1 for v in returns if v > 0) / len(returns)
        sentences.append(
            f"This sheet shows {len(returns)} {direction} trades; the best returned "
            f"{ps.pct(max(returns))}, the worst {ps.pct(min(returns))}, and {ps.pct(gained)} "
            f"of them gained; the stored average is {ps.pct(float(primary['mean']))}."
            if primary.get("mean") is not None
            else f"This sheet shows {len(returns)} {direction} trades; the best returned "
            f"{ps.pct(max(returns))} and the worst {ps.pct(min(returns))}."
        )
    else:
        sentences.append("This sheet has no completed trades to draw.")
    sentences.append(
        "The chart cannot tell you what the next trade will do, and it is one counted look "
        "at stored outcomes, not confirmed on the reserved data."
    )
    return sentences


def event_sentences(
    mean: list[float | None], drift: list[float | None], horizons: list[int], primary: int
) -> list[str]:
    """Reading of the event-study sheet from its stored average path."""
    sentences = [
        "The horizontal axis is the number of bars after each entry and the vertical axis is "
        "the return since entry, after costs; the upper panel shows every occurrence and the "
        "lower panel zooms in on the average.",
        "Each faint line is one occurrence. The thick line is the average after this setup, "
        "the grey band is the middle 90% of averages from random dates and the dashed line is "
        "the asset on any day. Dotted vertical lines mark the tested horizons.",
        "Look at whether the thick line leaves the grey band by the tested horizon and whether "
        "the faint lines spread to both sides of zero.",
    ]
    at = [m for m in mean if m is not None]
    if at and primary < len(mean) and mean[primary] is not None:
        base = drift[primary] if primary < len(drift) else None
        gap = f"; the asset on any day returned {ps.pct(float(base))}" if base is not None else ""
        sentences.append(
            f"At the tested horizon of {primary} bars the average is "
            f"{ps.pct(float(mean[primary] or 0.0))}{gap}; the average ranges from "
            f"{ps.pct(min(at))} to {ps.pct(max(at))} over the {max(horizons)} bars drawn."
        )
    sentences.append(
        "The chart cannot tell you that the setup causes the move, and it is one counted look "
        "at outcomes."
    )
    return sentences
