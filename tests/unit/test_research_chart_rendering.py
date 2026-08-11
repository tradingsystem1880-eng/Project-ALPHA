"""Deterministic Matplotlib rendering of governed research chart data."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta

from alpha_research import (
    ResearchChartData,
    ResearchChartPoint,
    ResearchChartSeries,
    render_research_line_chart,
)


def _series(series_id: str, offset: float) -> ResearchChartSeries:
    origin = datetime(2024, 1, 1, tzinfo=UTC)
    return ResearchChartSeries(
        series_id=series_id,
        label=series_id.title(),
        unit="return",
        points=tuple(
            ResearchChartPoint(origin + index * timedelta(hours=4), offset + index / 100)
            for index in range(5)
        ),
    )


def _chart(series: tuple[ResearchChartSeries, ...]) -> ResearchChartData:
    return ResearchChartData(
        chart_id="matched-path",
        title="Matched event path",
        x_label="UTC event time",
        y_label="Forward return",
        evidence_phase="exploratory",
        dataset_sha256="a" * 64,
        protocol_sha256="b" * 64,
        question="Does the registered event outperform its matched control?",
        plain_language_answer="The event and matched control remain close.",
        sample_size=20,
        effective_sample_size=14.0,
        uncertainty="Bands use the frozen cluster bootstrap.",
        caveat="Predictive association is not a causal effect.",
        run_id="research-run-1",
        artifact_id="matched-path-data",
        artifact_sha256="c" * 64,
        series=series,
    )


def test_line_chart_png_is_byte_stable_and_series_order_canonical() -> None:
    event = _series("event", 0.01)
    control = _series("control", 0.0)

    first = render_research_line_chart(_chart((event, control)))
    second = render_research_line_chart(_chart((control, event)))

    assert first == second
    assert first.startswith(b"\x89PNG\r\n\x1a\n")
    assert hashlib.sha256(first).hexdigest() == hashlib.sha256(second).hexdigest()
    assert b"Creation Time" not in first
    assert b"Date" not in first


def test_png_embeds_teaching_lineage_and_visible_watermark_metadata() -> None:
    rendered = render_research_line_chart(_chart((_series("event", 0.01),)))

    for expected in (
        b"EXPLORATORY",
        b"Question",
        b"Does the registered event outperform its matched control?",
        b"PlainLanguageAnswer",
        b"The event and matched control remain close.",
        b"Uncertainty",
        b"Caveat",
        b"RunID",
        b"research-run-1",
        b"ProtocolSHA256",
    ):
        assert expected in rendered
