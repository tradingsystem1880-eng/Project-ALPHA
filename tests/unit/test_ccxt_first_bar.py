"""`CCXTAdapter.first_bar` finds a pair's listing date without downloading its history."""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from alpha_core import DataError
from alpha_data.adapters.ccxt_adapter import CCXTAdapter

_LISTING_MS = 1_556_582_400_000  # 2019-04-30T00:00:00Z
_DAY_MS = 86_400_000


class _Exchange:
    """A fake exchange. ``windowed`` mimics Coinbase (bars only inside [since, since+limit*1d]);
    otherwise it mimics Binance (the earliest bars at or after ``since``, whatever the window)."""

    def __init__(self, *, markets: dict[str, dict[str, object]], windowed: bool) -> None:
        self.markets = markets
        self.windowed = windowed
        self.calls: list[tuple[str, str, int, int]] = []

    def load_markets(self) -> dict[str, dict[str, object]]:
        return self.markets

    def fetch_ohlcv(
        self, symbol: str, *, timeframe: str, since: int, limit: int
    ) -> list[list[float]]:
        self.calls.append((symbol, timeframe, since, limit))
        if self.windowed and since + limit * _DAY_MS <= _LISTING_MS:
            return []
        first = max(since, _LISTING_MS)
        return [[float(first), 1.0, 2.0, 0.5, 1.5, 10.0]]


def _install(monkeypatch: pytest.MonkeyPatch, exchange: _Exchange, name: str = "binance") -> None:
    monkeypatch.setitem(sys.modules, "ccxt", SimpleNamespace(**{name: lambda _config: exchange}))


def test_first_bar_takes_one_call_when_the_exchange_answers_from_the_listing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    exchange = _Exchange(markets={"XRP/USDT": {}}, windowed=False)
    _install(monkeypatch, exchange)

    first = CCXTAdapter("binance").first_bar("XRP/USDT")

    assert first == datetime(2019, 4, 30, tzinfo=UTC)
    assert exchange.calls == [("XRP/USDT", "1d", 1_230_940_800_000, 300)]


def test_first_bar_never_sends_since_zero_and_rejects_bars_before_the_requested_start(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _IgnoresSince(_Exchange):
        def fetch_ohlcv(
            self, symbol: str, *, timeframe: str, since: int, limit: int
        ) -> list[list[float]]:
            self.calls.append((symbol, timeframe, since, limit))
            return [[float(1_230_940_800_000 - _DAY_MS), 1.0, 2.0, 0.5, 1.5, 10.0]]

    exchange = _IgnoresSince(markets={"XRP/USD": {}}, windowed=True)
    _install(monkeypatch, exchange, name="coinbase")

    with pytest.raises(DataError, match="before the requested start"):
        CCXTAdapter("coinbase").first_bar("XRP/USD")
    assert all(call[2] > 0 for call in exchange.calls)


def test_first_bar_scans_forward_when_the_exchange_windows_since(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    exchange = _Exchange(markets={"XRP/USD": {}}, windowed=True)
    _install(monkeypatch, exchange, name="coinbase")

    first = CCXTAdapter("coinbase").first_bar("XRP/USD")

    assert first == datetime(2019, 4, 30, tzinfo=UTC)
    sinces = [call[2] for call in exchange.calls]
    assert sinces == sorted(sinces) and 5 < len(sinces) < 30


def test_first_bar_unknown_pair_fails_loud_without_fetching(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    exchange = _Exchange(markets={"BTC/USDT": {}}, windowed=False)
    _install(monkeypatch, exchange)

    with pytest.raises(DataError, match="XRP/USDT.*binance|binance.*XRP/USDT"):
        CCXTAdapter("binance").first_bar("XRP/USDT")
    assert exchange.calls == []


def test_first_bar_empty_history_fails_loud(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Empty(_Exchange):
        def fetch_ohlcv(
            self, symbol: str, *, timeframe: str, since: int, limit: int
        ) -> list[list[float]]:
            self.calls.append((symbol, timeframe, since, limit))
            return []

    exchange = _Empty(markets={"XRP/USDT": {}}, windowed=True)
    _install(monkeypatch, exchange)

    with pytest.raises(DataError, match="no history"):
        CCXTAdapter("binance").first_bar("XRP/USDT")


def test_first_bar_rejects_unknown_timeframe(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch, _Exchange(markets={"XRP/USDT": {}}, windowed=False))
    with pytest.raises(DataError, match="timeframe"):
        CCXTAdapter("binance").first_bar("XRP/USDT", timeframe="2h")
