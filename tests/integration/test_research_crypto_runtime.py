from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from alpha_cli import research_cmds
from alpha_cli.research_crypto_runtime import (
    crypto_d0_execution_fingerprint,
    registered_crypto_d0_operator,
    run_crypto_crowding_pilot,
    validate_crypto_d0_acceptance_artifact,
    validate_crypto_d0_contract,
)
from alpha_core import DataError
from alpha_research import registered_crypto_crowding_plan

PROJECT_ID = "f03802b8-df35-4f19-a90c-0b3437aa587d"
CONTRACT_ID = f"rc_{'a' * 64}"


def _contract() -> dict[str, object]:
    return {
        "answer_bundle_id": registered_crypto_crowding_plan().bundle_id,
        "source_pack_id": f"rsp_{'b' * 64}",
        "hashes": {
            "code": "1" * 64,
            "dependency_lock": "2" * 64,
            "environment": "3" * 64,
            "evaluator": "4" * 64,
            "data": None,
        },
        "protocol": {"d0_operator": registered_crypto_d0_operator()},
    }


def _contract_hash(contract: dict[str, object]) -> str:
    canonical = json.dumps(contract, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


def test_crypto_d0_runtime_publishes_idempotent_recomputable_non_evidence(
    tmp_path: Path,
) -> None:
    contract = _contract()
    assert research_cmds._is_crypto_crowding_contract(contract) is True
    assert research_cmds._validate_registered_d0_contract(contract) == (
        registered_crypto_d0_operator()
    )
    assert research_cmds._registered_d0_execution_fingerprint(contract) == (
        crypto_d0_execution_fingerprint(contract)
    )
    manifest = research_cmds._run_registered_d0_pilot(
        tmp_path,
        project_id=PROJECT_ID,
        contract_id=CONTRACT_ID,
        contract=contract,
    )
    repeated = run_crypto_crowding_pilot(
        tmp_path,
        project_id=PROJECT_ID,
        contract_id=CONTRACT_ID,
        contract=contract,
    )

    assert repeated == manifest
    assert manifest["evidence_zone"] == "D0"
    assert manifest["real_market_evidence"] is False
    assert manifest["eligible_for_holdout_or_execution"] is False
    assert manifest["places_orders"] is False
    assert manifest["snapshot_id"] is None
    assert manifest["d0_operator"] == registered_crypto_d0_operator()
    fixture = manifest["d0_operator"]["fixture"]
    assert fixture["fixture_id"] == "bybit_btcusdt_crowding_d0_v2"
    assert fixture["fixture_version"] == 2
    acceptance = validate_crypto_d0_acceptance_artifact(
        tmp_path / "runs" / str(manifest["run_id"]),
        manifest,
        project_id=PROJECT_ID,
        contract_id=CONTRACT_ID,
        contract_hash=_contract_hash(contract),
        execution_fingerprint=crypto_d0_execution_fingerprint(contract),
    )
    assert acceptance["real_market_evidence"] is False
    assert acceptance["measurements"]["passed"] is True  # type: ignore[index]


def test_crypto_d0_runtime_rejects_contract_drift_and_tampered_acceptance(
    tmp_path: Path,
) -> None:
    contract = _contract()
    drifted = {**contract, "answer_bundle_id": "other"}
    with pytest.raises(DataError, match="answer bundle"):
        validate_crypto_d0_contract(drifted)

    manifest = run_crypto_crowding_pilot(
        tmp_path,
        project_id=PROJECT_ID,
        contract_id=CONTRACT_ID,
        contract=contract,
    )
    acceptance_path = tmp_path / "runs" / str(manifest["run_id"]) / "d0_acceptance.json"
    os.chmod(acceptance_path, 0o600)
    acceptance_path.write_text("{}", encoding="utf-8")
    with pytest.raises(DataError, match="exact recomputation"):
        validate_crypto_d0_acceptance_artifact(
            acceptance_path.parent,
            manifest,
            project_id=PROJECT_ID,
            contract_id=CONTRACT_ID,
            contract_hash=_contract_hash(contract),
            execution_fingerprint=crypto_d0_execution_fingerprint(contract),
        )
