"""`CCXTAdapter.ticker` reads one public last-trade quote for display and never invents one."""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from alpha_core import DataError
from alpha_data.adapters.ccxt_adapter import CCXTAdapter

_STAMP_MS = 1_756_900_000_000


class _Exchange:
    def __init__(self, markets: dict[str, dict[str, object]], record: object) -> None:
        self.markets = markets
        self.record = record
        self.calls: list[str] = []

    def load_markets(self) -> dict[str, dict[str, object]]:
        return self.markets

    def fetch_ticker(self, symbol: str) -> object:
        self.calls.append(symbol)
        return self.record


def _install(monkeypatch: pytest.MonkeyPatch, exchange: _Exchange, name: str = "binance") -> None:
    monkeypatch.setitem(sys.modules, "ccxt", SimpleNamespace(**{name: lambda _config: exchange}))


def test_ticker_returns_the_last_price_and_its_utc_stamp(monkeypatch: pytest.MonkeyPatch) -> None:
    exchange = _Exchange({"XRP/USDT": {}}, {"last": 2.914, "timestamp": _STAMP_MS})
    _install(monkeypatch, exchange)

    last, stamp = CCXTAdapter("binance").ticker("XRP/USDT")

    assert last == pytest.approx(2.914)
    assert stamp == datetime.fromtimestamp(_STAMP_MS / 1000, tz=UTC)
    assert exchange.calls == ["XRP/USDT"]


def test_ticker_unknown_pair_fails_loud_without_fetching(monkeypatch: pytest.MonkeyPatch) -> None:
    exchange = _Exchange({"BTC/USDT": {}}, {"last": 1.0, "timestamp": _STAMP_MS})
    _install(monkeypatch, exchange)

    with pytest.raises(DataError, match="lists no market XRP/USDT"):
        CCXTAdapter("binance").ticker("XRP/USDT")
    assert exchange.calls == []


@pytest.mark.parametrize(
    "record",
    [
        {"last": None, "timestamp": _STAMP_MS},
        {"last": 0, "timestamp": _STAMP_MS},
        {"last": True, "timestamp": _STAMP_MS},
        {"last": 2.9, "timestamp": None},
        {"last": 2.9},
        [],
    ],
)
def test_ticker_never_invents_a_price_or_a_time(
    monkeypatch: pytest.MonkeyPatch, record: object
) -> None:
    exchange = _Exchange({"XRP/USDT": {}}, record)
    _install(monkeypatch, exchange)

    with pytest.raises(DataError, match="returned no (last price|timestamp)"):
        CCXTAdapter("binance").ticker("XRP/USDT")
