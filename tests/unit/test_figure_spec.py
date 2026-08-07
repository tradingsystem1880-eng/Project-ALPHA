"""The figure contract validates itself, so a malformed figure never reaches a renderer."""

from __future__ import annotations

import pytest

from alpha_core import DataError
from alpha_research.figures import (
    BandMark,
    BarMark,
    ErrorBarMark,
    FigureSpec,
    HeatmapMark,
    HistogramMark,
    LineMark,
    Panel,
    RuleMark,
    ScatterMark,
    TableMark,
    ValueLabel,
    ZoneMark,
)


def _line(**overrides: object) -> LineMark:
    base: dict[str, object] = {"x": (0.0, 1.0, 2.0), "y": (1.0, 1.1, 1.05)}
    return LineMark(**{**base, **overrides})  # type: ignore[arg-type]


def _panel(*marks: object, **overrides: object) -> Panel:
    base: dict[str, object] = {
        "panel_id": "equity",
        "y_label": "Equity (x initial)",
        "y_unit": "multiple",
        "marks": marks or (_line(),),
    }
    return Panel(**{**base, **overrides})  # type: ignore[arg-type]


def _spec(**overrides: object) -> FigureSpec:
    base: dict[str, object] = {
        "figure_id": "equity_underwater",
        "title": "Equity and drawdown",
        "subtitle": "SPY - ts_momentum",
        "x_label": "Date (UTC)",
        "x_kind": "time",
        "panels": (_panel(),),
        "question": "How did capital grow, and how deep were the holes?",
        "plain_language_answer": "Equity ended above where it started.",
        "uncertainty": "One realised path; not a distribution.",
        "caveat": "Net of modelled fees only.",
    }
    return FigureSpec(**{**base, **overrides})  # type: ignore[arg-type]


class TestMarks:
    def test_line_rejects_misaligned_series(self) -> None:
        with pytest.raises(DataError, match="must align"):
            _line(y=(1.0, 2.0))

    def test_line_rejects_non_finite_values(self) -> None:
        with pytest.raises(DataError, match="finite"):
            _line(y=(1.0, float("nan"), 1.0))

    def test_empty_series_is_rejected_rather_than_drawn_blank(self) -> None:
        with pytest.raises(DataError, match="at least one point"):
            LineMark(x=(), y=())

    def test_band_rejects_inverted_bounds(self) -> None:
        with pytest.raises(DataError, match="lower must never exceed"):
            BandMark(x=(0.0, 1.0), lower=(2.0, 0.0), upper=(1.0, 1.0))

    def test_histogram_requires_one_more_edge_than_count(self) -> None:
        with pytest.raises(DataError, match=r"len\(edges\)"):
            HistogramMark(edges=(0.0, 1.0), counts=(3.0, 4.0))

    def test_histogram_rejects_non_monotonic_edges(self) -> None:
        with pytest.raises(DataError, match="increase strictly"):
            HistogramMark(edges=(0.0, 1.0, 0.5), counts=(1.0, 2.0))

    def test_heatmap_requires_a_unit_bearing_colorbar_label(self) -> None:
        with pytest.raises(DataError, match="colorbar_label"):
            HeatmapMark(rows=("2024",), columns=("Jan",), values=((0.1,),), colorbar_label="  ")

    def test_heatmap_accepts_absent_cells_as_none_not_zero(self) -> None:
        mark = HeatmapMark(
            rows=("2024",),
            columns=("Jan", "Feb"),
            values=((0.1, None),),
            colorbar_label="Monthly return (%)",
        )
        assert mark.values[0][1] is None

    def test_errorbar_series_must_align_with_categories(self) -> None:
        with pytest.raises(DataError, match="align with its categories"):
            ErrorBarMark(categories=("sharpe", "cagr"), point=(0.8,), lower=(-0.1,), upper=(1.7,))

    def test_table_rows_must_align_with_columns(self) -> None:
        with pytest.raises(DataError, match="align with columns"):
            TableMark(columns=("peak", "trough"), rows=(("2020-02-19",),))

    def test_zone_requires_a_positive_span(self) -> None:
        with pytest.raises(DataError, match="x1 must exceed"):
            ZoneMark(x0=5.0, x1=5.0)

    def test_bar_hatching_must_align_when_supplied(self) -> None:
        with pytest.raises(DataError, match="hatched must align"):
            BarMark(x=(0.0, 1.0), y=(1.0, 2.0), hatched=(True,))

    def test_alpha_outside_the_unit_interval_is_rejected(self) -> None:
        with pytest.raises(DataError, match="alpha"):
            _line(alpha=0.0)


class TestRoles:
    def test_unknown_role_is_rejected(self) -> None:
        with pytest.raises(DataError, match="unsupported mark role"):
            _line(role="highlight")

    def test_categorical_mark_must_declare_its_slot(self) -> None:
        with pytest.raises(DataError, match="must declare its palette_index"):
            _line(role="categorical")

    def test_palette_index_is_meaningless_off_the_categorical_role(self) -> None:
        with pytest.raises(DataError, match="only meaningful for a categorical"):
            _line(role="subject", palette_index=2)


class TestPanel:
    def test_unit_must_come_from_the_closed_vocabulary(self) -> None:
        with pytest.raises(DataError, match="outside the declared vocabulary"):
            _panel(y_unit="furlongs")

    def test_panel_must_draw_something(self) -> None:
        with pytest.raises(DataError, match="at least one mark"):
            Panel(panel_id="empty", y_label="Nothing (ratio)", y_unit="ratio", marks=())

    def test_legend_entries_are_derived_from_labelled_marks(self) -> None:
        panel = _panel(
            _line(label="Equity"),
            _line(label=None, role="substrate"),
            RuleMark(orientation="horizontal", position=1.0, label="Start", role="reference"),
        )
        assert [mark.label for mark in panel.legend_entries] == ["Equity", "Start"]

    def test_inverted_limits_are_rejected(self) -> None:
        with pytest.raises(DataError, match="y_limits must be increasing"):
            _panel(y_limits=(1.0, 0.0))


class TestFigureSpec:
    def test_a_well_formed_spec_reports_its_panel_count(self) -> None:
        assert _spec().panel_count == 1

    def test_duplicate_panel_ids_are_rejected(self) -> None:
        with pytest.raises(DataError, match="duplicate ids"):
            _spec(panels=(_panel(), _panel()))

    def test_a_figure_must_answer_a_question_in_plain_language(self) -> None:
        with pytest.raises(DataError, match="plain_language_answer"):
            _spec(plain_language_answer="")

    def test_a_figure_must_state_the_question_it_answers(self) -> None:
        with pytest.raises(DataError, match="question"):
            _spec(question="   ")

    def test_category_axis_requires_categories(self) -> None:
        with pytest.raises(DataError, match="must declare x_categories"):
            _spec(x_kind="category")

    def test_categories_are_rejected_on_a_continuous_axis(self) -> None:
        with pytest.raises(DataError, match="only meaningful for a category"):
            _spec(x_kind="time", x_categories=("a", "b"))

    def test_a_spec_cannot_express_a_secondary_axis(self) -> None:
        """The #1 charting error is unrepresentable rather than merely discouraged."""
        assert not any(
            "twin" in name or "secondary" in name for name in FigureSpec.__dataclass_fields__
        )
        assert not any("twin" in name or "secondary" in name for name in Panel.__dataclass_fields__)


class TestFeatureMarks:
    def test_a_feature_mark_can_carry_its_value_in_place(self) -> None:
        mark = ScatterMark(
            x=(3.0,),
            y=(11500.0,),
            role="feature",
            label="Head & shoulders",
            marker="v",
        )
        labelled = _line(role="feature", end_label=ValueLabel(text="-12.4%"), label="Neckline")
        assert mark.role == "feature"
        assert labelled.end_label is not None
        assert labelled.end_label.text == "-12.4%"
