"""defi_tvl_residual feature (ADR-0036): alignment, lag, OLS parity with alpha_patterns, ATR."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import polars as pl
import pytest

from alpha_core import DataError
from alpha_data.crypto.contracts import CryptoDatasetIdentityV1, CryptoQualityReportV1
from alpha_data.crypto.features import (
    QualifiedCryptoFrame,
    _trailing_log_ols_prediction,
    defi_tvl_residual_features,
)
from alpha_patterns.vsa import rolling_ols_residual

NOW = datetime(2026, 8, 15, tzinfo=UTC)
SHA = "b" * 64


def _quality(observed_end: datetime, rows: int) -> CryptoQualityReportV1:
    return CryptoQualityReportV1(
        dataset_sha256=SHA,
        method_version="crypto-quality-v1",
        state="qualified",
        failures=(),
        warnings=(),
        observed_start=observed_end - timedelta(days=rows),
        observed_end=observed_end,
        row_count=rows,
        correction_lineage=(),
    )


def _tvl(
    days: list[datetime], values: list[float], chain: str = "ethereum"
) -> QualifiedCryptoFrame:
    frame = pl.DataFrame(
        {
            "chain": [chain] * len(days),
            "observed_at": days,
            "tvl_usd": values,
            "available_at": [d + timedelta(days=1) for d in days],
        }
    )
    return QualifiedCryptoFrame(
        name="tvl",
        dataset=CryptoDatasetIdentityV1(
            provider="defillama",
            venue="defillama",
            market_type="network",
            family="defi_tvl",
            instrument=chain,
            base_asset="ETH",
            quote_asset="USD",
            frequency="1d",
            units="usd",
            timestamp_convention="utc_day_start_available_next_day",
        ),
        artifact_sha256=SHA,
        quality=_quality(days[-1], len(days)),
        frame=frame,
    )


def _market(days: list[datetime], closes: list[float]) -> QualifiedCryptoFrame:
    frame = pl.DataFrame(
        {
            "timestamp": [d + timedelta(hours=12) for d in days],  # intraday stamps join by day
            "open": closes,
            "high": [c * 1.01 for c in closes],
            "low": [c * 0.99 for c in closes],
            "close": closes,
        }
    )
    return QualifiedCryptoFrame(
        name="market",
        dataset=CryptoDatasetIdentityV1(
            provider="binance",
            venue="binance",
            market_type="spot",
            family="market_bars",
            instrument="ETHUSDT",
            base_asset="ETH",
            quote_asset="USDT",
            frequency="1d",
            units="provider_native",
            timestamp_convention="interval_end_utc",
        ),
        artifact_sha256=SHA,
        quality=_quality(days[-1], len(days)),
        frame=frame,
    )


def _days(n: int) -> list[datetime]:
    return [NOW - timedelta(days=n - i) for i in range(n)]


def test_trailing_ols_prediction_matches_the_pattern_layer_residual() -> None:
    rng = np.random.default_rng(3)
    x = rng.normal(0.0, 1.0, 80)
    y = 0.7 * x + rng.normal(0.0, 0.3, 80)
    predicted = _trailing_log_ols_prediction(x, y, 20)
    reference = rolling_ols_residual(x, y, window=20, min_r=0.0, require_positive_slope=False)
    # vsa returns y - prediction over the same inclusive trailing window
    assert np.all(np.isnan(predicted[:19])) and np.all(np.isnan(reference[:19]))
    np.testing.assert_allclose(y[19:] - predicted[19:], reference[19:], rtol=1e-9, atol=1e-12)
    # a NaN inside the window blanks the prediction
    x_nan = x.copy()
    x_nan[30] = np.nan
    assert np.all(np.isnan(_trailing_log_ols_prediction(x_nan, y, 20)[30:50]))
    assert np.isfinite(_trailing_log_ols_prediction(x_nan, y, 20)[50])


def test_feature_lags_tvl_by_one_day_and_normalises_by_atr() -> None:
    days = _days(10)
    tvl_values = [1.0e9 * (1.0 + 0.05 * i) for i in range(10)]
    closes = [100.0 * (1.0 + 0.02 * i) for i in range(10)]
    frame, artifact = defi_tvl_residual_features(
        _tvl(days, tvl_values), _market(days, closes), available_at=NOW, window=4, atr_window=3
    )
    assert frame.columns == [
        "chain",
        "timestamp",
        "close",
        "tvl_usd_lag1",
        "predicted_close",
        "atr",
        "tvl_residual",
        "available_at",
    ]
    assert frame.height == 10 and artifact.feature_name == "defi_tvl_residual"
    lag = frame["tvl_usd_lag1"].to_list()
    assert lag[0] is None or np.isnan(lag[0])
    assert lag[1:] == pytest.approx(tvl_values[:-1])
    # ATR: true range needs a prior close, so the first full window ends at index atr_window
    atr = frame["atr"].to_numpy()
    assert np.all(np.isnan(atr[:3])) and np.all(np.isfinite(atr[3:]))
    high, low = np.array(closes) * 1.01, np.array(closes) * 0.99
    prev = np.concatenate(([np.nan], closes[:-1]))
    tr = np.maximum.reduce([high - low, np.abs(high - prev), np.abs(low - prev)])
    assert atr[5] == pytest.approx(np.mean(tr[3:6]))
    residual = frame["tvl_residual"].to_numpy()
    assert np.all(np.isnan(residual[:4]))  # OLS needs 4 lagged points: indices 1..4
    predicted = frame["predicted_close"].to_numpy()
    assert residual[6] == pytest.approx((closes[6] - predicted[6]) / atr[6])
    assert (frame["available_at"] == NOW).all()


def test_feature_fails_loud_on_bad_windows_alignment_and_values() -> None:
    days = _days(8)
    tvl = _tvl(days, [1.0e9] * 8)
    market = _market(days, [100.0] * 8)
    with pytest.raises(DataError, match=r"^defi_tvl_residual windows must be"):
        defi_tvl_residual_features(tvl, market, available_at=NOW, window=2)
    with pytest.raises(DataError, match=r"^defi_tvl_residual needs more aligned days"):
        defi_tvl_residual_features(tvl, market, available_at=NOW, window=8)
    with pytest.raises(DataError, match=r"^crypto feature requires defi_tvl input$"):
        defi_tvl_residual_features(market, tvl, available_at=NOW, window=4)
    two_chains = _tvl(days, [1.0e9] * 8)
    two_chains.frame[0, "chain"] = "arbitrum"
    with pytest.raises(DataError, match=r"^defi_tvl_residual requires exactly one chain$"):
        defi_tvl_residual_features(two_chains, market, available_at=NOW, window=4)
    negative = _market(days, [100.0] * 7 + [-1.0])
    with pytest.raises(DataError, match=r"^defi_tvl_residual requires positive close and TVL"):
        defi_tvl_residual_features(tvl, negative, available_at=NOW, window=4)
    with pytest.raises(
        DataError, match=r"^crypto feature availability precedes an input observation$"
    ):
        defi_tvl_residual_features(tvl, market, available_at=NOW - timedelta(days=3), window=4)
