"""Immutable synthetic position artifacts, distinct from statistical research evidence."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from alpha_cli import _artifacts
from alpha_cli._native_rule_protocol import (
    canonical,
    contract_is_costed,
    position_payload,
    selected_study,
    sha,
    study_data_hash,
    validate_rule_contract,
    worker_request,
)
from alpha_cli.artifact_contract import verify_manifest_artifacts
from alpha_core import DataError

PILOT_COMMAND = "research_rule_pilot_v1"
NATIVE_COMMAND = "research_rule_native_v1"


def d0_fingerprint(contract: Mapping[str, object]) -> str:
    from alpha_cli._native_daily_rule_protocol import contract_is_daily, validate_daily_contract

    if contract_is_daily(contract):
        return sha({"runtime": "DailyRuleD0V1", "operator": validate_daily_contract(contract)})
    return sha({"runtime": "SyntheticRuleD0V1", "operator": validate_rule_contract(contract)})


def publish_rule_run(
    data_dir: Path,
    *,
    project_id: str,
    contract_id: str,
    contract: Mapping[str, object],
    execution_fingerprint: str,
    native_receipt: Mapping[str, object] | None = None,
    native_receipt_bytes: bytes | None = None,
) -> dict[str, Any]:
    from alpha_cli._native_daily_rule_protocol import contract_is_daily

    if contract_is_daily(contract):
        from alpha_cli._native_daily_rule_artifacts import publish_daily_rule_run

        return publish_daily_rule_run(
            data_dir,
            project_id=project_id,
            contract_id=contract_id,
            contract=contract,
            execution_fingerprint=execution_fingerprint,
            native_receipt=native_receipt,
            native_receipt_bytes=native_receipt_bytes,
        )
    if native_receipt is not None and (
        native_receipt_bytes is None
        or canonical(json.loads(native_receipt_bytes)) != canonical(native_receipt)
    ):
        raise DataError("native publication requires the captured validated receipt bytes")
    if native_receipt is None and native_receipt_bytes is not None:
        raise DataError("D0 publication cannot carry native receipt bytes")
    operator = validate_rule_contract(contract)
    costed = contract_is_costed(contract)
    economics: dict[str, object] | None = None
    if native_receipt is not None and costed:
        from alpha_cli._native_rule_economics import validate_costed_result

        # Pure validation before the first artifact write; publication order is unchanged.
        economics = validate_costed_result(native_receipt.get("economics"))
    fixture = operator["fixture"]
    assert isinstance(fixture, dict)
    dataset_hash = (
        fixture["definition_fingerprint"] if native_receipt is None else study_data_hash(costed)
    )
    command = PILOT_COMMAND if native_receipt is None else NATIVE_COMMAND
    if costed and native_receipt is not None:
        command = "research_rule_costed_native_v1"
    identity = {
        "command": command,
        "project_id": project_id,
        "research_contract_id": contract_id,
        "contract_hash": sha(contract),
        "dataset_hash": dataset_hash,
        "execution_fingerprint": execution_fingerprint,
    }
    run_id = sha(identity)[:16]
    rdir = _artifacts.run_dir(data_dir, run_id)
    result = position_payload(costed)
    for name, payload in (
        (
            "baseline.json",
            {
                "schema": "RulePositionArtifactV1",
                "unit": "position",
                "positions": result["baseline"],
            },
        ),
        (
            "control.json",
            {
                "schema": "RulePositionArtifactV1",
                "unit": "position",
                "positions": result["control"],
            },
        ),
        (
            "d0_acceptance.json" if native_receipt is None else "rule_positions.json",
            {
                "schema": "SyntheticRuleD0AcceptanceV1"
                if native_receipt is None
                else "SyntheticNativeRuleResultV1",
                **identity,
                "run_id": run_id,
                "positions": result,
                "study": selected_study(costed).to_dict(),
            },
        ),
    ):

        def write_json(path: Path, text: str = canonical(payload)) -> None:
            path.write_text(text)

        _artifacts.publish_artifact(rdir / name, write_json)
    if native_receipt is not None and economics is not None:
        from alpha_cli._native_rule_projection import publish_projections

        selectors = publish_projections(
            data_dir,
            run_id,
            dict(native_receipt),
            source_fingerprint=str(cast(dict[str, object], contract["hashes"])["code"]),
        )
        _artifacts.publish_artifact(
            rdir / "projections.json", lambda path: path.write_text(canonical(selectors))
        )
        _artifacts.publish_artifact(
            rdir / "economics.json", lambda path: path.write_text(canonical(economics))
        )
    if native_receipt_bytes is not None:
        _artifacts.publish_artifact(
            rdir / "native_receipt.json", lambda path: path.write_bytes(native_receipt_bytes)
        )
    manifest = {
        **identity,
        "run_id": run_id,
        "run_identity_version": 3,
        "kind": "research",
        "source_pack_id": contract["source_pack_id"],
        "research_fingerprints": contract["hashes"],
        "evidence_zone": "D0" if native_receipt is None else "D1",
        "synthetic": True,
        "real_market_evidence": False,
        "scientific_acceptance": "not_admitted",
        "eligible_for_holdout_or_execution": False,
        "places_orders": False,
        "snapshot_id": None,
        "snapshot_hash": None,
        "strategy_fingerprint": None,
        "source_fingerprint": sha(contract),
        "d0_operator": operator,
        "d0_operator_fingerprint": operator["fingerprint"],
        "d0_acceptance_artifact": "d0_acceptance.json",
    }
    _artifacts.write_manifest(rdir, manifest)
    return _artifacts.read_manifest(rdir)


def validate_rule_artifacts(
    rdir: Path, manifest: Mapping[str, object], contract: Mapping[str, object]
) -> None:
    from alpha_cli._native_daily_rule_protocol import contract_is_daily

    if contract_is_daily(contract):
        from alpha_cli._native_daily_rule_artifacts import validate_daily_rule_artifacts

        validate_daily_rule_artifacts(rdir, manifest, contract)
        return
    operator = validate_rule_contract(contract)
    costed = contract_is_costed(contract)
    verify_manifest_artifacts(rdir, manifest)
    native = manifest.get("command") in {NATIVE_COMMAND, "research_rule_costed_native_v1"}
    expected_command = (
        ("research_rule_costed_native_v1" if costed else NATIVE_COMMAND)
        if native
        else PILOT_COMMAND
    )
    if manifest.get("command") != expected_command or manifest.get("d0_operator") != operator:
        raise DataError("fixed rule artifact command/operator changed")
    result = position_payload(costed)
    identity = {
        key: manifest[key]
        for key in (
            "command",
            "project_id",
            "research_contract_id",
            "contract_hash",
            "dataset_hash",
            "execution_fingerprint",
        )
    }
    parent_run_id = sha(identity)[:16]
    if manifest.get("run_id") != parent_run_id or rdir.name != parent_run_id:
        raise DataError("fixed rule parent identity differs from its immutable run path")
    expected = {
        "baseline.json": {
            "schema": "RulePositionArtifactV1",
            "unit": "position",
            "positions": result["baseline"],
        },
        "control.json": {
            "schema": "RulePositionArtifactV1",
            "unit": "position",
            "positions": result["control"],
        },
        "rule_positions.json" if native else "d0_acceptance.json": {
            "schema": "SyntheticNativeRuleResultV1" if native else "SyntheticRuleD0AcceptanceV1",
            **identity,
            "run_id": manifest["run_id"],
            "positions": result,
            "study": selected_study(costed).to_dict(),
        },
    }
    for name, payload in expected.items():
        if (rdir / name).read_text() != canonical(payload):
            raise DataError("fixed rule artifact fails exact mechanical recomputation")
    if native:
        receipt = json.loads((rdir / "native_receipt.json").read_text())
        admission = receipt.get("admission")
        if (
            not isinstance(admission, dict)
            or admission.get("rule_request") != worker_request(costed)
            or admission.get("study_id") != selected_study(costed).content_sha256
            or admission.get("trial_id") != admission.get("reservation_id")
            or admission.get("spec_sha256") != manifest.get("execution_fingerprint")
            or receipt.get("binding_sha256") != sha(admission)
            or receipt.get("rule_positions") != result
        ):
            raise DataError("native rule receipt disagrees with the frozen positions")

        if costed:
            from alpha_cli._native_rule_economics import validate_costed_result

            economics = validate_costed_result(receipt.get("economics"))
            from alpha_cli._native_rule_projection import validate_projections

            validate_projections(
                rdir.parent.parent,
                json.loads((rdir / "projections.json").read_text()),
                receipt,
                parent_run_id=parent_run_id,
                source_fingerprint=str(cast(dict[str, object], contract["hashes"])["code"]),
            )
            if (rdir / "economics.json").read_text() != canonical(economics):
                raise DataError("costed raw artifact differs from native execution receipt")
