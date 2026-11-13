"""Explicit feature recipe versions.

Version 3 computes all 158 Alpha158 columns with upstream Qlib (``upstream_alpha158``); new
work should use it. Versions 1 and 2 are legacy recipes kept, byte for byte, only to reproduce
stored results: v1 is the hand-written ``features`` module (Alpha158-style, not parity) and v2
replaces 40 of its columns with upstream operators. Version 1 remains the default.
"""

from __future__ import annotations

import copy
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
    if type(version) is not int or version not in (1, 2, 3):
        raise ValueError("unsupported alpha158 feature recipe version; expected integer 1, 2 or 3")
    return version


def build_features(panel: pl.DataFrame, *, version: int = 1) -> pd.DataFrame:
    """Build v3 from upstream Alpha158, or a legacy v1/v2 matrix for stored results.

    V3: every column from upstream Qlib expressions (``upstream_alpha158``).
    Legacy v1: the hand-written formulas, unchanged. Legacy v2: v1 with a bounded 40-column
    upstream-operator correction (eight families at five windows); not whole-recipe parity.
    """
    validate_feature_version(version)
    if version == 3:
        # Qlib's import modifies NumPy's process error policy. Keep this local call scoped.
        with np.errstate(divide="ignore", invalid="ignore"):
            from alpha_qlib_worker.upstream_alpha158 import upstream_alpha158_features

            return upstream_alpha158_features(panel)
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
    """Preserve historical diagnostics; new metadata is emitted only for opt-in v2/v3."""
    validate_feature_version(version)
    if version == 3:
        return _upstream_diagnostics()
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


def _upstream_diagnostics() -> dict[str, Any]:
    with np.errstate(divide="ignore", invalid="ignore"):
        from alpha_qlib_worker import upstream_alpha158 as upstream

        binding = upstream.upstream_binding()
        _, names = upstream.alpha158_config()
    return {
        "name": "Alpha158 v3 (upstream Qlib expressions and processors)",
        "feature_count": len(names),
        "names": list(names),
        "vwap_source": upstream.VWAP_SOURCE,
        "upstream_alpha158": {
            "name": "alpha158",
            "version": 3,
            "scope": "upstream_alpha158_all_158_columns",
            "upstream_columns": len(names),
            "legacy_columns": 0,
            "feature_config": "qlib.contrib.data.handler.Alpha158.get_feature_config",
            "expression_engine": (
                "qlib.utils.parse_field + qlib.data.ops.OpsList on in-memory panel fields; "
                "no provider or qlib.init"
            ),
            "precision": "float32 inputs and outputs, as Qlib providers and expressions",
            "calendar": "panel sessions; instruments dense from first to last session",
            "vwap": {
                "source": upstream.VWAP_SOURCE,
                "definition": "(high + low + close) / 3",
                "affected_columns": list(upstream.VWAP_COLUMNS),
            },
            "processors": {
                "handler": "qlib.data.dataset.handler.DataHandlerLP + StaticDataLoader",
                "process_type": "append",
                "infer": copy.deepcopy(list(upstream.INFER_PROCESSORS)),
                "learn": copy.deepcopy(list(upstream.LEARN_PROCESSORS)),
                "fit_segment": "training rows of each fold only",
            },
            "warmup": "Qlib partial windows and NaN warm-up for every column",
            "nonfinite": (
                "upstream NaN/inf kept in features; RobustZScoreNorm clips to +/-3 and "
                "Fillna sets missing to 0; non-finite processed labels fail the run"
            ),
            "input": "validated ALPHA OHLCV panel only; no vendor VWAP or pre-panel history",
            "upstream": binding,
            "source_sha256": {
                name: hashlib.sha256((Path(__file__).parent / name).read_bytes()).hexdigest()
                for name in ("feature_recipes.py", "upstream_alpha158.py")
            },
            "compatibility_key": "config_hash + worker_lock_hash + model_hash",
        },
    }


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
        {
            "name": "alpha158",
            "version": 3,
            "status": status,
            "reason": reason,
            "scope": "upstream_alpha158_all_158_columns",
            "versions": versions,
        },
    ]
