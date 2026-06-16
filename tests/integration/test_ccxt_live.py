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
