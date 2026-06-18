"""Unit tests for ``alpha_paper.config`` (Phase 4c)."""

from __future__ import annotations

from alpha_core.config import AlphaSettings
from alpha_paper.config import PaperSpec, paper_spec_from_settings


def test_paper_spec_defaults_follow_crypto_convention() -> None:
    spec = PaperSpec(symbol="BTC/USDT", exchange="coinbase", venue="SANDBOX")
    assert spec.allow_short is True
    assert spec.account_type == "MARGIN"
    assert spec.periods_per_year == 365
    assert spec.duration_seconds is None


def test_min_train_matches_warmup_floor() -> None:
    spec = PaperSpec(symbol="BTC/USDT", exchange="coinbase", venue="SANDBOX", lookback=100, skip=5)
    # max(lookback + skip + 1, vol_window + 1) = max(106, 64) = 106
    assert spec.min_train == 106
    short = PaperSpec(
        symbol="BTC/USDT", exchange="coinbase", venue="SANDBOX", lookback=10, skip=0, vol_window=63
    )
    assert short.min_train == 64  # vol_window + 1 dominates


def test_from_settings_uses_settings_then_applies_overrides() -> None:
    settings = AlphaSettings(paper_symbol="ETH/USDT", paper_exchange="binance", paper_venue="SBX")
    spec = paper_spec_from_settings(settings, target_vol=0.2, allow_short=False)
    assert (spec.symbol, spec.exchange, spec.venue) == ("ETH/USDT", "binance", "SBX")
    assert spec.target_vol == 0.2
    assert spec.allow_short is False
