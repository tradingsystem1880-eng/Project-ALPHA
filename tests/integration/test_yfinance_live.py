"""Live yfinance smoke test — skipped in CI/offline (run locally with -m network)."""
from __future__ import annotations

from datetime import date

import pytest

from alpha_data.adapters.yfinance_adapter import YFinanceAdapter

pytestmark = pytest.mark.network


def test_yfinance_live_pull_aapl() -> None:
    result = YFinanceAdapter().fetch("AAPL", date(2020, 8, 1), date(2020, 9, 30))
    assert result.bars.height > 10
    # the Aug-2020 4:1 split must be present as a raw action
    assert any(a.action_type.value == "split" and a.ratio == 4.0 for a in result.actions)
