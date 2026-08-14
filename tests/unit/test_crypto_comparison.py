from __future__ import annotations

from datetime import UTC, datetime, timedelta

import polars as pl

from alpha_data.crypto.quality import compare_market_observations

NOW = datetime(2026, 8, 15, tzinfo=UTC)


def _frame(values: list[float]) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "timestamp": [NOW - timedelta(hours=2), NOW - timedelta(hours=1)],
            "close": values,
        }
    )


def test_comparison_retains_all_venue_values_and_never_selects_fallback() -> None:
    diagnostics, summary = compare_market_observations(
        primary=_frame([100.0, 101.0]),
        primary_provider="binance",
        primary_sha256="a" * 64,
        comparisons=(
            ("ccxt:coinbase", "b" * 64, _frame([100.1, 101.1])),
            ("bybit", "c" * 64, _frame([99.9, 100.9])),
        ),
        timestamp_column="timestamp",
        value_column="close",
        warning_bps=100.0,
        quarantine_bps=500.0,
    )

    assert summary.state == "qualified"
    assert diagnostics["binance_close"].to_list() == [100.0, 101.0]
    assert diagnostics["ccxt_coinbase_close"].to_list() == [100.1, 101.1]
    assert not any("selected" in column or "fallback" in column for column in diagnostics.columns)


def test_divergence_warns_or_quarantines_without_rewriting_primary() -> None:
    warning_frame, warning = compare_market_observations(
        primary=_frame([100.0, 100.0]),
        primary_provider="binance",
        primary_sha256="a" * 64,
        comparisons=(("bybit", "b" * 64, _frame([102.0, 102.0])),),
        timestamp_column="timestamp",
        value_column="close",
        warning_bps=100,
        quarantine_bps=500,
    )
    quarantine_frame, quarantine = compare_market_observations(
        primary=_frame([100.0, 100.0]),
        primary_provider="binance",
        primary_sha256="a" * 64,
        comparisons=(("ccxt:coinbase", "c" * 64, _frame([110.0, 110.0])),),
        timestamp_column="timestamp",
        value_column="close",
        warning_bps=100,
        quarantine_bps=500,
    )
    assert warning.state == "warning" and warning.max_abs_divergence_bps == 200.0
    assert quarantine.state == "quarantined"
    assert warning_frame["binance_close"].to_list() == [100.0, 100.0]
    assert quarantine_frame["binance_close"].to_list() == [100.0, 100.0]


def test_missing_comparison_rows_are_explicit_and_change_identity() -> None:
    short = _frame([100.0, 100.0]).head(1)
    _, first = compare_market_observations(
        primary=_frame([100.0, 100.0]),
        primary_provider="binance",
        primary_sha256="a" * 64,
        comparisons=(("bybit", "b" * 64, short),),
        timestamp_column="timestamp",
        value_column="close",
        warning_bps=100,
        quarantine_bps=500,
    )
    _, changed = compare_market_observations(
        primary=_frame([100.0, 100.0]),
        primary_provider="binance",
        primary_sha256="a" * 64,
        comparisons=(("bybit", "c" * 64, short),),
        timestamp_column="timestamp",
        value_column="close",
        warning_bps=100,
        quarantine_bps=500,
    )
    assert first.state == "warning"
    assert first.missing_observations == 1
    assert first.comparison_id != changed.comparison_id
