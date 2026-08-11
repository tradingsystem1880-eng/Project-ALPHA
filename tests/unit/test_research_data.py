"""Research-only dataset references and equal-duration intraday bars."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest

from alpha_core import DataError
from alpha_research import EqualDurationResearchBars, ResearchBar, ResearchDatasetRef

_HASH = "a" * 64


def _dataset() -> ResearchDatasetRef:
    return ResearchDatasetRef(
        dataset_id="quantpad-spy-4h-v1",
        provider="quantpad",
        provider_symbol="SPY",
        symbol="SPY",
        venue="XNYS",
        timeframe="4h",
        timezone="America/New_York",
        session="extended_hours",
        content_sha256=_HASH,
    )


def _bar(index: int, *, hours: int = 4, dataset_id: str = "quantpad-spy-4h-v1") -> ResearchBar:
    start = datetime(2024, 1, 2, tzinfo=UTC) + index * timedelta(hours=4)
    return ResearchBar(
        dataset_id=dataset_id,
        start=start,
        end=start + timedelta(hours=hours),
        available_at=start + timedelta(hours=hours),
        open=100.0,
        high=102.0,
        low=99.0,
        close=101.0,
        volume=1_000.0,
    )


def test_dataset_ref_is_explicitly_research_only() -> None:
    dataset = _dataset()

    assert dataset.scope == "research_only"
    assert dataset.content_sha256 == _HASH


def test_dataset_ref_rejects_malformed_identity_or_hash() -> None:
    values = _dataset().to_dict()
    values["provider"] = ""
    with pytest.raises(DataError, match="non-empty"):
        ResearchDatasetRef.from_dict(values)

    values = _dataset().to_dict()
    values["content_sha256"] = "not-a-hash"
    with pytest.raises(DataError, match="SHA-256"):
        ResearchDatasetRef.from_dict(values)

    values = _dataset().to_dict()
    values.pop("venue")
    with pytest.raises(DataError, match="unexpected fields"):
        ResearchDatasetRef.from_dict(values)

    values = _dataset().to_dict()
    values["scope"] = "canonical"
    with pytest.raises(DataError, match="research_only"):
        ResearchDatasetRef.from_dict(values)


def test_equal_duration_bar_collection_accepts_gaps_but_not_mixed_durations() -> None:
    collection = EqualDurationResearchBars(_dataset(), (_bar(0), _bar(1), _bar(3)))

    assert collection.duration == timedelta(hours=4)
    assert len(collection.bars) == 3

    with pytest.raises(DataError, match="equal duration"):
        EqualDurationResearchBars(_dataset(), (_bar(0), _bar(1, hours=3)))


def test_bar_collection_rejects_overlap_order_and_dataset_mismatch() -> None:
    first = _bar(0)
    overlapping = ResearchBar(
        dataset_id=first.dataset_id,
        start=first.start + timedelta(hours=2),
        end=first.end + timedelta(hours=2),
        available_at=first.end + timedelta(hours=2),
        open=100.0,
        high=102.0,
        low=99.0,
        close=101.0,
        volume=1_000.0,
    )
    with pytest.raises(DataError, match="strictly ordered and non-overlapping"):
        EqualDurationResearchBars(_dataset(), (first, overlapping))
    with pytest.raises(DataError, match="dataset_id"):
        EqualDurationResearchBars(_dataset(), (first, _bar(1, dataset_id="other")))


def test_research_bar_enforces_availability_and_ohlcv_invariants() -> None:
    start = datetime(2024, 1, 2, tzinfo=UTC)
    with pytest.raises(DataError, match="available_at"):
        ResearchBar(
            dataset_id="dataset",
            start=start,
            end=start + timedelta(hours=4),
            available_at=start + timedelta(hours=3),
            open=100.0,
            high=102.0,
            low=99.0,
            close=101.0,
            volume=1_000.0,
        )
    with pytest.raises(DataError, match="OHLC"):
        ResearchBar(
            dataset_id="dataset",
            start=start,
            end=start + timedelta(hours=4),
            available_at=start + timedelta(hours=4),
            open=100.0,
            high=99.0,
            low=98.0,
            close=101.0,
            volume=1_000.0,
        )


@pytest.mark.parametrize(
    "bar",
    [
        lambda: ResearchBar(
            "",
            datetime(2024, 1, 2, tzinfo=UTC),
            datetime(2024, 1, 2, 4, tzinfo=UTC),
            datetime(2024, 1, 2, 4, tzinfo=UTC),
            100,
            102,
            99,
            101,
            1_000,
        ),
        lambda: ResearchBar(
            "dataset",
            datetime(2024, 1, 2),
            datetime(2024, 1, 2, 4),
            datetime(2024, 1, 2, 4),
            100,
            102,
            99,
            101,
            1_000,
        ),
        lambda: ResearchBar(
            "dataset",
            datetime(2024, 1, 2, 4, tzinfo=UTC),
            datetime(2024, 1, 2, tzinfo=UTC),
            datetime(2024, 1, 2, 4, tzinfo=UTC),
            100,
            102,
            99,
            101,
            1_000,
        ),
        lambda: ResearchBar(
            "dataset",
            datetime(2024, 1, 2, tzinfo=UTC),
            datetime(2024, 1, 2, 4, tzinfo=UTC),
            datetime(2024, 1, 2, 4, tzinfo=UTC),
            100,
            102,
            99,
            float("nan"),
            1_000,
        ),
        lambda: ResearchBar(
            "dataset",
            datetime(2024, 1, 2, tzinfo=UTC),
            datetime(2024, 1, 2, 4, tzinfo=UTC),
            datetime(2024, 1, 2, 4, tzinfo=UTC),
            -100,
            102,
            99,
            101,
            1_000,
        ),
        lambda: ResearchBar(
            "dataset",
            datetime(2024, 1, 2, tzinfo=UTC),
            datetime(2024, 1, 2, 4, tzinfo=UTC),
            datetime(2024, 1, 2, 4, tzinfo=UTC),
            100,
            102,
            99,
            101,
            -1,
        ),
    ],
)
def test_additional_research_bar_guards(bar: Callable[[], object]) -> None:
    with pytest.raises(DataError):
        bar()


def test_equal_duration_collection_rejects_empty_input() -> None:
    with pytest.raises(DataError, match="non-empty"):
        EqualDurationResearchBars(_dataset(), ())
