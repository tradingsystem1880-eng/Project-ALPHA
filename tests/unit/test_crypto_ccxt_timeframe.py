from __future__ import annotations

import sys
from datetime import UTC, date, datetime
from types import SimpleNamespace

import pytest

from alpha_core import DataError
from alpha_data.adapters.ccxt_adapter import CCXTAdapter, clip_ohlcv_period


class _Exchange:
    def __init__(self, config: dict[str, object]) -> None:
        assert config == {"enableRateLimit": True}
        self.calls: list[tuple[str, str, int, int]] = []

    def fetch_ohlcv(
        self, symbol: str, *, timeframe: str, since: int, limit: int
    ) -> list[list[float]]:
        self.calls.append((symbol, timeframe, since, limit))
        return [[float(since), 1.0, 2.0, 0.5, 1.5, 10.0]]


def test_ccxt_timeframe_fetch_is_bounded_paged_and_typed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    exchange = _Exchange({"enableRateLimit": True})
    monkeypatch.setitem(sys.modules, "ccxt", SimpleNamespace(coinbase=lambda _config: exchange))
    start = datetime(2024, 1, 1, tzinfo=UTC)
    end = datetime(2024, 1, 1, tzinfo=UTC)

    result = CCXTAdapter("coinbase").fetch_timeframe("BTC/USD", start, end, timeframe="1d")

    assert result.symbol == "BTC/USD"
    assert result.bars.height == 1
    assert exchange.calls == [("BTC/USD", "1d", 1_704_067_200_000, 300)]


def test_ccxt_timeframe_rejects_invalid_bounds_and_empty_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    exchange = _Exchange({"enableRateLimit": True})
    monkeypatch.setitem(sys.modules, "ccxt", SimpleNamespace(coinbase=lambda _config: exchange))
    aware = datetime(2024, 1, 1, tzinfo=UTC)
    with pytest.raises(DataError, match="timeframe"):
        CCXTAdapter().fetch_timeframe("BTC/USD", aware, aware, timeframe="2h")
    with pytest.raises(DataError, match="timezone"):
        CCXTAdapter().fetch_timeframe("BTC/USD", datetime(2024, 1, 1), aware, timeframe="1d")
    with pytest.raises(DataError, match="precedes"):
        CCXTAdapter().fetch_timeframe(
            "BTC/USD", aware, datetime(2023, 1, 1, tzinfo=UTC), timeframe="1d"
        )

    class Empty(_Exchange):
        def fetch_ohlcv(
            self, symbol: str, *, timeframe: str, since: int, limit: int
        ) -> list[list[float]]:
            return []

    monkeypatch.setitem(sys.modules, "ccxt", SimpleNamespace(coinbase=Empty))
    with pytest.raises(DataError, match="no data"):
        CCXTAdapter().fetch_timeframe("BTC/USD", aware, aware, timeframe="1d")


def test_ccxt_daily_fetch_uses_the_exact_daily_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    exchange = _Exchange({"enableRateLimit": True})
    monkeypatch.setitem(sys.modules, "ccxt", SimpleNamespace(coinbase=lambda _config: exchange))

    result = CCXTAdapter().fetch("BTC/USD", date(2024, 1, 1), date(2024, 1, 1))

    assert result.bars.height == 1
    assert exchange.calls == [("BTC/USD", "1d", 1_704_067_200_000, 300)]


def test_ccxt_period_clipping_rejects_unknown_interval_steps() -> None:
    with pytest.raises(DataError, match="unsupported CCXT comparison timeframe step"):
        clip_ohlcv_period([], since_ms=0, end_ms=0, now_ms=0, step_ms=123)
