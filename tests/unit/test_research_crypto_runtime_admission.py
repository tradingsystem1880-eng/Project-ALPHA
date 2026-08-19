from __future__ import annotations

import pytest

from alpha_cli.research_crypto_runtime import _admission
from alpha_core import DataError
from alpha_research import ResearchChartFingerprintV1, ResearchD2BoundaryV2


def _boundary(*, embargo: int) -> ResearchD2BoundaryV2:
    return ResearchD2BoundaryV2.from_eligible_groups(
        dataset_fingerprint="9" * 64,
        eligible_groups=tuple(f"group-{index:04d}" for index in range(100)),
        chart_fingerprint=ResearchChartFingerprintV1(
            instrument="BTCUSDT",
            provider="bybit",
            venue="bybit",
            timezone="UTC",
            session="continuous_crypto",
            bar_construction="fixed_60_elapsed_minute_bars",
            bar_duration_seconds=3_600,
            anchor="provider_interval_start",
            adjustment_basis="provider_native_unadjusted",
            timestamp_semantics="interval_start_utc",
        ),
        event_formula="registered-crypto-crowding-v1",
        event_availability_timestamp="bybit_funding_event_point_in_time",
        primary_endpoint="event_mark_return_minus_index_return",
        primary_horizon="next_provider_declared_funding_timestamp",
        outcome_overlap_embargo_groups=embargo,
    )


@pytest.mark.parametrize("evidence_zone", ("D1", "D2"))
def test_zero_embargo_boundary_is_refused(evidence_zone: str) -> None:
    """The operator peeks at the next observation, so the embargo may never be empty."""
    with pytest.raises(DataError, match="non-zero outcome-overlap embargo"):
        _admission(_boundary(embargo=0), evidence_zone)


@pytest.mark.parametrize("evidence_zone", ("D1", "D2"))
def test_admission_keeps_the_embargoed_tail_outside_the_zone(evidence_zone: str) -> None:
    boundary = _boundary(embargo=1)
    zone = boundary.d1 if evidence_zone == "D1" else boundary.d2

    assert _admission(boundary, evidence_zone) == (zone.start_index, zone.stop_index - 1)
