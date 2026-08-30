"""Immutable references to ALPHA's existing research control plane.

These contracts carry identity for a later CLI-owned verifier. They never
approve, reserve, launch, or attest.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import cast
from uuid import UUID

from alpha_core import DataError
from alpha_research import ResearchArtifactRef
from alpha_study._contracts import (
    _artifact_from_dict,
    _hash,
    _mapping,
    _strict_keys,
    _text,
    canonical_study_sha256,
)
from alpha_study._operator_registry import OPERATOR_REGISTRY_V1

_SEMVER_RE = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+")
_GIT_COMMIT_RE = re.compile(r"[0-9a-f]{40}")
_RUN_ID_RE = re.compile(r"[0-9a-f]{16}")


def _version(value: object) -> str:
    if not isinstance(value, str) or _SEMVER_RE.fullmatch(value) is None:
        raise DataError("operator_version must be a strict x.y.z version")
    return value


def _git_commit(value: object) -> str:
    if not isinstance(value, str) or _GIT_COMMIT_RE.fullmatch(value) is None:
        raise DataError("git_commit must be a lowercase 40-character commit")
    return value


def _project_id(value: object) -> str:
    text = _text("project_id", value)
    try:
        parsed = UUID(text)
    except ValueError as exc:
        raise DataError("project_id must be a canonical UUID") from exc
    if str(parsed) != text:
        raise DataError("project_id must be a canonical UUID")
    return text


def _content_id(name: str, value: object, prefix: str) -> str:
    text = _text(name, value)
    marker = f"{prefix}_"
    if not text.startswith(marker):
        raise DataError(f"{name} must be a content-addressed {marker} id")
    _hash(name, text[len(marker) :])
    return text


def _run_id(value: object) -> str:
    if not isinstance(value, str) or _RUN_ID_RE.fullmatch(value) is None:
        raise DataError("source_d0_run_id must be lowercase 16-character hex")
    return value


def _repo_path(value: object) -> str:
    text = _text("registry_path", value)
    path = PurePosixPath(text)
    if path.is_absolute() or ".." in path.parts or text != path.as_posix():
        raise DataError("registry_path must be canonical and repository-relative")
    return text


def _canonical_texts(name: str, value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise DataError(f"{name} must be a list or tuple")
    result = tuple(_text(f"{name} item", item) for item in value)
    if not result or len(result) != len(set(result)):
        raise DataError(f"{name} must contain unique values")
    return tuple(sorted(result))


def _canonical_hashes(name: str, value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise DataError(f"{name} must be a list or tuple")
    result = tuple(_hash(f"{name} item", item) for item in value)
    if not result or len(result) != len(set(result)):
        raise DataError(f"{name} must contain unique hashes")
    return tuple(sorted(result))


def _canonical_refs(name: str, value: object, prefix: str) -> tuple[tuple[str, str], ...]:
    if not isinstance(value, (list, tuple)):
        raise DataError(f"{name} must be a list or tuple")
    result: list[tuple[str, str]] = []
    for item in value:
        if isinstance(item, Mapping):
            data = _mapping(item, f"{name} item")
            _strict_keys(data, {"content_sha256", "id"}, f"{name} item")
            ref_id, digest = data["id"], data["content_sha256"]
        elif isinstance(item, tuple) and len(item) == 2:
            ref_id, digest = item
        else:
            raise DataError(f"{name} items must be id/hash references")
        clean_id = _content_id(f"{name} id", ref_id, prefix)
        clean_hash = _hash(f"{name} content_sha256", digest)
        if clean_id != f"{prefix}_{clean_hash}":
            raise DataError(f"{name} id does not match its content hash")
        result.append((clean_id, clean_hash))
    if not result or len(result) != len(set(result)):
        raise DataError(f"{name} must contain unique references")
    return tuple(sorted(result))


def _serialized_refs(value: tuple[tuple[str, str], ...]) -> list[dict[str, str]]:
    return [{"content_sha256": digest, "id": ref_id} for ref_id, digest in value]


def _check_content(supplied: object, expected: str) -> None:
    if _hash("content_sha256", supplied) != expected:
        raise DataError("content_sha256 does not match the semantic payload")


@dataclass(frozen=True, slots=True)
class OperatorRegistrationV1:
    """Closed, Git-owned declaration of one deterministic operator."""

    operator_id: str
    operator_version: str
    description: str
    kind: str
    output_schema: str
    supported_asset_classes: tuple[str, ...]
    required_fields: tuple[str, ...]
    compatible_analysis_families: tuple[str, ...]
    availability_rule_sha256: str
    parameter_schema_sha256: str
    overlap_rule_sha256: str
    dedup_rule_sha256: str
    implementation_module: str
    implementation_symbol: str
    implementation_code_sha256: str
    implementation_git_commit: str
    registry_path: str
    registry_blob_sha256: str
    dependency_lock_sha256: str
    environment_sha256: str

    def __post_init__(self) -> None:
        for name in (
            "operator_id",
            "description",
            "kind",
            "output_schema",
            "implementation_module",
            "implementation_symbol",
        ):
            _text(name, getattr(self, name))
        _version(self.operator_version)
        _git_commit(self.implementation_git_commit)
        _repo_path(self.registry_path)
        for name in ("supported_asset_classes", "required_fields", "compatible_analysis_families"):
            object.__setattr__(self, name, _canonical_texts(name, getattr(self, name)))
        for name in (
            "availability_rule_sha256",
            "parameter_schema_sha256",
            "overlap_rule_sha256",
            "dedup_rule_sha256",
            "implementation_code_sha256",
            "registry_blob_sha256",
            "dependency_lock_sha256",
            "environment_sha256",
        ):
            _hash(name, getattr(self, name))
        entry = OPERATOR_REGISTRY_V1.get(self.operator_id)
        if entry is None:
            raise DataError(f"operator_id {self.operator_id!r} is not in the closed registry")
        declared = {name: getattr(self, name) for name in entry}
        if declared != dict(entry):
            raise DataError("operator registration does not match its Git-owned registry entry")
        expected_blob = canonical_study_sha256(dict(entry))
        if self.registry_blob_sha256 != expected_blob:
            raise DataError("registry_blob_sha256 does not match the Git-owned registry entry")

    def _semantic_dict(self) -> dict[str, object]:
        return {
            "authority": "none",
            "availability_rule_sha256": self.availability_rule_sha256,
            "compatible_analysis_families": list(self.compatible_analysis_families),
            "dedup_rule_sha256": self.dedup_rule_sha256,
            "dependency_lock_sha256": self.dependency_lock_sha256,
            "description": self.description,
            "environment_sha256": self.environment_sha256,
            "implementation_git_commit": self.implementation_git_commit,
            "implementation_code_sha256": self.implementation_code_sha256,
            "implementation_module": self.implementation_module,
            "implementation_symbol": self.implementation_symbol,
            "kind": self.kind,
            "operator_id": self.operator_id,
            "operator_version": self.operator_version,
            "output_schema": self.output_schema,
            "overlap_rule_sha256": self.overlap_rule_sha256,
            "parameter_schema_sha256": self.parameter_schema_sha256,
            "registry_blob_sha256": self.registry_blob_sha256,
            "registry_owner": "git",
            "registry_path": self.registry_path,
            "required_fields": list(self.required_fields),
            "schema": "OperatorRegistrationV1",
            "schema_version": 1,
            "supported_asset_classes": list(self.supported_asset_classes),
            "verification": "not_checked",
        }

    @property
    def content_sha256(self) -> str:
        return canonical_study_sha256(self._semantic_dict())

    @property
    def registration_id(self) -> str:
        return f"opreg_{self.content_sha256}"

    def to_dict(self) -> dict[str, object]:
        return {
            **self._semantic_dict(),
            "content_sha256": self.content_sha256,
            "registration_id": self.registration_id,
        }

    @classmethod
    def from_registry(cls, operator_id: str) -> OperatorRegistrationV1:
        """Project one exact entry from the closed, source-owned registry."""
        clean_id = _text("operator_id", operator_id)
        entry = OPERATOR_REGISTRY_V1.get(clean_id)
        if entry is None:
            raise DataError(f"operator_id {clean_id!r} is not in the closed registry")
        values = dict(entry)
        return cls(
            operator_id=cast(str, values["operator_id"]),
            operator_version=cast(str, values["operator_version"]),
            description=cast(str, values["description"]),
            kind=cast(str, values["kind"]),
            output_schema=cast(str, values["output_schema"]),
            supported_asset_classes=cast(tuple[str, ...], values["supported_asset_classes"]),
            required_fields=cast(tuple[str, ...], values["required_fields"]),
            compatible_analysis_families=cast(
                tuple[str, ...], values["compatible_analysis_families"]
            ),
            availability_rule_sha256=cast(str, values["availability_rule_sha256"]),
            parameter_schema_sha256=cast(str, values["parameter_schema_sha256"]),
            overlap_rule_sha256=cast(str, values["overlap_rule_sha256"]),
            dedup_rule_sha256=cast(str, values["dedup_rule_sha256"]),
            implementation_module=cast(str, values["implementation_module"]),
            implementation_symbol=cast(str, values["implementation_symbol"]),
            implementation_code_sha256=cast(str, values["implementation_code_sha256"]),
            implementation_git_commit=cast(str, values["implementation_git_commit"]),
            registry_path=cast(str, values["registry_path"]),
            registry_blob_sha256=canonical_study_sha256(values),
            dependency_lock_sha256=cast(str, values["dependency_lock_sha256"]),
            environment_sha256=cast(str, values["environment_sha256"]),
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> OperatorRegistrationV1:
        data = _mapping(value, "OperatorRegistrationV1")
        _strict_keys(data, set(cls._keys()), "OperatorRegistrationV1")
        if (
            data["schema"],
            data["schema_version"],
            data["authority"],
            data["registry_owner"],
            data["verification"],
        ) != ("OperatorRegistrationV1", 1, "none", "git", "not_checked"):
            raise DataError("OperatorRegistrationV1 cannot claim mutable authority")
        result = cls(
            operator_id=cast(str, data["operator_id"]),
            operator_version=cast(str, data["operator_version"]),
            description=cast(str, data["description"]),
            kind=cast(str, data["kind"]),
            output_schema=cast(str, data["output_schema"]),
            supported_asset_classes=_canonical_texts(
                "supported_asset_classes", data["supported_asset_classes"]
            ),
            required_fields=_canonical_texts("required_fields", data["required_fields"]),
            compatible_analysis_families=_canonical_texts(
                "compatible_analysis_families", data["compatible_analysis_families"]
            ),
            availability_rule_sha256=cast(str, data["availability_rule_sha256"]),
            parameter_schema_sha256=cast(str, data["parameter_schema_sha256"]),
            overlap_rule_sha256=cast(str, data["overlap_rule_sha256"]),
            dedup_rule_sha256=cast(str, data["dedup_rule_sha256"]),
            implementation_module=cast(str, data["implementation_module"]),
            implementation_symbol=cast(str, data["implementation_symbol"]),
            implementation_code_sha256=cast(str, data["implementation_code_sha256"]),
            implementation_git_commit=cast(str, data["implementation_git_commit"]),
            registry_path=cast(str, data["registry_path"]),
            registry_blob_sha256=cast(str, data["registry_blob_sha256"]),
            dependency_lock_sha256=cast(str, data["dependency_lock_sha256"]),
            environment_sha256=cast(str, data["environment_sha256"]),
        )
        _check_content(data["content_sha256"], result.content_sha256)
        if data["registration_id"] != result.registration_id:
            raise DataError("registration_id does not match the semantic payload")
        return result

    @staticmethod
    def _keys() -> tuple[str, ...]:
        return (
            "authority",
            "availability_rule_sha256",
            "compatible_analysis_families",
            "content_sha256",
            "dedup_rule_sha256",
            "dependency_lock_sha256",
            "description",
            "environment_sha256",
            "implementation_git_commit",
            "implementation_code_sha256",
            "implementation_module",
            "implementation_symbol",
            "kind",
            "operator_id",
            "operator_version",
            "output_schema",
            "overlap_rule_sha256",
            "parameter_schema_sha256",
            "registration_id",
            "registry_blob_sha256",
            "registry_owner",
            "registry_path",
            "required_fields",
            "schema",
            "schema_version",
            "supported_asset_classes",
            "verification",
        )


@dataclass(frozen=True, slots=True)
class DetectorValidationV1:
    """Unverified reference to one mechanically recomputable D0 attempt."""

    project_id: str
    research_contract_id: str
    research_contract_sha256: str
    operator_registration_id: str
    operator_registration_sha256: str
    source_d0_attempt_id: str
    source_d0_run_id: str
    source_d0_reservation_id: str
    source_d0_config_fingerprint: str
    acceptance_selector: str
    acceptance: ResearchArtifactRef
    fixture_definition_sha256: str
    fixture: ResearchArtifactRef
    observed_table_sha256: str
    validator_code_sha256: str
    validator_environment_sha256: str

    def __post_init__(self) -> None:
        _project_id(self.project_id)
        _content_id("research_contract_id", self.research_contract_id, "rc")
        _hash("research_contract_sha256", self.research_contract_sha256)
        _content_id("operator_registration_id", self.operator_registration_id, "opreg")
        _hash("operator_registration_sha256", self.operator_registration_sha256)
        if self.operator_registration_id != f"opreg_{self.operator_registration_sha256}":
            raise DataError("operator registration id does not match its content hash")
        _content_id("source_d0_attempt_id", self.source_d0_attempt_id, "ra")
        _run_id(self.source_d0_run_id)
        _content_id("source_d0_reservation_id", self.source_d0_reservation_id, "rl")
        _hash("source_d0_config_fingerprint", self.source_d0_config_fingerprint)
        if self.acceptance_selector != "d0_acceptance.json":
            raise DataError("acceptance_selector must be exactly 'd0_acceptance.json'")
        if not isinstance(self.acceptance, ResearchArtifactRef) or not isinstance(
            self.fixture, ResearchArtifactRef
        ):
            raise DataError("acceptance and fixture must be ResearchArtifactRef values")
        if self.acceptance.artifact_id != self.acceptance_selector:
            raise DataError("acceptance artifact must match acceptance_selector")
        for name in (
            "fixture_definition_sha256",
            "observed_table_sha256",
            "validator_code_sha256",
            "validator_environment_sha256",
        ):
            _hash(name, getattr(self, name))

    def _semantic_dict(self) -> dict[str, object]:
        return {
            "acceptance": self.acceptance.to_dict(),
            "acceptance_selector": self.acceptance_selector,
            "authority": "existing_control_plane_reference",
            "fixture": self.fixture.to_dict(),
            "fixture_definition_sha256": self.fixture_definition_sha256,
            "observed_table_sha256": self.observed_table_sha256,
            "operator_registration_id": self.operator_registration_id,
            "operator_registration_sha256": self.operator_registration_sha256,
            "project_id": self.project_id,
            "research_contract_id": self.research_contract_id,
            "research_contract_sha256": self.research_contract_sha256,
            "schema": "DetectorValidationV1",
            "schema_version": 1,
            "source_d0_attempt_id": self.source_d0_attempt_id,
            "source_d0_config_fingerprint": self.source_d0_config_fingerprint,
            "source_d0_reservation_id": self.source_d0_reservation_id,
            "source_d0_run_id": self.source_d0_run_id,
            "validator_code_sha256": self.validator_code_sha256,
            "validator_environment_sha256": self.validator_environment_sha256,
            "verdict": "not_attested",
            "verification": "not_checked",
        }

    @property
    def content_sha256(self) -> str:
        return canonical_study_sha256(self._semantic_dict())

    @property
    def detector_validation_id(self) -> str:
        return f"detval_{self.content_sha256}"

    def to_dict(self) -> dict[str, object]:
        return {
            **self._semantic_dict(),
            "content_sha256": self.content_sha256,
            "detector_validation_id": self.detector_validation_id,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> DetectorValidationV1:
        data = _mapping(value, "DetectorValidationV1")
        _strict_keys(data, set(cls._keys()), "DetectorValidationV1")
        if (
            data["schema"],
            data["schema_version"],
            data["authority"],
            data["verdict"],
            data["verification"],
        ) != (
            "DetectorValidationV1",
            1,
            "existing_control_plane_reference",
            "not_attested",
            "not_checked",
        ):
            raise DataError("DetectorValidationV1 is an unattested reference only")
        result = cls(
            project_id=cast(str, data["project_id"]),
            research_contract_id=cast(str, data["research_contract_id"]),
            research_contract_sha256=cast(str, data["research_contract_sha256"]),
            operator_registration_id=cast(str, data["operator_registration_id"]),
            operator_registration_sha256=cast(str, data["operator_registration_sha256"]),
            source_d0_attempt_id=cast(str, data["source_d0_attempt_id"]),
            source_d0_run_id=cast(str, data["source_d0_run_id"]),
            source_d0_reservation_id=cast(str, data["source_d0_reservation_id"]),
            source_d0_config_fingerprint=cast(str, data["source_d0_config_fingerprint"]),
            acceptance_selector=cast(str, data["acceptance_selector"]),
            acceptance=_artifact_from_dict(data["acceptance"]),
            fixture_definition_sha256=cast(str, data["fixture_definition_sha256"]),
            fixture=_artifact_from_dict(data["fixture"]),
            observed_table_sha256=cast(str, data["observed_table_sha256"]),
            validator_code_sha256=cast(str, data["validator_code_sha256"]),
            validator_environment_sha256=cast(str, data["validator_environment_sha256"]),
        )
        _check_content(data["content_sha256"], result.content_sha256)
        if data["detector_validation_id"] != result.detector_validation_id:
            raise DataError("detector_validation_id does not match the semantic payload")
        return result

    @staticmethod
    def _keys() -> tuple[str, ...]:
        return (
            "acceptance",
            "acceptance_selector",
            "authority",
            "content_sha256",
            "detector_validation_id",
            "fixture",
            "fixture_definition_sha256",
            "observed_table_sha256",
            "operator_registration_id",
            "operator_registration_sha256",
            "project_id",
            "research_contract_id",
            "research_contract_sha256",
            "schema",
            "schema_version",
            "source_d0_attempt_id",
            "source_d0_config_fingerprint",
            "source_d0_reservation_id",
            "source_d0_run_id",
            "validator_code_sha256",
            "validator_environment_sha256",
            "verdict",
            "verification",
        )


@dataclass(frozen=True, slots=True)
class ExplorationMandateV1:
    """Non-authoritative D1 projection refined from exact existing records."""

    project_id: str
    study_id: str
    research_contract_id: str
    research_contract_sha256: str
    analysis_plan_sha256: str
    topology_sha256: str
    chart_spec_sha256: str
    dataset_sha256: str
    d1_execution_fingerprint: str
    code_sha256: str
    dependency_lock_sha256: str
    environment_sha256: str
    approved_budget_sha256: str
    source_d0_attempt_id: str
    source_d0_run_id: str
    source_d0_reservation_id: str
    source_d0_config_fingerprint: str
    source_d0_acceptance_sha256: str
    operator_registration_refs: tuple[tuple[str, str], ...]
    detector_validation_refs: tuple[tuple[str, str], ...]
    dataset_snapshot_sha256s: tuple[str, ...]

    def __post_init__(self) -> None:
        _project_id(self.project_id)
        _text("study_id", self.study_id)
        _content_id("research_contract_id", self.research_contract_id, "rc")
        _content_id("source_d0_attempt_id", self.source_d0_attempt_id, "ra")
        _run_id(self.source_d0_run_id)
        _content_id("source_d0_reservation_id", self.source_d0_reservation_id, "rl")
        _hash("source_d0_config_fingerprint", self.source_d0_config_fingerprint)
        _hash("d1_execution_fingerprint", self.d1_execution_fingerprint)
        for name in (
            "research_contract_sha256",
            "analysis_plan_sha256",
            "topology_sha256",
            "chart_spec_sha256",
            "dataset_sha256",
            "code_sha256",
            "dependency_lock_sha256",
            "environment_sha256",
            "approved_budget_sha256",
            "source_d0_acceptance_sha256",
        ):
            _hash(name, getattr(self, name))
        object.__setattr__(
            self,
            "operator_registration_refs",
            _canonical_refs("operator_registration_refs", self.operator_registration_refs, "opreg"),
        )
        object.__setattr__(
            self,
            "detector_validation_refs",
            _canonical_refs("detector_validation_refs", self.detector_validation_refs, "detval"),
        )
        object.__setattr__(
            self,
            "dataset_snapshot_sha256s",
            _canonical_hashes("dataset_snapshot_sha256s", self.dataset_snapshot_sha256s),
        )

    def _semantic_dict(self) -> dict[str, object]:
        return {
            "analysis_plan_sha256": self.analysis_plan_sha256,
            "approved_budget_sha256": self.approved_budget_sha256,
            "authority": "existing_control_plane_reference",
            "chart_spec_sha256": self.chart_spec_sha256,
            "code_sha256": self.code_sha256,
            "d1_execution_fingerprint": self.d1_execution_fingerprint,
            "dataset_sha256": self.dataset_sha256,
            "dataset_snapshot_sha256s": list(self.dataset_snapshot_sha256s),
            "dependency_lock_sha256": self.dependency_lock_sha256,
            "detector_validation_refs": _serialized_refs(self.detector_validation_refs),
            "environment_sha256": self.environment_sha256,
            "launch_authority": "none",
            "operator_registration_refs": _serialized_refs(self.operator_registration_refs),
            "project_id": self.project_id,
            "research_contract_id": self.research_contract_id,
            "research_contract_sha256": self.research_contract_sha256,
            "schema": "ExplorationMandateV1",
            "schema_version": 1,
            "source_d0_acceptance_sha256": self.source_d0_acceptance_sha256,
            "source_d0_attempt_id": self.source_d0_attempt_id,
            "source_d0_config_fingerprint": self.source_d0_config_fingerprint,
            "source_d0_reservation_id": self.source_d0_reservation_id,
            "source_d0_run_id": self.source_d0_run_id,
            "stage": "D1",
            "study_id": self.study_id,
            "topology_sha256": self.topology_sha256,
            "verification": "not_checked",
        }

    @property
    def content_sha256(self) -> str:
        return canonical_study_sha256(self._semantic_dict())

    @property
    def mandate_id(self) -> str:
        return f"mandate_{self.content_sha256}"

    def to_dict(self) -> dict[str, object]:
        return {
            **self._semantic_dict(),
            "content_sha256": self.content_sha256,
            "mandate_id": self.mandate_id,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> ExplorationMandateV1:
        data = _mapping(value, "ExplorationMandateV1")
        _strict_keys(data, set(cls._keys()), "ExplorationMandateV1")
        if (
            data["schema"],
            data["schema_version"],
            data["authority"],
            data["launch_authority"],
            data["stage"],
            data["verification"],
        ) != (
            "ExplorationMandateV1",
            1,
            "existing_control_plane_reference",
            "none",
            "D1",
            "not_checked",
        ):
            raise DataError("ExplorationMandateV1 is a reference-only D1 projection")
        for name in (
            "operator_registration_refs",
            "detector_validation_refs",
            "dataset_snapshot_sha256s",
        ):
            if not isinstance(data[name], list):
                raise DataError(f"{name} must be a JSON array")
        result = cls(
            project_id=cast(str, data["project_id"]),
            study_id=cast(str, data["study_id"]),
            research_contract_id=cast(str, data["research_contract_id"]),
            research_contract_sha256=cast(str, data["research_contract_sha256"]),
            analysis_plan_sha256=cast(str, data["analysis_plan_sha256"]),
            topology_sha256=cast(str, data["topology_sha256"]),
            chart_spec_sha256=cast(str, data["chart_spec_sha256"]),
            dataset_sha256=cast(str, data["dataset_sha256"]),
            d1_execution_fingerprint=cast(str, data["d1_execution_fingerprint"]),
            code_sha256=cast(str, data["code_sha256"]),
            dependency_lock_sha256=cast(str, data["dependency_lock_sha256"]),
            environment_sha256=cast(str, data["environment_sha256"]),
            approved_budget_sha256=cast(str, data["approved_budget_sha256"]),
            source_d0_attempt_id=cast(str, data["source_d0_attempt_id"]),
            source_d0_run_id=cast(str, data["source_d0_run_id"]),
            source_d0_reservation_id=cast(str, data["source_d0_reservation_id"]),
            source_d0_config_fingerprint=cast(str, data["source_d0_config_fingerprint"]),
            source_d0_acceptance_sha256=cast(str, data["source_d0_acceptance_sha256"]),
            operator_registration_refs=_canonical_refs(
                "operator_registration_refs", data["operator_registration_refs"], "opreg"
            ),
            detector_validation_refs=_canonical_refs(
                "detector_validation_refs", data["detector_validation_refs"], "detval"
            ),
            dataset_snapshot_sha256s=_canonical_hashes(
                "dataset_snapshot_sha256s", data["dataset_snapshot_sha256s"]
            ),
        )
        _check_content(data["content_sha256"], result.content_sha256)
        if data["mandate_id"] != result.mandate_id:
            raise DataError("mandate_id does not match the semantic payload")
        return result

    @staticmethod
    def _keys() -> tuple[str, ...]:
        return (
            "analysis_plan_sha256",
            "approved_budget_sha256",
            "authority",
            "chart_spec_sha256",
            "code_sha256",
            "content_sha256",
            "d1_execution_fingerprint",
            "dataset_sha256",
            "dataset_snapshot_sha256s",
            "dependency_lock_sha256",
            "detector_validation_refs",
            "environment_sha256",
            "launch_authority",
            "mandate_id",
            "operator_registration_refs",
            "project_id",
            "research_contract_id",
            "research_contract_sha256",
            "schema",
            "schema_version",
            "source_d0_acceptance_sha256",
            "source_d0_attempt_id",
            "source_d0_config_fingerprint",
            "source_d0_reservation_id",
            "source_d0_run_id",
            "stage",
            "study_id",
            "topology_sha256",
            "verification",
        )


__all__ = ["DetectorValidationV1", "ExplorationMandateV1", "OperatorRegistrationV1"]
