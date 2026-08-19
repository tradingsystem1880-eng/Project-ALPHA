"""Future-poison guards for the crypto crowding composition and the candidate runtime."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import polars as pl
import pytest

from alpha_cli.research_crypto_data import compose_crypto_crowding_observations
from alpha_cli.strategy_candidate_runtime import _admit, _causal_return_regimes
from alpha_strategies.hedged_basis import HedgedBasisObservationV1

START = datetime(2025, 1, 1, tzinfo=UTC)
EVENTS = 370
CUTOFF_INDEX = 367


def _frames(*, poison_after: datetime | None) -> dict[str, pl.DataFrame]:
    """Compose the registered family bundle, optionally absurd strictly after ``poison_after``."""
    funding_times = [START + timedelta(hours=8 * index) for index in range(EVENTS)]
    hourly = [
        START - timedelta(hours=25) + timedelta(hours=index)
        for index in range(25 + 8 * (EVENTS - 1) + 1)
    ]

    def poisoned(timestamps: list[datetime], values: list[float], absurd: float) -> list[float]:
        if poison_after is None:
            return values
        return [
            absurd if timestamp > poison_after else value
            for timestamp, value in zip(timestamps, values, strict=True)
        ]

    def bars(family: str) -> pl.DataFrame:
        if family == "trade":
            closes = [100.0 + 0.01 * index for index in range(len(hourly))]
        elif family == "premium":
            closes = [0.001 + 0.0001 * (index % 5) for index in range(len(hourly))]
        else:
            closes = [100.0 + 0.02 * (index % 7) for index in range(len(hourly))]
        absurd = 9.0 if family == "premium" else 900_000.0
        return pl.DataFrame(
            {
                "timestamp": hourly,
                "category": ["linear"] * len(hourly),
                "symbol": ["BTCUSDT"] * len(hourly),
                "family": [family] * len(hourly),
                "close": poisoned(hourly, closes, absurd),
            }
        )

    def hourly_frame(column: str, values: list[float], absurd: float) -> pl.DataFrame:
        return pl.DataFrame(
            {
                "timestamp": hourly,
                "category": ["linear"] * len(hourly),
                "symbol": ["BTCUSDT"] * len(hourly),
                column: poisoned(hourly, values, absurd),
            }
        )

    return {
        "funding": pl.DataFrame(
            {
                "timestamp": funding_times,
                "category": ["linear"] * EVENTS,
                "symbol": ["BTCUSDT"] * EVENTS,
                "funding_rate": poisoned(
                    funding_times,
                    [0.001 + 0.000_001 * index for index in range(EVENTS)],
                    5.0,
                ),
            }
        ),
        "open_interest": hourly_frame(
            "open_interest", [1_000.0 + index for index in range(len(hourly))], 9e9
        ),
        "long_short_ratio": hourly_frame("long_short_ratio", [1.25] * len(hourly), 900.0),
        "premium_bars": bars("premium"),
        "mark_bars": bars("mark"),
        "index_bars": bars("index"),
        "derivative_bars": bars("trade"),
        "instrument_catalog": pl.DataFrame(
            {
                "symbol": ["BTCUSDT"],
                "category": ["linear"],
                "status": ["Trading"],
                "base_coin": ["BTC"],
                "quote_coin": ["USDT"],
                "funding_interval_minutes": [480],
            }
        ),
    }


@pytest.mark.bias_guard
def test_crowding_observations_never_read_a_bar_after_their_own_funding_event() -> None:
    """Rewriting every input strictly after event ``k`` may not move observations ``0..k``."""
    clean = compose_crypto_crowding_observations(_frames(poison_after=None), correction_lineage=())
    cutoff = clean[CUTOFF_INDEX].funding_time
    poisoned = compose_crypto_crowding_observations(
        _frames(poison_after=cutoff), correction_lineage=()
    )

    assert len(poisoned) == len(clean)
    # Observations strictly before the cutoff resolve every mark, including their outcome.
    assert poisoned[:CUTOFF_INDEX] == clean[:CUTOFF_INDEX]
    decision = clean[CUTOFF_INDEX]
    observed = poisoned[CUTOFF_INDEX]
    for field in (
        "regime",
        "recent_trend",
        "recent_volatility",
        "premium",
        "entry_mark",
        "entry_index",
        "funding_rate",
        "open_interest",
        "long_short_ratio",
    ):
        assert getattr(observed, field) == getattr(decision, field), field
    assert decision.regime != "warmup"
    # The poison is potent: the events that legitimately read past the cutoff do move.
    assert poisoned[CUTOFF_INDEX + 1 :] != clean[CUTOFF_INDEX + 1 :]


def _observation(index: int, *, exit_price: float = 99.0) -> HedgedBasisObservationV1:
    event = START + timedelta(hours=16 * index)
    return HedgedBasisObservationV1.create(
        event_time=event,
        event_available_at=event,
        entry_time=event + timedelta(hours=1),
        entry_available_at=event + timedelta(hours=1),
        exit_time=event + timedelta(hours=8),
        exit_available_at=event + timedelta(hours=8),
        bybit_perp_entry=100.0,
        bybit_perp_exit=exit_price,
        binance_spot_entry=100.0,
        binance_spot_exit=100.0,
        funding_rate=0.001,
        funding_available_at=event,
        perp_quantity_btc=-1.0,
        spot_quantity_btc=1.0,
        input_sha256=(("binance_spot", "a" * 64), ("bybit_linear", "b" * 64)),
        event_operator_fingerprint="c" * 64,
        correction_lineage=(),
    )


@pytest.mark.bias_guard
def test_candidate_admission_excludes_events_whose_outcome_is_not_yet_available() -> None:
    observations = tuple(_observation(index) for index in range(6))
    cutoff = observations[2].exit_available_at
    poisoned = observations[:3] + tuple(
        _observation(index, exit_price=9_999_999.0) for index in range(3, 6)
    )

    assert _admit(observations, as_of=cutoff) == observations[:3]
    assert _admit(poisoned, as_of=cutoff) == observations[:3]
    # The poison is potent: without a cutoff the rewritten exits do reach the caller.
    assert _admit(poisoned, as_of=None) != observations


@pytest.mark.bias_guard
def test_causal_return_regimes_label_each_event_from_prior_magnitudes_only() -> None:
    returns = np.asarray([0.01, -0.02, 0.005, 0.03, -0.001, 0.04, -0.05, 0.002], dtype=np.float64)
    clean = _causal_return_regimes(returns)
    poisoned = _causal_return_regimes(
        np.concatenate((returns[:5], np.asarray([1e-9, -1e-9, 1e-9], dtype=np.float64)))
    )

    assert poisoned[:6].tolist() == clean[:6].tolist()
    assert poisoned[6:].tolist() != clean[6:].tolist()
