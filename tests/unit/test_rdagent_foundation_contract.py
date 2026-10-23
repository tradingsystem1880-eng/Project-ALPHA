from __future__ import annotations

import ast
import copy
import json
import math
import os
import subprocess
import sys
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest
from rdagent_foundation_contract import (
    ManifestValidationError,
    RDNativeFoundationManifestV1,
    validate_manifest,
)

from alpha_core import DataError
from alpha_research import ResearchArtifactRef
from alpha_research._canonical import canonical_sha256
from alpha_study import ExplorationMandateV1, FeatureInputRefV1

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "rdagent_foundation" / "manifest_v1.json"
HASH = "a" * 64


def _golden() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(FIXTURE.read_text(encoding="utf-8")))


def _reverse_mappings(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _reverse_mappings(value[key]) for key in reversed(tuple(value))}
    if isinstance(value, list):
        return [_reverse_mappings(item) for item in value]
    return value


def _mandate() -> ExplorationMandateV1:
    return ExplorationMandateV1(
        project_id="123e4567-e89b-12d3-a456-426614174000",
        study_id="study-fixture",
        research_contract_id=f"rc_{HASH}",
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
        source_d0_attempt_id=f"ra_{HASH}",
        source_d0_run_id="0123456789abcdef",
        source_d0_reservation_id=f"rl_{HASH}",
        source_d0_config_fingerprint=HASH,
        source_d0_acceptance_sha256=HASH,
        operator_registration_refs=((f"opreg_{HASH}", HASH),),
        detector_validation_refs=((f"detval_{HASH}", HASH),),
        dataset_snapshot_sha256s=(HASH,),
    )


def test_golden_round_trip_has_exact_fixed_contract() -> None:
    fixture = _golden()
    manifest = validate_manifest(fixture)

    assert isinstance(manifest, RDNativeFoundationManifestV1)
    assert manifest.to_dict() == fixture
    assert manifest.content_sha256 == fixture["content_sha256"]
    assert manifest.canonical_json() == json.dumps(
        fixture,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    assert fixture["execution_enabled"] is False
    assert fixture["native_runtime_qualification"] == "not_run"
    assert fixture["contract_roles"]["intermediate_feedback"] == "not_defined"


def test_digest_uses_alpha_canonical_json_convention() -> None:
    fixture = _golden()
    unsigned = {key: value for key, value in fixture.items() if key != "content_sha256"}

    assert canonical_sha256(unsigned) == fixture["content_sha256"]
    assert validate_manifest(_reverse_mappings(fixture)).content_sha256 == fixture["content_sha256"]
    changed = copy.deepcopy(unsigned)
    changed["purpose"] = "preparatory_contract_changed"
    assert canonical_sha256(changed) != fixture["content_sha256"]


def test_digest_is_stable_across_hash_seed_and_timezone() -> None:
    payload = json.dumps(_golden(), separators=(",", ":"), ensure_ascii=False)
    script = (
        "import json; from rdagent_foundation_contract import validate_manifest; "
        f"print(validate_manifest(json.loads({payload!r})).content_sha256)"
    )
    scripts = str(ROOT / "scripts")
    results: list[str] = []
    for seed, timezone in (("1", "UTC"), ("777", "Pacific/Kiritimati")):
        env = os.environ.copy()
        env["PYTHONPATH"] = scripts
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PYTHONHASHSEED"] = seed
        env["TZ"] = timezone
        completed = subprocess.run(
            [sys.executable, "-c", script],
            check=True,
            capture_output=True,
            text=True,
            env=env,
            cwd=ROOT,
        )
        results.append(completed.stdout.strip())

    assert results == [_golden()["content_sha256"]] * 2


@pytest.mark.parametrize(
    ("mutation", "value"),
    [
        ("schema", "RDNativeFoundationManifestV2"),
        ("schema_version", True),
        ("schema_version", math.nan),
        ("authority", "human_owner"),
        ("purpose", "runtime_configuration"),
        ("execution_enabled", True),
        ("native_runtime_qualification", "qualified"),
    ],
)
def test_manifest_rejects_wrong_types_and_stronger_states(mutation: str, value: object) -> None:
    altered = _golden()
    altered[mutation] = value

    with pytest.raises(ManifestValidationError):
        validate_manifest(altered)


@pytest.mark.parametrize(
    "field",
    [
        "missing_field",
        "step_n",
        "loop_n",
        "remaining_budget",
        "attempt_count",
        "reservation_id",
        "verification",
        "launch_authority",
        "runtime_config",
    ],
)
def test_manifest_rejects_missing_or_unrequested_authority_and_runtime_fields(field: str) -> None:
    altered = _golden()
    if field == "missing_field":
        del altered["purpose"]
    else:
        altered[field] = 1

    with pytest.raises(ManifestValidationError):
        validate_manifest(altered)


def test_manifest_rejects_malformed_content_hash() -> None:
    for digest in ("A" * 64, "f" * 63, 1, math.nan):
        altered = _golden()
        altered["content_sha256"] = digest
        with pytest.raises(ManifestValidationError, match="content_sha256"):
            validate_manifest(altered)


def test_manifest_rejects_well_formed_but_incorrect_content_hash() -> None:
    altered = _golden()
    altered["content_sha256"] = "0" * 64

    with pytest.raises(ManifestValidationError, match="content_sha256"):
        validate_manifest(altered)


@pytest.mark.parametrize(
    ("index", "field", "value"),
    [
        (0, "git_blob_sha", "0" * 40),
        (0, "path", "https://example.invalid/rd_loop.py"),
        (0, "path", "../rd_loop.py"),
        (0, "symbols", ["__import__('os').system('true')"]),
    ],
)
def test_source_inventory_is_fixed_and_symbols_are_inert(
    index: int, field: str, value: object
) -> None:
    altered = _golden()
    altered["source_inventory"][index][field] = value

    with pytest.raises(ManifestValidationError):
        validate_manifest(altered)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("stages", ["direct_exp_gen", "coding", "feedback", "running", "record"]),
        ("stages", ["direct_exp_gen", "coding", "running", "feedback", "feedback"]),
        ("loop_base", "rdagent.components.workflow.rd_loop.RDLoop"),
    ],
)
def test_native_stage_and_primitive_declarations_are_closed(field: str, value: object) -> None:
    altered = _golden()
    altered["intended_native_primitive"][field] = value

    with pytest.raises(ManifestValidationError):
        validate_manifest(altered)


def test_contract_roles_reject_payloads_and_terminal_feedback_substitution() -> None:
    artifact = ResearchArtifactRef("artifact-1", "table", "application/json", HASH, 1, 1)
    with pytest.raises(FrozenInstanceError):
        artifact.artifact_id = "changed"  # type: ignore[misc]

    artifact_reference = FeatureInputRefV1(
        artifact=artifact,
        input_available_at=datetime(2026, 1, 1, tzinfo=UTC),
        snapshot_id="snapshot-1",
        snapshot_manifest_sha256=HASH,
        provider="fixture",
        data_family="daily_bars",
        frequency="1d",
        venue="XNAS",
    )
    assert FeatureInputRefV1.from_dict(artifact_reference.to_dict()) == artifact_reference
    altered_reference = cast(dict[str, Any], artifact_reference.to_dict())
    altered_reference["artifact"]["path"] = "../private/result.json"
    with pytest.raises(DataError):
        FeatureInputRefV1.from_dict(altered_reference)

    for replacement in (
        artifact.to_dict(),
        {"path": "data/result.json", "content_sha256": HASH},
        "file:///private/data/result.json",
        "rdagent.core.proposal.HypothesisFeedback",
    ):
        altered = _golden()
        altered["contract_roles"]["artifact_reference"] = replacement
        with pytest.raises(ManifestValidationError):
            validate_manifest(altered)

    altered = _golden()
    altered["contract_roles"]["intermediate_feedback"] = "ResearchGatePacketV1"
    with pytest.raises(ManifestValidationError):
        validate_manifest(altered)


def test_existing_d1_mandate_flags_and_hash_scope_remain_reference_only() -> None:
    mandate = _mandate()
    payload = mandate.to_dict()

    assert payload["stage"] == "D1"
    assert payload["authority"] == "existing_control_plane_reference"
    assert payload["launch_authority"] == "none"
    assert payload["verification"] == "not_checked"
    assert payload["content_sha256"] == mandate.content_sha256
    assert _golden()["contract_roles"]["d1_mandate_reference"] == "ExplorationMandateV1"

    for key, value in (("launch_authority", "d1"), ("verification", "verified")):
        forged = copy.deepcopy(payload)
        forged[key] = value
        with pytest.raises(DataError):
            ExplorationMandateV1.from_dict(forged)

    embedded = _golden()
    embedded["contract_roles"]["d1_mandate_reference"] = payload
    with pytest.raises(ManifestValidationError):
        validate_manifest(embedded)


def test_validator_import_and_parse_have_no_runtime_or_io_surface(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module_path = ROOT / "scripts" / "rdagent_foundation_contract.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    forbidden_imports = {
        "rdagent",
        "alpha_cli",
        "alpha_data",
        "alpha_study",
        "alpha_research",
        "importlib",
        "os",
        "pathlib",
        "requests",
        "socket",
        "sqlite3",
        "subprocess",
        "urllib",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert not any(alias.name.split(".", 1)[0] in forbidden_imports for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".", 1)[0]
            assert root not in forbidden_imports

    class_names = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert not class_names.intersection({"run", "load", "resume", "reserve", "launch"})

    def fail_if_called(*args: object, **kwargs: object) -> None:
        raise AssertionError("validator attempted an external effect")

    monkeypatch.setattr("builtins.open", fail_if_called)
    assert validate_manifest(_golden()).content_sha256 == _golden()["content_sha256"]
    assert not any(name == "rdagent" or name.startswith("rdagent.") for name in sys.modules)
