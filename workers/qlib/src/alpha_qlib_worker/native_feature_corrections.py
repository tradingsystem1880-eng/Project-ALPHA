"""Legacy recipe v2 — kept to reproduce stored results; new work uses v3.

Eight Alpha158 families computed by pinned Qlib 0.9.7 operators, without providers.

Primary sources: installed pyqlib 0.9.7 qlib/contrib/data/loader.py Alpha158DL and
qlib/data/ops.py. The single adapter is a content-keyed in-memory Expression leaf.
No provider, parser, handler, model or initialization API is invoked here.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import polars as pl
from qlib.data import ops
from qlib.data.base import Expression

from alpha_qlib_worker.feature_recipes import CORRECTED_COLUMNS, NATIVE_VERSIONS, WINDOWS

# Platform-independent source bindings from the inspected installed 0.9.7 wheel.
_SOURCE_PINS = {
    "data/ops.py": "6f648355725a85a9f17528d864281fc065f8a4f887261a9909f7495d5db42760",
    "data/base.py": "30382dd1a3c47506e61514f37533a3407f63fd01c9a9fd5a12b8c0cce85c5d5c",
    "contrib/data/loader.py": "814b7f7ab3d418ae3c87ce352220080b239eba2670eac9e38376b794be4075cb",
}


def upstream_binding() -> dict[str, Any]:
    versions = {name: importlib.metadata.version(name) for name in NATIVE_VERSIONS}
    if versions != NATIVE_VERSIONS:
        raise RuntimeError("feature recipe v2 requires the pinned Qlib numerical dependencies")
    root = Path(ops.__file__).resolve().parents[1]
    hashes = {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in _SOURCE_PINS}
    if hashes != _SOURCE_PINS:
        raise RuntimeError("feature recipe v2 Qlib source differs from inspected upstream pins")
    return {"versions": versions, "source_sha256": hashes}


class _PanelSeries(Expression):  # type: ignore[misc]  # Upstream Expression is untyped.
    """Only raw values and slicing; upstream owns all operator behavior and caching."""

    def __init__(self, identity: str, field: str, values: pd.Series) -> None:
        self.identity, self.field = identity, field
        self.values = pd.Series(values.to_numpy(copy=True), dtype="float64")

    def __str__(self) -> str:
        return f"Alpha158V2Panel[{self.identity}:{self.field}]"

    def _load_internal(
        self, instrument: str, start_index: int, end_index: int, *args: object
    ) -> pd.Series:
        if instrument != self.identity or args != ("day",):
            raise RuntimeError("invalid in-memory feature identity or frequency")
        return self.values.loc[start_index:end_index].copy()

    def get_longest_back_rolling(self) -> int:
        return 0

    def get_extended_window_size(self) -> tuple[int, int]:
        return (0, 0)


def corrected_features(panel: pl.DataFrame) -> pd.DataFrame:
    """Compute only the 40 explicitly corrected columns on available trailing rows."""
    upstream_binding()
    frames: list[pd.DataFrame] = []
    for symbol, raw in panel.to_pandas().groupby("symbol", sort=True, observed=True):
        raw = raw.sort_values("session_ts", kind="mergesort").set_index("session_ts")
        digest = hashlib.sha256(b"alpha158:2:qlib-0.9.7\0" + str(symbol).encode() + b"\0")
        digest.update(str(raw.index.dtype).encode())
        digest.update(pd.DatetimeIndex(raw.index).astype("int64").to_numpy().tobytes())
        digest.update(raw[["high", "low", "close", "volume"]].to_numpy(dtype="<f8").tobytes())
        identity = digest.hexdigest()
        high, low, close, volume = (
            _PanelSeries(identity, field, raw[field])
            for field in ("high", "low", "close", "volume")
        )
        weighted = ops.Abs(close / ops.Ref(close, 1) - 1) * volume
        columns = {}
        for window in WINDOWS:
            expressions = {
                "MA": ops.Mean(close, window) / close,
                "STD": ops.Std(close, window) / close,
                "VSTD": ops.Std(volume, window) / (volume + 1e-12),
                "RANK": ops.Rank(close, window),
                "IMAX": ops.IdxMax(high, window) / window,
                "IMIN": ops.IdxMin(low, window) / window,
                "IMXD": (ops.IdxMax(high, window) - ops.IdxMin(low, window)) / window,
                "WVMA": ops.Std(weighted, window) / (ops.Mean(weighted, window) + 1e-12),
            }
            for family, expression in expressions.items():
                values = expression.load(identity, 0, len(raw) - 1, "day")
                if not values.index.equals(pd.RangeIndex(len(raw))):
                    raise RuntimeError("Qlib operator changed the in-memory row index")
                columns[f"{family}{window}"] = values.to_numpy(copy=True)
        frame = pd.DataFrame(columns, index=raw.index).replace([np.inf, -np.inf], np.nan)
        frame["instrument"] = str(symbol)
        frames.append(frame.reset_index().set_index(["session_ts", "instrument"]))
    result = pd.concat(frames).sort_index(kind="mergesort")
    result.index.names = ["datetime", "instrument"]
    return result.loc[:, list(CORRECTED_COLUMNS)].astype("float64")
