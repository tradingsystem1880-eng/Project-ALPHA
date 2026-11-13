"""Feature recipe v3: parity with upstream Qlib's own provider/handler path and processors."""

from __future__ import annotations

import re
import subprocess
import sys
import warnings
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import polars as pl
import pytest

from alpha_qlib_worker.feature_recipes import build_features, feature_recipe_diagnostics
from alpha_qlib_worker.features import alpha158_feature_names
from alpha_qlib_worker.upstream_alpha158 import (
    INFER_PROCESSORS,
    LEARN_PROCESSORS,
    VWAP_COLUMNS,
    alpha158_config,
    upstream_alpha158_features,
    upstream_fold_frames,
)

REFERENCE = Path(__file__).with_name("upstream_alpha158_reference.py")


def parity_panel(*, seed: int = 20261114, sessions: int = 150) -> pl.DataFrame:
    """Four instruments, irregular calendar, staggered starts, a gap and a zero volume."""
    rng = np.random.default_rng(seed)
    start = datetime(2022, 1, 3, tzinfo=UTC)
    # Weekday-like calendar with weekends and two "holidays" removed.
    calendar = [start + timedelta(days=i + 2 * (i // 5)) for i in range(sessions + 2)]
    calendar = [day for index, day in enumerate(calendar) if index not in (17, 93)]
    rows = []
    for k, symbol in enumerate(("AAA", "BBB", "CCC", "DDD")):
        days = calendar[k * 6 :]
        if symbol == "BBB":
            days = [day for index, day in enumerate(days) if index not in (70, 71, 72)]
        close = 20.0 + 15.0 * k
        for index, day in enumerate(days):
            close *= float(np.exp(rng.normal(0.0, 0.02)))
            open_ = close * float(np.exp(rng.normal(0.0, 0.01)))
            high = max(open_, close) * (1.0 + float(rng.uniform(0.0, 0.02)))
            low = min(open_, close) * (1.0 - float(rng.uniform(0.0, 0.02)))
            volume = float(rng.integers(1_000, 250_000))
            if symbol == "CCC" and index in (40, 41):
                volume = 0.0
            if symbol == "DDD" and index == 30:
                open_ = high = low = close  # zero-range bar
            rows.append(
                {
                    "symbol": symbol,
                    "session_ts": day,
                    "open": open_,
                    "high": high,
                    "low": low,
                    "close": close,
                    "volume": volume,
                }
            )
    return pl.DataFrame(rows).sort(["session_ts", "symbol"])


def upstream_reference(panel: pl.DataFrame, tmp_path: Path) -> pd.DataFrame:
    source = panel.with_columns(
        ((pl.col("high") + pl.col("low") + pl.col("close")) / 3.0).alias("vwap")
    )
    source_path, output = tmp_path / "panel.parquet", tmp_path / "reference.parquet"
    source.write_parquet(source_path)
    subprocess.run(
        [sys.executable, str(REFERENCE), str(source_path), str(tmp_path / "provider"), str(output)],
        check=True,
        capture_output=True,
        timeout=600,
    )
    frame = pd.read_parquet(output)
    frame["datetime"] = pd.DatetimeIndex(frame["datetime"]).tz_localize(UTC)
    return frame.set_index(["datetime", "instrument"]).sort_index()


def family(name: str) -> str:
    return re.sub(r"\d+$", "", name)


def test_v3_equals_upstream_provider_and_alpha158_handler_for_all_158_columns(
    tmp_path: Path,
) -> None:
    panel = parity_panel()
    observed = upstream_alpha158_features(panel)
    reference = upstream_reference(panel, tmp_path)
    _, names = alpha158_config()
    assert list(observed.columns) == list(names) == list(reference.columns)
    assert list(names) == list(alpha158_feature_names())  # names/order unchanged from v1
    expected = reference.loc[observed.index]  # provider rows inside a gap are all-NaN extras
    assert observed.shape == (panel.height, 158)
    worst: dict[str, float] = defaultdict(float)
    for name in names:
        left = observed[name].to_numpy(dtype="float64")
        right = expected[name].to_numpy(dtype="float64")
        # Exact equality, including NaN warm-up positions and upstream infinities.
        np.testing.assert_array_equal(left, right, err_msg=name)
        finite = np.isfinite(left)
        if finite.any():
            worst[family(name)] = max(
                worst[family(name)], float(np.abs(left[finite] - right[finite]).max())
            )
    print("max |v3 - upstream| by family:", dict(sorted(worst.items())))
    assert set(worst) == {family(name) for name in names}
    assert max(worst.values()) == 0.0
    # The fixture exercises warm-up NaNs and the instrument gap.
    assert observed.isna().to_numpy().any()
    # Named exclusion from *input* parity (not formula parity): VWAP0 reads $vwap, which both
    # paths receive as the typical-price proxy because ALPHA has no vendor VWAP.
    assert VWAP_COLUMNS == ("VWAP0",)


def test_v3_feature_config_is_taken_from_upstream_handler() -> None:
    from qlib.contrib.data.loader import Alpha158DL

    fields, names = alpha158_config()
    expected = Alpha158DL.get_feature_config(
        {
            "kbar": {},
            "price": {"windows": [0], "feature": ["OPEN", "HIGH", "LOW", "VWAP"]},
            "rolling": {},
        }
    )
    assert (list(fields), list(names)) == (list(expected[0]), list(expected[1]))
    assert "$vwap/$close" in fields


def test_v3_is_causal_deterministic_and_content_keyed() -> None:
    panel = parity_panel(sessions=110)
    cutoff = panel["session_ts"].unique().sort()[70]
    base = build_features(panel, version=3)
    again = build_features(panel, version=3)
    pd.testing.assert_frame_equal(base, again, check_exact=True)
    poisoned = panel.with_columns(
        [
            pl.when(pl.col("session_ts") > cutoff).then(pl.col(c) * 3).otherwise(pl.col(c)).alias(c)
            for c in ("open", "high", "low", "close", "volume")
        ]
    )
    altered = build_features(poisoned, version=3)
    past = base.index.get_level_values("datetime") <= cutoff
    pd.testing.assert_frame_equal(base.loc[past], altered.loc[past], check_exact=True)
    assert not base.loc[~past].equals(altered.loc[~past])
    # Same symbol names, different values: the expression cache must not reuse results.
    renamed = build_features(
        panel.with_columns(pl.col("close") * 1.01, pl.col("high") * 1.01), version=3
    )
    assert not renamed.equals(base)


def test_v3_fails_loud_on_non_finite_input() -> None:
    panel = parity_panel(sessions=70).with_columns(
        pl.when(pl.int_range(pl.len()) == 5)
        .then(float("nan"))
        .otherwise(pl.col("close"))
        .alias("close")
    )
    with pytest.raises(RuntimeError, match="finite OHLCV"):
        upstream_alpha158_features(panel)


def _fold(seed: int = 3) -> tuple[pd.DataFrame, pd.Series, pd.DataFrame, pd.Series, pd.DataFrame]:
    features = upstream_alpha158_features(parity_panel(seed=seed, sessions=150))
    features = features.loc[features.index.get_level_values("instrument") != "BBB"]
    dates = sorted(features.index.get_level_values("datetime").unique())
    rng = np.random.default_rng(seed)
    labels = pd.Series(rng.normal(0, 0.02, len(features)), index=features.index, name="label")
    when = features.index.get_level_values("datetime")
    train = (when >= dates[20]) & (when <= dates[90])
    valid = (when >= dates[95]) & (when <= dates[115])
    test = when >= dates[120]
    return (
        features.loc[train],
        labels.loc[train],
        features.loc[valid],
        labels.loc[valid],
        features.loc[test],
    )


def test_v3_processors_fit_on_training_rows_only() -> None:
    train_x, train_y, valid_x, valid_y, test_x = _fold()
    result = upstream_fold_frames((train_x, train_y), (valid_x, valid_y), test_x)
    state = result["state"]
    assert state["fit_start_time"] == train_x.index.get_level_values(0).min().isoformat()
    assert state["fit_end_time"] == train_x.index.get_level_values(0).max().isoformat()
    # Independent RobustZScoreNorm statistics over the training rows only.
    values = train_x.to_numpy(dtype="float64")
    with np.errstate(all="ignore"), warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        center = np.nanmedian(values, axis=0)
        scale = (np.nanmedian(np.abs(values - center), axis=0) + 1e-12) * 1.4826
    observed_center = np.array([np.nan if v is None else v for v in state["robust_center"]])
    np.testing.assert_array_equal(observed_center, center)

    def expected(frame: pd.DataFrame) -> np.ndarray:
        with np.errstate(all="ignore"):
            out = np.clip((frame.to_numpy(dtype="float64") - center) / scale, -3, 3)
        return np.where(np.isnan(out), 0.0, out)

    for key, frame in (
        ("train_features", train_x),
        ("validation_features", valid_x),
        ("test_features", test_x),
    ):
        np.testing.assert_allclose(result[key].to_numpy(), expected(frame), rtol=0, atol=1e-12)
        assert list(result[key].columns) == list(train_x.columns)
        assert result[key].index.equals(frame.index)
    # Alpha158 default learn processors: CSZScoreNorm (pandas sample std) per datetime.
    for key, raw in (("train_labels", train_y), ("validation_labels", valid_y)):
        grouped = raw.groupby(level="datetime")
        reference = (raw - grouped.transform("mean")) / grouped.transform("std")
        pd.testing.assert_series_equal(result[key], reference, check_exact=False, rtol=1e-12)
    # Poisoning validation/test rows cannot change training outputs or fitted state.
    poisoned = upstream_fold_frames(
        (train_x, train_y), (valid_x * 50.0, valid_y * 9.0), test_x * -7.0
    )
    assert poisoned["state"] == state
    pd.testing.assert_frame_equal(poisoned["train_features"], result["train_features"])
    pd.testing.assert_series_equal(poisoned["train_labels"], result["train_labels"])
    assert [p["class"] for p in state["infer_processors"]] == [p["class"] for p in INFER_PROCESSORS]
    assert [p["class"] for p in state["learn_processors"]] == [p["class"] for p in LEARN_PROCESSORS]
    assert "fit_start_time" not in INFER_PROCESSORS[0]["kwargs"]  # constants not mutated


def test_v3_processors_reject_overlap_and_degenerate_label_cross_sections() -> None:
    train_x, train_y, valid_x, valid_y, test_x = _fold()
    with pytest.raises(RuntimeError, match="overlap"):
        upstream_fold_frames((train_x, train_y), (train_x, train_y), test_x)
    constant = train_y.copy()
    first = constant.index.get_level_values("datetime") == constant.index.get_level_values(0)[0]
    constant[first] = 0.01
    with pytest.raises(RuntimeError, match="non-finite labels"):
        upstream_fold_frames((train_x, constant), (valid_x, valid_y), test_x)


def test_v3_diagnostics_disclose_scope_and_vwap_proxy() -> None:
    diagnostic = feature_recipe_diagnostics(3)
    upstream = diagnostic["upstream_alpha158"]
    assert diagnostic["feature_count"] == 158 and upstream["upstream_columns"] == 158
    assert upstream["legacy_columns"] == 0
    assert diagnostic["vwap_source"] == "causal_typical_price_proxy_not_vendor_vwap"
    assert upstream["vwap"]["affected_columns"] == ["VWAP0"]
    assert set(upstream["source_sha256"]) == {"feature_recipes.py", "upstream_alpha158.py"}
    assert "versioned_correction" not in diagnostic


def test_v3_does_not_initialise_qlib_or_change_numpy_error_mode(tmp_path: Path) -> None:
    # A fresh process: other worker tests legitimately initialise Qlib's recorder runtime.
    source = tmp_path / "panel.parquet"
    parity_panel(sessions=70).write_parquet(source)
    script = f"""
import numpy as np, polars as pl
from qlib.config import C
from qlib.data import data
from alpha_qlib_worker.feature_recipes import build_features
before = np.geterr()
build_features(pl.read_parquet({str(source)!r}), version=3)
assert np.geterr() == before
assert C.registered is False
assert all(
    vars(getattr(data, key)).get("_provider") is None
    for key in ("Cal", "Inst", "FeatureD", "PITD", "ExpressionD", "DatasetD", "D")
)
"""
    subprocess.run([sys.executable, "-c", script], check=True, timeout=300)


@pytest.mark.parametrize("envelope,model", [(1, "lightgbm"), (3, "linear")])
def test_v3_runs_end_to_end_in_the_real_worker(tmp_path: Path, envelope: int, model: str) -> None:
    import json

    from alpha_qlib_worker.contract import canonical_json_bytes, compute_config_hash
    from alpha_qlib_worker.real import run_real

    from .test_fake_worker import _exchange

    exchange = _exchange(tmp_path / "exchange")
    path = exchange / "request.json"
    request = json.loads(path.read_text())
    request["schema_version"], request["model"]["name"] = envelope, model
    request["model"]["parameters"] = (
        {"early_stopping_rounds": 3, "num_boost_round": 8, "num_leaves": 15, "num_threads": 1}
        if model == "lightgbm"
        else {}
    )
    request["feature_recipe"]["version"] = 3
    request["config_hash"] = compute_config_hash(request)
    path.write_bytes(canonical_json_bytes(request))
    result = run_real(exchange, worker_lock_path=Path(__file__).parents[1] / "uv.lock")
    diagnostics = result["diagnostics"]
    assert diagnostics["feature_recipe"]["upstream_alpha158"]["version"] == 3
    assert {fold["normalization"]["method"] for fold in diagnostics["folds"]} == {
        "qlib_processors_v3"
    }
    if envelope == 3:  # schema-3 fitted-component provenance links still validate
        assert diagnostics["fit_provenance"]["folds"]
    assert result["predictions"]["rows"] > 0
