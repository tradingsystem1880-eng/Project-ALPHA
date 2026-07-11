"""Content-addressed forecast cache: one parquet per key, append-only, no eviction.

The key hashes everything that determines a forecast (model, revision, the exact window
content, horizon, sampling params, seed) and deliberately EXCLUDES signal-mapping params
(e.g. deadband) so parameter sweeps over the signal reuse every forecast. Manual reset:
delete the cache directory.
"""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING

import polars as pl

from alpha_core import DataError

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from alpha_core import Bar

_SCHEMA_VERSION = 1


def cache_key(
    *,
    model: str,
    revision: str | None,
    window: Sequence[Bar],
    horizon: int,
    temperature: float,
    top_p: float,
    sample_count: int,
    seed: int,
) -> str:
    """sha256 hex of the canonical sorted-key JSON of everything that determines a forecast."""
    payload = {
        "schema": _SCHEMA_VERSION,
        "model": model,
        "revision": revision,
        "window": [[b.ts.isoformat(), b.open, b.high, b.low, b.close, b.volume] for b in window],
        "horizon": horizon,
        "temperature": temperature,
        "top_p": top_p,
        "sample_count": sample_count,
        "seed": seed,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def load(cache_dir: Path, key: str) -> pl.DataFrame | None:
    """Return the cached forecast frame for `key`, None on miss, DataError on a corrupt file."""
    path = cache_dir / f"{key}.parquet"
    if not path.exists():
        return None
    try:
        return pl.read_parquet(path)
    except Exception as exc:  # noqa: BLE001 - re-raised typed; a corrupt cache must fail loud
        raise DataError(
            f"corrupt forecast cache entry {path}; delete the file (or the whole "
            f"{cache_dir} directory) and re-run: {exc}"
        ) from exc


def store(cache_dir: Path, key: str, frame: pl.DataFrame) -> Path:
    """Write the forecast frame under its key (atomic-enough: content-addressed, idempotent)."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"{key}.parquet"
    frame.write_parquet(path)
    return path
