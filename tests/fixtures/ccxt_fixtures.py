"""Build a ccxt-shaped OHLCV list: [[ms_timestamp, open, high, low, close, volume], ...]."""

from __future__ import annotations


def ccxt_ohlcv() -> list[list[float]]:
    # 2024-01-01, 2024-01-02, 2024-01-03 (UTC midnight in ms)
    return [
        [1704067200000, 42000.0, 43000.0, 41500.0, 42500.0, 1000.0],
        [1704153600000, 42500.0, 44000.0, 42400.0, 43800.0, 1200.0],
        [1704240000000, 43800.0, 44200.0, 43000.0, 43500.0, 900.0],
    ]
