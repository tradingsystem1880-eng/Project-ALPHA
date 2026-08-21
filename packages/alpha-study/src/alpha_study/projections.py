"""Deterministic, non-authoritative study projections."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, cast
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

_RUN_ID_RE: Final = re.compile(r"[0-9a-f]{16}")
_FINDING_IDS: Final = frozenset(
    {
        "confirmation_classification",
        "mechanism",
        "multiplicity",
        "negative_controls",
        "power",
        "stability_parameter",
        "stability_temporal",
        "stability_transportability",
    }
)
_FINDING_STATUSES: Final = frozenset(
    {
        "PASSED",
        "FAILED",
        "STABLE",
        "UNSTABLE",
        "SUPPORTED",
        "CONTRADICTED",
        "INCONCLUSIVE",
        "NOT_TESTED",
    }
)
_FINDING_STATUS_BY_ID: Final = {
    "confirmation_classification": frozenset({"SUPPORTED", "CONTRADICTED", "INCONCLUSIVE"}),
    "mechanism": frozenset({"PASSED", "FAILED", "INCONCLUSIVE", "NOT_TESTED"}),
    "multiplicity": frozenset({"PASSED", "INCONCLUSIVE", "NOT_TESTED"}),
    "negative_controls": frozenset({"PASSED", "FAILED", "INCONCLUSIVE", "NOT_TESTED"}),
    "power": frozenset({"PASSED", "INCONCLUSIVE", "NOT_TESTED"}),
    "stability_parameter": frozenset({"STABLE", "UNSTABLE", "INCONCLUSIVE", "NOT_TESTED"}),
    "stability_temporal": frozenset({"STABLE", "UNSTABLE", "INCONCLUSIVE", "NOT_TESTED"}),
    "stability_transportability": frozenset({"STABLE", "UNSTABLE", "INCONCLUSIVE", "NOT_TESTED"}),
}
_NODE_KINDS: Final = frozenset(
    {
        "proposed_mechanism",
        "alternative",
        "confounder",
        "falsifier",
        "stability_finding",
        "screened_claim",
        "context_packet",
        "note",
    }
)
_RELATIONS: Final = frozenset(
    {
        "proposes",
        "alternative_to",
        "confounds",
        "falsifies",
        "tests_stability",
        "supports_context",
        "contradicts_context",
        "annotates",
    }
)
_REF_KINDS: Final = frozenset(
    {
        "advisor_proposal",
        "artifact",
        "chart",
        "context_packet",
        "dataset",
        "detector_validation",
        "finding",
        "mechanism_graph",
        "note",
        "operator_registration",
        "promotion_packet",
        "research_contract",
        "run_manifest",
        "screened_claim",
        "workspace",
    }
)
_REF_PREFIXES: Final = {
    "advisor_proposal": "advisor",
    "context_packet": "cp",
    "dataset": "rd",
    "detector_validation": "detval",
    "finding": "finding",
    "mechanism_graph": "mechanism",
    "note": "rn",
    "operator_registration": "opreg",
    "promotion_packet": "cp",
    "research_contract": "rc",
    "screened_claim": "sc",
    "workspace": "workspace",
}
_NODE_SOURCE_KINDS: Final = {
    "proposed_mechanism": frozenset({"research_contract", "context_packet"}),
    "alternative": frozenset({"research_contract"}),
    "confounder": frozenset({"research_contract"}),
    "falsifier": frozenset({"research_contract"}),
    "stability_finding": frozenset({"finding"}),
    "screened_claim": frozenset({"screened_claim"}),
    "context_packet": frozenset({"context_packet"}),
    "note": frozenset({"note"}),
}
_RELATION_SOURCE_KINDS: Final = {
    "proposes": frozenset({"research_contract", "context_packet", "note"}),
    "alternative_to": frozenset({"research_contract"}),
    "confounds": frozenset({"research_contract"}),
    "falsifies": frozenset({"finding", "research_contract", "screened_claim"}),
    "tests_stability": frozenset({"finding"}),
    "supports_context": frozenset({"screened_claim"}),
    "contradicts_context": frozenset({"screened_claim"}),
    "annotates": frozenset({"context_packet", "note"}),
}
_ADVISOR_ACTIONS: Final = frozenset(
    {
        "collect_qualified_source",
        "inspect_recorded_contradiction",
        "revise_hypothesis_draft",
        "request_owner_review",
        "run_non_empirical_diagnostic",
    }
)


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
        raise DataError("source_run_id must be lowercase 16-character hex")
    return value


def _closed(name: str, value: object, allowed: frozenset[str]) -> str:
    text = _text(name, value)
    if text not in allowed:
        raise DataError(f"{name} is not registered")
    return text


def _texts(name: str, value: object) -> tuple[str, ...]:
    if not isinstance(value, (tuple, list)):
        raise DataError(f"{name} must be a list or tuple")
    result = tuple(_text(f"{name} item", item) for item in value)
    if not result or len(result) != len(set(result)):
        raise DataError(f"{name} must contain unique values")
    return tuple(sorted(result))


def _check_hash(data: Mapping[str, object], expected: str, id_key: str, prefix: str) -> None:
    if _hash("content_sha256", data["content_sha256"]) != expected:
        raise DataError("content_sha256 does not match the semantic payload")
    if data[id_key] != f"{prefix}_{expected}":
        raise DataError(f"{id_key} does not match the semantic payload")


@dataclass(frozen=True, slots=True)
class ProjectionRefV1:
    """One exact reference to an existing artifact or derived projection."""

    ref_id: str
    content_sha256: str
    kind: str

    def __post_init__(self) -> None:
        _text("ref_id", self.ref_id)
        _hash("content_sha256", self.content_sha256)
        _closed("kind", self.kind, _REF_KINDS)
        prefix = _REF_PREFIXES.get(self.kind)
        if prefix is not None and self.ref_id != f"{prefix}_{self.content_sha256}":
            raise DataError("ref_id does not match its kind and content hash")
        if self.kind == "run_manifest":
            _run_id(self.ref_id)

    def to_dict(self) -> dict[str, object]:
        return {"content_sha256": self.content_sha256, "kind": self.kind, "ref_id": self.ref_id}

    @classmethod
    def from_dict(cls, value: object) -> ProjectionRefV1:
        data = _mapping(value, "ProjectionRefV1")
        _strict_keys(data, {"content_sha256", "kind", "ref_id"}, "ProjectionRefV1")
        return cls(
            ref_id=cast(str, data["ref_id"]),
            content_sha256=cast(str, data["content_sha256"]),
            kind=cast(str, data["kind"]),
        )


def _refs(name: str, value: object, *, allow_empty: bool = False) -> tuple[ProjectionRefV1, ...]:
    if not isinstance(value, (tuple, list)):
        raise DataError(f"{name} must be a list or tuple")
    result = tuple(
        item if isinstance(item, ProjectionRefV1) else ProjectionRefV1.from_dict(item)
        for item in value
    )
    keys = tuple((item.ref_id, item.content_sha256, item.kind) for item in result)
    if (not result and not allow_empty) or len(keys) != len(set(keys)):
        raise DataError(f"{name} must contain unique references")
    return tuple(sorted(result, key=lambda item: (item.ref_id, item.content_sha256, item.kind)))


@dataclass(frozen=True, slots=True)
class FindingV1:
    """Exact copy of one typed finding from immutable D1/D2 evidence."""

    project_id: str
    research_contract_id: str
    research_contract_sha256: str
    source_attempt_id: str
    source_run_id: str
    source_artifact: ResearchArtifactRef
    evidence_zone: str
    watermark: str
    finding_id: str
    finding_status: str
    summary: str

    def __post_init__(self) -> None:
        _project_id(self.project_id)
        _content_id("research_contract_id", self.research_contract_id, "rc")
        _hash("research_contract_sha256", self.research_contract_sha256)
        _content_id("source_attempt_id", self.source_attempt_id, "ra")
        _run_id(self.source_run_id)
        if not isinstance(self.source_artifact, ResearchArtifactRef):
            raise DataError("source_artifact must be a ResearchArtifactRef")
        if self.source_artifact.artifact_id != "research_gate_evidence.json":
            raise DataError("FindingV1 requires the typed research_gate_evidence.json artifact")
        if self.evidence_zone not in {"D1", "D2"}:
            raise DataError("evidence_zone must be D1 or D2")
        expected_watermark = (
            "EXPLORATORY" if self.evidence_zone == "D1" else "REGISTERED CONFIRMATORY"
        )
        if self.watermark != expected_watermark:
            raise DataError("watermark does not match evidence_zone")
        _closed("finding_id", self.finding_id, _FINDING_IDS)
        if self.finding_id == "confirmation_classification" and self.evidence_zone != "D2":
            raise DataError("confirmation_classification exists only in D2 evidence")
        _closed("finding_status", self.finding_status, _FINDING_STATUSES)
        if self.finding_status not in _FINDING_STATUS_BY_ID[self.finding_id]:
            raise DataError("finding_status is not valid for finding_id")
        _text("summary", self.summary)

    def _semantic_dict(self) -> dict[str, object]:
        return {
            "authority": "none",
            "evidence_zone": self.evidence_zone,
            "finding_id": self.finding_id,
            "finding_status": self.finding_status,
            "project_id": self.project_id,
            "research_contract_id": self.research_contract_id,
            "research_contract_sha256": self.research_contract_sha256,
            "schema": "FindingV1",
            "schema_version": 1,
            "source_artifact": self.source_artifact.to_dict(),
            "source_attempt_id": self.source_attempt_id,
            "source_run_id": self.source_run_id,
            "summary": self.summary,
            "verification": "not_checked",
            "watermark": self.watermark,
        }

    @property
    def content_sha256(self) -> str:
        return canonical_study_sha256(self._semantic_dict())

    @property
    def finding_ref_id(self) -> str:
        return f"finding_{self.content_sha256}"

    def to_dict(self) -> dict[str, object]:
        return {
            **self._semantic_dict(),
            "content_sha256": self.content_sha256,
            "finding_ref_id": self.finding_ref_id,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> FindingV1:
        data = _mapping(value, "FindingV1")
        keys = {
            "authority",
            "content_sha256",
            "evidence_zone",
            "finding_id",
            "finding_ref_id",
            "finding_status",
            "project_id",
            "research_contract_id",
            "research_contract_sha256",
            "schema",
            "schema_version",
            "source_artifact",
            "source_attempt_id",
            "source_run_id",
            "summary",
            "verification",
            "watermark",
        }
        _strict_keys(data, keys, "FindingV1")
        if (data["schema"], data["schema_version"], data["authority"], data["verification"]) != (
            "FindingV1",
            1,
            "none",
            "not_checked",
        ):
            raise DataError("FindingV1 is a not-checked projection only")
        result = cls(
            project_id=cast(str, data["project_id"]),
            research_contract_id=cast(str, data["research_contract_id"]),
            research_contract_sha256=cast(str, data["research_contract_sha256"]),
            source_attempt_id=cast(str, data["source_attempt_id"]),
            source_run_id=cast(str, data["source_run_id"]),
            source_artifact=_artifact_from_dict(data["source_artifact"]),
            evidence_zone=cast(str, data["evidence_zone"]),
            watermark=cast(str, data["watermark"]),
            finding_id=cast(str, data["finding_id"]),
            finding_status=cast(str, data["finding_status"]),
            summary=cast(str, data["summary"]),
        )
        _check_hash(data, result.content_sha256, "finding_ref_id", "finding")
        return result


@dataclass(frozen=True, slots=True)
class MechanismNodeV1:
    node_id: str
    kind: str
    label: str
    source: ProjectionRefV1

    def __post_init__(self) -> None:
        _text("node_id", self.node_id)
        _closed("kind", self.kind, _NODE_KINDS)
        _text("label", self.label)
        if not isinstance(self.source, ProjectionRefV1):
            raise DataError("source must be ProjectionRefV1")
        if self.source.kind not in _NODE_SOURCE_KINDS[self.kind]:
            raise DataError("mechanism node kind does not match its source kind")

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "label": self.label,
            "node_id": self.node_id,
            "source": self.source.to_dict(),
        }

    @classmethod
    def from_dict(cls, value: object) -> MechanismNodeV1:
        data = _mapping(value, "MechanismNodeV1")
        _strict_keys(data, {"kind", "label", "node_id", "source"}, "MechanismNodeV1")
        return cls(
            cast(str, data["node_id"]),
            cast(str, data["kind"]),
            cast(str, data["label"]),
            ProjectionRefV1.from_dict(data["source"]),
        )


@dataclass(frozen=True, slots=True)
class MechanismEdgeV1:
    source_node_id: str
    target_node_id: str
    relation: str
    source: ProjectionRefV1

    def __post_init__(self) -> None:
        _text("source_node_id", self.source_node_id)
        _text("target_node_id", self.target_node_id)
        if self.source_node_id == self.target_node_id:
            raise DataError("mechanism edges cannot be self-referential")
        _closed("relation", self.relation, _RELATIONS)
        if not isinstance(self.source, ProjectionRefV1):
            raise DataError("source must be ProjectionRefV1")
        if self.source.kind not in _RELATION_SOURCE_KINDS[self.relation]:
            raise DataError("mechanism relation does not match its source kind")

    def to_dict(self) -> dict[str, object]:
        return {
            "relation": self.relation,
            "source": self.source.to_dict(),
            "source_node_id": self.source_node_id,
            "target_node_id": self.target_node_id,
        }

    @classmethod
    def from_dict(cls, value: object) -> MechanismEdgeV1:
        data = _mapping(value, "MechanismEdgeV1")
        _strict_keys(
            data, {"relation", "source", "source_node_id", "target_node_id"}, "MechanismEdgeV1"
        )
        return cls(
            cast(str, data["source_node_id"]),
            cast(str, data["target_node_id"]),
            cast(str, data["relation"]),
            ProjectionRefV1.from_dict(data["source"]),
        )


@dataclass(frozen=True, slots=True)
class MechanismGraphV1:
    project_id: str
    research_contract_id: str
    research_contract_sha256: str
    nodes: tuple[MechanismNodeV1, ...]
    edges: tuple[MechanismEdgeV1, ...]

    def __post_init__(self) -> None:
        _project_id(self.project_id)
        _content_id("research_contract_id", self.research_contract_id, "rc")
        _hash("research_contract_sha256", self.research_contract_sha256)
        if not self.nodes or not all(isinstance(item, MechanismNodeV1) for item in self.nodes):
            raise DataError("nodes must contain MechanismNodeV1 values")
        node_ids = tuple(item.node_id for item in self.nodes)
        if len(node_ids) != len(set(node_ids)):
            raise DataError("node_id values must be unique")
        if not all(isinstance(item, MechanismEdgeV1) for item in self.edges):
            raise DataError("edges must contain MechanismEdgeV1 values")
        edge_keys = tuple(
            (
                item.source_node_id,
                item.target_node_id,
                item.relation,
                item.source.ref_id,
                item.source.content_sha256,
            )
            for item in self.edges
        )
        if len(edge_keys) != len(set(edge_keys)):
            raise DataError("edges must be unique")
        known = set(node_ids)
        if any(
            edge.source_node_id not in known or edge.target_node_id not in known
            for edge in self.edges
        ):
            raise DataError("every edge endpoint must reference a graph node")
        object.__setattr__(self, "nodes", tuple(sorted(self.nodes, key=lambda item: item.node_id)))
        object.__setattr__(
            self,
            "edges",
            tuple(
                sorted(
                    self.edges,
                    key=lambda item: (
                        item.source_node_id,
                        item.target_node_id,
                        item.relation,
                        item.source.ref_id,
                    ),
                )
            ),
        )

    def _semantic_dict(self) -> dict[str, object]:
        return {
            "authority": "none",
            "edges": [item.to_dict() for item in self.edges],
            "nodes": [item.to_dict() for item in self.nodes],
            "project_id": self.project_id,
            "research_contract_id": self.research_contract_id,
            "research_contract_sha256": self.research_contract_sha256,
            "schema": "MechanismGraphV1",
            "schema_version": 1,
            "verification": "not_checked",
        }

    @property
    def content_sha256(self) -> str:
        return canonical_study_sha256(self._semantic_dict())

    @property
    def mechanism_graph_id(self) -> str:
        return f"mechanism_{self.content_sha256}"

    def to_dict(self) -> dict[str, object]:
        return {
            **self._semantic_dict(),
            "content_sha256": self.content_sha256,
            "mechanism_graph_id": self.mechanism_graph_id,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> MechanismGraphV1:
        data = _mapping(value, "MechanismGraphV1")
        keys = {
            "authority",
            "content_sha256",
            "edges",
            "mechanism_graph_id",
            "nodes",
            "project_id",
            "research_contract_id",
            "research_contract_sha256",
            "schema",
            "schema_version",
            "verification",
        }
        _strict_keys(data, keys, "MechanismGraphV1")
        if (data["schema"], data["schema_version"], data["authority"], data["verification"]) != (
            "MechanismGraphV1",
            1,
            "none",
            "not_checked",
        ):
            raise DataError("MechanismGraphV1 is a not-checked reference graph only")
        if not isinstance(data["nodes"], list) or not isinstance(data["edges"], list):
            raise DataError("nodes and edges must be JSON arrays")
        result = cls(
            cast(str, data["project_id"]),
            cast(str, data["research_contract_id"]),
            cast(str, data["research_contract_sha256"]),
            tuple(MechanismNodeV1.from_dict(item) for item in data["nodes"]),
            tuple(MechanismEdgeV1.from_dict(item) for item in data["edges"]),
        )
        _check_hash(data, result.content_sha256, "mechanism_graph_id", "mechanism")
        return result


@dataclass(frozen=True, slots=True)
class AdvisorProposalV1:
    project_id: str
    research_contract_id: str
    research_contract_sha256: str
    source_refs: tuple[ProjectionRefV1, ...]
    actions: tuple[str, ...]
    uncertainty: str
    change_condition: str

    def __post_init__(self) -> None:
        _project_id(self.project_id)
        _content_id("research_contract_id", self.research_contract_id, "rc")
        _hash("research_contract_sha256", self.research_contract_sha256)
        object.__setattr__(self, "source_refs", _refs("source_refs", self.source_refs))
        actions = _texts("actions", self.actions)
        if any(action not in _ADVISOR_ACTIONS for action in actions):
            raise DataError("actions must use registered non-executable recommendation codes")
        object.__setattr__(self, "actions", actions)
        _text("uncertainty", self.uncertainty)
        _text("change_condition", self.change_condition)

    def _semantic_dict(self) -> dict[str, object]:
        return {
            "actions": list(self.actions),
            "authority": "none",
            "change_condition": self.change_condition,
            "evidence_status": "proposal_only",
            "project_id": self.project_id,
            "research_contract_id": self.research_contract_id,
            "research_contract_sha256": self.research_contract_sha256,
            "schema": "AdvisorProposalV1",
            "schema_version": 1,
            "source_refs": [item.to_dict() for item in self.source_refs],
            "uncertainty": self.uncertainty,
            "verification": "not_checked",
        }

    @property
    def content_sha256(self) -> str:
        return canonical_study_sha256(self._semantic_dict())

    @property
    def advisor_proposal_id(self) -> str:
        return f"advisor_{self.content_sha256}"

    def to_dict(self) -> dict[str, object]:
        return {
            **self._semantic_dict(),
            "advisor_proposal_id": self.advisor_proposal_id,
            "content_sha256": self.content_sha256,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> AdvisorProposalV1:
        data = _mapping(value, "AdvisorProposalV1")
        keys = {
            "actions",
            "advisor_proposal_id",
            "authority",
            "change_condition",
            "content_sha256",
            "evidence_status",
            "project_id",
            "research_contract_id",
            "research_contract_sha256",
            "schema",
            "schema_version",
            "source_refs",
            "uncertainty",
            "verification",
        }
        _strict_keys(data, keys, "AdvisorProposalV1")
        if (
            data["schema"],
            data["schema_version"],
            data["authority"],
            data["verification"],
            data["evidence_status"],
        ) != ("AdvisorProposalV1", 1, "none", "not_checked", "proposal_only"):
            raise DataError("AdvisorProposalV1 is proposal-only")
        if not isinstance(data["source_refs"], list) or not isinstance(data["actions"], list):
            raise DataError("source_refs and actions must be JSON arrays")
        result = cls(
            cast(str, data["project_id"]),
            cast(str, data["research_contract_id"]),
            cast(str, data["research_contract_sha256"]),
            _refs("source_refs", data["source_refs"]),
            _texts("actions", data["actions"]),
            cast(str, data["uncertainty"]),
            cast(str, data["change_condition"]),
        )
        _check_hash(data, result.content_sha256, "advisor_proposal_id", "advisor")
        return result


@dataclass(frozen=True, slots=True)
class StudyWorkspaceManifestV1:
    project_id: str
    study_id: str
    research_contract_id: str
    research_contract_sha256: str
    projection_refs: tuple[ProjectionRefV1, ...]
    run_manifest_refs: tuple[ProjectionRefV1, ...]
    chart_refs: tuple[ProjectionRefV1, ...]
    dataset_refs: tuple[ProjectionRefV1, ...]
    promotion_packet_refs: tuple[ProjectionRefV1, ...] = ()

    def __post_init__(self) -> None:
        _project_id(self.project_id)
        _text("study_id", self.study_id)
        _content_id("research_contract_id", self.research_contract_id, "rc")
        _hash("research_contract_sha256", self.research_contract_sha256)
        for name in ("projection_refs", "run_manifest_refs", "chart_refs", "dataset_refs"):
            object.__setattr__(self, name, _refs(name, getattr(self, name)))
        object.__setattr__(
            self,
            "promotion_packet_refs",
            _refs("promotion_packet_refs", self.promotion_packet_refs, allow_empty=True),
        )
        expected_kinds = {
            "projection_refs": {
                "advisor_proposal",
                "detector_validation",
                "finding",
                "mechanism_graph",
                "operator_registration",
            },
            "run_manifest_refs": {"run_manifest"},
            "chart_refs": {"chart"},
            "dataset_refs": {"dataset"},
            "promotion_packet_refs": {"promotion_packet"},
        }
        for name, allowed in expected_kinds.items():
            if any(item.kind not in allowed for item in getattr(self, name)):
                raise DataError(f"{name} contains a reference of the wrong kind")

    def _semantic_dict(self) -> dict[str, object]:
        return {
            "authority": "none",
            "chart_refs": [x.to_dict() for x in self.chart_refs],
            "dataset_refs": [x.to_dict() for x in self.dataset_refs],
            "project_id": self.project_id,
            "projection_refs": [x.to_dict() for x in self.projection_refs],
            "promotion_packet_refs": [x.to_dict() for x in self.promotion_packet_refs],
            "raw_data_included": False,
            "research_contract_id": self.research_contract_id,
            "research_contract_sha256": self.research_contract_sha256,
            "run_manifest_refs": [x.to_dict() for x in self.run_manifest_refs],
            "schema": "StudyWorkspaceManifestV1",
            "schema_version": 1,
            "study_id": self.study_id,
            "verification": "not_checked",
        }

    @property
    def content_sha256(self) -> str:
        return canonical_study_sha256(self._semantic_dict())

    @property
    def workspace_manifest_id(self) -> str:
        return f"workspace_{self.content_sha256}"

    def to_dict(self) -> dict[str, object]:
        return {
            **self._semantic_dict(),
            "content_sha256": self.content_sha256,
            "workspace_manifest_id": self.workspace_manifest_id,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> StudyWorkspaceManifestV1:
        data = _mapping(value, "StudyWorkspaceManifestV1")
        keys = {
            "authority",
            "chart_refs",
            "content_sha256",
            "dataset_refs",
            "project_id",
            "projection_refs",
            "promotion_packet_refs",
            "raw_data_included",
            "research_contract_id",
            "research_contract_sha256",
            "run_manifest_refs",
            "schema",
            "schema_version",
            "study_id",
            "verification",
            "workspace_manifest_id",
        }
        _strict_keys(data, keys, "StudyWorkspaceManifestV1")
        if (
            data["schema"],
            data["schema_version"],
            data["authority"],
            data["verification"],
            data["raw_data_included"],
        ) != ("StudyWorkspaceManifestV1", 1, "none", "not_checked", False):
            raise DataError("StudyWorkspaceManifestV1 is a reference-only workspace")
        for name in (
            "projection_refs",
            "run_manifest_refs",
            "chart_refs",
            "dataset_refs",
            "promotion_packet_refs",
        ):
            if not isinstance(data[name], list):
                raise DataError(f"{name} must be a JSON array")
        result = cls(
            cast(str, data["project_id"]),
            cast(str, data["study_id"]),
            cast(str, data["research_contract_id"]),
            cast(str, data["research_contract_sha256"]),
            _refs("projection_refs", data["projection_refs"]),
            _refs("run_manifest_refs", data["run_manifest_refs"]),
            _refs("chart_refs", data["chart_refs"]),
            _refs("dataset_refs", data["dataset_refs"]),
            _refs("promotion_packet_refs", data["promotion_packet_refs"], allow_empty=True),
        )
        _check_hash(data, result.content_sha256, "workspace_manifest_id", "workspace")
        return result


__all__ = [
    "AdvisorProposalV1",
    "FindingV1",
    "MechanismEdgeV1",
    "MechanismGraphV1",
    "MechanismNodeV1",
    "ProjectionRefV1",
    "StudyWorkspaceManifestV1",
]
