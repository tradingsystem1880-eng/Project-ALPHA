from __future__ import annotations

from datetime import UTC, datetime, timedelta

import polars as pl
import pytest

from alpha_cli.research_crypto_strategy import compose_hedged_basis_observations
from alpha_core import DataError
from alpha_research import CryptoCrowdingObservationV1
from alpha_strategies.hedged_basis import evaluate_hedged_basis


def _crowding_rows() -> tuple[CryptoCrowdingObservationV1, ...]:
    start = datetime(2025, 1, 1, tzinfo=UTC)
    rows: list[CryptoCrowdingObservationV1] = []
    for index in range(420):
        funding_time = start + timedelta(hours=8 * index)
        event = index == 380
        rows.append(
            CryptoCrowdingObservationV1(
                funding_time=funding_time,
                funding_available_at=funding_time,
                funding_rate=0.02 if event else 0.001 + index * 0.000001,
                open_interest=1_000.0 + index + (100.0 if event else 0.0),
                open_interest_available_at=funding_time,
                premium=0.002 if event else -0.001,
                premium_available_at=funding_time,
                entry_time=funding_time + timedelta(hours=1),
                entry_available_at=funding_time + timedelta(hours=1),
                entry_mark=100.0,
                entry_index=100.0,
                exit_time=funding_time + timedelta(hours=8),
                exit_available_at=funding_time + timedelta(hours=8),
                exit_mark=99.0 if event else 100.0,
                exit_index=100.0,
                long_short_ratio=1.0,
                recent_trend=0.0,
                recent_volatility=0.01,
                regime="normal",
                diagnostics_available_at=funding_time,
            )
        )
    return tuple(rows)


def _spot(rows: tuple[CryptoCrowdingObservationV1, ...]) -> pl.DataFrame:
    event = rows[380]
    return pl.DataFrame(
        {
            "open_time": [event.funding_time, event.exit_time - timedelta(hours=1)],
            "close_time": [
                event.entry_time - timedelta(milliseconds=1),
                event.exit_time - timedelta(milliseconds=1),
            ],
            "close": [100.0, 100.0],
        }
    )


def test_compose_hedged_basis_uses_registered_events_and_exact_spot_closes() -> None:
    rows = _crowding_rows()
    observations = compose_hedged_basis_observations(
        rows,
        _spot(rows),
        bybit_snapshot_sha256="a" * 64,
        binance_spot_sha256="b" * 64,
    )

    assert len(observations) == 1
    assert observations[0].event_time == rows[380].funding_time
    assert observations[0].bybit_perp_entry == 100.0
    assert observations[0].bybit_perp_exit == 99.0
    assert observations[0].binance_spot_entry == 100.0
    assert observations[0].binance_spot_exit == 100.0
    assert evaluate_hedged_basis(observations).trades[0].net_return == pytest.approx(0.026)


def test_compose_hedged_basis_rejects_missing_future_or_duplicate_spot_bars() -> None:
    rows = _crowding_rows()
    spot = _spot(rows)

    with pytest.raises(DataError, match="exact Binance spot close"):
        compose_hedged_basis_observations(
            rows,
            spot.head(1),
            bybit_snapshot_sha256="a" * 64,
            binance_spot_sha256="b" * 64,
        )
    future = spot.with_columns(
        pl.when(pl.col("open_time") == rows[380].funding_time)
        .then(pl.col("close_time") + timedelta(hours=2))
        .otherwise(pl.col("close_time"))
        .alias("close_time")
    )
    with pytest.raises(DataError, match="not causally available"):
        compose_hedged_basis_observations(
            rows,
            future,
            bybit_snapshot_sha256="a" * 64,
            binance_spot_sha256="b" * 64,
        )
    with pytest.raises(DataError, match="duplicated"):
        compose_hedged_basis_observations(
            rows,
            pl.concat((spot, spot.head(1))),
            bybit_snapshot_sha256="a" * 64,
            binance_spot_sha256="b" * 64,
        )
