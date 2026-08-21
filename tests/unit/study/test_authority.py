"""S3b reference-only authority contract tests."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from typing import cast

import pytest

from alpha_core import DataError
from alpha_research import ResearchArtifactRef
from alpha_study import DetectorValidationV1, ExplorationMandateV1, OperatorRegistrationV1

HASH = "a" * 64
ALT_HASH = "b" * 64
PROJECT_ID = "12345678-1234-5678-9234-567812345678"
CONTRACT_ID = "rc_" + HASH
ATTEMPT_ID = "ra_" + HASH
RESERVATION_ID = "rl_" + HASH
RUN_ID = "0123456789abcdef"


def artifact(name: str, *, digest: str = HASH) -> ResearchArtifactRef:
    return ResearchArtifactRef(name, "table", "application/json", digest, 1, 1)


def registration() -> OperatorRegistrationV1:
    return OperatorRegistrationV1.from_registry("double_bottom.v1")


def detector() -> DetectorValidationV1:
    operator = registration()
    return DetectorValidationV1(
        project_id=PROJECT_ID,
        research_contract_id=CONTRACT_ID,
        research_contract_sha256=HASH,
        operator_registration_id=operator.registration_id,
        operator_registration_sha256=operator.content_sha256,
        source_d0_attempt_id=ATTEMPT_ID,
        source_d0_run_id=RUN_ID,
        source_d0_reservation_id=RESERVATION_ID,
        source_d0_config_fingerprint=HASH,
        acceptance_selector="d0_acceptance.json",
        acceptance=artifact("d0_acceptance.json"),
        fixture_definition_sha256=HASH,
        fixture=artifact("fixture.json"),
        observed_table_sha256=HASH,
        validator_code_sha256=HASH,
        validator_environment_sha256=HASH,
    )


def mandate() -> ExplorationMandateV1:
    operator = registration()
    validation = detector()
    return ExplorationMandateV1(
        project_id=PROJECT_ID,
        study_id="study-1",
        research_contract_id=CONTRACT_ID,
        research_contract_sha256=HASH,
        analysis_plan_sha256=HASH,
        topology_sha256=HASH,
        chart_spec_sha256=HASH,
        dataset_sha256=HASH,
        d1_execution_fingerprint=HASH,
        code_sha256=HASH,
        dependency_lock_sha256=HASH,
        environment_sha256=HASH,
        approved_budget_sha256=HASH,
        source_d0_attempt_id=ATTEMPT_ID,
        source_d0_run_id=RUN_ID,
        source_d0_reservation_id=RESERVATION_ID,
        source_d0_config_fingerprint=HASH,
        source_d0_acceptance_sha256=HASH,
        operator_registration_refs=((operator.registration_id, operator.content_sha256),),
        detector_validation_refs=((validation.detector_validation_id, validation.content_sha256),),
        dataset_snapshot_sha256s=(HASH,),
    )


def test_operator_is_closed_git_owned_and_round_trips() -> None:
    value = registration()
    assert OperatorRegistrationV1.from_dict(value.to_dict()) == value
    assert value.to_dict()["registry_owner"] == "git"
    assert value.to_dict()["authority"] == "none"
    assert value.to_dict()["verification"] == "not_checked"
    with pytest.raises(FrozenInstanceError):
        value.description = "changed"  # type: ignore[misc]


def test_operator_canonicalizes_and_rejects_tampering() -> None:
    value = registration()
    reordered = replace(
        value,
        required_fields=("low", "high", "end", "available_at"),
    )
    assert reordered.content_sha256 == value.content_sha256
    for key, replacement in (("operator_id", "other"), ("content_sha256", ALT_HASH)):
        payload = value.to_dict()
        payload[key] = replacement
        with pytest.raises(DataError):
            OperatorRegistrationV1.from_dict(payload)
    with pytest.raises(DataError):
        replace(value, registry_path="../operators.json")
    with pytest.raises(DataError):
        OperatorRegistrationV1.from_registry("unregistered")
    with pytest.raises(DataError):
        replace(value, registry_blob_sha256=ALT_HASH)
    with pytest.raises(DataError):
        OperatorRegistrationV1.from_dict({**value.to_dict(), "status": "approved"})


def test_detector_binds_exact_existing_d0_reference() -> None:
    value = detector()
    assert DetectorValidationV1.from_dict(value.to_dict()) == value
    payload = value.to_dict()
    assert payload["authority"] == "existing_control_plane_reference"
    assert payload["verification"] == "not_checked"
    assert payload["verdict"] == "not_attested"
    assert payload["acceptance_selector"] == "d0_acceptance.json"


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("project_id", "foreign"),
        ("research_contract_id", "rc_bad"),
        ("source_d0_attempt_id", "ra_bad"),
        ("source_d0_run_id", "run-1"),
        ("source_d0_reservation_id", "rl_bad"),
        ("source_d0_config_fingerprint", "not-a-hash"),
        ("acceptance_selector", "acceptance.json"),
    ],
)
def test_detector_rejects_invalid_control_shapes(field: str, replacement: str) -> None:
    payload = detector().to_dict()
    payload[field] = replacement
    with pytest.raises(DataError):
        DetectorValidationV1.from_dict(payload)


def test_detector_rejects_forged_claims_and_child_tamper() -> None:
    value = detector()
    for field in ("passed", "success", "readiness", "status", "approved"):
        with pytest.raises(DataError):
            DetectorValidationV1.from_dict({**value.to_dict(), field: True})
    payload = value.to_dict()
    payload["acceptance"] = artifact("other.json").to_dict()
    with pytest.raises(DataError):
        DetectorValidationV1.from_dict(payload)
    payload = value.to_dict()
    payload["operator_registration_id"] = "opreg_" + ALT_HASH
    with pytest.raises(DataError):
        DetectorValidationV1.from_dict(payload)


def test_mandate_is_reference_only_and_canonical() -> None:
    value = mandate()
    assert ExplorationMandateV1.from_dict(value.to_dict()) == value
    payload = value.to_dict()
    assert payload["stage"] == "D1"
    assert payload["authority"] == "existing_control_plane_reference"
    assert payload["launch_authority"] == "none"
    assert payload["verification"] == "not_checked"
    assert "reservation_id" not in payload
    assert payload["source_d0_reservation_id"] == RESERVATION_ID


def test_mandate_rejects_parallel_authority_and_stale_links() -> None:
    value = mandate()
    for field in ("owner_actor", "status", "remaining_budget", "retry_count", "approved_at"):
        with pytest.raises(DataError):
            ExplorationMandateV1.from_dict({**value.to_dict(), field: "forged"})
    stale = value.to_dict()
    stale["mandate_id"] = "mandate_" + ALT_HASH
    with pytest.raises(DataError):
        ExplorationMandateV1.from_dict(stale)
    stale = value.to_dict()
    stale["d1_execution_fingerprint"] = "not-a-hash"
    with pytest.raises(DataError):
        ExplorationMandateV1.from_dict(stale)
    stale = value.to_dict()
    refs = list(cast(list[dict[str, str]], stale["operator_registration_refs"]))
    refs[0] = {"id": refs[0]["id"], "content_sha256": ALT_HASH}
    stale["operator_registration_refs"] = refs
    with pytest.raises(DataError):
        ExplorationMandateV1.from_dict(stale)


def test_mandate_identity_binds_every_existing_source_reference() -> None:
    value = mandate()
    mutations = (
        replace(value, project_id="87654321-4321-5678-9234-567812345678"),
        replace(value, research_contract_id="rc_" + ALT_HASH),
        replace(value, source_d0_attempt_id="ra_" + ALT_HASH),
        replace(value, source_d0_run_id="fedcba9876543210"),
        replace(value, source_d0_reservation_id="rl_" + ALT_HASH),
        replace(value, source_d0_config_fingerprint=ALT_HASH),
        replace(value, source_d0_acceptance_sha256=ALT_HASH),
        replace(value, d1_execution_fingerprint=ALT_HASH),
    )
    assert all(mutated.content_sha256 != value.content_sha256 for mutated in mutations)
