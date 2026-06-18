"""Unit tests for the shared ``alpha_execution`` instrument seam (Phase 4b)."""

from __future__ import annotations

import pytest

from alpha_core import DataError
from alpha_execution.instruments import crypto_instrument, equity_instrument


def test_equity_instrument_is_integer_lot_cash_equity() -> None:
    inst = equity_instrument("AAPL")
    assert str(inst.id) == "AAPL.SIM"
    assert inst.price_precision == 2
    assert inst.size_precision == 0  # integer lots


def test_crypto_instrument_is_fractional_currency_pair() -> None:
    inst = crypto_instrument("BTC/USDT")
    assert str(inst.id) == "BTCUSDT.BINANCE"
    assert inst.size_precision > 0  # crypto trades fractional, unlike equities


@pytest.mark.parametrize("symbol", ["BTCUSDT", "btc/usdt", "BTC-USDT"])
def test_crypto_instrument_normalizes_symbol_forms(symbol: str) -> None:
    assert str(crypto_instrument(symbol).id) == "BTCUSDT.BINANCE"


def test_crypto_instrument_fails_loud_on_unknown_symbol() -> None:
    with pytest.raises(DataError, match="unsupported crypto symbol"):
        crypto_instrument("DOGE/USDT")
