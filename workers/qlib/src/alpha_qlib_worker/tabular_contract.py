"""Bounded numeric schema-three recipes; mirrored at the independent root boundary."""

from __future__ import annotations

import math

LIGHTGBM_RULES: dict[str, tuple[float, float, bool]] = {
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
TABULAR_PARAMETER_RULES: dict[str, dict[str, tuple[float, float, bool]]] = {
    "lightgbm": LIGHTGBM_RULES,
    "linear": {"alpha": (0.0, 1_000_000.0, False)},
    "catboost": {
        "num_boost_round": (1.0, 5000.0, True),
        "early_stopping_rounds": (1.0, 1000.0, True),
        "depth": (1.0, 10.0, True),
        "learning_rate": (0.0001, 1.0, False),
        "l2_leaf_reg": (0.0, 1_000_000.0, False),
        "num_threads": (1.0, 8.0, True),
    },
    "xgboost": {
        "num_boost_round": (1.0, 5000.0, True),
        "early_stopping_rounds": (1.0, 1000.0, True),
        "max_depth": (1.0, 16.0, True),
        "learning_rate": (0.0001, 1.0, False),
        "subsample": (0.01, 1.0, False),
        "colsample_bytree": (0.01, 1.0, False),
        "reg_alpha": (0.0, 1_000_000.0, False),
        "reg_lambda": (0.0, 1_000_000.0, False),
        "num_threads": (1.0, 8.0, True),
    },
    "double_ensemble": {**LIGHTGBM_RULES, "num_models": (2.0, 6.0, True)},
}


def validate_parameters(name: str, raw: object) -> dict[str, int | float | str]:
    if (
        not isinstance(name, str)
        or name not in TABULAR_PARAMETER_RULES
        or not isinstance(raw, dict)
    ):
        raise ValueError("unsupported tabular model recipe")
    rules = TABULAR_PARAMETER_RULES[name]
    allowed = set(rules) | ({"estimator"} if name == "linear" else set())
    unknown = sorted(set(raw) - allowed)
    if unknown:
        raise ValueError(f"unsupported {name} parameters: {unknown}")
    result: dict[str, int | float | str] = {}
    if name == "linear":
        estimator = raw.get("estimator", "ridge")
        if not isinstance(estimator, str) or estimator not in {"ols", "ridge", "lasso", "nnls"}:
            raise ValueError("linear estimator must be ols, ridge, lasso or nnls")
        if estimator in {"ols", "nnls"} and raw.get("alpha", 0) != 0:
            raise ValueError("linear alpha is only supported for ridge or lasso")
        result["estimator"] = estimator
    for key, value in raw.items():
        if key == "estimator":
            continue
        minimum, maximum, integer = rules[key]
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise ValueError(f"model.parameters.{key} must be a finite number")
        if not math.isfinite(value) or not minimum <= value <= maximum:
            raise ValueError(f"model.parameters.{key} must be between {minimum} and {maximum}")
        if integer and not float(value).is_integer():
            raise ValueError(f"model.parameters.{key} must be an integer")
        result[key] = int(value) if integer else float(value)
    return result
