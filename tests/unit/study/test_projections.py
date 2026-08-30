"""S3c derived projection contract tests."""

from __future__ import annotations

from dataclasses import replace

import pytest

from alpha_core import DataError
from alpha_research import ResearchArtifactRef
from alpha_study import (
    AdvisorProposalV1,
    FindingV1,
    MechanismEdgeV1,
    MechanismGraphV1,
    MechanismNodeV1,
    ProjectionRefV1,
    StudyWorkspaceManifestV1,
)

HASH = "a" * 64
ALT = "b" * 64
PROJECT = "12345678-1234-5678-9234-567812345678"
CONTRACT = "rc_" + HASH
ATTEMPT = "ra_" + HASH
RUN = "0123456789abcdef"


def ref(ref_id: str | None = None, *, kind: str = "finding", digest: str = HASH) -> ProjectionRefV1:
    prefixes = {
        "advisor_proposal": "advisor",
        "context_packet": "cp",
        "dataset": "rd",
        "finding": "finding",
        "mechanism_graph": "mechanism",
        "note": "rn",
        "promotion_packet": "cp",
        "research_contract": "rc",
        "screened_claim": "sc",
    }
    resolved = ref_id or (RUN if kind == "run_manifest" else f"{prefixes[kind]}_{digest}")
    return ProjectionRefV1(resolved, digest, kind)


def finding(*, zone: str = "D1") -> FindingV1:
    return FindingV1(
        PROJECT,
        CONTRACT,
        HASH,
        ATTEMPT,
        RUN,
        ResearchArtifactRef(
            "research_gate_evidence.json", "report", "application/json", HASH, 10, None
        ),
        zone,
        "EXPLORATORY" if zone == "D1" else "REGISTERED CONFIRMATORY",
        "multiplicity" if zone == "D1" else "confirmation_classification",
        "PASSED" if zone == "D1" else "SUPPORTED",
        "Copied typed evidence summary.",
    )


def graph() -> MechanismGraphV1:
    source = ref(kind="research_contract")
    nodes = (
        MechanismNodeV1("mechanism", "proposed_mechanism", "Recorded proposal", source),
        MechanismNodeV1("confounder", "confounder", "Recorded confounder", source),
    )
    edge = MechanismEdgeV1("confounder", "mechanism", "confounds", source)
    return MechanismGraphV1(PROJECT, CONTRACT, HASH, nodes, (edge,))


def proposal() -> AdvisorProposalV1:
    return AdvisorProposalV1(
        PROJECT,
        CONTRACT,
        HASH,
        (ref(),),
        ("collect_qualified_source", "inspect_recorded_contradiction"),
        "The mechanism remains uncertain.",
        "Revisit only if new qualified evidence is recorded.",
    )


def workspace() -> StudyWorkspaceManifestV1:
    return StudyWorkspaceManifestV1(
        PROJECT,
        "study-1",
        CONTRACT,
        HASH,
        (ref(), ref(kind="mechanism_graph")),
        (ref(kind="run_manifest"),),
        (ref("chart-1", kind="chart"),),
        (ref(kind="dataset"),),
    )


def test_finding_round_trip_and_exact_typed_evidence_binding() -> None:
    value = finding()
    assert FindingV1.from_dict(value.to_dict()) == value
    assert value.to_dict()["authority"] == "none"
    assert value.to_dict()["verification"] == "not_checked"
    assert finding(zone="D2").watermark == "REGISTERED CONFIRMATORY"
    with pytest.raises(DataError):
        replace(value, watermark="REGISTERED CONFIRMATORY")
    with pytest.raises(DataError):
        replace(
            value,
            source_artifact=ResearchArtifactRef(
                "notes.json", "report", "application/json", HASH, 1
            ),
        )


def test_finding_rejects_free_or_authority_shaped_claims() -> None:
    value = finding()
    for field in ("approved", "pass", "promotion_ready", "paper_ready", "owner_actor", "d2_reveal"):
        with pytest.raises(DataError):
            FindingV1.from_dict({**value.to_dict(), field: True})
    stale = value.to_dict()
    stale["summary"] = "Changed"
    with pytest.raises(DataError):
        FindingV1.from_dict(stale)
    with pytest.raises(DataError):
        replace(value, finding_id="agent_conclusion")
    with pytest.raises(DataError):
        replace(value, finding_id="confirmation_classification")


def test_mechanism_graph_is_canonical_reference_graph_only() -> None:
    value = graph()
    assert MechanismGraphV1.from_dict(value.to_dict()) == value
    assert replace(value, nodes=tuple(reversed(value.nodes))).content_sha256 == value.content_sha256
    with pytest.raises(DataError):
        replace(value, nodes=(value.nodes[0], value.nodes[0]))
    with pytest.raises(DataError):
        replace(value, edges=(MechanismEdgeV1("missing", "mechanism", "annotates", ref()),))
    with pytest.raises(DataError):
        MechanismEdgeV1("a", "b", "causes", ref())
    with pytest.raises(DataError):
        MechanismEdgeV1("a", "b", "supports_context", ref(kind="research_contract"))


def test_advisor_is_proposal_only_and_order_deterministic() -> None:
    value = proposal()
    assert AdvisorProposalV1.from_dict(value.to_dict()) == value
    assert value.to_dict()["evidence_status"] == "proposal_only"
    assert (
        replace(value, actions=tuple(reversed(value.actions))).content_sha256
        == value.content_sha256
    )
    for field in ("priority", "score", "advance", "launch", "approved", "budget"):
        with pytest.raises(DataError):
            AdvisorProposalV1.from_dict({**value.to_dict(), field: True})
    with pytest.raises(DataError):
        replace(value, actions=("launch_d1_and_approve_promotion",))


def test_workspace_contains_references_not_raw_or_mutable_authority() -> None:
    value = workspace()
    assert StudyWorkspaceManifestV1.from_dict(value.to_dict()) == value
    payload = value.to_dict()
    assert payload["raw_data_included"] is False
    assert payload["authority"] == "none"
    for field in ("raw_data", "artifact_path", "remaining_budget", "owner_decision", "d3_data"):
        with pytest.raises(DataError):
            StudyWorkspaceManifestV1.from_dict({**payload, field: "forged"})


def test_workspace_and_refs_reject_duplicates_and_tampering() -> None:
    value = workspace()
    assert (
        replace(value, projection_refs=tuple(reversed(value.projection_refs))).content_sha256
        == value.content_sha256
    )
    with pytest.raises(DataError):
        replace(value, projection_refs=(value.projection_refs[0], value.projection_refs[0]))
    with pytest.raises(DataError):
        replace(value, dataset_refs=(ref(kind="finding"),))
    stale = value.to_dict()
    stale["workspace_manifest_id"] = "workspace_" + ALT
    with pytest.raises(DataError):
        StudyWorkspaceManifestV1.from_dict(stale)
    with pytest.raises(DataError):
        ProjectionRefV1("x", "not-a-hash", "finding")
