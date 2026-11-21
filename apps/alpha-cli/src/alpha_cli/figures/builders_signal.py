"""Figure builders: the price chart with the strategy's own signals."""

from __future__ import annotations

from typing import Any, cast

from alpha_cli.figures import _sources as src
from alpha_cli.figures._common import BuildContext, _truncation
from alpha_core import DataError
from alpha_research.figures import (
    CandleMark,
    FigureSpec,
    LineMark,
    Mark,
    Panel,
    ScatterMark,
    ValueLabel,
    ZoneMark,
)
from alpha_research.figures.spec import Role, YUnit


def _price_marks(rows: list[dict[str, Any]]) -> list[Mark]:
    ts = tuple(row["t"] for row in rows)
    if len(rows) <= 400:
        return [
            CandleMark(
                x=ts,
                open=tuple(row["o"] for row in rows),
                high=tuple(row["h"] for row in rows),
                low=tuple(row["l"] for row in rows),
                close=tuple(row["c"] for row in rows),
                alpha=0.85,
            )
        ]
    return [
        LineMark(
            x=ts, y=tuple(row["c"] for row in rows), role="substrate", label="Close", width=1.0
        )
    ]


def _annotation_marks(ctx: BuildContext) -> tuple[list[Mark], int, int]:
    """Strategy-authored annotations: zones and lines; returns marks, drawn and total."""
    annotations = src.frame(ctx.rdir, "chart_annotations.parquet", "annotation_id", "anchor_index")
    marks: list[Mark] = []
    if annotations is None or annotations.is_empty():
        return marks, 0, 0
    groups = annotations.partition_by("annotation_id", maintain_order=True)
    for drawn, group in enumerate(groups[:40]):
        label = str(group["label"].to_list()[0])
        xs = src.epochs(group["ts"])
        ys = src.floats(group["value"], name="annotation value")
        first = label if drawn == 0 else None
        if str(group["kind"].to_list()[0]) == "zone":
            marks.append(
                ZoneMark(
                    x0=min(xs),
                    x1=max(xs),
                    role="feature",
                    alpha=0.12,
                    label=first,
                    corner_label=ValueLabel(text=label),
                )
            )
        else:
            marks.append(
                LineMark(
                    x=xs,
                    y=ys,
                    role="feature",
                    label=first,
                    end_label=ValueLabel(text=f"{label} {ys[-1]:.2f}"),
                )
            )
    return marks, min(len(groups), 40), len(groups)


def _fill_marks(trace: Any) -> list[Mark]:
    if trace is None or trace.is_empty():
        return []
    fills = trace.filter(trace["event_type"] == "fill")
    marks: list[Mark] = []
    for side, marker, role, label in (
        ("BUY", "^", "up", "Buy fill"),
        ("SELL", "v", "down", "Sell fill"),
    ):
        subset = fills.filter(fills["side"] == side)
        if subset.is_empty():
            continue
        marks.append(
            ScatterMark(
                x=src.epochs(subset["ts"]),
                y=src.floats(subset["price"], name="fill price"),
                marker="^" if marker == "^" else "v",
                role="up" if role == "up" else "down",
                size=26.0,
                label=label,
            )
        )
    return marks


def _indicator_groups(indicators: Any) -> dict[str, list[str]]:
    """Indicators grouped by unit, not one panel each.

    Anything measured in price belongs over the price, which is how a moving average is
    read; each remaining unit gets one panel with its series named in the legend.
    """
    by_unit: dict[str, list[str]] = {}
    if indicators is None or indicators.is_empty():
        return by_unit
    for name in sorted({str(value) for value in indicators["name"].to_list()}):
        subset = indicators.filter(indicators["name"] == name)
        unit = _indicator_unit(str(subset["unit"].to_list()[0]))
        # `close` restates the price line this figure already draws.
        if unit == "price" and name == "close":
            continue
        by_unit.setdefault(unit, []).append(name)
    return by_unit


def _indicator_marks(indicators: Any, names: tuple[str, ...], role: Role) -> tuple[Mark, ...]:
    marks: list[Mark] = []
    for index, name in enumerate(names):
        subset = indicators.filter(indicators["name"] == name)
        values = src.floats(subset["value"], name=name)
        # Several series sharing a panel must be told apart; one wears the role's colour.
        several = len(names) > 1
        marks.append(
            LineMark(
                x=src.epochs(subset["ts"]),
                y=values,
                role="categorical" if several else role,
                palette_index=index if several else None,
                label=name,
                width=1.2,
                end_label=ValueLabel(text=f"{values[-1]:,.2f}"),
            )
        )
    return tuple(marks)


def _indicator_panels(indicators: Any, by_unit: dict[str, list[str]]) -> list[Panel]:
    panels: list[Panel] = []
    for index, (unit, names) in enumerate(sorted(by_unit.items())):
        capped = tuple(names[:3])
        panels.append(
            Panel(
                panel_id=f"indicator_{index}",
                y_label=_UNIT_LABELS.get(unit, unit.replace("_", " ").capitalize()),
                y_unit=cast(YUnit, unit),
                marks=_indicator_marks(indicators, capped, "subject"),
                note=(
                    None
                    if len(capped) == len(names)
                    else f"showing {len(capped)} of {len(names)} {unit} series"
                ),
            )
        )
    return panels


def price_signal(ctx: BuildContext) -> FigureSpec:
    keys = ("symbol", "snapshot_id", "start", "end", "timeframe", "source_timeframe", "session")
    rows, reason = src.bars({key: ctx.field(key) for key in keys}, data_dir=ctx.data_dir)
    if reason is not None or not rows:
        raise DataError(f"price bars unavailable for this run ({reason or 'no bars'})")
    marks = _price_marks(rows)
    notes, drawn, total = _annotation_marks(ctx)
    marks.extend(notes)
    trace = src.frame(ctx.rdir, "execution_trace.parquet", "sequence_id")
    marks.extend(_fill_marks(trace))
    indicators = src.frame(ctx.rdir, "indicator_series.parquet", "name", "ts")
    by_unit = _indicator_groups(indicators)
    overlays = tuple(by_unit.pop("price", [])[:3])
    if overlays:
        marks.extend(_indicator_marks(indicators, overlays, "feature"))
    price_panel = Panel(
        panel_id="price",
        y_label="Price (native quote)",
        y_unit="price",
        height_ratio=3.0,
        marks=tuple(marks),
        note=None if drawn else "the strategy emitted no chart annotations",
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
        panels=(price_panel, *_indicator_panels(indicators, by_unit)),
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
