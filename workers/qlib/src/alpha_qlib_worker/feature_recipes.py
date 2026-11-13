"""Explicit feature versions; version 1 remains the historical Alpha158-style recipe."""

from __future__ import annotations

import hashlib
import importlib.metadata
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import polars as pl

from alpha_qlib_worker.features import alpha158_feature_names, alpha158_features

CORRECTED_FAMILIES = ("MA", "STD", "VSTD", "RANK", "IMAX", "IMIN", "IMXD", "WVMA")
WINDOWS = (5, 10, 20, 30, 60)
CORRECTED_COLUMNS = tuple(
    f"{family}{window}" for family in CORRECTED_FAMILIES for window in WINDOWS
)
NATIVE_VERSIONS = {"pyqlib": "0.9.7", "pandas": "2.3.3", "numpy": "2.2.6"}


def validate_feature_version(version: object) -> int:
    if type(version) is not int or version not in (1, 2):
        raise ValueError("unsupported alpha158 feature recipe version; expected integer 1 or 2")
    return version


def build_features(panel: pl.DataFrame, *, version: int = 1) -> pd.DataFrame:
    """Build v1 unchanged, or v2's bounded 40-column upstream-operator correction.

    V2 follows Qlib 0.9.7 Alpha158DL for eight families at five windows. It is not
    whole-recipe or provider parity. Remaining columns, including proxy VWAP, retain v1.
    """
    validate_feature_version(version)
    legacy = alpha158_features(panel)
    if version == 1:
        return legacy
    # Qlib's import modifies NumPy's process error policy. Keep this local call scoped.
    with np.errstate(divide="ignore", invalid="ignore"):
        from alpha_qlib_worker.native_feature_corrections import corrected_features

        corrected = corrected_features(panel)
    if not legacy.index.equals(corrected.index):
        raise RuntimeError("native feature correction changed row identity")
    legacy.loc[:, list(CORRECTED_COLUMNS)] = corrected.loc[:, list(CORRECTED_COLUMNS)]
    return legacy


def feature_recipe_diagnostics(version: int) -> dict[str, Any]:
    """Preserve historical diagnostics; new metadata is emitted only for opt-in v2."""
    validate_feature_version(version)
    result: dict[str, Any] = {
        "name": "Alpha158-style",
        "feature_count": len(alpha158_feature_names()),
        "names": list(alpha158_feature_names()),
        "vwap_source": "causal_typical_price_proxy_not_vendor_vwap",
    }
    if version == 2:
        result["name"] = "Alpha158-style v2 (40 upstream columns; 118 legacy columns)"
        with np.errstate(divide="ignore", invalid="ignore"):
            from alpha_qlib_worker.native_feature_corrections import upstream_binding

            upstream = upstream_binding()
        result["versioned_correction"] = {
            "name": "alpha158",
            "version": 2,
            "scope": "partial_alpha158_style_40_column_correction",
            "full_alpha158_parity": False,
            "corrected_columns": list(CORRECTED_COLUMNS),
            "inherited_v1_columns": [
                n for n in alpha158_feature_names() if n not in CORRECTED_COLUMNS
            ],
            "warmup": "Qlib partial windows for corrected columns; v1 full windows elsewhere",
            "nonfinite": "upstream NaNs retained; infinities converted to NaN as in v1",
            "input": "validated ALPHA OHLCV panel only; no vendor VWAP or pre-panel history",
            "upstream": upstream,
            "source_sha256": {
                name: hashlib.sha256((Path(__file__).parent / name).read_bytes()).hexdigest()
                for name in ("features.py", "feature_recipes.py", "native_feature_corrections.py")
            },
            "compatibility_key": "config_hash + worker_lock_hash + model_hash",
        }
    return result


def feature_capabilities() -> list[dict[str, Any]]:
    """Report version availability without importing Qlib or initializing a provider."""
    versions: dict[str, str] = {}
    status, reason = "available", None
    try:
        versions = {name: importlib.metadata.version(name) for name in NATIVE_VERSIONS}
        if versions != NATIVE_VERSIONS:
            status, reason = (
                "incompatible_dependency",
                "requires pinned Qlib numerical dependencies",
            )
    except importlib.metadata.PackageNotFoundError as exc:
        status, reason = "missing_dependency", f"missing installed dependency: {exc.name}"
    return [
        {
            "name": "alpha158",
            "version": 1,
            "status": "available",
            "reason": None,
            "scope": "historical_alpha158_style",
            "versions": {},
        },
        {
            "name": "alpha158",
            "version": 2,
            "status": status,
            "reason": reason,
            "scope": "partial_alpha158_style_40_column_correction",
            "versions": versions,
        },
    ]
