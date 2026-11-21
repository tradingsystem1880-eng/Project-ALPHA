"""Facts read from a figure's stored data: the callouts, bands and run sentences.

Everything here is computed from the marks of a built ``FigureSpec``, which holds only
stored run values. The annotated variant and the long explanation share these functions,
so the numbers in a callout and in the "How to read" box can never disagree.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final

import numpy as np

from alpha_cli.figures.plain_style import CRISES, month, pct
from alpha_core.reserve import RESERVED_INSTANT
from alpha_research.figures.spec import (
    BarMark,
    ErrorBarMark,
    FigureSpec,
    HeatmapMark,
    HistogramMark,
    LineMark,
    Panel,
    RuleMark,
    ScatterMark,
)

_RESERVED_EPOCH: Final = RESERVED_INSTANT.timestamp()


@dataclass(frozen=True, slots=True)
class Call:
    """One callout: its text and the data point its arrow touches (raw x, y)."""

    text: str
    x: float
    y: float


@dataclass(frozen=True, slots=True)
class Plan:
    """What the annotated variant draws on one panel, and what it says about it."""

    calls: tuple[Call, ...] = ()
    bands: tuple[tuple[float, float, str], ...] = ()
    sentences: tuple[str, ...] = ()


def fmt_y(panel: Panel, value: float) -> str:
    if panel.y_percent:
        return pct(value)
    if panel.y_unit == "multiple":
        return f"{value:.2f}x"
    if panel.y_unit in ("count", "days"):
        return f"{value:,.0f}"
    return f"{value:,.3g}" if abs(value) < 1000 else f"{value:,.0f}"


def fmt_x(spec: FigureSpec, value: float) -> str:
    if spec.x_kind == "time":
        return month(value)
    if spec.x_kind == "category" and 0 <= round(value) < len(spec.x_categories):
        return spec.x_categories[round(value)]
    return f"{value:,.3g}"


def _line_plan(spec: FigureSpec, panel: Panel, mark: LineMark) -> Plan:
    y = np.asarray(mark.y)
    x = np.asarray(mark.x)
    name = mark.label or panel.y_label
    hi, lo = int(y.argmax()), int(y.argmin())
    sentence = (
        f"{name} starts at {fmt_y(panel, y[0])} ({fmt_x(spec, x[0])}), ends at "
        f"{fmt_y(panel, y[-1])} ({fmt_x(spec, x[-1])}), peaks at {fmt_y(panel, y[hi])} "
        f"({fmt_x(spec, x[hi])}) and bottoms at {fmt_y(panel, y[lo])} ({fmt_x(spec, x[lo])})."
    )
    if mark.fill_to is None or y[lo] >= mark.fill_to:
        calls = [Call(f"Highest: {fmt_y(panel, y[hi])}, {fmt_x(spec, x[hi])}", x[hi], y[hi])]
        if lo != hi:
            calls.append(Call(f"Lowest: {fmt_y(panel, y[lo])}, {fmt_x(spec, x[lo])}", x[lo], y[lo]))
        return Plan(tuple(calls), (), (sentence,))
    below = y < mark.fill_to
    longest, begin = (0, 0), None
    for index, flag in enumerate(below):
        if not flag:
            begin = None
            continue
        begin = index if begin is None else begin
        if index - begin > longest[1] - longest[0]:
            longest = (begin, index)
    first, last = longest
    share = float(below.mean())
    text = (
        f"Worst point {fmt_y(panel, y[lo])} on {fmt_x(spec, x[lo])}. The line was below a "
        f"prior peak at {pct(share)} of the plotted points."
    )
    bands: tuple[tuple[float, float, str], ...] = ()
    if last > first and spec.x_kind == "time":
        bands = (
            (
                x[first],
                x[last],
                f"longest time below a peak: {fmt_x(spec, x[first])} to {fmt_x(spec, x[last])}",
            ),
        )
    return Plan(
        (Call(f"Worst: {fmt_y(panel, y[lo])}, {fmt_x(spec, x[lo])}", x[lo], y[lo]),),
        bands,
        (sentence, text),
    )


def _histogram_plan(spec: FigureSpec, panel: Panel, mark: HistogramMark) -> Plan:
    counts = np.asarray(mark.counts)
    edges = np.asarray(mark.edges)
    total = float(counts.sum())
    top = int(counts.argmax())
    centre = float((edges[top] + edges[top + 1]) / 2)
    calls = [
        Call(
            f"Tallest bin: {edges[top]:,.3g} to {edges[top + 1]:,.3g} ({counts[top]:,.0f})",
            centre,
            counts[top],
        )
    ]
    sentences = [
        f"The bars hold {total:,.0f} observations between {edges[0]:,.3g} and {edges[-1]:,.3g}; "
        f"the tallest bin, {edges[top]:,.3g} to {edges[top + 1]:,.3g}, holds {counts[top]:,.0f}."
    ]
    rules = [m for m in panel.marks if isinstance(m, RuleMark) and m.orientation == "vertical"]
    for rule in rules[:1]:
        above = float(counts[edges[:-1] >= rule.position].sum()) / total if total else 0.0
        label = rule.label or "Marked value"
        calls.append(Call(f"{label}: {rule.position:,.3g}", rule.position, counts[top] * 0.5))
        sentences.append(
            f"{label} sits at {rule.position:,.3g}; about {pct(above)} of the binned "
            "observations lie at or above it."
        )
    cumulative = np.cumsum(counts) / total if total else counts
    cut = int(np.searchsorted(cumulative, 0.95))
    bands = (
        ((float(edges[min(cut + 1, len(edges) - 1)]), float(edges[-1]), "upper 5% tail"),)
        if cut + 1 < len(counts)
        else ()
    )
    return Plan(tuple(calls), bands, tuple(sentences))


def _bar_plan(spec: FigureSpec, panel: Panel, mark: BarMark) -> Plan:
    y = np.asarray(mark.y)
    x = np.asarray(mark.x)
    hi, lo = int(y.argmax()), int(y.argmin())
    calls = [Call(f"Largest: {fmt_y(panel, y[hi])} at {fmt_x(spec, x[hi])}", x[hi], y[hi])]
    if lo != hi:
        calls.append(Call(f"Smallest: {fmt_y(panel, y[lo])} at {fmt_x(spec, x[lo])}", x[lo], y[lo]))
    sentence = (
        f"There are {len(y):,} bars; the largest is {fmt_y(panel, y[hi])} at {fmt_x(spec, x[hi])} "
        f"and the smallest is {fmt_y(panel, y[lo])} at {fmt_x(spec, x[lo])}; "
        f"the mean is {fmt_y(panel, float(y.mean()))}."
    )
    if mark.horizontal:
        calls = []
    return Plan(tuple(calls), (), (sentence,))


def _heatmap_plan(mark: HeatmapMark) -> Plan:
    data = np.array([[np.nan if v is None else v for v in row] for row in mark.values], dtype=float)
    if not np.isfinite(data).any():
        return Plan(sentences=("Every cell is empty.",))
    hi = np.unravel_index(np.nanargmax(data), data.shape)
    lo = np.unravel_index(np.nanargmin(data), data.shape)
    name = mark.colorbar_label

    def cell(index: tuple[int, ...] | tuple[np.intp, ...]) -> str:
        return f"{data[index]:,.3g} ({mark.rows[index[0]]}, {mark.columns[index[1]]})"

    calls = (
        Call("Highest", float(hi[1]), float(hi[0])),
        Call("Lowest", float(lo[1]), float(lo[0])),
    )
    empty = int(np.isnan(data).sum())
    note = f" {empty} cells are empty." if empty else ""
    return Plan(
        calls,
        (),
        (
            f"On the {name} scale the highest cell is {cell(hi)} and the lowest is {cell(lo)}. "
            f"The highest cell is outlined solid and the lowest dashed.{note}",
        ),
    )


def _errorbar_plan(spec: FigureSpec, panel: Panel, mark: ErrorBarMark) -> Plan:
    point = np.asarray(mark.point)
    spans = np.asarray(mark.upper) - np.asarray(mark.lower)
    wide = int(spans.argmax())
    crossing = int(((np.asarray(mark.lower) <= 0) & (np.asarray(mark.upper) >= 0)).sum())
    call = Call(f"Widest interval: {mark.categories[wide]}", float(point[wide]), float(wide))
    sentence = (
        f"There are {len(point):,} intervals; the point estimates run from "
        f"{point.min():,.3g} to {point.max():,.3g}, "
        f"and {crossing:,} of the intervals include zero."
    )
    return Plan((call,), (), (sentence,))


def _scatter_plan(spec: FigureSpec, panel: Panel, mark: ScatterMark) -> Plan:
    y = np.asarray(mark.y)
    x = np.asarray(mark.x)
    hi = int(y.argmax())
    text = f"{len(y):,} points; the highest is {fmt_y(panel, y[hi])} at {fmt_x(spec, x[hi])}."
    return Plan((Call(f"Highest: {fmt_y(panel, y[hi])}", x[hi], y[hi]),), (), (text,))


def panel_plan(spec: FigureSpec, panel: Panel) -> Plan:
    """The plan for one panel, read from its first data-bearing mark."""
    lines = [
        m for m in panel.marks if isinstance(m, LineMark) and len(m.x) > 1 and m.role != "reference"
    ]
    if lines:
        subject = [m for m in lines if m.role in ("subject", "feature", "categorical")]
        return _line_plan(spec, panel, (subject or lines)[0])
    for mark in panel.marks:
        if isinstance(mark, HistogramMark):
            return _histogram_plan(spec, panel, mark)
        if isinstance(mark, BarMark):
            return _bar_plan(spec, panel, mark)
        if isinstance(mark, HeatmapMark):
            return _heatmap_plan(mark)
        if isinstance(mark, ErrorBarMark):
            return _errorbar_plan(spec, panel, mark)
        if isinstance(mark, ScatterMark):
            return _scatter_plan(spec, panel, mark)
    return Plan(sentences=(f"The {panel.y_label} panel is a table of stored values.",))


def time_extent(spec: FigureSpec) -> tuple[float, float] | None:
    """First and last plotted instant of a time axis (epoch seconds), else None."""
    if spec.x_kind != "time":
        return None
    values: list[float] = []
    for panel in spec.panels:
        for mark in panel.marks:
            x = getattr(mark, "x", None)
            if x:
                values.extend((min(x), max(x)))
    return (min(values), max(values)) if values else None


def figure_bands(spec: FigureSpec) -> tuple[tuple[float, float, str], ...]:
    """Named crisis windows that fall inside a time axis."""
    extent = time_extent(spec)
    if extent is None:
        return ()
    found = []
    for start, end, label in CRISES:
        a = datetime.fromisoformat(start).replace(tzinfo=UTC).timestamp()
        b = datetime.fromisoformat(end).replace(tzinfo=UTC).timestamp()
        if a >= extent[0] and b <= extent[1]:
            found.append((a, b, label))
    return tuple(found)


def held_back_span(spec: FigureSpec) -> tuple[float, float] | None:
    """Where the held-back band goes: only when the data stop just before the reserved date."""
    extent = time_extent(spec)
    if extent is None:
        return None
    gap = _RESERVED_EPOCH - extent[1]
    width = extent[1] - extent[0]
    if gap < 0 or gap > 0.1 * width:
        return None
    return _RESERVED_EPOCH, _RESERVED_EPOCH + 0.06 * width


def run_sentences(spec: FigureSpec) -> list[str]:
    """Sentences about this run, each number read from the stored data (two panels at most)."""
    sentences: list[str] = []
    for panel in spec.panels[:2]:
        sentences.extend(panel_plan(spec, panel).sentences)
    extent = time_extent(spec)
    if extent is not None:
        sentences.append(f"The plotted data run from {month(extent[0])} to {month(extent[1])}.")
    return sentences
