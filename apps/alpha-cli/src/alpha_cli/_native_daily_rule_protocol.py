"""Registered bounded daily discovery route; no approval or numerical effects here."""

from __future__ import annotations

import hashlib
import json
import math
import os
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from alpha_cli._native_daily_rule_identity import (
    NAME as NAME,
)
from alpha_cli._native_daily_rule_identity import (
    PLAN_SCHEMA as PLAN_SCHEMA,
)
from alpha_cli._native_daily_rule_identity import (
    contract_is_daily as contract_is_daily,
)
from alpha_cli._native_daily_rule_study import DailyRuleResourcesV1, DailyRuleStudyV1
from alpha_core import DataError
from alpha_data.crypto.contracts import CryptoSnapshotV1
from alpha_strategies.rules import rule_signal, rule_spec_from_json

MAX_DAILY_RECEIPT_BYTES = 32 * 1024 * 1024
DAILY_CHILD_ENV = {
    "OPENBLAS_NUM_THREADS": "1",
    "OMP_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "POLARS_MAX_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
    "MALLOC_ARENA_MAX": "1",
    "_RJEM_MALLOC_CONF": "narenas:1,background_thread:false,retain:false",
}


def daily_resource_command(
    command: list[str], resources: DailyRuleResourcesV1, seconds: float, cpu_milliseconds: int
) -> list[str]:
    """Fixed Linux wrappers enforce CPU, address-space and per-file limits before Python."""
    if (
        not 0 < seconds <= resources.max_wall_seconds
        or type(cpu_milliseconds) is not int
        or not 0 < cpu_milliseconds <= resources.max_wall_seconds * 1000
    ):
        raise DataError("daily child resource reservation differs from owner bounds")
    taskset, prlimit = Path("/usr/bin/taskset"), Path("/usr/bin/prlimit")
    if not taskset.is_file() or not prlimit.is_file() or not hasattr(os, "sched_getaffinity"):
        raise DataError("daily child requires supported Linux resource enforcement")
    cpus = sorted(os.sched_getaffinity(0))
    if not cpus:
        raise DataError("daily child has no available reserved CPU")
    return [
        str(taskset),
        "--cpu-list",
        str(cpus[0]),
        str(prlimit),
        "--as=" + str(resources.max_memory_bytes),
        "--cpu=" + str(math.ceil(cpu_milliseconds / 1000)),
        "--fsize=" + str(resources.max_artifact_bytes),
        "--",
        *command,
    ]


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha(value: object) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def study_from_contract(contract: Mapping[str, object]) -> DailyRuleStudyV1:
    plan = contract.get("analysis_plan")
    if not isinstance(plan, Mapping) or plan.get("schema") != PLAN_SCHEMA:
        raise DataError("daily rule contract requires its versioned plan")
    try:
        return DailyRuleStudyV1.model_validate(plan.get("study"))
    except ValidationError as error:
        raise DataError("daily rule contract study is invalid") from error


def daily_plan(study: DailyRuleStudyV1) -> dict[str, object]:
    return {
        "schema": PLAN_SCHEMA,
        "study": study.to_dict(),
        "trial_limit": 1,
        "control": "same_units_buy_once_hold",
        "repair": "forbidden",
        "continuation": "same_live_owner_only",
        "claim_scope": study.claim_scope,
        "empirical_confirmation_authorized": False,
    }


def validate_daily_plan(plan: Mapping[str, object], *, max_grid_cells: int) -> dict[str, Any]:
    study = study_from_contract({"analysis_plan": plan})
    if (
        type(max_grid_cells) is not int
        or max_grid_cells < 5
        or canonical(plan) != canonical(daily_plan(study))
    ):
        raise DataError("daily rule analysis plan changed or lacks D0/baseline/control allowance")
    return dict(plan)


def daily_operator(study: DailyRuleStudyV1) -> dict[str, object]:
    # D0 remains an independent artificial mechanics fixture, not market acceptance.
    from alpha_cli._native_rule_protocol import registered_rule_operator

    fixture = registered_rule_operator(True)["fixture"]
    body = {
        "schema": "AlphaRegisteredResearchOperatorV1",
        "name": NAME,
        "version": 1,
        "event_availability": "completed_utc_day_next_open_plus_1us",
        "fixture": fixture,
        "study_sha256": study.content_sha256,
        "query_sha256": study.query_sha256,
    }
    return {**body, "fingerprint": sha(body)}


def daily_boundary_authority(study: DailyRuleStudyV1) -> dict[str, object]:
    return {
        "kind": "exploratory_reconstructed_discovery_history",
        "real_market_evidence": study.data_origin == "captured_provider_history",
        "empirical_confirmation_authorized": False,
    }


def daily_topology(study: DailyRuleStudyV1) -> dict[str, object]:
    """All declared rows are discovery; no D2/D3 samples are allocated or releasable."""
    boundary = {
        "schema": "DailyDiscoveryBoundaryV1",
        "snapshot_id": study.snapshot_sha256,
        "query_sha256": study.query_sha256,
        "data_origin": study.data_origin,
        "start": study.discovery_start,
        "end_exclusive": study.discovery_end_exclusive,
        "claim_scope": study.claim_scope,
        "point_in_time_claim": False,
    }
    return {
        "boundary": boundary,
        "D0": {"share": 0.0, "artificial_mechanics_only": True},
        "D1": {"share": 1.0},
        "D2": {"state": "sealed", "share": 0.0, "available": False, "boundary_hash": sha(boundary)},
        "D3": {"state": "sealed", "share": 0.0, "available": False},
    }


def draft_daily_contract(
    source_pack_id: str,
    fingerprints: Mapping[str, str | None],
    budget: Mapping[str, int | float],
    study: DailyRuleStudyV1,
) -> dict[str, object]:
    """Inert exact draft; independent owner confirmation and source reopening remain mandatory."""
    return {
        "schema": "ResearchContractV1",
        "scope": "exploration",
        "approval_ready": True,
        "blocking_questions": [],
        "thesis": {
            "primary_claims": [
                {
                    "claim": (
                        "Frozen daily rule versus same-unit buy and hold; "
                        "exploratory result, including loss/null"
                    )
                }
            ]
        },
        "source_pack_id": source_pack_id,
        "analysis_plan": daily_plan(study),
        "protocol": {
            "d0_operator": daily_operator(study),
            "boundary_authority": daily_boundary_authority(study),
            "evidence_topology": daily_topology(study),
        },
        "budget": dict(budget),
        "hashes": dict(fingerprints),
    }


def validate_daily_contract(contract: Mapping[str, object]) -> dict[str, object]:
    study = study_from_contract(contract)
    protocol, budget, hashes = (contract.get(key) for key in ("protocol", "budget", "hashes"))
    if (
        set(contract)
        != {
            "schema",
            "scope",
            "approval_ready",
            "blocking_questions",
            "thesis",
            "source_pack_id",
            "analysis_plan",
            "protocol",
            "budget",
            "hashes",
        }
        or contract.get("schema") != "ResearchContractV1"
        or not contract_is_daily(contract)
        or not isinstance(protocol, Mapping)
        or set(protocol) != {"d0_operator", "boundary_authority", "evidence_topology"}
        or canonical(protocol.get("d0_operator")) != canonical(daily_operator(study))
        or protocol.get("boundary_authority") != daily_boundary_authority(study)
        or canonical(protocol.get("evidence_topology")) != canonical(daily_topology(study))
        or contract.get("scope") != "exploration"
        or not isinstance(budget, Mapping)
        or not isinstance(hashes, Mapping)
        or set(hashes) != {"code", "dependency_lock", "environment", "evaluator", "data"}
    ):
        raise DataError("daily rule operator/version/exploratory authority binding changed")
    variants = budget.get("variants")
    if type(variants) is not int or variants != 5:
        raise DataError("daily rule requires exactly three D0 and two execution exposures")
    for key in ("model_calls", "input_tokens", "output_tokens", "tool_calls"):
        if (
            type(budget.get("rdagent_native_v1_" + key)) is not int
            or budget.get("rdagent_native_v1_" + key) != 0
        ):
            raise DataError("daily rule forbids model/token/tool effects")
    if (
        type(budget.get("wall_seconds")) not in (int, float)
        or not 0 < budget["wall_seconds"] <= study.resources.max_wall_seconds
        or type(budget.get("rdagent_native_v1_cpu_milliseconds")) is not int
        or not 0
        < budget["rdagent_native_v1_cpu_milliseconds"]
        <= study.resources.max_wall_seconds * 1000
        or budget.get("rdagent_native_v1_loop_steps") != 5
        or hashes.get("data") != study.query_sha256
        or hashes.get("environment") != study.runtime_profile_sha256
    ):
        raise DataError("daily rule budget/profile/query differs from frozen study bounds")
    plan = contract["analysis_plan"]
    assert isinstance(plan, Mapping)
    validate_daily_plan(plan, max_grid_cells=variants)
    return daily_operator(study)


def daily_worker_request(study: DailyRuleStudyV1) -> dict[str, object]:
    query = json.loads(study.query_document)
    return {
        "study": study.to_dict(),
        "study_sha256": study.content_sha256,
        "bars": [
            [row[key] for key in ("open_time", "open", "high", "low", "close", "base_volume")]
            for row in query["rows"]
        ],
    }


def daily_position_payload(study: DailyRuleStudyV1) -> dict[str, object]:
    """Pure deterministic signal projection; confers neither admission nor acceptance."""
    request = daily_worker_request(study)
    bars = request["bars"]
    assert isinstance(bars, list)
    spec = rule_spec_from_json(study.rules_spec)
    baseline = [
        rule_signal(
            spec,
            [b[2] for b in bars[:stop]],
            [b[3] for b in bars[:stop]],
            [b[4] for b in bars[:stop]],
        )
        for stop in range(study.warmup_bars + 1, len(bars) + 1)
    ]
    return {
        "schema": "DailyRulePositionsV1",
        "study_sha256": study.content_sha256,
        "baseline": baseline,
        "control": [1] * len(baseline),
        "unit": "position",
        "evidence_zone": "D1",
        "data_origin": study.data_origin,
        "real_market_evidence": study.data_origin == "captured_provider_history",
        "scientific_acceptance": "not_admitted",
    }


def reopen_daily_study(root: Path, study: DailyRuleStudyV1) -> None:
    """Reopen actual immutable storage and reproduce the exact bound query before effects."""
    from alpha_cli.crypto_bulk_store import configured_crypto_bulk_store
    from alpha_cli.crypto_price_snapshot_query import query_binance_daily_price_snapshot

    config = root / "crypto" / "storage-config.json"
    snapshot_path = root / "crypto" / "snapshots" / (study.snapshot_sha256 + ".json")
    for path in (config, snapshot_path):
        if path.is_symlink() or any(parent.is_symlink() for parent in path.parents):
            raise DataError("daily study storage path is unsafe")
    try:
        with config.open("rb") as stream:
            raw_config = stream.read(8193)
        if len(raw_config) > 8192:
            raise DataError("daily study storage profile exceeds its bounded size")
        if hashlib.sha256(raw_config).hexdigest() != study.storage_config_sha256:
            raise DataError("daily study storage profile changed after freeze")
        with snapshot_path.open("rb") as stream:
            raw_snapshot = stream.read(65537)
        if len(raw_snapshot) > 65536:
            raise DataError("daily study source snapshot exceeds its bounded size")
        snapshot = CryptoSnapshotV1.from_dict(json.loads(raw_snapshot))
    except (OSError, ValueError) as error:
        raise DataError("daily study storage/snapshot is unavailable") from error
    if snapshot.snapshot_id != study.snapshot_sha256:
        raise DataError("daily study snapshot identity differs")
    query = json.loads(study.query_document)
    actual = query_binance_daily_price_snapshot(
        snapshot,
        configured_crypto_bulk_store(root),
        normalized_manifest_id=query["normalized_manifest_id"],
        start=datetime.fromisoformat(study.discovery_start),
        end=datetime.fromisoformat(study.discovery_end_exclusive),
        available_by=datetime.fromisoformat(study.discovery_end_exclusive),
    )
    if (
        actual.content_sha256 != study.query_sha256
        or canonical(actual.to_dict()) != study.query_document
    ):
        raise DataError("daily study query no longer reproduces frozen source/profile/rows")
