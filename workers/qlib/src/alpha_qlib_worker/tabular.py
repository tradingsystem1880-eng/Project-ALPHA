"""CPU-only adapters for the Qlib 0.9.7 tabular models.

Primary API source: microsoft/qlib, revision da920b7f954f48ab1bb64117c976710de198373e,
qlib/contrib/model/{linear,catboost_model,xgboost,double_ensemble}.py.
"""

from __future__ import annotations

import hashlib
import importlib
import importlib.metadata
import importlib.util
import platform
from pathlib import Path
from typing import Any

from alpha_qlib_worker.tabular_contract import TABULAR_PARAMETER_RULES, validate_parameters

_DEFAULTS: dict[str, dict[str, int | float | str]] = {
    "lightgbm": {
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
    },
    "linear": {"alpha": 1.0},
    "catboost": {
        "num_boost_round": 300,
        "early_stopping_rounds": 20,
        "depth": 6,
        "learning_rate": 0.05,
        "l2_leaf_reg": 3.0,
        "num_threads": 1,
    },
    "xgboost": {
        "num_boost_round": 300,
        "early_stopping_rounds": 20,
        "max_depth": 6,
        "learning_rate": 0.05,
        "subsample": 1.0,
        "colsample_bytree": 1.0,
        "reg_alpha": 0.0,
        "reg_lambda": 1.0,
        "num_threads": 1,
    },
}
_DEFAULTS["double_ensemble"] = {**_DEFAULTS["lightgbm"], "num_models": 3, "num_boost_round": 30}
_MODULES = {
    "lightgbm": ("lightgbm", "qlib.contrib.model.gbdt"),
    "linear": ("sklearn", "qlib.contrib.model.linear"),
    "catboost": ("catboost", "qlib.contrib.model.catboost_model"),
    "xgboost": ("xgboost", "qlib.contrib.model.xgboost"),
    "double_ensemble": ("lightgbm", "qlib.contrib.model.double_ensemble"),
}

_LOCKED_VERSIONS = {
    "pyqlib": "0.9.7",
    "lightgbm": "4.6.0",
    "scikit-learn": "1.9.0",
    "catboost": "1.2.10",
    "xgboost": "3.4.1",
    "xgboost-cpu": "3.4.1",
}


def _backend_distribution(name: str) -> str:
    if name not in {"catboost", "xgboost"}:
        return "scikit-learn" if name == "linear" else _MODULES[name][0]
    system, machine = platform.system(), platform.machine().lower()
    supported = (
        (system == "Darwin" and machine in {"arm64", "x86_64"})
        or (system == "Linux" and machine in {"aarch64", "x86_64"})
        or (system == "Windows" and machine in {"amd64", "x86_64"})
        or (name == "xgboost" and system == "Windows" and machine == "arm64")
    )
    if not supported:
        raise ValueError(f"unsupported wheel platform for {name}: {system}/{machine}")
    if name == "catboost":
        return "catboost"
    return "xgboost" if system == "Darwin" else "xgboost-cpu"


def _check_xgboost_distribution(expected: str) -> None:
    installed = []
    for distribution in ("xgboost", "xgboost-cpu"):
        try:
            importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError:
            continue
        installed.append(distribution)
    if len(installed) > 1:
        raise ValueError("ambiguous xgboost distributions: xgboost and xgboost-cpu coexist")
    if installed and installed != [expected]:
        raise ValueError(f"this platform requires {expected}; found {installed[0]}")


def resolve_parameters(name: str, raw: object) -> dict[str, int | float | str]:
    validated = validate_parameters(name, raw)
    result = {**_DEFAULTS.get(name, {}), **validated}
    if name == "linear":
        if validated["estimator"] in {"ols", "nnls"}:
            result["alpha"] = 0.0
        elif validated["estimator"] == "lasso" and "alpha" not in validated:
            result["alpha"] = 0.01
    return result


def backend_capabilities() -> dict[str, Any]:
    """Inspect installed distributions/importability only; never install or contact a provider."""
    rows: list[dict[str, Any]] = []
    for name in TABULAR_PARAMETER_RULES:
        versions: dict[str, str] = {}
        reason: str | None = None
        status = "available"
        dependency, _ = _MODULES[name]
        try:
            distribution = _backend_distribution(name)
            if name == "xgboost":
                _check_xgboost_distribution(distribution)
            distributions = ("pyqlib", distribution)
            for distribution in distributions:
                versions[distribution] = importlib.metadata.version(distribution)
            mismatches = [
                distribution
                for distribution, version in versions.items()
                if _LOCKED_VERSIONS.get(distribution) != version
            ]
            if mismatches:
                status = "incompatible_dependency"
                reason = f"requires approved locked versions; unqualified: {', '.join(mismatches)}"
            elif importlib.util.find_spec(dependency) is None:
                status, reason = (
                    "missing_dependency",
                    f"missing importable dependency: {dependency}",
                )
            else:
                importlib.import_module(dependency)
        except importlib.metadata.PackageNotFoundError as exc:
            status, reason = "missing_dependency", f"missing installed dependency: {exc.name}"
        except (ImportError, OSError, AttributeError, ValueError) as exc:
            status, reason = "incompatible_dependency", f"{dependency} import failed: {exc}"
        rows.append({"name": name, "status": status, "reason": reason, "versions": versions})
    qlib_version = next(
        (row["versions"].get("pyqlib") for row in rows if "pyqlib" in row["versions"]), None
    )
    return {"schema_version": 1, "qlib_version": qlib_version, "backends": rows}


def require_backend(name: str) -> dict[str, str]:
    for row in backend_capabilities()["backends"]:
        if row["name"] == name:
            if row["status"] != "available":
                raise RuntimeError(f"{name} unavailable: {row['reason']}; no fallback is permitted")
            versions: dict[str, str] = row["versions"]
            return versions
    raise ValueError(f"unsupported tabular model {name!r}")


def backend_source_hash(name: str) -> str:
    """Bind the actual installed Qlib implementation bytes, independently of a version label."""
    module = importlib.import_module(_MODULES[name][1])
    if module.__file__ is None:
        raise RuntimeError(f"{name} Qlib implementation has no inspectable source")
    return hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()
