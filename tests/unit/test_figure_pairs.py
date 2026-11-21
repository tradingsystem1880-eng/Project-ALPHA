"""Every figure as a pair: the plain notebook chart and the annotated, explained chart.

Synthetic specs cover every mark kind; a stored synthetic rule run covers the builders.
Checks: both variants draw, no text leaves the figure, no tick labels overlap, the plain
variant is white on matplotlib's default colours, both variants plot the same values, and
the annotated variant has callouts or labelled bands plus a how-to-read box whose numbers
equal values computed from the stored data.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from alpha_cli.figures import available_figures, build_figure_spec
from alpha_cli.figures.explanations_checks import TEXTS as CHECK_TEXTS
from alpha_cli.figures.explanations_models import TEXTS as MODEL_TEXTS
from alpha_cli.figures.explanations_runs import TEXTS as RUN_TEXTS
from alpha_cli.figures.plain_spec import draw_spec
from alpha_cli.figures.spec_facts import fmt_y, held_back_span
from alpha_cli.figures.variants import explanation, fixed_text, render_variant
from alpha_cli.spine.run import run_idea
from alpha_cli.spine.spec import load_spec
from alpha_data.store import ParquetStore
from alpha_research.figures import FigureSpec, figures_for_command
from alpha_research.figures.spec import (
    BandMark,
    BarMark,
    ErrorBarMark,
    HeatmapMark,
    HistogramMark,
    LineMark,
    Mark,
    Panel,
    RuleMark,
    ScatterMark,
    TableMark,
    XKind,
    ZoneMark,
)
from tests.fixtures.cli_fixtures import seed_store

_DEFAULT_CYCLE = {f"C{i}" for i in range(10)}  # matplotlib's own colour cycle, referenced by name
_GREYS = {"0.6", "0.35", "0.3", "black", "white"}
_FIXED = {"title": "T", "x": "Date (UTC)"}


def _epochs(count: int, start: datetime = datetime(2021, 1, 1, tzinfo=UTC)) -> tuple[float, ...]:
    return tuple((start + timedelta(days=i)).timestamp() for i in range(count))


def _spec(figure_id: str, marks: list[Mark], *, kind: XKind = "time", **panel: Any) -> FigureSpec:
    return FigureSpec(
        figure_id=figure_id,
        title="Synthetic chart",
        subtitle="TEST · synthetic",
        x_label="Date (UTC)" if kind == "time" else "Value (ratio)",
        x_kind=kind,
        panels=(
            Panel(
                panel_id="main",
                y_label=panel.pop("y_label", "Value (x initial)"),
                y_unit=panel.pop("y_unit", "multiple"),
                marks=tuple(marks),
                **panel,
            ),
        ),
        question="q",
        plain_language_answer="a",
        uncertainty="u",
        caveat="c",
        caption="synthetic",
    )


def _all_specs() -> dict[str, FigureSpec]:
    x = _epochs(120)
    y = tuple(1.0 + 0.002 * i + 0.05 * np.sin(i / 7) for i in range(120))
    under = tuple(min(0.0, v / max(y[: i + 1]) - 1.0) for i, v in enumerate(y))
    edges = tuple(float(v) for v in np.linspace(-3, 3, 21))
    counts = tuple(float(v) for v in np.exp(-(np.linspace(-3, 3, 20) ** 2)) * 100)
    grid = tuple(tuple(float(i - j) / 10 for j in range(6)) for i in range(5))
    return {
        "line": _spec("equity_underwater", [LineMark(x=x, y=y, label="Equity")]),
        "underwater": _spec(
            "equity_underwater",
            [LineMark(x=x, y=under, fill_to=0.0, role="down", label="Drawdown")],
            y_percent=True,
            y_unit="percent",
            y_label="Drawdown (%)",
        ),
        "band": _spec(
            "forecast_fan",
            [
                BandMark(x=x, lower=tuple(v - 0.1 for v in y), upper=tuple(v + 0.1 for v in y)),
                LineMark(x=x, y=y, label="Median"),
            ],
        ),
        "histogram": _spec(
            "null_distribution",
            [
                HistogramMark(edges=edges, counts=counts, label="Null"),
                RuleMark(orientation="vertical", position=1.2, role="feature", label="Observed"),
            ],
            kind="numeric",
            y_unit="count",
            y_label="Runs (n)",
        ),
        "bars": _spec(
            "trade_pnl",
            [
                BarMark(
                    x=tuple(float(i) for i in range(30)),
                    y=tuple(np.sin(np.arange(30)) * 100),
                    signed_colour=True,
                )
            ],
            kind="numeric",
            y_unit="account_currency",
            y_label="Profit (account ccy)",
            y_zero_rule=True,
        ),
        "heatmap": _spec(
            "monthly_heatmap",
            [
                HeatmapMark(
                    rows=tuple(f"r{i}" for i in range(5)),
                    columns=tuple(f"c{j}" for j in range(6)),
                    values=grid,
                    colorbar_label="Return (%)",
                )
            ],
            kind="numeric",
            y_unit="category",
            legend=False,
        ),
        "errors": _spec(
            "confidence_intervals",
            [
                ErrorBarMark(
                    categories=("a", "b", "c"),
                    point=(0.5, 1.0, -0.2),
                    lower=(0.1, 0.4, -0.9),
                    upper=(0.9, 1.6, 0.4),
                )
            ],
            kind="numeric",
            y_unit="category",
        ),
        "scatter": _spec(
            "price_signal",
            [
                LineMark(x=x, y=y, role="substrate", label="Close"),
                ScatterMark(x=x[::20], y=y[::20], marker="^", role="up", label="Buy fill"),
                ZoneMark(x0=x[10], x1=x[30], role="feature"),
            ],
            y_unit="price",
            y_label="Price (native quote)",
        ),
        "table": _spec(
            "research_discovery_trace",
            [TableMark(columns=("Field", "Value"), rows=(("a", "1"), ("b", "2")))],
            kind="numeric",
            y_unit="count",
            legend=False,
        ),
    }


def _fixed(spec: FigureSpec) -> tuple[str, str, str, str]:
    try:
        return fixed_text(spec.figure_id)
    except Exception:
        return ("a.", "b.", "c.", "d.")


def _draw(spec: FigureSpec, variant: str) -> Any:
    figure = draw_spec(spec, variant, explanation(spec, _fixed(spec)))
    figure.canvas.draw()
    return figure


def _texts(figure: Any) -> list[Any]:
    from matplotlib.text import Text

    return [t for t in figure.findobj(Text) if t.get_visible() and t.get_text().strip()]


def _drawn_ticks(axes: Any, axis: Any, limits: tuple[float, float]) -> list[Any]:
    """Tick labels whose tick lies inside the view; the others are never drawn."""
    low, high = sorted(limits)
    return [
        label
        for loc, label in zip(axis.get_majorticklocs(), axis.get_ticklabels(), strict=False)
        if low <= loc <= high
    ]


def _undrawn(figure: Any) -> set[int]:
    hidden: set[int] = set()
    for axes in figure.axes:
        for axis, limits in ((axes.xaxis, axes.get_xlim()), (axes.yaxis, axes.get_ylim())):
            shown = {id(label) for label in _drawn_ticks(axes, axis, limits)}
            hidden |= {id(label) for label in axis.get_ticklabels() if id(label) not in shown}
    return hidden


def _assert_inside(figure: Any) -> None:
    renderer = figure.canvas.get_renderer()
    bounds = figure.bbox
    hidden = _undrawn(figure)
    for text in _texts(figure):
        if id(text) in hidden:
            continue
        box = text.get_window_extent(renderer)
        if not np.isfinite([box.x0, box.x1, box.y0, box.y1]).all():
            continue  # a tick label outside the view is not drawn
        assert box.x0 >= bounds.x0 - 1 and box.y0 >= bounds.y0 - 1, text.get_text()
        assert box.x1 <= bounds.x1 + 1 and box.y1 <= bounds.y1 + 1, text.get_text()


def _assert_no_tick_overlap(figure: Any) -> None:
    renderer = figure.canvas.get_renderer()
    for axes in figure.axes:
        shown = (
            _drawn_ticks(axes, axes.xaxis, axes.get_xlim()),
            _drawn_ticks(axes, axes.yaxis, axes.get_ylim()),
        )
        for labels in shown:
            boxes = [
                t.get_window_extent(renderer)
                for t in labels
                if t.get_visible() and t.get_text().strip()
            ]
            boxes = [b for b in boxes if np.isfinite([b.x0, b.x1, b.y0, b.y1]).all()]
            for i, a in enumerate(boxes):
                for b in boxes[i + 1 :]:
                    assert not a.overlaps(b) or _touching(a, b), (a, b)


def _touching(a: Any, b: Any) -> bool:
    across_x = float(min(a.x1, b.x1) - max(a.x0, b.x0))
    across_y = float(min(a.y1, b.y1) - max(a.y0, b.y0))
    return across_x < 1 or across_y < 1


@pytest.mark.parametrize("name", sorted(_all_specs()))
@pytest.mark.parametrize("variant", ["plain", "annotated"])
def test_every_mark_kind_draws_inside_the_figure(name: str, variant: str) -> None:
    figure = _draw(_all_specs()[name], variant)
    _assert_inside(figure)
    _assert_no_tick_overlap(figure)


@pytest.mark.parametrize("name", sorted(_all_specs()))
def test_the_plain_chart_is_white_on_matplotlib_defaults(name: str) -> None:
    from matplotlib.colors import to_hex

    figure = _draw(_all_specs()[name], "plain")
    assert figure.get_facecolor()[:3] == (1.0, 1.0, 1.0)
    cycle = {to_hex(c) for c in (f"C{i}" for i in range(10))}
    allowed = {to_hex(c) for c in _DEFAULT_CYCLE | _GREYS}
    for axes in figure.axes:
        for line in axes.get_lines():
            assert to_hex(line.get_color()) in allowed | cycle


@pytest.mark.parametrize("name", sorted(_all_specs()))
def test_both_variants_plot_the_same_values(name: str) -> None:
    spec = _all_specs()[name]
    plain, annotated = _draw(spec, "plain"), _draw(spec, "annotated")

    def data(figure: Any) -> list[Any]:
        out: list[Any] = []
        for axes in figure.axes:
            out.extend(
                np.asarray(line.get_ydata(), dtype=float).tolist() for line in axes.get_lines()
            )
            out.extend([p.get_height() for p in getattr(c, "patches", [])] for c in axes.containers)
        return out

    assert data(plain) == data(annotated)


@pytest.mark.parametrize("name", sorted(_all_specs()))
def test_the_annotated_chart_has_callouts_or_bands_and_a_reading_box(name: str) -> None:
    from matplotlib.text import Annotation

    spec = _all_specs()[name]
    figure = _draw(spec, "annotated")
    notes = [a for a in figure.findobj(Annotation) if a.get_text()]
    patches = [p for axes in figure.axes for p in axes.patches]
    assert notes or patches
    box = [t for t in _texts(figure) if t.get_text().startswith("How to read this chart")]
    assert len(box) == 1
    plain_texts = [t.get_text() for t in _texts(_draw(spec, "plain"))]
    assert not any(t.startswith("How to read this chart") for t in plain_texts)


def test_the_box_numbers_are_computed_from_the_stored_data() -> None:
    spec = _all_specs()["line"]
    mark = spec.panels[0].marks[0]
    assert isinstance(mark, LineMark)
    text = " ".join(explanation(spec, _fixed(spec)))
    for value in (max(mark.y), min(mark.y), mark.y[0], mark.y[-1]):
        assert fmt_y(spec.panels[0], value) in text


def test_the_worst_drawdown_in_the_box_is_the_data_minimum() -> None:
    spec = _all_specs()["underwater"]
    mark = spec.panels[0].marks[0]
    assert isinstance(mark, LineMark)
    assert f"{min(mark.y) * 100:.1f}%" in " ".join(explanation(spec, _fixed(spec)))


def test_the_histogram_box_counts_the_stored_bins() -> None:
    spec = _all_specs()["histogram"]
    mark = spec.panels[0].marks[0]
    assert isinstance(mark, HistogramMark)
    assert f"{sum(mark.counts):,.0f} observations" in " ".join(explanation(spec, _fixed(spec)))


def test_the_explanation_has_four_to_seven_sentences() -> None:
    for spec in _all_specs().values():
        assert 4 <= len(explanation(spec, _fixed(spec))) <= 7


def test_every_catalogue_figure_has_a_fixed_explanation() -> None:
    known = set(RUN_TEXTS) | set(CHECK_TEXTS) | set(MODEL_TEXTS)
    from alpha_research.figures import catalog_document

    ids = {item["figure_id"] for item in catalog_document()}
    assert ids <= known
    assert {"lookalike", "unusual"} <= known
    for texts in (RUN_TEXTS, CHECK_TEXTS, MODEL_TEXTS):
        for figure_id, sentences in texts.items():
            assert len(sentences) == 4 and all(s.endswith(".") for s in sentences), figure_id
            joined = " ".join(sentences).lower()
            for banned in ("pass/fail", "you should", "guarantee", "grade", "buy now"):
                assert banned not in joined, (figure_id, banned)


def test_the_held_back_band_appears_only_when_data_stop_before_the_reserved_date() -> None:
    near = _all_specs()["line"]
    assert held_back_span(near) is None
    x = _epochs(200, datetime(2023, 6, 1, tzinfo=UTC))
    late = _spec("equity_underwater", [LineMark(x=x, y=tuple(1.0 + i / 100 for i in range(200)))])
    span = held_back_span(late)
    assert span is not None
    figure = _draw(late, "annotated")
    assert any(t.get_text() == "held back, not used" for t in _texts(figure))


def test_bytes_are_deterministic() -> None:
    spec = _all_specs()["line"]
    for variant in ("plain", "annotated"):
        for fmt in ("svg", "png"):
            assert render_variant(spec, variant, fmt, _fixed(spec)) == render_variant(
                spec, variant, fmt, _fixed(spec)
            )


@pytest.fixture(scope="module")
def stored_run(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, dict[str, Any]]:
    home = tmp_path_factory.mktemp("pairs")
    seed_store(home, symbol="SPY", n=400)
    ParquetStore(home / "store").write_provenance(
        "SPY", source="fixture", adapter_version="1", parser_version="1"
    )
    idea = load_spec(None, rule="ma_cross", param=["fast=5", "slow=20"], asset=["SPY"])
    result = run_idea(idea, home=home, quick=True)["results"][0]
    assert result["error"] is None, result["error"]
    rdir = Path(result["run_dir"])
    return rdir, json.loads((rdir / "manifest.json").read_bytes())


def test_every_available_builder_renders_both_variants(
    stored_run: tuple[Path, dict[str, Any]],
) -> None:
    rdir, manifest = stored_run
    drawn = 0
    for entry in available_figures(rdir, manifest):
        if not entry.available:
            continue
        spec = build_figure_spec(
            entry.definition.figure_id,
            run_id=rdir.name,
            rdir=rdir,
            manifest=manifest,
            data_dir=rdir.parent.parent,
        )
        plain, annotated = _draw(spec, "plain"), _draw(spec, "annotated")
        for figure in (plain, annotated):
            _assert_inside(figure)
            _assert_no_tick_overlap(figure)
        assert plain.get_facecolor()[:3] == (1.0, 1.0, 1.0)
        drawn += 1
    assert drawn >= 10
    assert figures_for_command("validate")
