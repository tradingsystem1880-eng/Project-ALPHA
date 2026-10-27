"""Fit pinned Qlib adapters using the shared, already normalized fold dataset."""

from __future__ import annotations

import hashlib
import importlib
import json
import sys
import tempfile
import warnings
from contextlib import nullcontext, redirect_stdout
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

import numpy as np
import pandas as pd

from alpha_qlib_worker.contract import canonical_json_bytes
from alpha_qlib_worker.fit_provenance import FitTrace, observe_call, value_digest
from alpha_qlib_worker.tabular import backend_source_hash, require_backend, resolve_parameters


@dataclass(frozen=True)
class FittedTabular:
    scores: pd.Series
    model_hash: str
    importance: list[tuple[str, float, int]]
    diagnostics: dict[str, Any]


def _bounded_native_scores(
    model: Any,
    test: pd.DataFrame,
    *,
    name: str,
    thread_limit: int,
) -> pd.Series:
    """Bound native prediction and matrix construction, preserving the declared row index."""
    if name == "xgboost":
        xgboost = importlib.import_module("xgboost")
        model.set_param({"nthread": thread_limit, "device": "cpu"})
        values = model.predict(xgboost.DMatrix(test.values, nthread=thread_limit))
    elif name == "catboost":
        values = model.predict(test.values, thread_count=thread_limit, task_type="CPU")
    else:
        raise ValueError(f"unsupported bounded native prediction backend {name!r}")
    values = np.asarray(values)
    if values.ndim != 1 or len(values) != len(test):
        raise RuntimeError(f"Qlib {name} OOS prediction index differs from the declared test fold")
    return pd.Series(values, index=test.index)


def _reload_scores(
    model: Any,
    dataset: Any,
    name: str,
    *,
    thread_limit: int,
) -> np.ndarray[Any, Any]:
    """Roundtrip only state created in this worker; no pickle or external object is accepted."""
    test = dataset.prepare("test", col_set="feature")
    if name == "linear":
        restored = type(model)(estimator=model.estimator, alpha=model.alpha, include_valid=False)
        state = json.loads(
            canonical_json_bytes(
                {
                    "coef": np.asarray(model.coef_).tolist(),
                    "intercept": float(model.intercept_),
                }
            )
        )
        restored.coef_ = np.asarray(state["coef"], dtype="float64")
        restored.intercept_ = state["intercept"]
        with importlib.import_module("threadpoolctl").threadpool_limits(limits=1):
            return np.asarray(restored.predict(dataset, segment="test"), dtype="float64")
    if name in {"lightgbm", "double_ensemble"}:
        lightgbm = importlib.import_module("lightgbm")
        boosters = [model.model] if name == "lightgbm" else model.ensemble
        subsets = [test.columns] if name == "lightgbm" else model.sub_features
        values = np.zeros(len(test), dtype="float64")
        for booster, subset in zip(boosters, subsets, strict=True):
            restored = lightgbm.Booster(
                model_str=booster.model_to_string(num_iteration=booster.best_iteration)
            )
            values += restored.predict(test.loc[:, subset].values, num_threads=thread_limit)
        return values / len(boosters)
    if name == "xgboost":
        xgboost = importlib.import_module("xgboost")
        restored = xgboost.Booster()
        restored.load_model(model.model.save_raw(raw_format="json"))
        return np.asarray(
            _bounded_native_scores(restored, test, name=name, thread_limit=thread_limit),
            dtype="float64",
        )
    catboost = importlib.import_module("catboost")
    with tempfile.TemporaryDirectory(prefix="alpha-model-roundtrip-") as temporary:
        path = Path(temporary) / "model.json"
        model.model.save_model(str(path), format="json")
        restored = catboost.CatBoost()
        restored.load_model(str(path), format="json")
    return np.asarray(
        _bounded_native_scores(restored, test, name=name, thread_limit=thread_limit),
        dtype="float64",
    )


def _linear_state(model: Any) -> dict[str, Any]:
    return {
        "coefficients": np.asarray(model.coef_, dtype="float64").tolist(),
        "intercept": float(model.intercept_),
    }


def _label_column(frame: pd.DataFrame) -> pd.Series:
    labels = cast(pd.DataFrame, frame["label"])
    return labels.iloc[:, 0].rename("label")


def _observed_linear_class(
    base: Any, *, dataset: Any, recorder: FitTrace | None, context: dict[str, Any]
) -> Any:
    if recorder is None:
        return base

    class ObservedLinear(base):  # type: ignore[misc]
        def _observe_native(self, native: Any, x: Any, y: Any, weights: Any) -> Any:
            frame = dataset.prepare("train", col_set=["feature", "label"]).dropna()
            features = pd.DataFrame(
                np.asarray(x), index=frame.index, columns=frame["feature"].columns
            )
            labels = pd.Series(np.asarray(y), index=frame.index, name="label")
            inputs: dict[str, object] = {
                "context": context,
                "train_features": features,
                "train_labels": labels,
                "weights": None if weights is None else np.asarray(weights),
            }

            def fit() -> Any:
                if not np.array_equal(
                    np.asarray(x), frame["feature"].to_numpy(), equal_nan=True
                ) or not np.array_equal(
                    np.asarray(y), _label_column(frame).to_numpy(), equal_nan=True
                ):
                    raise RuntimeError("Qlib linear native inputs differ from consumed train rows")
                return native(x, y, weights)

            return observe_call(
                recorder, "model", "fit", inputs, fit, lambda _: {"state": _linear_state(self)}
            )

        def _fit(self, x: Any, y: Any, weights: Any) -> Any:
            return self._observe_native(super()._fit, x, y, weights)

        def _fit_nnls(self, x: Any, y: Any, weights: Any = None) -> Any:
            return self._observe_native(super()._fit_nnls, x, y, weights)

    return ObservedLinear


def _ordered_double_class(base: Any, *, recorder: FitTrace | None, context: dict[str, Any]) -> Any:
    class OrderedDEnsemble(base):  # type: ignore[misc]
        def train_submodel(self, df_train: Any, df_valid: Any, weights: Any, features: Any) -> Any:
            if recorder is not None:
                self._provenance_training_index = df_train.index.copy()
            native = super().train_submodel
            return observe_call(
                recorder,
                f"member.{len(self.ensemble)}",
                "fit",
                {
                    "context": context,
                    "source_train_features": df_train["feature"],
                    "source_validation_features": df_valid["feature"],
                    "train_features": df_train["feature"].loc[:, features],
                    "train_labels": _label_column(df_train),
                    "validation_features": df_valid["feature"].loc[:, features],
                    "validation_labels": _label_column(df_valid),
                    "weights": weights,
                    "features": pd.Index(features),
                },
                lambda: native(df_train, df_valid, weights, features),
                lambda booster: {
                    "state": booster.model_to_string(num_iteration=booster.best_iteration).encode()
                },
            )

        def sample_reweight(self, loss_curve: Any, loss_values: Any, k_th: Any) -> Any:
            native = super().sample_reweight
            return observe_call(
                recorder,
                f"reweight.{int(k_th)}",
                "reweight",
                {
                    "context": context,
                    "training_row_ids": pd.Index(self._provenance_training_index)
                    if recorder is not None
                    else None,
                    "source_member_state": self.ensemble[-1]
                    .model_to_string(num_iteration=self.ensemble[-1].best_iteration)
                    .encode()
                    if recorder is not None
                    else None,
                    "loss_curve": loss_curve,
                    "loss_values": loss_values,
                    "rule": {
                        "k_th": int(k_th),
                        "alpha1": float(self.alpha1),
                        "alpha2": float(self.alpha2),
                        "bins_sr": int(self.bins_sr),
                        "decay": float(self.decay),
                    },
                },
                lambda: native(loss_curve, loss_values, k_th),
                lambda weights: {"state": weights, "weights": weights},
            )

        def feature_selection(self, df_train: Any, loss_values: Any) -> Any:
            native = super().feature_selection

            def select() -> Any:
                selected = native(df_train, loss_values)
                return df_train["feature"].columns[df_train["feature"].columns.isin(selected)]

            return observe_call(
                recorder,
                f"selection.{len(self.ensemble)}",
                "select",
                {
                    "context": context,
                    "train_features": df_train["feature"],
                    "train_labels": _label_column(df_train),
                    "loss_values": loss_values,
                    "member_state_sha256": {
                        str(index): value_digest(
                            booster.model_to_string(num_iteration=booster.best_iteration).encode()
                        )
                        for index, booster in enumerate(self.ensemble)
                    }
                    if recorder is not None
                    else {},
                    "members": [
                        booster.model_to_string(num_iteration=booster.best_iteration)
                        for booster in self.ensemble
                    ],
                    "member_features": [list(subset) for subset in self.sub_features],
                    "rule": {
                        "bins_fs": int(self.bins_fs),
                        "sample_ratios": [float(value) for value in self.sample_ratios],
                    },
                },
                select,
                lambda selected: {"state": selected, "features": selected},
            )

    return OrderedDEnsemble


def fit_tabular(
    dataset: Any, *, name: str, raw: object, seed: int, recorder: FitTrace | None = None
) -> FittedTabular:
    """No validation/test labels enter fit except declared early-stopping validation."""
    versions = require_backend(name)
    resolved = resolve_parameters(name, raw)
    parameters = dict(resolved)
    observation_context = (
        {
            "backend": name,
            "parameters": resolved,
            "seed": seed,
            "backend_versions": versions,
            "upstream_source_hash": backend_source_hash(name),
        }
        if recorder is not None
        else {}
    )
    train = dataset.prepare("train", col_set="feature")
    features = list(train.columns.get_level_values(-1))
    history: dict[str, Any] = {}
    importance = [(feature, 0.0, 0) for feature in features]
    best_iteration = 0
    fit_count = 1
    iteration_diagnostic: dict[str, Any] = {}
    # Qlib's model package prints optional-dependency messages during import. Keep the worker's
    # command output machine-readable without hiding those messages from stderr.
    native_threads = (
        importlib.import_module("threadpoolctl").threadpool_limits(limits=1)
        if name == "linear"
        else nullcontext()
    )
    with redirect_stdout(sys.stderr), native_threads:
        if name == "linear":
            cls = importlib.import_module("qlib.contrib.model.linear").LinearModel
            cls = _observed_linear_class(
                cls, dataset=dataset, recorder=recorder, context=observation_context
            )
            model = cls(
                estimator=parameters["estimator"],
                alpha=parameters["alpha"],
                fit_intercept=False,
                include_valid=False,
            )
            convergence_warning = importlib.import_module("sklearn.exceptions").ConvergenceWarning
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("error", convergence_warning)
                    model.fit(dataset)
            except convergence_warning as exc:
                raise RuntimeError("Qlib linear fit did not converge") from exc
            coefficients = np.asarray(model.coef_, dtype="float64")
            if not np.isfinite(coefficients).all():
                raise RuntimeError("Qlib linear produced non-finite coefficients")
            payload = canonical_json_bytes(
                {"coefficients": coefficients.tolist(), "intercept": float(model.intercept_)}
            )
            importance = []  # Coefficients are not tree gain/split importance.
        elif name in {"lightgbm", "double_ensemble"}:
            rounds = int(parameters.pop("num_boost_round"))
            early = int(parameters.pop("early_stopping_rounds"))
            fixed = dict(
                device_type="cpu",
                deterministic=True,
                force_col_wise=True,
                seed=seed,
                bagging_seed=seed,
                feature_fraction_seed=seed,
                data_random_seed=seed,
                verbosity=-1,
            )
            if name == "lightgbm":
                cls = importlib.import_module("qlib.contrib.model.gbdt").LGBModel
                model = cls(
                    loss="mse",
                    num_boost_round=rounds,
                    early_stopping_rounds=early,
                    objective="regression",
                    metric="l2",
                    **fixed,
                    **parameters,
                )
                model.fit(dataset, verbose_eval=0, evals_result=history)
                boosters = [model.model]
            else:
                cls = importlib.import_module("qlib.contrib.model.double_ensemble").DEnsembleModel

                OrderedDEnsemble = _ordered_double_class(
                    cls, recorder=recorder, context=observation_context
                )

                fit_count = int(parameters.pop("num_models"))
                model = OrderedDEnsemble(
                    base_model="gbm",
                    loss="mse",
                    num_models=fit_count,
                    epochs=rounds,
                    early_stopping_rounds=early,
                    decay=1.0,
                    enable_sr=True,
                    enable_fs=True,
                    **fixed,
                    **parameters,
                )
                state = np.random.get_state()
                try:
                    np.random.seed(seed)
                    observed_train = (
                        dataset.prepare("train", col_set=["feature", "label"])
                        if recorder is not None
                        else None
                    )
                    observed_valid = (
                        dataset.prepare("valid", col_set=["feature", "label"])
                        if recorder is not None
                        else None
                    )
                    observe_call(
                        recorder,
                        "model",
                        "fit",
                        {
                            "context": observation_context,
                            **(
                                {
                                    "train_features": observed_train["feature"],
                                    "train_labels": _label_column(observed_train),
                                    "validation_features": observed_valid["feature"],
                                    "validation_labels": _label_column(observed_valid),
                                }
                                if observed_train is not None and observed_valid is not None
                                else {}
                            ),
                        },
                        lambda: model.fit(dataset),
                        lambda _: {
                            "state": canonical_json_bytes(
                                {
                                    "boosters": [
                                        booster.model_to_string(
                                            num_iteration=booster.best_iteration
                                        )
                                        for booster in model.ensemble
                                    ],
                                    "features": [list(subset) for subset in model.sub_features],
                                }
                            ),
                            "member_state_sha256": {
                                str(i): value_digest(
                                    booster.model_to_string(
                                        num_iteration=booster.best_iteration
                                    ).encode()
                                )
                                for i, booster in enumerate(model.ensemble)
                            },
                            "member_feature_sha256": {
                                str(i): value_digest(pd.Index(subset))
                                for i, subset in enumerate(model.sub_features)
                            },
                        },
                    )
                finally:
                    np.random.set_state(state)
                boosters = model.ensemble
            if len(boosters) != fit_count or any(booster is None for booster in boosters):
                raise RuntimeError(f"Qlib {name} did not fit its declared boosters")
            payload = canonical_json_bytes(
                {
                    "boosters": [
                        booster.model_to_string(num_iteration=booster.best_iteration)
                        for booster in boosters
                    ],
                    "features": [list(subset) for subset in model.sub_features]
                    if name == "double_ensemble"
                    else [features],
                }
            )
            best_iteration = max(int(booster.best_iteration) for booster in boosters)
            gains = {feature: [0.0, 0.0] for feature in features}
            subsets = model.sub_features if name == "double_ensemble" else [features]
            for booster, subset in zip(boosters, subsets, strict=True):
                for feature, gain, splits in zip(
                    subset,
                    booster.feature_importance(importance_type="gain"),
                    booster.feature_importance(importance_type="split"),
                    strict=True,
                ):
                    gains[feature][0] += float(gain) / fit_count
                    gains[feature][1] += float(splits)
            importance = [
                (feature, gains[feature][0], int(gains[feature][1])) for feature in features
            ]
        elif name == "xgboost":
            cls = importlib.import_module("qlib.contrib.model.xgboost").XGBModel
            rounds = int(parameters.pop("num_boost_round"))
            early = int(parameters.pop("early_stopping_rounds"))
            parameters["nthread"] = parameters.pop("num_threads")
            model = cls(
                objective="reg:squarederror",
                eval_metric="rmse",
                tree_method="hist",
                device="cpu",
                seed=seed,
                **parameters,
            )
            model.fit(
                dataset,
                num_boost_round=rounds,
                early_stopping_rounds=early,
                verbose_eval=False,
                evals_result=history,
            )
            native_best = int(model.model.best_iteration)
            trained_rounds = int(model.model.num_boosted_rounds())
            # Qlib 0.9.7 predicts every fitted tree. Materialize the validation-selected state
            # once so prediction, hashing, importance and native reload all use identical trees.
            model.model = model.model[: native_best + 1]
            best_iteration = int(model.model.num_boosted_rounds())
            if best_iteration != native_best + 1:
                raise RuntimeError("XGBoost did not retain the selected validation rounds")
            if json.loads(model.model.save_config())["learner"]["generic_param"]["device"] != "cpu":
                raise RuntimeError("XGBoost did not fit the required CPU model")
            payload = bytes(model.model.save_raw(raw_format="json"))
            iteration_diagnostic = {
                "iteration_policy": "validation_selected_round_count",
                "native_best_iteration_index": native_best,
                "selected_tree_count": best_iteration,
                "trained_round_count": trained_rounds,
                "device_type": "cpu",
            }
            gains = model.model.get_score(importance_type="gain")
            splits = model.model.get_score(importance_type="weight")
            importance = [
                (feature, float(gains.get(f"f{index}", 0.0)), int(splits.get(f"f{index}", 0)))
                for index, feature in enumerate(features)
            ]
        elif name == "catboost":
            module = importlib.import_module("qlib.contrib.model.catboost_model")
            rounds = int(parameters.pop("num_boost_round"))
            early = int(parameters.pop("early_stopping_rounds"))
            parameters["thread_count"] = parameters.pop("num_threads")
            model = module.CatBoostModel(
                loss="RMSE", random_seed=seed, allow_writing_files=False, **parameters
            )
            # Qlib0.9.7 unconditionally chooses GPU from this function inside fit; its constructor
            # task_type is overwritten. Override only that probe for this isolated CPU-only fit.
            with patch.object(module, "get_gpu_device_count", return_value=0):
                model.fit(
                    dataset, num_boost_round=rounds, early_stopping_rounds=early, verbose_eval=False
                )
            with tempfile.TemporaryDirectory(prefix="alpha-catboost-") as temporary:
                path = Path(temporary) / "model.json"
                model.model.save_model(str(path), format="json")
                content = json.loads(path.read_text())
            content.pop("model_info", None)  # Includes wall clock timing and a random model GUID.
            payload = canonical_json_bytes(content)
            native_best = int(model.model.get_best_iteration())
            best_iteration = int(model.model.tree_count_)
            if best_iteration != native_best + 1:
                raise RuntimeError("CatBoost did not retain the selected validation rounds")
            if model.model.get_all_params()["task_type"] != "CPU":
                raise RuntimeError("CatBoost did not fit the required CPU model")
            history = model.model.get_evals_result()
            importance = []  # PredictionValuesChange is not tree gain/split importance.
            iteration_diagnostic = {
                "iteration_policy": "validation_selected_round_count",
                "native_best_iteration_index": native_best,
                "selected_tree_count": best_iteration,
                "trained_round_count": max(
                    len(values) for metrics in history.values() for values in metrics.values()
                ),
                "device_type": "cpu",
            }
        else:
            raise ValueError(f"unsupported tabular backend {name!r}")
        thread_limit = 1 if name == "linear" else int(resolved["num_threads"])
        scores = (
            _bounded_native_scores(
                model.model,
                dataset.prepare("test", col_set="feature"),
                name=name,
                thread_limit=thread_limit,
            )
            if name in {"catboost", "xgboost"}
            else model.predict(dataset, segment="test")
        )
    if not isinstance(scores, pd.Series) or not np.isfinite(scores.to_numpy(dtype="float64")).all():
        raise RuntimeError(f"Qlib {name} produced missing or non-finite OOS scores")
    expected = dataset.prepare("test", col_set="feature").index
    if not scores.index.equals(expected):
        raise RuntimeError(f"Qlib {name} OOS prediction index differs from the declared test fold")
    restored_scores = _reload_scores(model, dataset, name, thread_limit=thread_limit)
    if not np.allclose(scores.to_numpy(dtype="float64"), restored_scores, rtol=1e-12, atol=1e-12):
        raise RuntimeError(f"Qlib {name} state reload changed OOS predictions")
    if any(not np.isfinite(gain) for _, gain, _ in importance):
        raise RuntimeError(f"Qlib {name} produced non-finite feature importance")
    history = {
        split: metrics if isinstance(metrics, dict) else {"loss": metrics}
        for split, metrics in history.items()
    }
    model_hash = hashlib.sha256(
        canonical_json_bytes({"backend": name, "parameters": resolved, "seed": seed}) + payload
    ).hexdigest()
    return FittedTabular(
        scores,
        model_hash,
        importance,
        {
            "model_backend": name,
            "resolved_parameters": resolved,
            "backend_versions": versions,
            "native_thread_limit": 1 if name == "linear" else int(resolved["num_threads"]),
            "upstream_source_hash": backend_source_hash(name),
            "fit_count": fit_count,
            "best_iteration": best_iteration,
            "training_history": history,
            "importance_kind": "not_available"
            if name in {"linear", "catboost"}
            else "backend_feature_importance",
            **iteration_diagnostic,
            "state_roundtrip": {
                "status": "verified",
                "format": "native_json_or_model_text",
                "rtol": 1e-12,
                "atol": 1e-12,
            },
            "persistent_model_reuse": "unsupported_ephemeral_worker",
        },
    )
