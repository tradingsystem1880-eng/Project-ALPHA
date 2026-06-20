"""Offline guard for the ccxt OHLCV pagination walk.

Coinbase (and most exchanges) cap ``fetch_ohlcv`` at ~300 candles per call, so a single call
silently truncates a multi-year range. ``_paginate_ohlcv`` must page forward to cover the whole
window — a silent data gap is exactly what the project's fail-loud rule forbids. These tests drive
a synthetic, coinbase-shaped pager (returns up to ``page_limit`` bars at/after ``since``, ascending)
so the walk logic is verified without the network.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from alpha_data.adapters.ccxt_adapter import _paginate_ohlcv

_DAY_MS = 86_400_000
Pager = Callable[[int], list[list[float]]]


def _make_bars(start_ms: int, n: int) -> list[list[float]]:
    return [
        [float(start_ms + i * _DAY_MS), 1.0, 2.0, 0.5, 1.5, 10.0]  # ts in ms; OHLCV arbitrary
        for i in range(n)
    ]


def _coinbase_like(all_bars: list[list[float]], page_limit: int) -> Pager:
    """A fetch-page callable mimicking coinbase: up to ``page_limit`` bars with ts >= since."""

    def fetch_page(since_ms: int) -> list[list[float]]:
        return [r for r in all_bars if r[0] >= since_ms][:page_limit]

    return fetch_page


def test_paginate_walks_full_multipage_range() -> None:
    start = int(datetime(2018, 1, 1, tzinfo=UTC).timestamp() * 1000)
    total = 1000  # > 3 pages of 300 — a single fetch would return only the first 300
    all_bars = _make_bars(start, total)
    end_ms = int(all_bars[-1][0])

    out = _paginate_ohlcv(
        _coinbase_like(all_bars, page_limit=300), since_ms=start, end_ms=end_ms, page_limit=300
    )

    ts = [int(r[0]) for r in out]
    assert len(out) == total  # full coverage, not truncated to 300
    assert ts == sorted(ts) and len(set(ts)) == total  # strictly ascending, no gaps/dupes
    assert ts[0] == start and ts[-1] == end_ms


def test_paginate_stops_near_end_ms_without_running_away() -> None:
    start = int(datetime(2018, 1, 1, tzinfo=UTC).timestamp() * 1000)
    all_bars = _make_bars(start, 1000)
    end_ms = int(all_bars[400][0])  # only want ~401 bars even though 1000 exist

    out = _paginate_ohlcv(
        _coinbase_like(all_bars, page_limit=300), since_ms=start, end_ms=end_ms, page_limit=300
    )

    assert max(int(r[0]) for r in out) >= end_ms  # reached the requested boundary
    assert len(out) < 1000  # did not fetch the entire forward history past end


def test_paginate_terminates_on_no_forward_progress() -> None:
    # A broken exchange that ignores `since` and always returns the same bar must not hang.
    stuck_bar = [[1_704_067_200_000.0, 1.0, 2.0, 0.5, 1.5, 1.0]]

    def stuck(_since_ms: int) -> list[list[float]]:
        return stuck_bar

    out = _paginate_ohlcv(stuck, since_ms=0, end_ms=1_704_067_200_000 * 2, page_limit=300)
    assert out == stuck_bar  # taken once, then no-progress guard stops the walk


def test_paginate_handles_empty_first_page() -> None:
    out = _paginate_ohlcv(lambda _s: [], since_ms=0, end_ms=_DAY_MS * 10, page_limit=300)
    assert out == []
