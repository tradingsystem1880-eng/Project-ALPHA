"""Causal in-memory implementation of Qlib's Alpha158-style feature recipe.

The worker receives a verified ALPHA OHLCV panel rather than a Qlib binary provider.  These
features therefore implement the official Alpha158 names and trailing-window definitions directly
over that immutable panel.  No expression reads a row after its feature timestamp.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np
import pandas as pd
import polars as pl
from numpy.typing import NDArray

_WINDOWS = (5, 10, 20, 30, 60)
_ROLLING_OPERATORS = (
    "ROC",
    "MA",
    "STD",
    "BETA",
    "RSQR",
    "RESI",
    "MAX",
    "MIN",
    "QTLU",
    "QTLD",
    "RANK",
    "RSV",
    "IMAX",
    "IMIN",
    "IMXD",
    "CORR",
    "CORD",
    "CNTP",
    "CNTN",
    "CNTD",
    "SUMP",
    "SUMN",
    "SUMD",
    "VMA",
    "VSTD",
    "WVMA",
    "VSUMP",
    "VSUMN",
    "VSUMD",
)
_BASE_NAMES = (
    "KMID",
    "KLEN",
    "KMID2",
    "KUP",
    "KUP2",
    "KLOW",
    "KLOW2",
    "KSFT",
    "KSFT2",
    "OPEN0",
    "HIGH0",
    "LOW0",
    "VWAP0",
)


def alpha158_feature_names() -> tuple[str, ...]:
    """Return the exact 158-column order used by Qlib's canonical Alpha158 handler."""
    names = _BASE_NAMES + tuple(
        f"{operator}{window}" for operator in _ROLLING_OPERATORS for window in _WINDOWS
    )
    if len(names) != 158:
        raise RuntimeError(f"Alpha158 recipe drift: expected 158 names, got {len(names)}")
    return names


def _regression_stat(values: NDArray[np.float64], *, kind: str) -> float:
    x = np.arange(values.size, dtype=np.float64)
    x_centered = x - float(x.mean())
    y_centered = values - float(values.mean())
    denominator = float(np.dot(x_centered, x_centered))
    if denominator <= 0.0:
        return 0.0
    slope = float(np.dot(x_centered, y_centered) / denominator)
    fitted = float(values.mean()) + slope * x_centered
    if kind == "slope":
        return slope
    if kind == "residual":
        return float(values[-1] - fitted[-1])
    total = float(np.dot(y_centered, y_centered))
    if total <= 0.0:
        return 0.0
    residual = values - fitted
    return float(max(0.0, 1.0 - np.dot(residual, residual) / total))


def _last_rank(values: NDArray[np.float64]) -> float:
    return float(np.count_nonzero(values <= values[-1]) / values.size)


def _distance_to_extreme(values: NDArray[np.float64], reducer: Callable[[Any], int]) -> float:
    return float(values.size - 1 - reducer(values))


def _symbol_features(raw: pd.DataFrame) -> pd.DataFrame:
    raw = raw.sort_values("session_ts", kind="mergesort").set_index("session_ts")
    open_ = raw["open"].astype("float64")
    high = raw["high"].astype("float64")
    low = raw["low"].astype("float64")
    close = raw["close"].astype("float64")
    volume = raw["volume"].astype("float64")
    log_volume = pd.Series(np.log(volume.to_numpy() + 1.0), index=raw.index)
    spread = high - low
    upper_body = pd.Series(np.maximum(open_, close), index=raw.index)
    lower_body = pd.Series(np.minimum(open_, close), index=raw.index)
    features: dict[str, pd.Series] = {}

    with np.errstate(divide="ignore", invalid="ignore"):
        features["KMID"] = (close - open_) / open_
        features["KLEN"] = spread / open_
        features["KMID2"] = (close - open_) / (spread + 1e-12)
        features["KUP"] = (high - upper_body) / open_
        features["KUP2"] = (high - upper_body) / (spread + 1e-12)
        features["KLOW"] = (lower_body - low) / open_
        features["KLOW2"] = (lower_body - low) / (spread + 1e-12)
        features["KSFT"] = (2.0 * close - high - low) / open_
        features["KSFT2"] = (2.0 * close - high - low) / (spread + 1e-12)
        features["OPEN0"] = open_ / close
        features["HIGH0"] = high / close
        features["LOW0"] = low / close
        # ALPHA's canonical panel has no vendor VWAP.  A causal typical-price proxy is explicit in
        # result provenance and is never presented as exchange-reported VWAP.
        features["VWAP0"] = ((high + low + close) / 3.0) / close

    close_change = close - close.shift(1)
    volume_change = volume - volume.shift(1)
    close_ratio = close / close.shift(1)
    volume_ratio_log = np.log(volume / volume.shift(1) + 1.0)
    price_direction = close_change.abs() * volume
    up = close_change.clip(lower=0.0)
    down = (-close_change).clip(lower=0.0)
    volume_up = volume_change.clip(lower=0.0)
    volume_down = (-volume_change).clip(lower=0.0)

    for window in _WINDOWS:
        rolling_close = close.rolling(window, min_periods=window)
        rolling_high = high.rolling(window, min_periods=window)
        rolling_low = low.rolling(window, min_periods=window)
        rolling_volume = volume.rolling(window, min_periods=window)
        absolute_move = close_change.abs().rolling(window, min_periods=window).sum()
        absolute_volume_move = volume_change.abs().rolling(window, min_periods=window).sum()
        with np.errstate(divide="ignore", invalid="ignore"):
            features[f"ROC{window}"] = close.shift(window) / close
            features[f"MA{window}"] = rolling_close.mean() / close
            features[f"STD{window}"] = rolling_close.std(ddof=0) / close
            features[f"BETA{window}"] = (
                rolling_close.apply(lambda values: _regression_stat(values, kind="slope"), raw=True)
                / close
            )
            features[f"RSQR{window}"] = rolling_close.apply(
                lambda values: _regression_stat(values, kind="r2"), raw=True
            )
            features[f"RESI{window}"] = (
                rolling_close.apply(
                    lambda values: _regression_stat(values, kind="residual"), raw=True
                )
                / close
            )
            features[f"MAX{window}"] = rolling_high.max() / close
            features[f"MIN{window}"] = rolling_low.min() / close
            features[f"QTLU{window}"] = rolling_close.quantile(0.8) / close
            features[f"QTLD{window}"] = rolling_close.quantile(0.2) / close
            features[f"RANK{window}"] = rolling_close.apply(_last_rank, raw=True)
            low_bound = rolling_low.min()
            high_bound = rolling_high.max()
            features[f"RSV{window}"] = (close - low_bound) / (high_bound - low_bound + 1e-12)
            imax = rolling_high.apply(
                lambda values: _distance_to_extreme(values, np.argmax), raw=True
            )
            imin = rolling_low.apply(
                lambda values: _distance_to_extreme(values, np.argmin), raw=True
            )
            features[f"IMAX{window}"] = imax / window
            features[f"IMIN{window}"] = imin / window
            features[f"IMXD{window}"] = (imax - imin) / window
            features[f"CORR{window}"] = rolling_close.corr(log_volume)
            features[f"CORD{window}"] = close_ratio.rolling(window, min_periods=window).corr(
                volume_ratio_log
            )
            positive = (close_change > 0.0).where(close_change.notna()).astype("float64")
            negative = (close_change < 0.0).where(close_change.notna()).astype("float64")
            cntp = positive.rolling(window, min_periods=window).mean()
            cntn = negative.rolling(window, min_periods=window).mean()
            features[f"CNTP{window}"] = cntp
            features[f"CNTN{window}"] = cntn
            features[f"CNTD{window}"] = cntp - cntn
            sum_up = up.rolling(window, min_periods=window).sum()
            sum_down = down.rolling(window, min_periods=window).sum()
            features[f"SUMP{window}"] = sum_up / (absolute_move + 1e-12)
            features[f"SUMN{window}"] = sum_down / (absolute_move + 1e-12)
            features[f"SUMD{window}"] = (sum_up - sum_down) / (absolute_move + 1e-12)
            features[f"VMA{window}"] = rolling_volume.mean() / (volume + 1e-12)
            features[f"VSTD{window}"] = rolling_volume.std(ddof=0) / (volume + 1e-12)
            weighted = price_direction.rolling(window, min_periods=window)
            features[f"WVMA{window}"] = weighted.std(ddof=0) / (weighted.mean() + 1e-12)
            sum_volume_up = volume_up.rolling(window, min_periods=window).sum()
            sum_volume_down = volume_down.rolling(window, min_periods=window).sum()
            features[f"VSUMP{window}"] = sum_volume_up / (absolute_volume_move + 1e-12)
            features[f"VSUMN{window}"] = sum_volume_down / (absolute_volume_move + 1e-12)
            features[f"VSUMD{window}"] = (sum_volume_up - sum_volume_down) / (
                absolute_volume_move + 1e-12
            )

    return (
        pd.DataFrame(features, index=raw.index)
        .replace([np.inf, -np.inf], np.nan)
        .loc[:, alpha158_feature_names()]
    )


def alpha158_features(panel: pl.DataFrame) -> pd.DataFrame:
    """Build a sorted ``(datetime, instrument) × 158`` trailing feature matrix."""
    source = panel.to_pandas()
    frames: list[pd.DataFrame] = []
    for symbol, raw in source.groupby("symbol", sort=True, observed=True):
        frame = _symbol_features(raw)
        frame["instrument"] = str(symbol)
        frames.append(frame.reset_index().set_index(["session_ts", "instrument"]))
    if not frames:
        raise RuntimeError("cannot build Alpha158 features from an empty panel")
    result = pd.concat(frames).sort_index(kind="mergesort")
    result.index.names = ["datetime", "instrument"]
    return result.loc[:, alpha158_feature_names()].astype("float64")
