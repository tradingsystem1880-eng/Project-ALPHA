"""`alpha data pull` accepts the symbol forms a trader types and fails loud on the rest."""

from __future__ import annotations

import pytest
import typer

from alpha_cli.data_cmds import normalize_symbol


@pytest.mark.parametrize("raw", ["xrp-usdt", "XRPUSDT", "xrp/usdt", " xrp_usdt ", "Xrp/Usdt"])
def test_ccxt_forms_normalise_to_slash_upper(raw: str) -> None:
    assert normalize_symbol(raw, "ccxt") == "XRP/USDT"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("btcusd", "BTC/USD"), ("ETHUSDC", "ETH/USDC"), ("solbtc", "SOL/BTC"), ("ada-eur", "ADA/EUR")],
)
def test_ccxt_compact_forms_split_on_the_closed_quote_list(raw: str, expected: str) -> None:
    assert normalize_symbol(raw, "ccxt") == expected


@pytest.mark.parametrize(
    ("source", "raw", "expected"),
    [("yfinance", "aapl", "AAPL"), ("tiingo", "brk.b", "BRK.B"), ("stooq", " spy ", "SPY")],
)
def test_equities_are_upper_cased_only(source: str, raw: str, expected: str) -> None:
    assert normalize_symbol(raw, source) == expected


@pytest.mark.parametrize(
    "raw", ["arp", "xrpusdtusd", "", "   ", "XRP/", "/USDT", "XRPFOO", "a/b/c"]
)
def test_ambiguous_or_garbage_ccxt_symbols_fail_loud_listing_accepted_forms(raw: str) -> None:
    with pytest.raises(typer.BadParameter) as excinfo:
        normalize_symbol(raw, "ccxt")
    message = str(excinfo.value)
    assert "XRP/USDT" in message and "USDT" in message


@pytest.mark.parametrize("raw", ["", "   ", "AA PL"])
def test_equities_reject_empty_or_spaced_symbols(raw: str) -> None:
    with pytest.raises(typer.BadParameter):
        normalize_symbol(raw, "yfinance")
