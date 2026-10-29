"""Fold-refitted Qlib/LightGBM worker behind the portable ALPHA exchange contract."""

from __future__ import annotations

import hashlib
import importlib
import math
import os
import tempfile
import warnings
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import numpy as np
import pandas as pd
import polars as pl

from alpha_qlib_worker import __version__
from alpha_qlib_worker.contract import (
    PREDICTION_COLUMNS,
    WorkerRequest,
    canonical_json_bytes,
    sha256_file,
    validate_request,
)
from alpha_qlib_worker.features import alpha158_feature_names, alpha158_features
from alpha_qlib_worker.fit_provenance import (
    FitInvocation,
    FitTrace,
    row_digest,
    validate_reference_graph,
    value_digest,
)
from alpha_qlib_worker.rank_ensemble import rank_ensemble_v1
from alpha_qlib_worker.tabular_adapters import fit_tabular


class WorkerDependencyError(RuntimeError):
    """The optional real-worker dependency stack is unavailable."""


class _MemoryDataset:
    """Small DatasetH-compatible adapter for already-verified, in-memory fold frames."""

    def __init__(self, frames: Mapping[str, pd.DataFrame], *, flatten_single: bool = False) -> None:
        self._flatten_single = flatten_single
        self._frames = dict(frames)
        self.segments = {name: name for name in self._frames}

    def prepare(
        self,
        segment: str | Sequence[str],
        col_set: str | Sequence[str] = "__all",
        data_key: str = "infer",
        **_: object,
    ) -> Any:
        del data_key
        if not isinstance(segment, str):
            return [self.prepare(name, col_set=col_set) for name in segment]
        frame = self._frames[segment]
        if col_set == "__all__":
            return frame
        if isinstance(col_set, str):
            if self._flatten_single:
                return frame[col_set]
            return frame.loc[:, frame.columns.get_level_values(0) == col_set]
        requested = set(col_set)
        return frame.loc[:, frame.columns.get_level_values(0).isin(requested)]


_QLIB_RUNTIME: tempfile.TemporaryDirectory[str] | None = None
_MODEL_PARAMETER_DEFAULTS: dict[str, int | float] = {
    "bagging_fraction": 1.0,
    "early_stopping_rounds": 20,
    "feature_fraction": 1.0,
    "lambda_l1": 0.0,
    "lambda_l2": 0.0,
    "learning_rate": 0.05,
    "max_depth": -1,
    "min_data_in_leaf": 20,
    "num_boost_round": 300,
    "num_leaves": 31,
    "num_threads": 4,
}


def require_real_dependencies(
    *, import_module: Callable[[str], ModuleType] = importlib.import_module
) -> tuple[ModuleType, ModuleType]:
    """Load the heavy stack lazily, outside every ALPHA process."""
    loaded: list[ModuleType] = []
    missing: list[str] = []
    for name in ("qlib", "lightgbm"):
        try:
            loaded.append(import_module(name))
        except (ImportError, ModuleNotFoundError):
            missing.append(name)
    if missing:
        raise WorkerDependencyError(
            "Qlib and LightGBM are unavailable in the isolated worker environment "
            f"(missing: {', '.join(missing)}). Run `uv sync --project workers/qlib "
            "--locked` or use the deterministic fake worker."
        )
    return loaded[0], loaded[1]


def _number(
    value: object,
    name: str,
    *,
    minimum: float,
    maximum: float | None = None,
    integer: bool = False,
) -> int | float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise RuntimeError(f"model.parameters.{name} must be a finite number")
    number = float(value)
    if not math.isfinite(number) or number < minimum or (maximum is not None and number > maximum):
        ceiling = f" and <= {maximum}" if maximum is not None else ""
        raise RuntimeError(f"model.parameters.{name} must be >= {minimum}{ceiling}")
    if integer:
        if not number.is_integer():
            raise RuntimeError(f"model.parameters.{name} must be an integer")
        return int(number)
    return number


def resolve_model_parameters(raw: object) -> dict[str, int | float]:
    """Resolve the bounded CPU-only model recipe; seeds and determinism are not overridable."""
    if not isinstance(raw, dict):
        raise RuntimeError("model.parameters must be an object")
    unknown = sorted(set(raw) - set(_MODEL_PARAMETER_DEFAULTS))
    if unknown:
        raise RuntimeError(f"unsupported model parameters: {unknown}")
    result = dict(_MODEL_PARAMETER_DEFAULTS)
    validators: dict[str, tuple[float, float | None, bool]] = {
        "bagging_fraction": (0.01, 1.0, False),
        "early_stopping_rounds": (1.0, 1000.0, True),
        "feature_fraction": (0.01, 1.0, False),
        "lambda_l1": (0.0, 1_000_000.0, False),
        "lambda_l2": (0.0, 1_000_000.0, False),
        "learning_rate": (0.0001, 1.0, False),
        "max_depth": (-1.0, 64.0, True),
        "min_data_in_leaf": (1.0, 1_000_000.0, True),
        "num_boost_round": (1.0, 5000.0, True),
        "num_leaves": (2.0, 4096.0, True),
        "num_threads": (1.0, 8.0, True),
    }
    for name, value in raw.items():
        minimum, maximum, integer = validators[name]
        result[name] = _number(value, name, minimum=minimum, maximum=maximum, integer=integer)
    return result


def _ensure_qlib_runtime(qlib_module: ModuleType) -> Any:
    global _QLIB_RUNTIME
    if _QLIB_RUNTIME is None:
        _QLIB_RUNTIME = tempfile.TemporaryDirectory(prefix="alpha-qlib-runtime-")
        root = Path(_QLIB_RUNTIME.name)
        qlib_module.init(
            provider_uri=root / "provider",
            exp_manager={
                "class": "MLflowExpManager",
                "module_path": "qlib.workflow.expm",
                "kwargs": {
                    "uri": f"sqlite:///{root / 'mlflow.db'}",
                    "default_exp_name": "ALPHA",
                },
            },
        )
    return importlib.import_module("qlib.workflow").R


@contextmanager
def _qlib_runtime_directory() -> Iterator[None]:
    if _QLIB_RUNTIME is None:
        raise RuntimeError("Qlib runtime was not initialized")
    previous = Path.cwd()
    os.chdir(_QLIB_RUNTIME.name)
    try:
        yield
    finally:
        os.chdir(previous)


def _official_feature_names() -> tuple[str, ...]:
    loader = importlib.import_module("qlib.contrib.data.loader").Alpha158DL
    config = {
        "kbar": {},
        "price": {"windows": [0], "feature": ["OPEN", "HIGH", "LOW", "VWAP"]},
        "rolling": {},
    }
    _, names = loader.get_feature_config(config)
    result = tuple(str(name) for name in names)
    if result != alpha158_feature_names():
        raise RuntimeError("installed Qlib Alpha158 definition differs from worker recipe")
    return result


def _sample_table(request: WorkerRequest, features: pd.DataFrame) -> pd.DataFrame:
    sessions = list(request.sessions)
    next_session = {sessions[index]: sessions[index + 1] for index in range(len(sessions) - 1)}
    panel = request.panel.to_pandas()
    opens = panel.pivot(index="session_ts", columns="symbol", values="open").sort_index()
    realized = opens.shift(-1) / opens - 1.0
    label_lookup = realized.stack(future_stack=True).to_dict()
    table = features.reset_index()
    table["target_ts"] = table["datetime"].map(next_session)
    table["label"] = [
        label_lookup.get((target, symbol), float("nan"))
        for target, symbol in zip(table["target_ts"], table["instrument"], strict=True)
    ]
    # A prediction for the final aligned session cannot be evaluated as an open-to-open target:
    # its realized label needs the following aligned open.  Filter it before model inference so
    # the real worker emits the same production contract as the fake worker and canonical import.
    return table.loc[table["target_ts"].isin(next_session)].copy()


def _select_split(
    samples: pd.DataFrame,
    *,
    start: datetime,
    end: datetime,
    require_label: bool,
) -> tuple[pd.DataFrame, pd.Series, pd.DataFrame]:
    selected = samples.loc[samples["target_ts"].between(start, end, inclusive="both")].copy()
    if require_label:
        selected = selected.loc[selected["label"].notna()].copy()
    if selected.empty:
        raise RuntimeError(f"fold segment {start}..{end} has no usable samples")
    selected = selected.sort_values(["datetime", "instrument"], kind="mergesort").set_index(
        ["datetime", "instrument"]
    )
    features = selected.loc[:, alpha158_feature_names()].astype("float64")
    labels = selected["label"].astype("float64")
    metadata = selected.loc[:, ["target_ts"]]
    return features, labels, metadata


def _interval_records(request: WorkerRequest, metadata: pd.DataFrame) -> list[list[str]]:
    sessions = [pd.Timestamp(session) for session in request.sessions]
    following = dict(zip(sessions[:-1], sessions[1:], strict=True))
    available = {
        (pd.Timestamp(session), symbol): pd.Timestamp(known)
        for session, symbol, known in request.panel.select(
            "session_ts", "symbol", "available_at"
        ).iter_rows()
    }
    records: list[list[str]] = []
    for row, target_raw in metadata["target_ts"].items():
        if not isinstance(row, tuple) or len(row) != 2 or not isinstance(row[1], str):
            raise RuntimeError("provenance requires canonical origin/symbol row keys")
        origin_raw, symbol = row
        origin, target = pd.Timestamp(origin_raw), pd.Timestamp(target_raw)
        if following.get(origin) != target or target not in following:
            raise RuntimeError("provenance requires the declared one-session target interval")
        end = following[target]
        feature_known, label_known = available[(origin, symbol)], available[(end, symbol)]
        if feature_known >= target or label_known < end:
            raise RuntimeError("provenance availability clock violates the target interval")
        records.append(
            [
                origin.isoformat(),
                str(symbol),
                target.isoformat(),
                end.isoformat(),
                feature_known.isoformat(),
                label_known.isoformat(),
            ]
        )
    return records


def _scope_provenance(
    features: pd.DataFrame,
    labels: pd.Series | None,
    metadata: pd.DataFrame,
    records: list[list[str]],
) -> dict[str, Any]:
    if (
        not features.index.equals(metadata.index)
        or len(features) != len(records)
        or (labels is not None and not labels.index.equals(features.index))
        or not records
    ):
        raise RuntimeError("provenance scope rows are empty or misaligned")
    windows: dict[str, str] = {}
    for name, column in [
        ("origin", 0),
        ("target", 2),
        ("label_end", 3),
        ("feature_known_at", 4),
        ("label_known_at", 5),
    ]:
        values = [record[column] for record in records]
        windows[f"{name}_start"], windows[f"{name}_end"] = min(values), max(values)
    return {
        "row_count": len(features),
        "origin_session_count": len({record[0] for record in records}),
        "target_session_count": len({record[2] for record in records}),
        "outcome_interval_count": len({(record[2], record[3]) for record in records}),
        "event_cluster_count": len({(record[2], record[3]) for record in records}),
        "row_ids_sha256": row_digest(features),
        "feature_values_sha256": value_digest(features),
        "label_values_sha256": value_digest(labels) if labels is not None else None,
        "target_sessions_sha256": value_digest(pd.Index(metadata["target_ts"])),
        "intervals_sha256": value_digest(records),
        "windows": windows,
    }


def _fold_input_provenance(
    request: WorkerRequest,
    samples: pd.DataFrame,
    fold: dict[str, Any],
    *,
    train: tuple[pd.DataFrame, pd.Series, pd.DataFrame],
    validation: tuple[pd.DataFrame, pd.Series, pd.DataFrame],
    test: tuple[pd.DataFrame, None, pd.DataFrame],
) -> dict[str, Any]:
    segments = {"train": train, "validation": validation, "test": test}
    records = {name: _interval_records(request, meta) for name, (_, _, meta) in segments.items()}
    scopes = {
        name: _scope_provenance(features, labels, meta, records[name])
        for name, (features, labels, meta) in segments.items()
    }

    def excluded(left: datetime, right: datetime) -> dict[str, Any]:
        selected = (
            samples.loc[
                (samples["target_ts"] > left) & (samples["target_ts"] < right),
                ["datetime", "instrument", "target_ts"],
            ]
            .sort_values(["datetime", "instrument"], kind="mergesort")
            .set_index(["datetime", "instrument"])
        )
        return {
            "row_count": len(selected),
            "row_ids_sha256": row_digest(selected),
            "intervals_sha256": value_digest(_interval_records(request, selected)),
        }

    train_cutoff = scopes["validation"]["windows"]["feature_known_at_start"]
    validation_cutoff = scopes["test"]["windows"]["feature_known_at_start"]
    if pd.Timestamp(scopes["train"]["windows"]["label_known_at_end"]) > pd.Timestamp(
        train_cutoff
    ) or pd.Timestamp(scopes["validation"]["windows"]["label_known_at_end"]) > pd.Timestamp(
        validation_cutoff
    ):
        raise RuntimeError("fitted labels were unavailable at the next segment origin")
    intervals = {
        name: sorted({(record[2], record[3]) for record in role_records})
        for name, role_records in records.items()
    }
    overlaps = sum(
        1
        for left, right in [("train", "validation"), ("train", "test"), ("validation", "test")]
        for left_start, left_end in intervals[left]
        for right_start, right_end in intervals[right]
        if left_start < right_end and right_start < left_end
    )
    if overlaps:
        raise RuntimeError("fitted and evaluation label intervals overlap")
    session_index = {session: index for index, session in enumerate(request.sessions)}
    return {
        "scopes": scopes,
        "exclusions": {
            "interval_policy": "aligned_session_open_to_next_open_half_open",
            "horizon_sessions": 1,
            "purge_sessions": int(request.payload["purge_sessions"]),
            "embargo_sessions": int(request.payload["embargo_sessions"]),
            "train_validation_gap_sessions": session_index[fold["validation_start"]]
            - session_index[fold["train_end"]]
            - 1,
            "validation_test_gap_sessions": session_index[fold["test_start"]]
            - session_index[fold["validation_end"]]
            - 1,
            "train_validation": excluded(fold["train_end"], fold["validation_start"]),
            "validation_test": excluded(fold["validation_end"], fold["test_start"]),
            "train_label_cutoff": train_cutoff,
            "validation_label_cutoff": validation_cutoff,
            "cross_split_interval_overlap_count": overlaps,
            "dependence_policy": "same_target_session_across_symbols_is_dependent",
            "general_event_clusters": "not_evaluated",
        },
    }


def _seal_fold_provenance(
    trace: FitTrace,
    *,
    fold: int,
    model_hash: str,
    inputs: dict[str, Any],
    model_name: str,
    parameters: Mapping[str, Any],
) -> dict[str, Any]:
    sealed = trace.seal()
    events = {event["component"]: event for event in sealed["events"]}
    normalizer = events.get("normalizer", {})
    train = inputs["scopes"]["train"]
    if (
        normalizer.get("input_row_ids_sha256", {}).get("train") != train["row_ids_sha256"]
        or normalizer.get("input_hashes", {}).get("train") != train["feature_values_sha256"]
        or normalizer.get("input_row_counts", {}).get("train") != train["row_count"]
    ):
        raise RuntimeError("normalizer consumed a different raw training scope")
    for role in ["train", "validation"]:
        label = events.get(f"label.{role}", {})
        scope = inputs["scopes"][role]
        if (
            label.get("input_hashes", {}).get("labels") != scope["label_values_sha256"]
            or label.get("input_hashes", {}).get("target_sessions")
            != scope["target_sessions_sha256"]
            or label.get("input_row_ids_sha256", {}).get("labels") != scope["row_ids_sha256"]
            or label.get("input_row_counts", {}).get("labels") != scope["row_count"]
        ):
            raise RuntimeError("label transform consumed a different raw label scope")
    graph_status = validate_reference_graph(sealed, name=model_name, parameters=parameters)
    return {
        "fold": fold,
        "model_hash": model_hash,
        **inputs,
        **sealed,
        "graph_status": graph_status,
    }


def _normalize_label(
    labels: pd.Series,
    targets: pd.Series,
    *,
    recorder: FitTrace | None = None,
    component: str = "label",
) -> pd.Series:
    token = (
        recorder.begin(
            component, "transform", {"labels": labels, "target_sessions": pd.Index(targets)}
        )
        if recorder is not None
        else None
    )
    try:
        frame = pd.DataFrame({"label": labels, "target": targets}, index=labels.index)

        def normalize(group: pd.Series) -> pd.Series:
            std = float(group.std(ddof=0))
            if not math.isfinite(std) or std <= 0.0:
                return pd.Series(0.0, index=group.index)
            return (group - float(group.mean())) / std

        result = frame.groupby("target", sort=False, observed=True)["label"].transform(normalize)
        if recorder is not None and token is not None:
            recorder.complete(token, {"state": result, "normalized_labels": result})
        return result
    except BaseException as exc:
        if recorder is not None and token is not None:
            recorder.failed(token, exc)
        raise


def _normalize_features(
    train: pd.DataFrame,
    others: Sequence[pd.DataFrame],
    *,
    recorder: FitTrace | None = None,
) -> tuple[pd.DataFrame, list[pd.DataFrame], str, int]:
    token = recorder.begin("normalizer", "fit", {"train": train}) if recorder is not None else None
    try:
        median = train.median(axis=0, skipna=True)
        all_missing = int(median.isna().sum())
        median = median.fillna(0.0)
        filled_train = train.fillna(median)
        center = filled_train.mean(axis=0)
        scale = filled_train.std(axis=0, ddof=0).replace(0.0, 1.0).fillna(1.0)
        normalized_train = (filled_train - center) / scale
        normalized_others = [(frame.fillna(median) - center) / scale for frame in others]
        for frame in [normalized_train, *normalized_others]:
            if not np.isfinite(frame.to_numpy(dtype="float64")).all():
                raise RuntimeError("fold-local feature normalization produced non-finite values")
        payload = {
            "method": "train_only_median_then_zscore",
            "median": [float(value) for value in median],
            "center": [float(value) for value in center],
            "scale": [float(value) for value in scale],
        }
        normalization_hash = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
        if recorder is not None and token is not None:
            recorder.complete(
                token,
                {
                    "state": payload,
                    "train_features": normalized_train,
                    **{
                        f"other_{index}_features": frame
                        for index, frame in enumerate(normalized_others)
                    },
                },
            )
        return normalized_train, normalized_others, normalization_hash, all_missing
    except BaseException as exc:
        if recorder is not None and token is not None:
            recorder.failed(token, exc)
        raise


def _qlib_frame(
    features: pd.DataFrame,
    labels: pd.Series | None = None,
) -> pd.DataFrame:
    feature_frame = features.copy()
    feature_frame.columns = pd.MultiIndex.from_product([["feature"], list(feature_frame.columns)])
    if labels is None:
        return feature_frame
    label_frame = labels.to_frame("LABEL0")
    label_frame.columns = pd.MultiIndex.from_product([["label"], ["LABEL0"]])
    return pd.concat([feature_frame, label_frame], axis=1)


def _finite_float(value: Any, label: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise RuntimeError(f"{label} is non-finite")
    return result


def _history(evals: Mapping[str, Mapping[str, Sequence[object]]]) -> dict[str, Any]:
    return {
        split: {
            metric: [_finite_float(value, f"training history {split}.{metric}") for value in values]
            for metric, values in metrics.items()
        }
        for split, metrics in evals.items()
    }


def _fold_model(
    *,
    request: WorkerRequest,
    samples: pd.DataFrame,
    fold: dict[str, Any],
    qlib_module: ModuleType,
    lightgbm_module: ModuleType,
    fit_trace: FitTrace | None = None,
) -> tuple[
    pl.DataFrame,
    dict[str, Any],
    list[tuple[str, float, int]],
    pl.DataFrame | None,
]:
    del lightgbm_module
    schema3 = request.payload["schema_version"] == 3
    if not schema3 and fit_trace is not None:
        raise RuntimeError("fitted-component traces require schema 3")
    trace = fit_trace if fit_trace is not None else (FitTrace() if schema3 else None)
    train_x, train_y, train_meta = _select_split(
        samples,
        start=fold["train_start"],
        end=fold["train_end"],
        require_label=True,
    )
    valid_x, valid_y, valid_meta = _select_split(
        samples,
        start=fold["validation_start"],
        end=fold["validation_end"],
        require_label=True,
    )
    test_x, _, test_meta = _select_split(
        samples,
        start=fold["test_start"],
        end=fold["test_end"],
        require_label=False,
    )
    input_provenance = (
        _fold_input_provenance(
            request,
            samples,
            fold,
            train=(train_x, train_y, train_meta),
            validation=(valid_x, valid_y, valid_meta),
            test=(test_x, None, test_meta),
        )
        if schema3
        else None
    )
    train_x, (valid_x, test_x), normalization_hash, all_missing = _normalize_features(
        train_x, [valid_x, test_x], recorder=trace
    )
    train_y = _normalize_label(
        train_y, train_meta["target_ts"], recorder=trace, component="label.train"
    )
    valid_y = _normalize_label(
        valid_y, valid_meta["target_ts"], recorder=trace, component="label.validation"
    )
    dataset = _MemoryDataset(
        {
            "train": _qlib_frame(train_x, train_y),
            "valid": _qlib_frame(valid_x, valid_y),
            "test": _qlib_frame(test_x),
        },
        flatten_single=request.payload["schema_version"] == 3,
    )
    tabular_diagnostic: dict[str, Any] | None = None
    evaluations: dict[str, Any] = {}
    scores: Any
    if request.payload["schema_version"] == 3:
        recorder = _ensure_qlib_runtime(qlib_module)
        with _qlib_runtime_directory():
            recorder.start_exp(
                experiment_name=f"alpha-{request.payload['config_hash'][:12]}",
                recorder_name=f"fold-{fold['fold']}",
            )
            try:
                fitted = fit_tabular(
                    dataset,
                    name=request.payload["model"]["name"],
                    raw=request.payload["model"]["parameters"],
                    seed=int(request.payload["seed"]),
                    recorder=trace,
                )
            except BaseException:
                recorder.end_exp("FAILED")
                raise
            else:
                recorder.end_exp("FINISHED")
        scores, model_hash, importance = fitted.scores, fitted.model_hash, fitted.importance
        tabular_diagnostic = fitted.diagnostics
        best_iteration = int(tabular_diagnostic["best_iteration"])
        evaluations = tabular_diagnostic["training_history"]
        seed = int(request.payload["seed"])
    else:
        params = resolve_model_parameters(request.payload["model"]["parameters"])
        rounds = int(params.pop("num_boost_round"))
        early = int(params.pop("early_stopping_rounds"))
        seed = int(request.payload["seed"])
        model_class = importlib.import_module("qlib.contrib.model.gbdt").LGBModel
        model = model_class(
            loss="mse",
            num_boost_round=rounds,
            early_stopping_rounds=early,
            objective="regression",
            metric="l2",
            device_type="cpu",
            deterministic=True,
            force_col_wise=True,
            seed=seed,
            bagging_seed=seed,
            feature_fraction_seed=seed,
            data_random_seed=seed,
            verbosity=-1,
            **params,
        )
        recorder = _ensure_qlib_runtime(qlib_module)
        evaluations = {}
        with (
            _qlib_runtime_directory(),
            recorder.start(
                experiment_name=f"alpha-{request.payload['config_hash'][:12]}",
                recorder_name=f"fold-{fold['fold']}",
            ),
        ):
            model.fit(dataset, verbose_eval=0, evals_result=evaluations)
            scores = model.predict(dataset, segment="test")
        booster = model.model
        if booster is None:
            raise RuntimeError(f"Qlib fold {fold['fold']} did not produce a LightGBM booster")
        model_text = booster.model_to_string(num_iteration=booster.best_iteration)
        model_hash = hashlib.sha256(model_text.encode("utf-8")).hexdigest()
        best_iteration = int(booster.best_iteration)
        importance = [
            (name, float(gain), int(split))
            for name, gain, split in zip(
                alpha158_feature_names(),
                booster.feature_importance(importance_type="gain"),
                booster.feature_importance(importance_type="split"),
                strict=True,
            )
        ]
    availability = {
        (row[0], row[1]): row[2]
        for row in request.panel.select("symbol", "session_ts", "available_at").iter_rows()
    }
    prediction_rows: list[dict[str, Any]] = []
    for (origin, symbol), score in scores.items():
        target = test_meta.loc[(origin, symbol), "target_ts"]
        prediction_rows.append(
            {
                "symbol": str(symbol),
                "origin_ts": origin.to_pydatetime(),
                "available_at": availability[(str(symbol), origin.to_pydatetime())],
                "target_ts": target.to_pydatetime(),
                "score": float(score),
                "fold": int(fold["fold"]),
                "split": "test",
                "model_hash": model_hash,
                "config_hash": request.payload["config_hash"],
                "worker_lock_hash": request.payload["worker_lock_hash"],
                "seed": seed,
            }
        )
    predictions = pl.DataFrame(
        prediction_rows,
        schema={
            "symbol": pl.String,
            "origin_ts": pl.Datetime("us", "UTC"),
            "available_at": pl.Datetime("us", "UTC"),
            "target_ts": pl.Datetime("us", "UTC"),
            "score": pl.Float64,
            "fold": pl.Int64,
            "split": pl.String,
            "model_hash": pl.String,
            "config_hash": pl.String,
            "worker_lock_hash": pl.String,
            "seed": pl.Int64,
        },
    ).select(PREDICTION_COLUMNS)
    ensemble_diagnostics: pl.DataFrame | None = None
    ridge_diagnostic: dict[str, Any] | None = None
    if request.payload["schema_version"] == 2:
        ridge_class = importlib.import_module("qlib.contrib.model.linear").LinearModel
        ridge = ridge_class(
            estimator="ridge",
            alpha=1.0,
            fit_intercept=False,
            include_valid=False,
        )
        # NumPy 2 may emit spurious matmul overflow warnings from sklearn's finite-check fast
        # path even for the bounded, fold-normalized matrix.  Validate the fitted outputs below.
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message="(divide by zero|overflow) encountered in matmul",
                category=RuntimeWarning,
            )
            ridge.fit(dataset)
            ridge_scores = ridge.predict(dataset, segment="test")
        coefficients = np.asarray(ridge.coef_, dtype="float64")
        if not np.isfinite(coefficients).all():
            raise RuntimeError("Qlib ridge produced non-finite coefficients")
        if not np.isfinite(ridge_scores.to_numpy(dtype="float64")).all():
            raise RuntimeError("Qlib ridge produced non-finite OOS scores")
        ridge_hash = hashlib.sha256(
            canonical_json_bytes(
                {
                    "recipe": "qlib_ridge_v1",
                    "alpha": 1.0,
                    "fit_intercept": False,
                    "include_valid": False,
                    "coefficients": [float(value) for value in coefficients],
                }
            )
        ).hexdigest()
        ridge_predictions = predictions.with_columns(
            pl.Series(
                "score",
                [float(ridge_scores.loc[index]) for index in scores.index],
                dtype=pl.Float64,
            ),
            pl.lit(ridge_hash).alias("model_hash"),
        )
        predictions, ensemble_diagnostics = rank_ensemble_v1(predictions, ridge_predictions)
        ridge_diagnostic = {
            "recipe": "qlib_ridge_v1",
            "alpha": 1.0,
            "fit_intercept": False,
            "include_valid": False,
            "model_hash": ridge_hash,
            "coefficient_l1": float(np.abs(coefficients).sum()),
            "coefficient_l2": float(np.linalg.norm(coefficients)),
            "nonzero_coefficients": int(np.count_nonzero(coefficients)),
        }
    diagnostic: dict[str, Any] = {
        "fold": int(fold["fold"]),
        "fit_count": 2 if ridge_diagnostic is not None else 1,
        "train_rows": len(train_x),
        "validation_rows": len(valid_x),
        "test_rows": len(test_x),
        "best_iteration": best_iteration,
        "model_hash": model_hash,
        "normalization": {
            "method": "train_only_median_then_zscore",
            "statistics_hash": normalization_hash,
            "all_missing_train_features": all_missing,
        },
        "training_history": _history(evaluations),
        "boundaries": {
            name: fold[name].isoformat()
            for name in (
                "train_start",
                "train_end",
                "validation_start",
                "validation_end",
                "test_start",
                "test_end",
            )
        },
    }
    if tabular_diagnostic is not None:
        diagnostic.update(tabular_diagnostic)
        if trace is None or input_provenance is None:
            raise RuntimeError("schema 3 fitted-component observation is missing")
        diagnostic["_fit_provenance"] = _seal_fold_provenance(
            trace,
            fold=int(fold["fold"]),
            model_hash=model_hash,
            inputs=input_provenance,
            model_name=request.payload["model"]["name"],
            parameters=tabular_diagnostic["resolved_parameters"],
        )
    if ridge_diagnostic is not None:
        diagnostic["ridge"] = ridge_diagnostic
        diagnostic["feature_importance"] = [
            {"feature": name, "gain": gain, "split_count": split_count}
            for name, gain, split_count in importance
        ]
    return predictions, diagnostic, importance, ensemble_diagnostics


def _member_signal_summary(
    request: WorkerRequest,
    ensemble_diagnostics: pl.DataFrame,
    *,
    score_column: str,
    model_hash_column: str,
) -> dict[str, Any]:
    member = ensemble_diagnostics.select(
        "symbol",
        "origin_ts",
        "available_at",
        "target_ts",
        pl.col(score_column).alias("score"),
        "fold",
        "split",
        pl.col(model_hash_column).alias("model_hash"),
        "config_hash",
        "worker_lock_hash",
        "seed",
    ).select(PREDICTION_COLUMNS)
    analysis = _diagnostic_signal_analysis(request, member)
    ic = cast(dict[str, Any], analysis["ic"])
    portfolio = cast(dict[str, Any], analysis["portfolio"])
    return {
        "ic_mean": ic["mean"],
        "rank_ic_mean": ic["rank_mean"],
        "costed_total_return": portfolio["costed_total_return"],
        "costed_excess_total_return": portfolio["costed_excess_total_return"],
        "mean_turnover": portfolio["mean_turnover"],
        "periods": portfolio["periods"],
    }


def _portable_diagnostics(
    request: WorkerRequest,
    predictions: pl.DataFrame,
    fold_diagnostics: list[dict[str, Any]],
    importances: list[list[tuple[str, float, int]]],
    *,
    qlib_version: str,
    lightgbm_version: str,
    ensemble_diagnostics: pl.DataFrame | None = None,
    adapter_source_hash: str | None = None,
) -> dict[str, Any]:
    score = predictions.get_column("score")
    importance_rows: list[dict[str, str | float]] = []
    importance_features = alpha158_feature_names() if all(importances) else ()
    for index, name in enumerate(importance_features):
        gains = [fold[index][1] for fold in importances]
        splits = [fold[index][2] for fold in importances]
        importance_rows.append(
            {
                "feature": name,
                "mean_gain": float(np.mean(gains)),
                "mean_split_count": float(np.mean(splits)),
            }
        )
    importance_rows.sort(
        key=lambda row: (
            -_finite_float(row["mean_gain"], "mean feature gain"),
            str(row["feature"]),
        )
    )
    signal_analysis = _diagnostic_signal_analysis(request, predictions)
    result: dict[str, Any] = {
        "authority": "qlib_diagnostic_only",
        "versions": {
            "worker": __version__,
            "pyqlib": qlib_version,
            "lightgbm": lightgbm_version,
        },
        "feature_recipe": {
            "name": "Alpha158-style",
            "feature_count": len(alpha158_feature_names()),
            "names": list(alpha158_feature_names()),
            "vwap_source": "causal_typical_price_proxy_not_vendor_vwap",
        },
        "label_recipe": {
            "name": "next_session_open_to_open",
            "definition": "open[target+1] / open[target] - 1",
            "decision": "close_t",
            "entry": "open_t_plus_1",
        },
        "score_distribution": {
            "min": _finite_float(score.min(), "score minimum"),
            "max": _finite_float(score.max(), "score maximum"),
            "mean": _finite_float(score.mean(), "score mean"),
            "std": _finite_float(score.std(ddof=0), "score standard deviation"),
            "q05": _finite_float(score.quantile(0.05, interpolation="linear"), "score q05"),
            "q25": _finite_float(score.quantile(0.25, interpolation="linear"), "score q25"),
            "q50": _finite_float(score.quantile(0.50, interpolation="linear"), "score q50"),
            "q75": _finite_float(score.quantile(0.75, interpolation="linear"), "score q75"),
            "q95": _finite_float(score.quantile(0.95, interpolation="linear"), "score q95"),
        },
        "folds": fold_diagnostics,
        "feature_importance": importance_rows,
        "signal_analysis": signal_analysis,
        "portfolio_replay": {
            "status": "pending_canonical_alpha_engine_replay",
            "reason": (
                "the current canonical BacktestEngine run seam is single-instrument; "
                "portable OOS predictions are ready for the governed multi-asset replay composer"
            ),
            "selection": request.payload["portfolio"],
            "costs": request.payload["costs"],
        },
        "counterfactual_refit": False,
        "label": "OOS prediction contract validated — canonical ALPHA replay pending",
    }
    if request.payload["schema_version"] == 3:
        result["portfolio_replay"]["reason"] = (
            "run alpha ml replay for canonical synchronized multi-asset execution "
            "with declared costs"
        )
        if adapter_source_hash is None:
            raise RuntimeError(
                "schema 3 diagnostics require the captured adapter source fingerprint"
            )
        result.update(
            {
                "model_backend": request.payload["model"]["name"],
                "model_parameters": fold_diagnostics[0]["resolved_parameters"],
                "backend_versions": fold_diagnostics[0]["backend_versions"],
                "upstream_source_hash": fold_diagnostics[0]["upstream_source_hash"],
                "adapter_source_hash": adapter_source_hash,
            }
        )
    if ensemble_diagnostics is not None:
        disagreement = ensemble_diagnostics.get_column("disagreement")
        result["rank_ensemble_v1"] = {
            "recipe": "equal_weight_percentile_rank",
            "weights": {"lightgbm": 0.5, "ridge": 0.5},
            "ridge_alpha": 1.0,
            "members": {
                "lightgbm": _member_signal_summary(
                    request,
                    ensemble_diagnostics,
                    score_column="lightgbm_score",
                    model_hash_column="lightgbm_model_hash",
                ),
                "ridge": _member_signal_summary(
                    request,
                    ensemble_diagnostics,
                    score_column="ridge_score",
                    model_hash_column="ridge_model_hash",
                ),
            },
            "ensemble": {
                "ic_mean": signal_analysis["ic"]["mean"],
                "rank_ic_mean": signal_analysis["ic"]["rank_mean"],
                "costed_total_return": signal_analysis["portfolio"]["costed_total_return"],
                "costed_excess_total_return": signal_analysis["portfolio"][
                    "costed_excess_total_return"
                ],
                "mean_turnover": signal_analysis["portfolio"]["mean_turnover"],
                "periods": signal_analysis["portfolio"]["periods"],
            },
            "disagreement": {
                "mean": _finite_float(disagreement.mean(), "mean ensemble disagreement"),
                "q95": _finite_float(
                    disagreement.quantile(0.95, interpolation="linear"),
                    "ensemble disagreement q95",
                ),
                "max": _finite_float(disagreement.max(), "maximum ensemble disagreement"),
            },
        }
    return result


def _mean_or_none(values: Sequence[float]) -> float | None:
    return float(np.mean(values)) if values else None


def _diagnostic_signal_analysis(
    request: WorkerRequest, predictions: pl.DataFrame
) -> dict[str, Any]:
    """Compute Qlib-style OOS diagnostics without claiming canonical ALPHA authority."""
    frame = predictions.to_pandas().sort_values(
        ["target_ts", "score", "symbol"],
        ascending=[True, False, True],
        kind="mergesort",
    )
    panel = request.panel.to_pandas()
    opens = panel.pivot(index="session_ts", columns="symbol", values="open").sort_index()
    realized = opens.shift(-1) / opens - 1.0
    costs = request.payload["costs"]
    cost_rate = (float(costs["fee_bps"]) + float(costs["slippage_bps"])) / 10_000.0
    previous_weights: dict[str, float] = {}
    gross_equity = 1.0
    costed_equity = 1.0
    benchmark_equity = 1.0
    ic_values: list[float] = []
    rank_ic_values: list[float] = []
    quantile_values: dict[int, list[float]] = {value: [] for value in range(1, 6)}
    timeline: list[dict[str, Any]] = []
    ic_timeline: list[dict[str, Any]] = []
    degenerate_cross_sections = 0
    tied_cross_sections = 0
    quantile_cross_sections = 0
    for target, cross_section in frame.groupby("target_ts", sort=True, observed=True):
        target_timestamp = pd.Timestamp(cast(Any, target))
        if target_timestamp not in realized.index:
            continue
        returns = realized.loc[target_timestamp]
        resolved = cross_section.copy()
        resolved["realized_return"] = [
            returns.get(symbol, float("nan")) for symbol in resolved["symbol"]
        ]
        if not np.isfinite(resolved["realized_return"].to_numpy(dtype="float64")).all():
            continue
        score_values = resolved["score"].to_numpy(dtype="float64")
        return_values = resolved["realized_return"].to_numpy(dtype="float64")
        ic: float | None = None
        rank_ic: float | None = None
        if float(np.std(score_values)) > 0.0 and float(np.std(return_values)) > 0.0:
            ic = float(np.corrcoef(score_values, return_values)[0, 1])
            score_rank = resolved["score"].rank(method="average").to_numpy(dtype="float64")
            return_rank = (
                resolved["realized_return"].rank(method="average").to_numpy(dtype="float64")
            )
            if float(np.std(score_rank)) > 0.0 and float(np.std(return_rank)) > 0.0:
                rank_ic = float(np.corrcoef(score_rank, return_rank)[0, 1])
        if ic is not None and math.isfinite(ic):
            ic_values.append(ic)
        else:
            ic = None
        if rank_ic is not None and math.isfinite(rank_ic):
            rank_ic_values.append(rank_ic)
        else:
            rank_ic = None
        ic_timeline.append(
            {
                "target_ts": target_timestamp.isoformat(),
                "ic": ic,
                "rank_ic": rank_ic,
                "sample_count": len(resolved),
            }
        )

        if request.payload["schema_version"] == 3:
            distinct_scores = resolved["score"].nunique()
            if distinct_scores <= 1:
                degenerate_cross_sections += 1
            if distinct_scores < len(resolved):
                tied_cross_sections += 1
            else:
                quantile_cross_sections += 1
                ascending = resolved.sort_values(
                    ["score", "symbol"], ascending=[True, True], kind="mergesort"
                )
                for position, value in enumerate(ascending["realized_return"]):
                    quantile = min(5, position * 5 // len(ascending) + 1)
                    quantile_values[quantile].append(float(value))

        else:
            ascending = resolved.sort_values(
                ["score", "symbol"], ascending=[True, True], kind="mergesort"
            )
            for position, value in enumerate(ascending["realized_return"]):
                quantile = min(5, position * 5 // len(ascending) + 1)
                quantile_values[quantile].append(float(value))

        if request.payload["schema_version"] == 3:
            continue
        top_count = max(1, math.ceil(len(resolved) * 0.2))
        selected = resolved.head(top_count)
        weight = 1.0 / top_count
        current_weights = {str(symbol): weight for symbol in selected["symbol"]}
        turnover = sum(
            abs(current_weights.get(symbol, 0.0) - previous_weights.get(symbol, 0.0))
            for symbol in set(current_weights) | set(previous_weights)
        )
        previous_weights = current_weights
        gross_return = float(selected["realized_return"].mean())
        costed_return = gross_return - turnover * cost_rate
        benchmark_return = float(resolved["realized_return"].mean())
        gross_equity *= 1.0 + gross_return
        costed_equity *= 1.0 + costed_return
        benchmark_equity *= 1.0 + benchmark_return
        timeline.append(
            {
                "target_ts": target_timestamp.isoformat(),
                "gross_return": gross_return,
                "costed_return": costed_return,
                "benchmark_return": benchmark_return,
                "excess_return": costed_return - benchmark_return,
                "turnover": turnover,
                "gross_equity": gross_equity,
                "costed_equity": costed_equity,
                "benchmark_equity": benchmark_equity,
            }
        )
    turnovers = [float(row["turnover"]) for row in timeline]
    analysis: dict[str, Any] = {
        "authority": "qlib_diagnostic_only",
        "ic": {
            "mean": _mean_or_none(ic_values),
            "rank_mean": _mean_or_none(rank_ic_values),
            "by_target": ic_timeline,
        },
        "quantile_returns": [
            {
                "quantile": quantile,
                "mean_return": _mean_or_none(values),
                "observations": len(values),
            }
            for quantile, values in quantile_values.items()
        ],
        "portfolio": None
        if request.payload["schema_version"] == 3
        else {
            "selection": "long_only_top_quintile_equal_weight",
            "declared_costs": costs,
            "periods": len(timeline),
            "gross_total_return": gross_equity - 1.0,
            "costed_total_return": costed_equity - 1.0,
            "benchmark_total_return": benchmark_equity - 1.0,
            "costed_excess_total_return": costed_equity - benchmark_equity,
            "mean_turnover": _mean_or_none(turnovers),
            "timeline": timeline,
        },
    }

    if request.payload["schema_version"] == 3:
        analysis["quantile_returns"] = [
            row for row in analysis["quantile_returns"] if row["observations"]
        ]
        analysis["diagnostic_state"] = {
            "score_status": "degenerate"
            if degenerate_cross_sections == len(ic_timeline)
            else "ties_present"
            if tied_cross_sections
            else "nondegenerate",
            "reason": "tied score cross-sections are excluded from quantile groups"
            if tied_cross_sections
            else "all cross-sections have distinct scores",
            "degenerate_cross_sections": degenerate_cross_sections,
            "tied_cross_sections": tied_cross_sections,
            "quantile_cross_sections": quantile_cross_sections,
        }
    return analysis


def source_fingerprint() -> str:
    sources = (
        "real.py",
        "features.py",
        "fit_provenance.py",
        "contract.py",
        "tabular.py",
        "tabular_contract.py",
        "tabular_adapters.py",
    )
    return hashlib.sha256(
        canonical_json_bytes({name: sha256_file(Path(__file__).parent / name) for name in sources})
    ).hexdigest()


def _publish(
    path: Path,
    writer: Callable[[Path], object],
    *,
    before_publish: Callable[[], None] | None = None,
) -> None:
    fd, raw_temp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    os.close(fd)
    temp = Path(raw_temp)
    try:
        writer(temp)
        if before_publish is not None:
            before_publish()
        if path.exists():
            if path.stat().st_size == temp.stat().st_size and sha256_file(path) == sha256_file(
                temp
            ):
                return
            raise RuntimeError(f"immutable worker artifact {path.name} already differs")
        try:
            os.link(temp, path)
        except FileExistsError:
            if sha256_file(path) != sha256_file(temp):
                raise RuntimeError(
                    f"immutable worker artifact {path.name} was concurrently published differently"
                ) from None
    finally:
        temp.unlink(missing_ok=True)


def run_real(
    exchange_dir: Path, *, worker_lock_path: Path, _observation: FitInvocation | None = None
) -> dict[str, Any]:
    """Run one exchange; optionally expose its private in-memory component observations."""
    observation = _observation if _observation is not None else FitInvocation()
    observation.start()
    try:
        result = _run_real(exchange_dir, worker_lock_path=worker_lock_path, observation=observation)
    except BaseException as exc:
        observation.failed(exc)
        raise
    observation.complete()
    return result


def _run_real(
    exchange_dir: Path, *, worker_lock_path: Path, observation: FitInvocation
) -> dict[str, Any]:
    """Train one deterministic CPU LightGBM per declared fold and publish portable OOS scores."""
    exchange_dir = Path(exchange_dir)
    result_path = exchange_dir / "result.json"
    if result_path.exists():
        raise RuntimeError("worker result already exists; refusing to overwrite immutable exchange")
    request = validate_request(exchange_dir)
    adapter_hash = source_fingerprint() if request.payload["schema_version"] == 3 else None
    request_hash = value_digest(request.payload)

    def verify_source() -> None:
        if adapter_hash is not None and source_fingerprint() != adapter_hash:
            raise RuntimeError("worker adapter source changed during execution")
        if adapter_hash is not None and (
            sha256_file(exchange_dir / "request.json") != request_hash
            or sha256_file(exchange_dir / "panel.parquet") != request.payload["panel"]["sha256"]
            or sha256_file(worker_lock_path) != request.payload["worker_lock_hash"]
        ):
            raise RuntimeError("worker input identity changed during execution")

    worker_lock_path = Path(worker_lock_path)
    if worker_lock_path.is_symlink() or not worker_lock_path.is_file():
        raise RuntimeError(f"worker lock must be a regular file: {worker_lock_path}")
    actual_lock_hash = sha256_file(worker_lock_path)
    if request.payload["worker_lock_hash"] != actual_lock_hash:
        raise RuntimeError(
            "worker_lock_hash does not match the executing worker lock: "
            f"expected {actual_lock_hash}"
        )
    verify_source()
    qlib_module, lightgbm_module = require_real_dependencies()
    _official_feature_names()
    features = alpha158_features(request.panel)
    samples = _sample_table(request, features)
    prediction_frames: list[pl.DataFrame] = []
    ensemble_frames: list[pl.DataFrame] = []
    fold_diagnostics: list[dict[str, Any]] = []
    provenance_folds: list[dict[str, Any]] = []
    importances: list[list[tuple[str, float, int]]] = []
    for fold in request.folds:
        trace = FitTrace() if adapter_hash is not None else None
        if trace is not None:
            observation.folds[int(fold["fold"])] = trace
        predictions, diagnostic, importance, ensemble_diagnostics = _fold_model(
            request=request,
            samples=samples,
            fold=fold,
            qlib_module=qlib_module,
            lightgbm_module=lightgbm_module,
            fit_trace=trace,
        )
        if adapter_hash is not None:
            provenance_folds.append(diagnostic.pop("_fit_provenance"))
        prediction_frames.append(predictions)
        fold_diagnostics.append(diagnostic)
        importances.append(importance)
        if ensemble_diagnostics is not None:
            ensemble_frames.append(ensemble_diagnostics)
    combined = pl.concat(prediction_frames).sort(
        ["fold", "split", "target_ts", "symbol", "origin_ts"]
    )
    if not combined.get_column("score").is_finite().all():
        raise RuntimeError("real worker produced non-finite OOS scores")
    fit_provenance: dict[str, Any] | None = None
    if adapter_hash is not None:
        fit_provenance = {
            "schema_version": 1,
            "authority": "engineering_provenance_only",
            "request_sha256": request_hash,
            "panel_sha256": request.payload["panel"]["sha256"],
            "worker_source_sha256": adapter_hash,
            "worker_lock_sha256": actual_lock_hash,
            "seed": int(request.payload["seed"]),
            "model": request.payload["model"],
            "folds": provenance_folds,
        }
        fit_provenance["provenance_sha256"] = value_digest(fit_provenance)
    verify_source()
    predictions_path = exchange_dir / "predictions.parquet"
    _publish(predictions_path, combined.write_parquet, before_publish=verify_source)
    combined_ensemble = (
        pl.concat(ensemble_frames).sort(["fold", "split", "target_ts", "symbol", "origin_ts"])
        if ensemble_frames
        else None
    )
    ensemble_path = exchange_dir / "ensemble_diagnostics.parquet"
    if combined_ensemble is not None:
        _publish(ensemble_path, combined_ensemble.write_parquet, before_publish=verify_source)
    diagnostics = _portable_diagnostics(
        request,
        combined,
        fold_diagnostics,
        importances,
        qlib_version=str(getattr(qlib_module, "__version__", "unknown")),
        lightgbm_version=str(getattr(lightgbm_module, "__version__", "unknown")),
        ensemble_diagnostics=combined_ensemble,
        adapter_source_hash=adapter_hash,
    )
    if fit_provenance is not None:
        diagnostics["fit_provenance"] = fit_provenance
    result: dict[str, Any] = {
        "schema_version": request.payload["schema_version"],
        "status": "succeeded",
        "request_sha256": sha256_file(exchange_dir / "request.json"),
        "snapshot_hash": request.payload["snapshot_hash"],
        "config_hash": request.payload["config_hash"],
        "worker_lock_hash": request.payload["worker_lock_hash"],
        "seed": request.payload["seed"],
        "worker": {"kind": "qlib", "implementation_version": __version__},
        "predictions": {
            "path": "predictions.parquet",
            "sha256": sha256_file(predictions_path),
            "rows": combined.height,
        },
        "diagnostics": diagnostics,
        "diagnostic_only": True,
        "counterfactual_refit": False,
    }
    if combined_ensemble is not None:
        result["ensemble_diagnostics"] = {
            "schema": "QlibRankEnsembleDiagnosticsV1",
            "schema_version": 1,
            "path": "ensemble_diagnostics.parquet",
            "sha256": sha256_file(ensemble_path),
            "rows": combined_ensemble.height,
        }
    _publish(
        result_path,
        lambda path: path.write_bytes(canonical_json_bytes(result)),
        before_publish=verify_source,
    )
    return result
