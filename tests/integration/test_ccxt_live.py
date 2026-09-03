"""Live ccxt smoke test — skipped in CI/offline (run locally with -m network)."""

from __future__ import annotations

from datetime import date

import pytest

from alpha_data.adapters.ccxt_adapter import CCXTAdapter

pytestmark = pytest.mark.network


def test_ccxt_live_pull_btc() -> None:
    result = CCXTAdapter().fetch("BTC/USD", date(2024, 1, 1), date(2024, 1, 15))
    assert result.bars.height > 5
    assert result.actions == []


def test_ccxt_live_first_bar_binance_xrp_usdt() -> None:
    # XRP/USDT listed on Binance in May 2018; a bounded inequality, not an exact date.
    assert CCXTAdapter("binance").first_bar("XRP/USDT").date() <= date(2018, 6, 1)


def test_ccxt_live_first_bar_coinbase_xrp_usd() -> None:
    # Coinbase listed XRP in 2019 and relisted it in mid-2023; only the bound is asserted.
    assert CCXTAdapter("coinbase").first_bar("XRP/USD").date() <= date(2023, 8, 1)
