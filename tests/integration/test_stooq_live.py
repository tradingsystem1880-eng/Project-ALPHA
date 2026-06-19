"""Live Stooq smoke test — skipped in CI/offline (run locally with -m network).

Verifies the real HTTP fetch + parser wiring against Stooq's live CSV endpoint. The pure parser is
covered offline in ``tests/unit/test_stooq_parser.py``.
"""

from __future__ import annotations

from datetime import date

import pytest

from alpha_data.adapters.stooq_adapter import StooqAdapter

pytestmark = pytest.mark.network


def test_stooq_live_pull_spy() -> None:
    result = StooqAdapter().fetch("spy.us", date(2020, 1, 1), date(2020, 3, 31))
    assert result.bars.height > 30  # ~60 trading days in the window
    assert result.actions == []  # Stooq is provider-adjusted: no separate corporate actions
    # OHLC invariants held (every row was validated through Bar in the parser)
    assert result.bars["close"].min() > 0
