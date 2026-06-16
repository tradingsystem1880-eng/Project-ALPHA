"""The bar-feed seam: alpha_core.Bar (PIT-safe) -> nautilus Bar, chronology preserved."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

from alpha_backtest.feed import daily_bar_type, to_nautilus_bar, to_nautilus_bars
from alpha_core import Bar
from alpha_data.source import PointInTimeSource
from alpha_data.store import ParquetStore
from tests.fixtures.pit_fixtures import linear_bars


def _bar(symbol: str, ts: datetime, close: float) -> Bar:
    return Bar(
        symbol=symbol, ts=ts, open=close, high=close + 1, low=close - 1, close=close, volume=10.0
    )


def test_daily_bar_type_equity_and_slash_symbol() -> None:
    bt = daily_bar_type("AAPL")
    assert str(bt) == "AAPL.SIM-1-DAY-LAST-EXTERNAL"
    assert str(daily_bar_type("BTC/USD").instrument_id) == "BTC/USD.SIM"  # slash survives


def test_to_nautilus_bar_preserves_ohlcv_and_close_timestamp() -> None:
    ts = datetime(2024, 3, 15, tzinfo=UTC)
    nb = to_nautilus_bar(_bar("AAPL", ts, 100.0), daily_bar_type("AAPL"))
    assert (float(nb.open), float(nb.high), float(nb.low), float(nb.close)) == (
        100.0,
        101.0,
        99.0,
        100.0,
    )
    assert float(nb.volume) == 10.0
    # daily bar decided on close of t; both engine timestamps are the bar-close instant (ns).
    expected_ns = int(ts.timestamp() * 1_000_000_000)
    assert nb.ts_event == expected_ns == nb.ts_init


def test_fx_precision_and_crypto_magnitude_round_trip() -> None:
    ts = datetime(2024, 1, 2, tzinfo=UTC)
    fx = to_nautilus_bar(_bar("EURUSD", ts, 1.23456), daily_bar_type("EURUSD"), price_precision=5)
    assert float(fx.close) == 1.23456
    crypto = to_nautilus_bar(
        _bar("BTC/USD", ts, 42500.0), daily_bar_type("BTC/USD"), price_precision=2, size_precision=2
    )
    assert float(crypto.close) == 42500.0


def test_to_nautilus_bars_preserves_chronological_run(tmp_path: Path) -> None:
    store = ParquetStore(tmp_path)
    store.write_bars("X", linear_bars("X", date(2024, 1, 1), 6))
    src = PointInTimeSource(store, actions={})
    pit_bars = src.as_of("X", datetime(2024, 1, 4, tzinfo=UTC))  # 4 bars
    nbs = to_nautilus_bars(pit_bars, daily_bar_type("X"))
    assert len(nbs) == len(pit_bars) == 4
    assert [nb.ts_event for nb in nbs] == sorted(nb.ts_event for nb in nbs)
    assert [float(nb.close) for nb in nbs] == [b.close for b in pit_bars]
