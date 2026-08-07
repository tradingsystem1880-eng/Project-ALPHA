"""Deterministic research artifact and chart-data contracts."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest

from alpha_core import DataError
from alpha_research import (
    ResearchArtifactRef,
    ResearchChartData,
    ResearchChartPoint,
    ResearchChartSeries,
)


def _series(series_id: str, offset: float = 0.0) -> ResearchChartSeries:
    origin = datetime(2024, 1, 1, tzinfo=UTC)
    return ResearchChartSeries(
        series_id=series_id,
        label=series_id.upper(),
        unit="return",
        points=tuple(
            ResearchChartPoint(origin + i * timedelta(hours=4), offset + i / 100) for i in range(3)
        ),
    )


def _chart(
    series: tuple[ResearchChartSeries, ...],
    *,
    evidence_phase: str = "exploratory",
    sample_size: int = 40,
    effective_sample_size: float = 25.0,
) -> ResearchChartData:
    return ResearchChartData(
        chart_id="event-path",
        title="Event path",
        x_label="time",
        y_label="return",
        evidence_phase=evidence_phase,  # type: ignore[arg-type]
        dataset_sha256="e" * 64,
        protocol_sha256="f" * 64,
        question="Do confirmed double bottoms predict a positive return?",
        plain_language_answer="The chart compares registered event and control paths.",
        sample_size=sample_size,
        effective_sample_size=effective_sample_size,
        uncertainty="Intervals account for the registered dependence model.",
        caveat="Predictive association is not a causal effect.",
        run_id="research-run-1",
        artifact_id="event-path-data",
        artifact_sha256="a" * 64,
        series=series,
    )


def test_artifact_ref_validates_content_identity() -> None:
    artifact = ResearchArtifactRef(
        artifact_id="event-table",
        kind="table",
        media_type="application/vnd.apache.parquet",
        content_sha256="d" * 64,
        size_bytes=100,
        row_count=5,
    )

    assert artifact.to_dict()["content_sha256"] == "d" * 64
    assert artifact.contract_hash == artifact.contract_hash
    with pytest.raises(DataError, match="row_count"):
        ResearchArtifactRef("bad", "table", "text/csv", "d" * 64, 1, -1)


def test_chart_contract_hash_is_canonical_across_series_input_order() -> None:
    first = _chart((_series("event"), _series("control", 0.01)))
    second = _chart((_series("control", 0.01), _series("event")))

    assert first.contract_hash == second.contract_hash
    assert len(first.contract_hash) == 64
    assert first.watermark == "EXPLORATORY"
    assert first.to_dict()["plain_language_answer"]


def test_registered_chart_has_lineage_teaching_and_effective_sample_metadata() -> None:
    chart = _chart((_series("event"),), evidence_phase="confirmatory")

    assert chart.watermark == "REGISTERED CONFIRMATORY"
    assert chart.to_dict()["run_id"] == "research-run-1"
    assert chart.to_dict()["effective_sample_size"] == 25.0


def test_chart_series_rejects_noncausal_order_and_nonfinite_values() -> None:
    origin = datetime(2024, 1, 1, tzinfo=UTC)
    with pytest.raises(DataError, match="strictly increasing"):
        ResearchChartSeries(
            "bad-order",
            "Bad order",
            "return",
            (
                ResearchChartPoint(origin + timedelta(hours=4), 0.1),
                ResearchChartPoint(origin, 0.2),
            ),
        )
    with pytest.raises(DataError, match="finite"):
        ResearchChartPoint(origin, float("nan"))


def test_chart_rejects_duplicate_series_ids() -> None:
    with pytest.raises(DataError, match="unique"):
        _chart((_series("event"), _series("event")))


@pytest.mark.parametrize(
    "factory",
    [
        lambda: ResearchArtifactRef("", "table", "text/csv", "d" * 64, 1),
        lambda: ResearchArtifactRef("bad", "video", "text/csv", "d" * 64, 1),  # type: ignore[arg-type]
        lambda: ResearchArtifactRef("bad", "table", "text/csv", "x", 1),
        lambda: ResearchArtifactRef("bad", "table", "text/csv", "d" * 64, -1),
        lambda: ResearchChartPoint(datetime(2024, 1, 1), 0.0),
        lambda: ResearchChartSeries("empty", "Empty", "return", ()),
        lambda: _chart((_series("event"),), evidence_phase="other"),
        lambda: _chart((), evidence_phase="exploratory"),
        lambda: _chart((_series("event"),), sample_size=0),
        lambda: _chart((_series("event"),), effective_sample_size=41.0),
    ],
)
def test_artifact_and_chart_contracts_fail_loud(factory: Callable[[], object]) -> None:
    with pytest.raises(DataError):
        factory()
