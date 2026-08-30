"""S8 acceptance studies through alpha-study's common projection contracts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import polars as pl
import pytest

from alpha_core import DataError
from alpha_data.crypto.providers.binance import point_in_time_liquid_markets
from alpha_research import (
    DoubleBottomSpec,
    EqualDurationResearchBars,
    ResearchArtifactRef,
    ResearchBar,
    ResearchDatasetRef,
)
from alpha_research.crypto_crowding import (
    CryptoCrowdingObservationV1,
    registered_crypto_crowding_plan,
    select_registered_crypto_crowding_events,
)
from alpha_study import (
    EventRowV1,
    EventTableV1,
    FactorObservationTableV1,
    FactorObservationV1,
    FeatureInputRefV1,
    FeatureValueV1,
    adapt_double_bottom_events,
    canonical_study_sha256,
)

HASH_A = "a" * 64
HASH_B = "b" * 64
ORIGIN = datetime(2026, 8, 1, tzinfo=UTC)
FORBIDDEN_AUTHORITY_KEYS = {
    "approval",
    "approved",
    "broker_authority",
    "d2_reveal",
    "execution_authority",
    "order_authority",
    "paper_ready",
    "promotion_ready",
}


def _all_keys(value: object) -> set[str]:
    if isinstance(value, Mapping):
        return {str(key) for key in value} | {
            nested for child in value.values() for nested in _all_keys(child)
        }
    if isinstance(value, list):
        return {nested for child in value for nested in _all_keys(child)}
    return set()


def _assert_common_boundary(
    table: EventTableV1 | FactorObservationTableV1,
) -> None:
    payload = table.to_dict()
    restored = type(table).from_dict(payload)
    assert restored == table
    assert payload["authority"] == "none"
    assert payload["lineage_verification"] == "unverified_reference"
    assert not (_all_keys(payload) & FORBIDDEN_AUTHORITY_KEYS)


def _technical_bars() -> EqualDurationResearchBars:
    lows = (105.0, 103.0, 100.0, 95.0, 99.0, 101.0, 100.0, 95.5, 99.0, 101.0)
    dataset = ResearchDatasetRef(
        dataset_id="binance-btcusdt-technical-fixture",
        provider="binance",
        provider_symbol="BTCUSDT",
        symbol="BTCUSDT",
        venue="binance",
        timeframe="1h",
        timezone="UTC",
        session="continuous",
        content_sha256=HASH_A,
    )
    bars = tuple(
        ResearchBar(
            dataset_id=dataset.dataset_id,
            start=ORIGIN + timedelta(hours=index),
            end=ORIGIN + timedelta(hours=index + 1),
            available_at=ORIGIN + timedelta(hours=index + 1),
            open=low + 1.0,
            high=low + (6.0 if index == 4 else 2.0),
            low=low,
            close=low + 1.5,
            volume=1_000.0 + index,
        )
        for index, low in enumerate(lows)
    )
    return EqualDurationResearchBars(dataset, bars)


def _factor_source(
    *,
    provider: str,
    family: str,
    venue: str,
    available_at: datetime,
    row_count: int = 2,
    frequency: str = "1h",
) -> FeatureInputRefV1:
    artifact_hash = canonical_study_sha256(
        {"available_at": available_at.isoformat(), "family": family, "provider": provider}
    )
    return FeatureInputRefV1(
        artifact=ResearchArtifactRef(
            f"{family}-fixture", "table", "application/json", artifact_hash, 100, row_count
        ),
        input_available_at=available_at,
        snapshot_id=f"snapshot-{family}",
        snapshot_manifest_sha256=HASH_B,
        provider=provider,
        data_family=family,
        frequency=frequency,
        venue=venue,
    )


def _crowding_observations() -> tuple[CryptoCrowdingObservationV1, ...]:
    rows: list[CryptoCrowdingObservationV1] = []
    for index in range(420):
        funding_time = ORIGIN + timedelta(hours=8 * index)
        is_event = index == 380
        rows.append(
            CryptoCrowdingObservationV1(
                funding_time=funding_time,
                funding_available_at=funding_time,
                funding_rate=0.02 if is_event else 0.001 + index * 0.000001,
                open_interest=120.0 + index + (25.0 if is_event else 0.0),
                open_interest_available_at=funding_time,
                premium=0.002 if is_event else -0.001,
                premium_available_at=funding_time,
                entry_time=funding_time + timedelta(hours=1),
                entry_available_at=funding_time + timedelta(hours=1),
                entry_mark=100.0,
                entry_index=100.0,
                exit_time=funding_time + timedelta(hours=8),
                exit_available_at=funding_time + timedelta(hours=8),
                exit_mark=99.8 if is_event else 100.0,
                exit_index=100.0,
                long_short_ratio=1.2 if is_event else 1.0,
                recent_trend=0.01,
                recent_volatility=0.02,
                regime="normal",
                diagnostics_available_at=funding_time,
            )
        )
    return tuple(rows)


def _crowding_event_table(
    observations: tuple[CryptoCrowdingObservationV1, ...] | None = None,
) -> EventTableV1:
    observations = observations or _crowding_observations()
    plan = registered_crypto_crowding_plan()
    events = select_registered_crypto_crowding_events(observations)
    assert len(events) == 1
    event = events[0]
    observation = observations[event.observation_index]
    sources = {
        family: _factor_source(
            provider=plan.provider,
            family=family,
            venue=plan.provider,
            available_at=observation.funding_time,
            row_count=len(observations),
            frequency="funding_interval" if family == "funding" else plan.bar_frequency,
        )
        for family in ("funding", "open_interest", "premium_bars")
    }

    def feature(feature_id: str, value: float, unit: str, source_family: str) -> FeatureValueV1:
        return FeatureValueV1(
            feature_id=feature_id,
            role="state",
            value=value,
            value_type="float",
            observed_at=observation.funding_time,
            available_at=observation.funding_time,
            vintage_at=observation.funding_time,
            vintage_id="bybit-crowding-vintage-2026-12-05T16:00:00Z",
            sources=(sources[source_family],),
            computation_sha256=plan.operator_fingerprint,
            unit=unit,
            venue=plan.provider,
        )

    row = EventRowV1(
        study_id="crypto-crowding-btcusdt",
        entity_id="BTC",
        asset_class="crypto",
        instrument_id=plan.instrument,
        venue=plan.venue.casefold(),
        event_start=event.funding_time,
        event_end=event.funding_time,
        printed_at=event.funding_time,
        confirmed_at=observation.funding_time,
        available_at=observation.funding_time,
        direction=-1,
        operator_id=plan.bundle_id,
        operator_version="1.0.0",
        operator_code_sha256=plan.operator_fingerprint,
        parameter_sha256=plan.operator_fingerprint,
        features=(
            feature("crowding.funding_rate", event.funding_rate, "rate", "funding"),
            feature("crowding.funding_threshold", event.funding_threshold, "rate", "funding"),
            feature(
                "crowding.open_interest_change_24h",
                event.open_interest_change_24h,
                "base_coin",
                "open_interest",
            ),
            feature("crowding.premium", event.premium, "ratio", "premium_bars"),
        ),
        overlap_cluster_id=None,
        diagnostic_flags=(),
        parent_event_ids=(),
    )
    return EventTableV1("crypto-crowding-btcusdt", (row,))


def _factor_row(
    *,
    study_id: str,
    entity_id: str,
    instrument_id: str,
    factor_id: str,
    value: float,
    provider: str,
    family: str,
    venue: str,
    available_at: datetime,
    universe_snapshot_sha256: str = HASH_B,
) -> FactorObservationV1:
    observed_at = ORIGIN + timedelta(hours=24)
    source = _factor_source(
        provider=provider, family=family, venue=venue, available_at=available_at
    )
    factor = FeatureValueV1(
        feature_id=factor_id,
        role="factor",
        value=value,
        value_type="float",
        observed_at=observed_at,
        available_at=available_at,
        vintage_at=observed_at,
        vintage_id=f"{family}-vintage-2026-08-02T00:00:00Z",
        sources=(source,),
        computation_sha256=HASH_A,
        unit="ratio",
        venue=venue,
    )
    return FactorObservationV1(
        study_id=study_id,
        entity_id=entity_id,
        instrument_id=instrument_id,
        factor_id=factor_id,
        cross_section_at=observed_at,
        observed_at=observed_at,
        available_at=available_at,
        universe_snapshot_id=f"{study_id}-btc-eth",
        universe_snapshot_sha256=universe_snapshot_sha256,
        universe_available_at=observed_at,
        value=factor,
    )


def test_technical_event_crypto_study_uses_event_projection_without_authority() -> None:
    bars = _technical_bars()
    artifact = ResearchArtifactRef(
        "binance-btcusdt-bars", "table", "application/json", HASH_A, 1_000, len(bars.bars)
    )
    table = adapt_double_bottom_events(
        bars,
        DoubleBottomSpec(1, 2, 3, 6, 0.03, 0.05),
        study_id="technical-event-btcusdt",
        input_artifact=artifact,
        asset_class="crypto",
        entity_id="BTC",
        instrument_id="BTCUSDT",
    )

    _assert_common_boundary(table)
    assert len(table.rows) == 1
    row = table.rows[0]
    assert (row.asset_class, row.instrument_id, row.venue) == (
        "crypto",
        "BTCUSDT",
        "binance",
    )
    assert row.event_end <= row.printed_at <= row.confirmed_at <= row.available_at


def test_crypto_crowding_study_projects_only_pit_event_inputs() -> None:
    table = _crowding_event_table()
    _assert_common_boundary(table)
    row = table.rows[0]
    plan = registered_crypto_crowding_plan()
    assert (plan.provider, plan.venue, plan.market_type, plan.instrument, plan.quote_asset) == (
        "bybit",
        "BYBIT",
        "linear",
        "BTCUSDT",
        "USDT",
    )
    assert plan.required_families == (
        "funding",
        "open_interest",
        "premium_bars",
        "mark_bars",
        "index_bars",
        "derivative_bars",
        "instrument_catalog",
    )
    assert row.instrument_id == plan.instrument
    assert row.venue == plan.venue.casefold()
    assert row.parameter_sha256 == plan.operator_fingerprint
    assert row.direction == -1
    assert {feature.feature_id for feature in row.features} == {
        "crowding.funding_rate",
        "crowding.funding_threshold",
        "crowding.open_interest_change_24h",
        "crowding.premium",
    }
    assert {source.data_family for feature in row.features for source in feature.sources} == {
        "funding",
        "open_interest",
        "premium_bars",
    }
    assert {
        (source.provider, source.venue) for feature in row.features for source in feature.sources
    } == {(plan.provider, plan.provider)}
    assert "mark_minus_index_return" not in _all_keys(table.to_dict())
    poisoned = list(_crowding_observations())
    poisoned[380] = replace(poisoned[380], exit_mark=1_000_000.0, exit_index=1.0)
    assert _crowding_event_table(tuple(poisoned)).content_sha256 == table.content_sha256
    with pytest.raises(DataError, match="event input is not point-in-time available"):
        replace(
            poisoned[380],
            premium_available_at=poisoned[380].funding_time + timedelta(seconds=1),
        )


def test_cross_sectional_crypto_study_binds_exact_universe_and_quote() -> None:
    available_at = ORIGIN + timedelta(hours=24, minutes=2)
    observations = pl.DataFrame(
        {
            "session": [ORIGIN, ORIGIN, ORIGIN + timedelta(days=1)],
            "category": ["spot", "spot", "spot"],
            "symbol": ["BTCUSDT", "ETHUSDT", "FUTUREUSDT"],
            "base_asset": ["BTC", "ETH", "FUTURE"],
            "quote_asset": ["USDT", "USDT", "USDT"],
            "base_volume": [10.0, 50.0, 1_000_000.0],
            "quote_volume": [1_000.0, 500.0, 1_000_000.0],
            "contract_size": [None, None, None],
        }
    )
    selected = point_in_time_liquid_markets(
        observations,
        as_of=available_at,
        category="spot",
        quote_asset="USDT",
        limit=2,
        cadence=timedelta(days=1),
    )
    universe_sha256 = canonical_study_sha256(selected.to_dicts())
    returns = {"BTC": 0.031, "ETH": -0.012}
    rows = tuple(
        _factor_row(
            study_id="cross-sectional-crypto-btc-eth",
            entity_id=str(row["base_asset"]),
            instrument_id=str(row["symbol"]),
            factor_id="cross_sectional.trailing_return_24h",
            value=returns[str(row["base_asset"])],
            provider="binance",
            family="market_bars",
            venue="binance",
            available_at=available_at,
            universe_snapshot_sha256=universe_sha256,
        )
        for row in selected.to_dicts()
    )
    table = FactorObservationTableV1("cross-sectional-crypto-btc-eth", rows)

    _assert_common_boundary(table)
    assert {row.instrument_id for row in table.rows} == {"BTCUSDT", "ETHUSDT"}
    assert "FUTUREUSDT" not in {row.instrument_id for row in table.rows}
    assert selected.select("category", "quote_asset", "liquidity_units").unique().row(0) == (
        "spot",
        "USDT",
        "USDT_quote_volume",
    )
    assert len({row.universe_snapshot_sha256 for row in table.rows}) == 1
    assert table.rows[0].universe_snapshot_sha256 == universe_sha256
    assert all(row.universe_available_at <= row.available_at for row in table.rows)


def test_factor_projection_rejects_future_source_and_universe_poison() -> None:
    available_at = ORIGIN + timedelta(hours=24, minutes=2)
    row = _factor_row(
        study_id="cross-sectional-crypto-btc-eth",
        entity_id="BTC",
        instrument_id="BTCUSDT",
        factor_id="cross_sectional.trailing_return_24h",
        value=0.031,
        provider="binance",
        family="market_bars",
        venue="binance",
        available_at=available_at,
    )
    future_source = replace(
        row.value.sources[0], input_available_at=available_at + timedelta(seconds=1)
    )
    with pytest.raises(DataError, match="source input_available_at"):
        replace(row.value, sources=(future_source,))
    with pytest.raises(DataError, match="universe availability"):
        replace(row, universe_available_at=available_at + timedelta(seconds=1))
