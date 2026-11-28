"""The web candle/overlay cache keeps at most 32 results and drops the oldest first."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest

from alpha_web import _candles


def _day(i: int) -> str:
    return (date(2020, 1, 1) + timedelta(days=i)).isoformat()


def _counting_stub(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    calls: list[list[str]] = []

    def stub(args: list[str], **kwargs: Any) -> dict[str, Any]:
        calls.append(list(args))
        return {"symbol": args[2], "snapshot_id": None, "bars": []}

    monkeypatch.setattr(_candles, "_run_json", stub)
    return calls


def test_candles_cache_serves_a_repeated_request_without_refetching(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _counting_stub(monkeypatch)
    first = _candles.candles("SPY", data_dir=tmp_path, end=_day(0))
    again = _candles.candles("SPY", data_dir=tmp_path, end=_day(0))
    assert again == first
    assert len(calls) == 1


def test_candles_cache_refetches_the_oldest_window_after_32_others(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _counting_stub(monkeypatch)
    for i in range(33):
        _candles.candles("SPY", data_dir=tmp_path, end=_day(i))
    assert len(calls) == 33
    # The newest window is still cached: no new fetch.
    _candles.candles("SPY", data_dir=tmp_path, end=_day(32))
    assert len(calls) == 33
    # The oldest window was dropped once the cache went over 32 entries: it is fetched again.
    _candles.candles("SPY", data_dir=tmp_path, end=_day(0))
    assert len(calls) == 34
    assert calls[-1][:3] == ["data", "candles", "SPY"]


def test_overlays_cache_refetches_the_oldest_window_after_32_others(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _counting_stub(monkeypatch)
    for i in range(33):
        _candles.overlays("SPY", data_dir=tmp_path, indicators=("sma:5",), end=_day(i))
    assert len(calls) == 33
    _candles.overlays("SPY", data_dir=tmp_path, indicators=("sma:5",), end=_day(32))
    assert len(calls) == 33
    _candles.overlays("SPY", data_dir=tmp_path, indicators=("sma:5",), end=_day(0))
    assert len(calls) == 34
    assert calls[-1][:3] == ["chart", "overlays", "SPY"]
