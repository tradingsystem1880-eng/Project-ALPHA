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
from typing import Any, Literal, TypedDict

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
        # Keep already-issued inert UUID plans stable; durable associations require
        # the actual ControlStore content identity and project membership.
        if isinstance(self.experiment_id, str) and self.experiment_id.startswith("ex_"):
            _require_hash(self.experiment_id[3:])
        else:
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


def bind_worker_observations(
    manifest: W09ManifestV1, snapshot: dict[str, Any], *, worker_project: Path
) -> dict[str, object]:
    """Join untrusted local diagnostics to planned IDs, never to completed accounting.

    Current first-party files can be compared with the declared dependency identity.
    This does not attest the source/binaries used by a past invocation, authenticate
    records, verify fitted state, or turn a copied/forged trace into execution proof.
    """
    validate_manifest(manifest)
    protocol = manifest.protocol
    fingerprint = fingerprint_worker(worker_project)
    if fingerprint.sha256 != protocol.dependency_sha256:
        raise MLContractError("W09 current dependencies differ from the declared identity")
    bindings = _completed_bindings(manifest, snapshot, dict(fingerprint.files)["uv.lock"])
    return {
        "status": "STRUCTURALLY_BOUND",
        "authority": "engineering_observation_only",
        "protocol_id": protocol.protocol_id,
        "manifest_id": manifest.manifest_id,
        "component_bindings": bindings,
        "current_dependency_sha256": fingerprint.sha256,
        "runtime_dependency_identity": "UNVERIFIED",
        "fitted_state_verified": False,
        "durable_accounting_verified": False,
        "execution_allowed": False,
        "reuse_allowed": False,
        "approved_resource_units": None,
        "independent_trials": None,
        "promotion_allowed": False,
    }


def _completed_bindings(
    manifest: W09ManifestV1, snapshot: dict[str, Any], worker_lock_sha256: str
) -> list[dict[str, Any]]:
    """Pure completed-graph checks for current writes and historical diagnostic reads."""
    validate_manifest(manifest)
    protocol = manifest.protocol
    context = {
        "request_schema_version": protocol.request_schema_version,
        "recipe": protocol.recipe,
        "request_sha256": protocol.request_sha256,
        "panel_sha256": protocol.panel_sha256,
        "snapshot_sha256": protocol.snapshot_sha256,
        "worker_lock_sha256": worker_lock_sha256,
    }
    bindings = []
    try:
        if (
            set(snapshot) != {"authority", "status", "error_type", "context", "folds"}
            or type(snapshot["context"]["request_schema_version"]) is not int
            or type(snapshot["folds"]) is not dict
            or snapshot["authority"] != "invocation_local_observation_only"
            or snapshot["status"] != "completed"
            or snapshot["error_type"] is not None
            or snapshot["context"] != context
            or set(snapshot["folds"]) != {str(fold) for fold in protocol.folds}
        ):
            raise MLContractError("W09 invocation context or completion differs")
        for fold in protocol.folds:
            nodes = [node for node in manifest.components if node.fold == fold]
            expected = [
                (node.name, operation)
                for node in nodes
                for operation in (node.operation, "predict")
                if operation != "predict" or node.name in {"lightgbm", "ridge"}
            ]
            sealed = snapshot["folds"][str(fold)]
            events = sealed["events"]
            if (
                set(sealed) != {"events", "trace_sha256"}
                or not isinstance(events, list)
                or len(events) != len(expected)
                or sealed["trace_sha256"] != _hash(events)
            ):
                raise MLContractError("W09 observation graph or trace identity differs")
            by_call = {}
            for index, (event, call) in enumerate(zip(events, expected, strict=True)):
                if set(event) != {
                    "sequence",
                    "component",
                    "operation",
                    "status",
                    "error_type",
                    "input_hashes",
                    "input_row_counts",
                    "input_row_ids_sha256",
                    "output_hashes",
                    "state_sha256",
                } or any(
                    type(event[key]) is not dict
                    for key in (
                        "input_hashes",
                        "input_row_counts",
                        "input_row_ids_sha256",
                        "output_hashes",
                    )
                ):
                    raise MLContractError("Unsupported W09 observation fields")
                outputs = event["output_hashes"]
                if call[0] == "normalizer":
                    output_fields = {
                        "state",
                        "train_features",
                        "other_0_features",
                        "other_1_features",
                    }
                elif call[0].startswith("label."):
                    output_fields = {"state", "normalized_labels"}
                elif call[1] == "fit":
                    output_fields = {"state"}
                elif call[1] == "predict":
                    output_fields = {"scores"}
                else:
                    output_fields = {"predictions", "diagnostics"}
                if (
                    type(event["sequence"]) is not int
                    or event["sequence"] != index
                    or (event["component"], event["operation"]) != call
                    or event["status"] != "completed"
                    or event["error_type"] is not None
                    or set(outputs) != output_fields
                    or event["state_sha256"] != outputs.get("state", _hash(outputs))
                ):
                    raise MLContractError("W09 observation sequence or state differs")
                for digest in [*event["input_hashes"].values(), *outputs.values()]:
                    _require_hash(digest)
                rows = event["input_row_ids_sha256"]
                counts = event["input_row_counts"]
                if set(rows) != set(counts) or not set(rows) <= set(event["input_hashes"]):
                    raise MLContractError("W09 observation row metadata differs")
                for key, digest in rows.items():
                    _require_hash(digest)
                    if type(counts[key]) is not int or counts[key] <= 0:
                        raise MLContractError(
                            "W09 observation row counts must be positive integers"
                        )
                if event["component"] in {"lightgbm", "ridge", "rank_ensemble"} and (
                    event["input_hashes"].get("context")
                    != _hash({"request_sha256": protocol.request_sha256, "fold": fold})
                ):
                    raise MLContractError("W09 observation is bound to another request/fold")
                by_call[call] = event
            for model in ["lightgbm", *(["ridge"] if protocol.request_schema_version == 2 else [])]:
                fitted = by_call[model, "fit"]
                predicted = by_call[model, "predict"]
                links = [
                    (by_call["normalizer", "fit"], "train_features", fitted, "train_features"),
                    (
                        by_call["label.train", "transform"],
                        "normalized_labels",
                        fitted,
                        "train_labels",
                    ),
                    (by_call["normalizer", "fit"], "other_1_features", predicted, "test_features"),
                ]
                if model == "lightgbm":
                    links += [
                        (
                            by_call["normalizer", "fit"],
                            "other_0_features",
                            fitted,
                            "validation_features",
                        ),
                        (
                            by_call["label.validation", "transform"],
                            "normalized_labels",
                            fitted,
                            "validation_labels",
                        ),
                    ]
                elif any(key.startswith("validation_") for key in fitted["input_hashes"]):
                    raise MLContractError("W09 ridge observation consumed validation inputs")
                train = by_call["normalizer", "fit"]
                aligned = [
                    (by_call["label.train", "transform"], "labels"),
                    (fitted, "train_features"),
                    (fitted, "train_labels"),
                ]
                for consumer, input_name in aligned:
                    for field in ("input_row_counts", "input_row_ids_sha256"):
                        if train[field].get("train") is None or train[field].get(
                            "train"
                        ) != consumer[field].get(input_name):
                            raise MLContractError("W09 fitted training rows are unlinked")
                if model == "lightgbm":
                    valid = by_call["label.validation", "transform"]
                    for field in ("input_row_counts", "input_row_ids_sha256"):
                        for input_name in ("validation_features", "validation_labels"):
                            if valid[field].get("labels") is None or valid[field].get(
                                "labels"
                            ) != fitted[field].get(input_name):
                                raise MLContractError("W09 fitted validation rows are unlinked")
                if predicted["input_hashes"].get("model_state") != fitted["state_sha256"]:
                    raise MLContractError("W09 prediction state is unlinked from its fit")
                for producer, output, consumer, input_name in links:
                    produced = producer["output_hashes"].get(output)
                    if produced is None or produced != consumer["input_hashes"].get(input_name):
                        raise MLContractError("W09 preprocessing/model observations are unlinked")
                if protocol.request_schema_version == 2:
                    assembled = by_call["rank_ensemble", "assemble"]
                    if (
                        assembled["input_hashes"].get(f"{model}_state") != fitted["state_sha256"]
                        or assembled["input_hashes"].get(f"{model}_scores")
                        != predicted["output_hashes"]["scores"]
                    ):
                        raise MLContractError("W09 fixed assembly is unlinked from its members")
            for node in nodes:
                bindings.append(
                    {
                        "component_id": node.component_id,
                        "fold": fold,
                        "event_sequence": by_call[node.name, node.operation]["sequence"],
                    }
                )
    except (KeyError, TypeError, ValueError) as exc:
        raise MLContractError(f"Unsupported W09 observation snapshot: {exc}") from exc
    return bindings


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
