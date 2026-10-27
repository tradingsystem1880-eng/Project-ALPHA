"""Closed synthetic rule protocol. Engineering approval never establishes market evidence."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

from alpha_cli._native_rule_economics import CostedRuleStudy, fixed_costed_study
from alpha_cli._native_rule_study import _CONTROL, _DATA_SHA256, _RULE, SyntheticRuleStudy
from alpha_core import DataError
from alpha_research import (
    EqualDurationResearchBars,
    ResearchArtifactRef,
    ResearchBar,
    ResearchDatasetRef,
)
from alpha_strategies.rules import rule_signal, rule_spec_from_json

NAME = "synthetic_frozen_rule_positions"
PLAN_SCHEMA = "FrozenRulePositionsPlanV1"


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha(value: object) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def fixed_study() -> SyntheticRuleStudy:
    start = datetime(2000, 1, 1, tzinfo=UTC)
    dataset = ResearchDatasetRef(
        dataset_id="synthetic-rules-v1",
        provider="synthetic",
        provider_symbol="RULES",
        symbol="RULES",
        venue="SYNTHETIC",
        timeframe="1d",
        timezone="UTC",
        session="UTC_DAY",
        content_sha256=_DATA_SHA256,
    )
    bars = tuple(
        ResearchBar(
            dataset_id=dataset.dataset_id,
            start=start + timedelta(days=i),
            end=start + timedelta(days=i + 1),
            available_at=start + timedelta(days=i + 1),
            open=close,
            high=close + 1,
            low=close - 1,
            close=close,
            volume=1.0,
        )
        for i, close in enumerate((8.0, 12.0, 10.0, 16.0, 4.0))
    )
    return SyntheticRuleStudy(
        _RULE,
        _CONTROL,
        EqualDurationResearchBars(dataset, bars),
        ResearchArtifactRef(
            "synthetic-bars.json", "table", "application/json", _DATA_SHA256, 542, 5
        ),
        datetime(2000, 1, 5, tzinfo=UTC),
        1,
        "synthetic_price",
        "position",
        "frozen_rule_positions_v1",
    )


def selected_study(costed: bool = False) -> SyntheticRuleStudy | CostedRuleStudy:
    return fixed_costed_study() if costed else fixed_study()


def study_data_hash(costed: bool = False) -> str:
    return str(fixed_costed_study().to_dict()["data_sha256"]) if costed else _DATA_SHA256


def contract_is_costed(contract: Mapping[str, object]) -> bool:
    plan = contract.get("analysis_plan")
    return isinstance(plan, Mapping) and plan.get("schema") == "FrozenRuleCostedPlanV1"


def rule_plan(costed: bool = False) -> dict[str, Any]:
    return {
        "schema": "FrozenRuleCostedPlanV1" if costed else PLAN_SCHEMA,
        "study": selected_study(costed).to_dict(),
        "trial_limit": 1,
        "control": "predeclared_always_flat_positions",
        "repair": "forbidden",
        "continuation": "same_live_owner_only",
        "real_market_evidence": False,
    }


def validate_rule_plan(plan: Mapping[str, object], *, max_grid_cells: int) -> dict[str, Any]:
    if (
        type(max_grid_cells) is not int
        or max_grid_cells < 1
        or canonical(plan) != canonical(rule_plan(plan.get("schema") == "FrozenRuleCostedPlanV1"))
    ):
        raise DataError("fixed rule analysis plan changed or has no variant allowance")
    return dict(plan)


def is_rule_contract(contract: Mapping[str, object]) -> bool:
    protocol = contract.get("protocol")
    operator = protocol.get("d0_operator") if isinstance(protocol, Mapping) else None
    return isinstance(operator, Mapping) and operator.get("name") == NAME


def registered_rule_operator(costed: bool = False) -> dict[str, object]:
    body = {
        "schema": "AlphaRegisteredResearchOperatorV1",
        "name": NAME,
        "version": 2 if costed else 1,
        "event_availability": "daily_close_available_at",
        "fixture": {
            "fixture_id": "synthetic-rule-costed-v1" if costed else "synthetic-rule-positions-v1",
            "fixture_version": 1,
            "definition_fingerprint": selected_study(costed).content_sha256,
        },
    }
    return {**body, "fingerprint": sha(body)}


def validate_rule_contract(contract: Mapping[str, object]) -> dict[str, object]:
    costed = contract_is_costed(contract)
    protocol = contract.get("protocol")
    if not isinstance(protocol, Mapping) or canonical(protocol.get("d0_operator")) != canonical(
        registered_rule_operator(costed)
    ):
        raise DataError("fixed rule operator version or binding changed")
    if protocol.get("boundary_authority") != {
        "kind": "synthetic_acceptance_fixture",
        "real_market_evidence": False,
        "empirical_confirmation_authorized": False,
    }:
        raise DataError("fixed rule capability is synthetic only")
    plan = contract.get("analysis_plan")
    budget = contract.get("budget")
    if not isinstance(plan, Mapping) or not isinstance(budget, Mapping):
        raise DataError("fixed rule contract requires its plan and budget")
    variants = budget.get("variants")
    if type(variants) is not int or variants < 5:
        raise DataError("fixed rule budget requires D0 plus baseline/control exposures")
    for key in ("model_calls", "input_tokens", "output_tokens", "tool_calls"):
        if budget.get("rdagent_native_v1_" + key) != 0:
            raise DataError("fixed rule protocol forbids model and tool budgets")
    validate_rule_plan(plan, max_grid_cells=variants)
    hashes = contract.get("hashes")
    if not isinstance(hashes, Mapping) or hashes.get("data") != study_data_hash(costed):
        raise DataError("fixed rule data fingerprint changed")
    return registered_rule_operator(costed)


def position_payload(costed: bool = False) -> dict[str, object]:
    if costed:
        document = fixed_costed_study().to_dict()
        rows = document["bars"]
        assert isinstance(rows, list)
        actual = [
            [
                rule_signal(
                    rule_spec_from_json(str(document[key])),
                    [row[2] for row in rows[:stop]],
                    [row[3] for row in rows[:stop]],
                    [row[4] for row in rows[:stop]],
                )
                for stop in range(2, len(rows) + 1)
            ]
            for key in ("rules_spec", "control_spec")
        ]
        if actual != [[0, 1, 0, 1, 0, 0], [0, 0, 0, 0, 0, 0]]:
            raise DataError("costed rule positions disagree with independent reference")
        return {
            "schema": "SyntheticRulePositionsV2",
            "study_sha256": fixed_costed_study().content_sha256,
            "baseline": actual[0],
            "control": actual[1],
            "unit": "position",
            "evidence_zone": "D0",
            "real_market_evidence": False,
            "scientific_acceptance": "not_admitted",
        }
    study = fixed_study()
    bars = tuple(bar for bar in study.data.bars if bar.available_at <= study.cutoff)
    actual = []
    for spec_text in (study.rules_spec, study.control_spec):
        spec = rule_spec_from_json(spec_text)
        actual.append(
            [
                rule_signal(
                    spec,
                    [b.high for b in bars[:i]],
                    [b.low for b in bars[:i]],
                    [b.close for b in bars[:i]],
                )
                for i in range(2, len(bars) + 1)
            ]
        )
    if actual != [[1, 0, 1], [0, 0, 0]]:
        raise DataError("fixed rule D0 disagrees with independent reference positions")
    return {
        "schema": "SyntheticRulePositionsV1",
        "study_sha256": study.content_sha256,
        "baseline": actual[0],
        "control": actual[1],
        "unit": "position",
        "evidence_zone": "D0",
        "real_market_evidence": False,
        "scientific_acceptance": "not_admitted",
    }


def require_rule_confirmation(
    connection: sqlite3.Connection,
    project_id: str,
    contract_id: str,
    actor: str,
    revision: str | None = None,
) -> str:
    """Require the real consumed owner challenge, never a caller's actor assertion."""
    rows = connection.execute(
        """SELECT r.*, c.binding_json, c.used_at FROM owner_action_receipts r
        JOIN owner_auth_challenges c ON c.challenge_id=r.challenge_id
        WHERE r.project_id=? AND r.action_type='approve_exploration' AND r.artifact_hash=?""",
        (project_id, contract_id.removeprefix("rc_")),
    ).fetchall()
    expected_request = sha({"contract_id": contract_id})
    matches = [
        row
        for row in rows
        if row["actor"] == actor
        and row["used_at"] is not None
        and row["request_hash"] == expected_request
        and (revision is None or row["expected_case_revision"] == revision)
        and json.loads(row["binding_json"]).get("request_hash") == expected_request
    ]
    if len(matches) != 1:
        raise DataError("fixed rule approval requires one exact consumed owner confirmation")
    return str(matches[0]["receipt_id"])


def draft_rule_contract(
    source_pack_id: str,
    fingerprints: Mapping[str, str | None],
    budget: Mapping[str, int | float],
    *,
    costed: bool = False,
) -> dict[str, object]:
    """Inert internal draft for one fixed capability; never approves its own inputs."""
    from alpha_research import ResearchChartFingerprintV1, ResearchD2BoundaryV1

    boundary = ResearchD2BoundaryV1.from_eligible_groups(
        dataset_fingerprint=study_data_hash(costed),
        eligible_groups=tuple(f"synthetic-reserved-group-{i}" for i in range(10)),
        chart_fingerprint=ResearchChartFingerprintV1(
            instrument="RULES",
            provider="synthetic",
            venue="SYNTHETIC",
            timezone="UTC",
            session="UTC_DAY",
            bar_construction="equal_duration",
            bar_duration_seconds=86400,
            anchor="2000-01-01T00:00:00+00:00",
            adjustment_basis="synthetic_not_applicable",
            timestamp_semantics="bar_end_available",
        ),
        event_formula="close > 10",
        event_availability_timestamp="daily_close_available_at",
        primary_endpoint="position",
        primary_horizon="one_daily_bar",
        outcome_overlap_embargo_groups=1,
    )
    return {
        "schema": "ResearchContractV1",
        "scope": "exploration",
        "approval_ready": True,
        "blocking_questions": [],
        "thesis": {"primary_claims": [{"claim": "Fixed synthetic position mechanics only"}]},
        "source_pack_id": source_pack_id,
        "analysis_plan": rule_plan(costed),
        "protocol": {
            "d0_operator": registered_rule_operator(costed),
            "chart_fingerprint": boundary.chart_fingerprint.to_dict(),
            "boundary_authority": {
                "kind": "synthetic_acceptance_fixture",
                "real_market_evidence": False,
                "empirical_confirmation_authorized": False,
            },
            "evidence_topology": {
                "boundary": boundary.to_dict(),
                "D0": {"share": 0.0},
                "D1": {"share": 0.6},
                "D2": {"state": "sealed", "share": 0.2, "boundary_hash": boundary.boundary_sha256},
                "D3": {"state": "sealed", "share": 0.2},
            },
        },
        "budget": dict(budget),
        "hashes": dict(fingerprints),
    }


def worker_request(costed: bool = False) -> dict[str, object]:
    if costed:
        costed_study = fixed_costed_study()
        return {
            "study": costed_study.to_dict(),
            "study_sha256": costed_study.content_sha256,
            "bars": costed_study.to_dict()["bars"],
        }
    study = fixed_study()
    return {
        "study": study.to_dict(),
        "study_sha256": study.content_sha256,
        "bars": [
            [
                b.start.isoformat(),
                b.end.isoformat(),
                b.available_at.isoformat(),
                b.open,
                b.high,
                b.low,
                b.close,
                b.volume,
            ]
            for b in study.data.bars
        ],
    }


def real_discovery_readiness(proposal: Mapping[str, object]) -> dict[str, object]:
    """Inert missing-input projection; this synthetic capability cannot admit real data."""
    required = (
        "instrument",
        "venue",
        "discovery_start",
        "discovery_end",
        "cutoff",
        "rules_spec",
        "control_spec",
        "fill_timing",
        "horizon",
        "fees",
        "spread",
        "slippage",
        "capital_and_exposure",
        "snapshot_id",
        "snapshot_sha256",
        "qualified_source_receipt",
        "budget",
        "owner_frozen_contract",
        "owner_confirmation_receipt",
        "claim_scope",
    )
    return {
        "schema": "FrozenRuleRealDiscoveryReadinessV1",
        "status": "blocked",
        "authority": "none",
        "missing_fields": [field for field in required if proposal.get(field) is None],
        "blockers": [
            "Real daily rule/control protocol is unqualified; "
            "current protocols are synthetic only.",
            "Qualified data and an exact owner-frozen real study are required before effects.",
        ],
        "scientific_acceptance": "not_admitted",
        "effects_started": False,
    }
