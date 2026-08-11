"""Availability-time and future-poison guards for MarketStateV1."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from alpha_research.market_state import (
    MarketSessionCloseV1,
    MarketStateContractV1,
    derive_market_state,
)


def _contract() -> MarketStateContractV1:
    return MarketStateContractV1(
        universe=("BTC", "ETH", "SOL"),
        benchmark="BTC",
        calendar="crypto_24_7",
        volatility_window=5,
        trend_window=5,
        correlation_window=5,
        annualization_sessions=365,
        volatility_thresholds=(0.25, 0.75),
        trend_threshold=0.02,
        breadth_thresholds=(1 / 3, 2 / 3),
        correlation_thresholds=(0.25, 0.75),
        minimum_state_samples=3,
    )


def _observations() -> list[MarketSessionCloseV1]:
    return [
        MarketSessionCloseV1(
            session=date(2026, 1, 1) + timedelta(days=index),
            available_at=datetime(2026, 1, 2, tzinfo=UTC) + timedelta(days=index),
            closes=(
                100.0 * (1.01**index),
                80.0 * (1.008**index),
                60.0 * (1.012**index),
            ),
        )
        for index in range(30)
    ]


@pytest.mark.bias_guard
def test_future_prices_cannot_rewrite_prior_market_states() -> None:
    clean_input = _observations()
    clean = derive_market_state(_contract(), clean_input)
    cutoff = 18
    poisoned_input = [
        *clean_input[:cutoff],
        *[
            MarketSessionCloseV1(
                session=row.session,
                available_at=row.available_at,
                closes=(
                    row.closes[0] * (10.0 if index % 2 else 0.1),
                    row.closes[1] * (0.1 if index % 2 else 10.0),
                    row.closes[2] * (5.0 if index % 2 else 0.2),
                ),
            )
            for index, row in enumerate(clean_input[cutoff:])
        ],
    ]
    poisoned = derive_market_state(_contract(), poisoned_input)
    assert poisoned.points[:cutoff] == clean.points[:cutoff]
    assert all(
        point.available_at == observation.available_at
        for point, observation in zip(poisoned.points, poisoned_input, strict=True)
    )
