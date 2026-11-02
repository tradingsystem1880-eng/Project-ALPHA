"""Inert W09 metadata contracts; no registration, records, fits or authority.

The finite graph describes existing v1/v2 computations. Its parser bounds and
operation counts are not approved resource units, variants or independent trials.
"""

from __future__ import annotations

import hashlib
import os
import stat
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal, TypedDict

from alpha_cli.ml_contract import MLContractError, canonical_json_bytes
from alpha_cli.ml_refit import _file_snapshot

_PACKAGE = "src/alpha_qlib_worker"
_REQUIRED = frozenset(
    {"pyproject.toml", "uv.lock"}
    | {
        f"{_PACKAGE}/{name}"
        for name in (
            "__init__.py",
            "__main__.py",
            "real.py",
            "contract.py",
            "features.py",
            "rank_ensemble.py",
            "schemas/request.schema.json",
            "schemas/request-v2.schema.json",
            "schemas/result.schema.json",
            "schemas/result-v2.schema.json",
            "schemas/panel.parquet.schema.json",
            "schemas/predictions.parquet.schema.json",
            "schemas/ensemble-diagnostics.parquet.schema.json",
        )
    }
)
# Shape/read bounds only, never an execution or fit allowance.
_MAX_FOLDS = 64
_MAX_FILES = 256
_MAX_FILE_BYTES = 4 * 1024 * 1024


def _hash(value: object) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _require_hash(value: object) -> None:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(c not in "0123456789abcdef" for c in value)
    ):
        raise MLContractError("W09 references require lowercase SHA-256 identities")


def _require_uuid(value: object) -> None:
    try:
        valid = isinstance(value, str) and str(uuid.UUID(value)) == value
    except ValueError:
        valid = False
    if not valid:
        raise MLContractError("W09 record references require canonical UUIDs")


@dataclass(frozen=True)
class W09ProtocolV1:
    """Declared existing-record/input references, not verified records or admission."""

    project_id: str
    experiment_id: str
    contract_id: str
    request_schema_version: int
    recipe: str
    request_sha256: str
    panel_sha256: str
    snapshot_sha256: str
    dependency_sha256: str
    folds: tuple[int, ...]

    def __post_init__(self) -> None:
        _require_uuid(self.project_id)
        _require_uuid(self.experiment_id)
        if not isinstance(self.contract_id, str) or not self.contract_id.startswith("rc_"):
            raise MLContractError("W09 contract reference requires an rc_ identity")
        _require_hash(self.contract_id[3:])
        for value in (
            self.request_sha256,
            self.panel_sha256,
            self.snapshot_sha256,
            self.dependency_sha256,
        ):
            _require_hash(value)
        if (
            type(self.request_schema_version) is not int
            or not isinstance(self.recipe, str)
            or (
                self.request_schema_version,
                self.recipe,
            )
            not in {(1, "lightgbm"), (2, "rank_ensemble_v1")}
        ):
            raise MLContractError("W09 supports only exact v1 LightGBM and v2 fixed rank recipes")
        if (
            type(self.folds) is not tuple
            or not 1 <= len(self.folds) <= _MAX_FOLDS
            or any(type(fold) is not int for fold in self.folds)
            or self.folds != tuple(range(len(self.folds)))
        ):
            raise MLContractError("W09 folds must be finite, contiguous integer metadata from zero")

    @property
    def protocol_id(self) -> str:
        return _hash({"schema": "W09PlanningProtocolV1", **asdict(self)})


@dataclass(frozen=True)
class W09ComponentV1:
    component_id: str
    fold: int
    name: str
    operation: str
    parents: tuple[str, ...]


def _components(protocol: W09ProtocolV1) -> tuple[W09ComponentV1, ...]:
    if type(protocol) is not W09ProtocolV1:
        raise MLContractError("W09 manifest requires its typed planning protocol")
    protocol.__post_init__()
    steps: tuple[tuple[str, str, tuple[str, ...]], ...] = (
        ("normalizer", "fit", ()),
        ("label.train", "transform", ()),
        ("label.validation", "transform", ()),
        ("lightgbm", "fit", ("normalizer", "label.train", "label.validation")),
    )
    if protocol.request_schema_version == 2:
        steps += (
            ("ridge", "fit", ("normalizer", "label.train")),
            ("rank_ensemble", "assemble", ("lightgbm", "ridge")),
        )
    nodes: list[W09ComponentV1] = []
    protocol_id = protocol.protocol_id
    for fold in protocol.folds:
        ids: dict[str, str] = {}

        for name, operation, parents in steps:
            identifier = _hash({"protocol": protocol_id, "fold": fold, "component": name})
            nodes.append(
                W09ComponentV1(identifier, fold, name, operation, tuple(ids[p] for p in parents))
            )
            ids[name] = identifier

    return tuple(nodes)


@dataclass(frozen=True)
class W09ManifestV1:
    protocol: W09ProtocolV1
    components: tuple[W09ComponentV1, ...]

    @property
    def manifest_id(self) -> str:
        validate_manifest(self)
        return _hash(
            {
                "schema": "W09ComponentManifestV1",
                "protocol_id": self.protocol.protocol_id,
                "components": [asdict(node) for node in self.components],
            }
        )


def build_manifest(protocol: W09ProtocolV1) -> W09ManifestV1:
    return W09ManifestV1(protocol, _components(protocol))


def validate_manifest(manifest: W09ManifestV1) -> None:
    """Require the exact closed recipe DAG, not an executable user-supplied graph."""
    if (
        type(manifest) is not W09ManifestV1
        or type(manifest.components) is not tuple
        or any(
            type(node) is not W09ComponentV1
            or type(node.fold) is not int
            or type(node.parents) is not tuple
            for node in manifest.components
        )
        or manifest.components != _components(manifest.protocol)
    ):
        raise MLContractError("W09 manifest differs from its exact finite recipe DAG")


@dataclass(frozen=True)
class WorkerFingerprintV1:
    files: tuple[tuple[str, str], ...]

    @property
    def sha256(self) -> str:
        return _hash({"schema": "W09WorkerDependenciesV1", "files": dict(self.files)})


def _inventory(project: Path) -> dict[str, Path]:
    """Only first-party worker package/project/lock; no tests, panels or results."""
    if project != project.resolve(strict=True):
        raise MLContractError("W09 dependency roots must not follow symlinks")
    files = {name: project / name for name in ("pyproject.toml", "uv.lock")}

    def visit(directory: Path, depth: int = 0) -> None:
        if depth > 16:
            raise MLContractError("W09 dependency directory depth exceeds its read bound")
        if not stat.S_ISDIR(directory.lstat().st_mode):
            raise MLContractError("W09 dependency directories must not follow symlinks")
        for entry in sorted(directory.iterdir()):
            if entry.name == "__pycache__":
                continue
            if entry.name in {"tests", "holdout", "evaluation", "evaluations"}:
                raise MLContractError("W09 inventory cannot inspect protected/evaluation paths")
            mode = entry.lstat().st_mode
            if stat.S_ISDIR(mode):
                visit(entry, depth + 1)
            elif stat.S_ISREG(mode):
                if not (
                    entry.suffix == ".py"
                    or entry.name == "py.typed"
                    or (entry.parent == project / _PACKAGE / "schemas" and entry.suffix == ".json")
                ):
                    raise MLContractError("W09 dependency package contains an unsupported resource")
                files[entry.relative_to(project).as_posix()] = entry
            else:
                raise MLContractError("W09 dependencies must be regular files/directories")
            if len(files) > _MAX_FILES:
                raise MLContractError("W09 dependency inventory exceeds its read bound")

    source = project / "src"
    if not stat.S_ISDIR(source.lstat().st_mode):
        raise MLContractError("W09 dependency source directory must not follow symlinks")
    visit(source / "alpha_qlib_worker")
    if _REQUIRED - files.keys():
        raise MLContractError("W09 dependency inventory is incomplete")
    for path in files.values():
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_size > _MAX_FILE_BYTES:
            raise MLContractError("W09 dependency is linked, special or exceeds its read bound")
    return dict(sorted(files.items()))


def fingerprint_worker(project: Path) -> WorkerFingerprintV1:
    """Bind the complete first-party package (including new files), schemas and lock.

    This does not import packages or qualify installed dependencies, binaries or runtime.
    """
    project = Path(os.path.abspath(project))
    try:
        paths = _inventory(project)
        before = {
            name: _file_snapshot(path, max_bytes=_MAX_FILE_BYTES) for name, path in paths.items()
        }
        if paths != _inventory(project) or before != {
            name: _file_snapshot(path, max_bytes=_MAX_FILE_BYTES) for name, path in paths.items()
        }:
            raise MLContractError("W09 dependencies changed during fingerprinting")
    except OSError as exc:
        raise MLContractError("W09 dependencies are unavailable") from exc
    return WorkerFingerprintV1(tuple((name, snapshot[0]) for name, snapshot in before.items()))


class W09Readiness(TypedDict):
    schema: str
    authority: Literal["none"]
    status: Literal["BLOCKED"]
    protocol_id: str
    manifest_id: str
    source_status: Literal["MATCHED", "CHANGED", "UNAVAILABLE"]
    current_dependency_sha256: str | None
    planned_operations: dict[str, int]
    observed_operations: None
    fitted_state_verified: Literal[False]
    approved_resource_units: None
    execution_authorized: Literal[False]
    reuse_authorized: Literal[False]
    counterfactual_refit: Literal[False]
    promotion_eligible: Literal[False]
    blockers: list[str]


def readiness(manifest: W09ManifestV1, worker_project: Path) -> W09Readiness:
    """Report structural/source facts without accepting caller claims of readiness."""
    validate_manifest(manifest)
    blockers = [
        "NATIVE_PROTOCOL_UNREGISTERED",
        "FIT_UNIT_POLICY_UNVERIFIED",
        "CHARGE_RESERVE_RELEASE_POLICY_UNVERIFIED",
        "ANCESTRY_REUSE_POLICY_UNVERIFIED",
        "PROTECTED_RELEASE_POLICY_UNVERIFIED",
        "RECORD_AND_INPUT_REFERENCES_UNVERIFIED",
        "PANEL_QUALIFICATION_UNVERIFIED",
        "NATIVE_RUNTIME_QUALIFICATION_UNVERIFIED",
        "PARITY_UNVERIFIED",
    ]
    current: str | None = None
    source_status: Literal["MATCHED", "CHANGED", "UNAVAILABLE"] = "UNAVAILABLE"
    try:
        current = fingerprint_worker(worker_project).sha256
    except MLContractError:
        blockers.append("DEPENDENCY_UNAVAILABLE")
    else:
        source_status = "MATCHED" if current == manifest.protocol.dependency_sha256 else "CHANGED"
        if source_status == "CHANGED":
            blockers.append("DEPENDENCY_CHANGED")
    return {
        "schema": "W09PlanningReadinessV1",
        "authority": "none",
        "status": "BLOCKED",
        "protocol_id": manifest.protocol.protocol_id,
        "manifest_id": manifest.manifest_id,
        "source_status": source_status,
        "current_dependency_sha256": current,
        "planned_operations": {
            operation: sum(node.operation == operation for node in manifest.components)
            for operation in ("fit", "transform", "assemble")
        },
        "observed_operations": None,
        "fitted_state_verified": False,
        "approved_resource_units": None,
        "execution_authorized": False,
        "reuse_authorized": False,
        "counterfactual_refit": False,
        "promotion_eligible": False,
        "blockers": blockers,
    }
