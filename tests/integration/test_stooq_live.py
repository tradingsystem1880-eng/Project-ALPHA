"""Live Stooq smoke test — skipped in CI/offline (run locally with -m network).

Verifies the real HTTP fetch + parser wiring against Stooq's live CSV endpoint. The pure parser is
covered offline in ``tests/unit/test_stooq_parser.py``.
"""

from __future__ import annotations

from datetime import date

import pytest

from alpha_core import DataError
from alpha_data.adapters.stooq_adapter import StooqAdapter

pytestmark = pytest.mark.network

# Substrings the adapter emits when Stooq's *transport* withholds data (anti-bot gate / per-IP
# "Access denied" quota / no data for the window). These are environmental, not a code bug, so the
# test skips. Parser-level DataErrors ("invalid Stooq row", "missing columns") have none of these
# tokens and so propagate as real failures — a genuine live-shape regression must not be masked.
_BLOCKED_TOKENS = ("anti-bot", "Access denied", "returned no data")


def test_stooq_live_pull_spy() -> None:
    try:
        result = StooqAdapter().fetch("spy.us", date(2020, 1, 1), date(2020, 3, 31))
    except DataError as exc:
        if any(tok in str(exc) for tok in _BLOCKED_TOKENS):
            pytest.skip(f"Stooq blocked the live CSV download from this IP: {exc}")
        raise  # parser-level failure → real breakage against the live shape
    assert result.bars.height > 30  # ~60 trading days in the window
    assert result.actions == []  # Stooq is provider-adjusted: no separate corporate actions
    # OHLC invariants held (every row was validated through Bar in the parser)
    assert all(c > 0 for c in result.bars["close"].to_list())
