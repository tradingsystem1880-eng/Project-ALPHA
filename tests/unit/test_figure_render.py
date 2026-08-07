"""Structural assertions on rendered figures.

A byte digest tells you a figure *changed*; it never tells you the figure is *right*.
These tests read the SVG as XML and assert its semantics -- how many panels, which legend
entries, which axis titles -- which is the part a human would otherwise have to eyeball.

They render with ``text_as_paths=False`` so text is real ``<text>``. Production keeps
outlines on for viewer-independent bytes, which is precisely why that switch exists.
"""

from __future__ import annotations

import ast
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from alpha_core import DataError
from alpha_research.figures import (
    FigureSpec,
    HistogramMark,
    LineMark,
    Panel,
    RenderOptions,
    RuleMark,
    ScatterMark,
    ValueLabel,
    default_size,
    load_theme,
    render_figure,
)

_SVG_NS = {"svg": "http://www.w3.org/2000/svg"}
_TS = tuple(1_420_070_400.0 + index * 86_400.0 for index in range(40))


def _readable(spec: FigureSpec) -> ET.Element:
    payload = render_figure(
        spec,
        RenderOptions(
            theme=load_theme(),
            size=default_size(spec.panel_count),
            fmt="svg",
            text_as_paths=False,
        ),
    )
    return ET.fromstring(payload.decode("utf-8"))


def _texts(root: ET.Element) -> list[str]:
    return [element.text or "" for element in root.iter(f"{{{_SVG_NS['svg']}}}text")]


def _spec(panels: tuple[Panel, ...], **overrides: object) -> FigureSpec:
    base: dict[str, object] = {
        "figure_id": "structural",
        "title": "Rolling risk",
        "subtitle": "SPY - ts_momentum",
        "x_label": "Date (UTC)",
        "x_kind": "time",
        "panels": panels,
        "question": "Was the edge stable through time?",
        "plain_language_answer": "Sharpe held above zero for most of the window.",
        "uncertainty": "Rolling windows overlap, so points are not independent.",
        "caveat": "126-session window; shorter regimes are invisible.",
    }
    return FigureSpec(**{**base, **overrides})  # type: ignore[arg-type]


def _line_panel(panel_id: str, label: str, unit: str = "sharpe") -> Panel:
    return Panel(
        panel_id=panel_id,
        y_label=f"{label} ({unit})",
        y_unit="sharpe",
        marks=(LineMark(x=_TS, y=tuple(0.5 + i / 100 for i in range(40)), label=label),),
    )


class TestStructure:
    def test_each_panel_becomes_its_own_axes_group(self) -> None:
        root = _readable(
            _spec(
                (
                    _line_panel("a", "Sharpe"),
                    _line_panel("b", "Volatility"),
                    _line_panel("c", "Return"),
                )
            )
        )
        ids = [
            element.get("id", "")
            for element in root.iter()
            if re.fullmatch(r"axes_\d+", element.get("id", ""))
        ]
        assert len(ids) == 3

    def test_the_title_subtitle_and_answer_all_reach_the_page(self) -> None:
        spec = _spec((_line_panel("a", "Sharpe"),), caption="run abc123 - UTC")
        texts = _texts(_readable(spec))
        assert spec.title in texts
        assert spec.subtitle in texts
        assert spec.plain_language_answer in texts
        assert spec.caption in texts

    def test_every_labelled_mark_appears_in_a_legend(self) -> None:
        panel = Panel(
            panel_id="equity",
            y_label="Growth of 1 (x initial)",
            y_unit="multiple",
            marks=(
                LineMark(x=_TS, y=tuple(1 + i / 200 for i in range(40)), label="Strategy"),
                LineMark(
                    x=_TS,
                    y=tuple(1 + i / 400 for i in range(40)),
                    role="substrate",
                    label="Passive price index",
                ),
                LineMark(x=_TS, y=tuple(1.0 for _ in range(40)), role="reference"),
            ),
        )
        texts = _texts(_readable(_spec((panel,))))
        assert "Strategy" in texts
        assert "Passive price index" in texts

    def test_axis_titles_carry_their_units(self) -> None:
        texts = _texts(_readable(_spec((_line_panel("a", "Sharpe"),))))
        assert "Sharpe (sharpe)" in texts
        assert "Date (UTC)" in texts

    def test_a_feature_value_label_is_drawn_in_place(self) -> None:
        panel = Panel(
            panel_id="dd",
            y_label="Drawdown (%)",
            y_unit="percent",
            marks=(
                LineMark(x=_TS, y=tuple(-i / 500 for i in range(40)), role="down"),
                RuleMark(
                    orientation="horizontal",
                    position=-0.078,
                    role="feature",
                    width=1.0,
                    annotate=ValueLabel(text="worst -7.8%", ha="right", dx_pt=-6.0),
                ),
            ),
        )
        assert "worst -7.8%" in _texts(_readable(_spec((panel,))))

    def test_a_panel_note_states_what_is_missing_rather_than_drawing_zeros(self) -> None:
        panel = Panel(
            panel_id="turnover",
            y_label="Turnover (ratio)",
            y_unit="ratio",
            note="turnover unavailable for this run",
            marks=(LineMark(x=_TS, y=tuple(0.0 for _ in range(40)), role="substrate"),),
        )
        assert "turnover unavailable for this run" in _texts(_readable(_spec((panel,))))

    def test_a_truncation_is_always_disclosed_on_the_face_of_the_figure(self) -> None:
        spec = _spec(
            (_line_panel("a", "Sharpe"),),
            truncation_note="showing 200 of 1,412 annotations",
        )
        assert any("200 of 1,412" in text for text in _texts(_readable(spec)))

    def test_the_surface_is_the_theme_background_not_white(self) -> None:
        payload = render_figure(
            _spec((_line_panel("a", "Sharpe"),)),
            RenderOptions(theme=load_theme(), size=default_size(1), text_as_paths=False),
        )
        assert load_theme().bg.encode() in payload
        assert b"#ffffff" not in payload.lower()

    def test_a_histogram_renders_from_pre_binned_counts(self) -> None:
        panel = Panel(
            panel_id="dist",
            y_label="Sessions (count)",
            y_unit="count",
            marks=(
                HistogramMark(
                    edges=tuple(-0.05 + i * 0.01 for i in range(11)),
                    counts=(1.0, 3.0, 9.0, 22.0, 51.0, 60.0, 33.0, 12.0, 4.0, 1.0),
                    label="Daily returns",
                ),
                RuleMark(orientation="vertical", position=0.0, role="reference", label="Zero"),
            ),
        )
        spec = _spec((panel,), x_kind="numeric", x_label="Daily return (ratio)")
        texts = _texts(_readable(spec))
        assert "Daily returns" in texts


def _executable_source(module_path: str) -> str:
    """Source with comments and docstrings removed.

    The banned constructs are all *discussed* in this module's own prose, so a raw text
    scan would flag the documentation explaining why they are banned.
    """
    tree = ast.parse(Path(module_path).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        holders = (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        if not isinstance(node, holders):
            continue
        body = node.body
        leading = body[0] if body else None
        if (
            isinstance(leading, ast.Expr)
            and isinstance(leading.value, ast.Constant)
            and isinstance(leading.value.value, str)
        ):
            node.body = body[1:] or [ast.Pass()]
    return ast.unparse(tree)


_RENDER_SOURCE = "packages/alpha-research/src/alpha_research/figures/render.py"


class TestInvariants:
    def test_the_renderer_never_creates_a_secondary_axis(self) -> None:
        """Enforced in source as well as in the contract: two scales become two panels."""
        source = _executable_source(_RENDER_SOURCE)
        assert "twinx" not in source
        assert "twiny" not in source
        assert "secondary_yaxis" not in source

    def test_the_renderer_never_rasterises(self) -> None:
        assert "rasterized=True" not in _executable_source(_RENDER_SOURCE)

    def test_layout_is_never_delegated_to_a_text_measuring_engine(self) -> None:
        source = _executable_source(_RENDER_SOURCE)
        assert "tight_layout" not in source
        assert "bbox_inches" not in source

    def test_a_missing_font_fails_loudly_rather_than_silently_substituting(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from matplotlib import font_manager

        def _absent(*args: object, **kwargs: object) -> str:
            raise ValueError("no such font")

        monkeypatch.setattr(font_manager, "findfont", _absent)
        with pytest.raises(DataError, match="figure font"):
            render_figure(_spec((_line_panel("a", "Sharpe"),)))

    def test_a_scatter_can_stay_visible_while_reading_as_degenerate(self) -> None:
        """Dropping a NaN fold would quietly improve the picture; a hollow marker doesn't."""
        panel = Panel(
            panel_id="folds",
            y_label="Fold OOS Sharpe (sharpe)",
            y_unit="sharpe",
            marks=(
                ScatterMark(x=(0.0, 1.0), y=(0.4, 0.9), label="Fold Sharpe"),
                ScatterMark(x=(2.0,), y=(0.0,), hollow=True, role="neutral", label="Degenerate"),
            ),
        )
        assert "Degenerate" in _texts(
            _readable(_spec((panel,), x_kind="numeric", x_label="Fold index"))
        )


class TestLabelFitting:
    """A y-label must survive a short panel with its unit intact."""

    def test_a_short_label_is_left_alone(self) -> None:
        from alpha_research.figures.render import _fit_label

        assert _fit_label("Drawdown (%)", 22) == "Drawdown (%)"

    def test_a_long_label_wraps_rather_than_losing_its_unit(self) -> None:
        # "Ratio (unitl…" told a reader nothing; the whole point of the label is the unit.
        from alpha_research.figures.render import _fit_label

        assert _fit_label("Ratio (unitless)", 12) == "Ratio\n(unitless)"

    def test_it_breaks_before_the_unit_rather_than_inside_it(self) -> None:
        # A purely balanced split would cut "(native" from "quote)".
        from alpha_research.figures.render import _fit_label

        assert _fit_label("Price (native quote)", 14) == "Price\n(native quote)"

    def test_a_single_unbreakable_word_still_elides(self) -> None:
        from alpha_research.figures.render import _fit_label

        assert _fit_label("Supercalifragilistic", 10) == "Supercali…"
