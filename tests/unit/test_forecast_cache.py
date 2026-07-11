"""Content-addressed forecast cache: key stability/sensitivity + roundtrip + fail-loud."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import polars as pl
import pytest

from alpha_core import DataError
from alpha_forecast import cache
from tests.fixtures.forecast_fixtures import daily_bars

_KW: dict[str, Any] = {
    "model": "base",
    "revision": None,
    "horizon": 5,
    "temperature": 1.0,
    "top_p": 0.9,
    "sample_count": 1,
    "seed": 7,
}


def test_key_is_stable() -> None:
    bars = daily_bars(n=10)
    assert cache.cache_key(window=bars, **_KW) == cache.cache_key(window=bars, **_KW)


def test_key_sensitive_to_every_field() -> None:
    bars = daily_bars(n=10)
    base = cache.cache_key(window=bars, **_KW)
    assert cache.cache_key(window=bars[:-1], **_KW) != base
    for field, value in [
        ("model", "mini"),
        ("revision", "abc123"),
        ("horizon", 6),
        ("temperature", 1.1),
        ("top_p", 0.8),
        ("sample_count", 2),
        ("seed", 8),
    ]:
        assert cache.cache_key(window=bars, **{**_KW, field: value}) != base, field


def test_key_sensitive_to_window_content() -> None:
    bars = daily_bars(n=10)
    tweaked = [*bars[:-1], bars[-1].model_copy(update={"close": bars[-1].close + 0.01})]
    assert cache.cache_key(window=tweaked, **_KW) != cache.cache_key(window=bars, **_KW)


def test_roundtrip_and_miss(tmp_path: Path) -> None:
    frame = pl.DataFrame(
        {
            "ts": ["2026-01-05T00:00:00+00:00"],
            "open": [1.0],
            "high": [1.1],
            "low": [0.9],
            "close": [1.05],
            "volume": [10.0],
            "close_p10": [1.0],
            "close_p90": [1.1],
        }
    )
    key = "k" * 64
    assert cache.load(tmp_path, key) is None
    cache.store(tmp_path, key, frame)
    loaded = cache.load(tmp_path, key)
    assert loaded is not None
    assert loaded.equals(frame)


def test_corrupt_entry_fails_loud(tmp_path: Path) -> None:
    key = "c" * 64
    (tmp_path / f"{key}.parquet").write_bytes(b"not parquet at all")
    with pytest.raises(DataError, match="corrupt forecast cache"):
        cache.load(tmp_path, key)
