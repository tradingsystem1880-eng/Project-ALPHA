"""Research-contract authority and schema-v2 migration invariants."""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import shutil
import sqlite3
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

import alpha_cli.control_store as control_store_module
from alpha_cli import _artifacts
from alpha_cli.artifact_contract import artifact_metadata
from alpha_cli.control_store import SCHEMA_VERSION, ControlStore
from alpha_cli.research_d2 import _claim as _d2_claim
from alpha_cli.research_d2 import derive_d2_findings
from alpha_cli.research_intake import draft_exploration_contract
from alpha_cli.research_runtime import (
    _GENERATION_60M,
    _d0_acceptance_payload,
    _recomputed_d0_measurements,
    d0_execution_fingerprint,
    registered_d0_operator,
)
from alpha_core import DataError
from alpha_research import (
    ResearchChartFingerprintV1,
    ResearchD2BoundaryV1,
    ResearchD2BoundaryV2,
    build_research_gate_packet,
)
from tests.fixtures.control_store_fixtures import mark_project_as_migrated_legacy

PROJECT_ID = "9e4908b1-a9cd-4c13-a47e-740d92175680"
LEGACY_PROJECT_ID = "bf09e202-a02a-45c5-904e-1dbda4bf298e"
START = datetime(2026, 8, 6, 9, 0, tzinfo=UTC)
# The approval-frozen confirmation dataset bytes every fabricated D2 run must claim.
_CONFIRMATION_DATA_SHA = hashlib.sha256(b"confirmation-dataset-bytes").hexdigest()


def _project(store: ControlStore, project_id: str = PROJECT_ID) -> None:
    store.create_project(
        name="SPY four-hour double bottom",
        hypothesis="Confirmed double bottoms precede positive forward returns.",
        falsification_criterion="Reject when matched-control effects are non-positive.",
        project_id=project_id,
        at=START,
    )


def _v4_database(tmp_path: Path) -> tuple[Path, str]:
    """Build a committed v4 store without opening the v5 runtime path."""
    root = tmp_path / "control"
    root.mkdir()
    database = root / "workstation.sqlite3"
    connection = sqlite3.connect(database, isolation_level=None)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("BEGIN IMMEDIATE")
        control_store_module._execute_static_sql_script(connection, control_store_module._SCHEMA)
        control_store_module._execute_static_sql_script(connection, control_store_module._SCHEMA_V2)
        control_store_module._execute_static_sql_script(connection, control_store_module._SCHEMA_V3)
        control_store_module._execute_static_sql_script(connection, control_store_module._SCHEMA_V4)
        connection.execute(
            """INSERT INTO projects VALUES (?, ?, ?, ?, 'active', NULL, NULL, ?, ?)""",
            (
                PROJECT_ID,
                "v4 migration project",
                "Preserve this v4 row",
                "Reject if migration loses it",
                "2026-08-13T00:00:00.000000Z",
                "2026-08-13T00:00:00.000000Z",
            ),
        )
        control_store_module._execute_static_sql_script(
            connection, control_store_module._GOVERNANCE_BACKFILL
        )
        connection.execute("PRAGMA user_version = 4")
        connection.commit()
    finally:
        connection.close()
    return database, PROJECT_ID


def _insert_v4_receipt(database: Path) -> list[tuple[object, ...]]:
    connection = sqlite3.connect(database)
    try:
        connection.execute(
            "INSERT INTO owner_credentials VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("cred-1", b"key", 1, "owner", "[]", "2026-08-13T00:00:00Z", None),
        )
        connection.execute(
            "INSERT INTO owner_auth_challenges VALUES (?, 'action', ?, NULL, ?, ?, ?, NULL, NULL)",
            (
                "challenge-1",
                b"challenge",
                '{"action_type":"approve_exploration"}',
                "2026-08-13T00:00:00Z",
                "2026-08-13T01:00:00Z",
            ),
        )
        connection.execute(
            """INSERT INTO owner_action_receipts VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )""",
            (
                "receipt-1",
                "challenge-1",
                "cred-1",
                "owner",
                "approve_exploration",
                PROJECT_ID,
                "a" * 64,
                "b" * 64,
                "approve",
                "test receipt",
                "c" * 64,
                "d" * 64,
                '{"status":"performed"}',
                "2026-08-13T00:00:01Z",
            ),
        )
        rows = connection.execute(
            "SELECT * FROM owner_action_receipts ORDER BY receipt_id"
        ).fetchall()
        connection.commit()
        return rows
    finally:
        connection.close()


def _semantic_source() -> dict[str, object]:
    return {
        "project_id": PROJECT_ID,
        "case_contract_id": "rc_" + "1" * 64,
        "source_contract_id": "rc_" + "2" * 64,
        "case_revision": "a" * 64,
        "verified_read_sha256": "b" * 64,
        "projection_sha256": "c" * 64,
        "run_id": "0123456789abcdef",
        "cutoff_confirmed_at": "2026-08-13T00:00:00.000000Z",
    }


def _semantic_definition_payload(source: dict[str, object], head: str) -> dict[str, object]:
    return {
        "schema": "SemanticOwnerActionV1",
        "schema_version": 1,
        "event_type": "definition",
        "verified_read_sha256": source["verified_read_sha256"],
        "projection_sha256": source["projection_sha256"],
        "run_id": source["run_id"],
        "cutoff_confirmed_at": source["cutoff_confirmed_at"],
        "expected_semantic_head_sha256": head,
        "definition_label": "Test definition",
        "definition_text": "A bounded semantic definition.",
    }


def _semantic_review_payload(
    source: dict[str, object], head: str, definition_id: str, decision: str
) -> dict[str, object]:
    return {
        "schema": "SemanticOwnerActionV1",
        "schema_version": 1,
        "event_type": "review",
        "verified_read_sha256": source["verified_read_sha256"],
        "projection_sha256": source["projection_sha256"],
        "run_id": source["run_id"],
        "cutoff_confirmed_at": source["cutoff_confirmed_at"],
        "expected_semantic_head_sha256": head,
        "definition_id": definition_id,
        "review_decision": decision,
        "review_text": "Review the bounded semantic definition.",
    }


def _semantic_freeze_payload(
    source: dict[str, object], head: str, definition_id: str, review_id: str
) -> dict[str, object]:
    return {
        "schema": "SemanticOwnerActionV1",
        "schema_version": 1,
        "event_type": "freeze",
        "verified_read_sha256": source["verified_read_sha256"],
        "projection_sha256": source["projection_sha256"],
        "run_id": source["run_id"],
        "cutoff_confirmed_at": source["cutoff_confirmed_at"],
        "expected_semantic_head_sha256": head,
        "definition_id": definition_id,
        "review_id": review_id,
    }


def _seed_semantic_dependencies(tmp_path: Path) -> None:
    database = tmp_path / "control" / control_store_module.DATABASE_NAME
    connection = sqlite3.connect(database)
    try:
        for contract_id in ("rc_" + "1" * 64, "rc_" + "2" * 64):
            connection.execute(
                """INSERT INTO research_contracts
                (contract_id, project_id, scope, parent_contract_id, payload_json,
                 created_by, author_kind, created_at)
                VALUES (?, ?, 'exploration', NULL, '{}', 'owner', 'human', ?)""",
                (contract_id, PROJECT_ID, "2026-08-13T00:00:00.000000Z"),
            )
        connection.execute(
            "INSERT INTO owner_credentials VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("cred-semantic", b"key", 1, "owner", "[]", "2026-08-13T00:00:00Z", None),
        )
        connection.execute(
            """INSERT INTO owner_auth_challenges
            VALUES (?, 'action', ?, NULL, ?, ?, ?, NULL, NULL)""",
            (
                "challenge-semantic",
                b"challenge",
                '{"action_type":"record_semantic_event"}',
                "2026-08-13T00:00:00Z",
                "2026-08-14T00:00:00Z",
            ),
        )
        connection.commit()
    finally:
        connection.close()


def _insert_semantic_receipt(
    tmp_path: Path,
    *,
    source: dict[str, object],
    payload: dict[str, object],
    receipt_id: str,
    sequence: int,
    prior_head: str,
) -> tuple[str, str]:
    artifact_id, artifact_sha, _ = control_store_module._semantic_artifact(
        source, payload, prior_head
    )
    event_id, identity = control_store_module._semantic_event_identity(
        source=source,
        payload=payload,
        sequence=sequence,
        prior_head=prior_head,
        semantic_artifact_id=artifact_id,
        semantic_artifact_sha256=artifact_sha,
        receipt_id=receipt_id,
        actor="owner",
        reason="owner test",
        recorded_at="2026-08-13T00:00:01.000000Z",
    )
    database = tmp_path / "control" / control_store_module.DATABASE_NAME
    connection = sqlite3.connect(database)
    try:
        challenge_id = f"challenge-{receipt_id}"
        connection.execute(
            """INSERT INTO owner_auth_challenges
            VALUES (?, 'action', ?, NULL, ?, ?, ?, NULL, NULL)""",
            (
                challenge_id,
                b"challenge-" + receipt_id.encode(),
                '{"action_type":"record_semantic_event"}',
                "2026-08-13T00:00:00Z",
                "2026-08-14T00:00:00Z",
            ),
        )
        connection.execute(
            """INSERT INTO owner_action_receipts VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )""",
            (
                receipt_id,
                challenge_id,
                "cred-semantic",
                "owner",
                "record_semantic_event",
                PROJECT_ID,
                artifact_sha,
                source["case_revision"],
                "record semantic event",
                "owner test",
                identity["payload_sha256"],
                "d" * 64,
                json.dumps(
                    {
                        "status": "semantic_event_recorded",
                        "semantic_event_id": event_id,
                        "semantic_event_sha256": event_id[3:],
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                "2026-08-13T00:00:01.000000Z",
            ),
        )
        connection.commit()
    finally:
        connection.close()
    return event_id, artifact_id


def test_semantic_owner_payload_and_empty_head_are_canonical_and_closed(tmp_path: Path) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    source = _semantic_source()
    head = control_store_module._semantic_empty_head_sha256(PROJECT_ID)
    payload = _semantic_definition_payload(source, head)
    artifact_id, artifact_sha, artifact = control_store_module._semantic_artifact(
        source, payload, head
    )
    assert artifact_id == f"sd_{artifact_sha}"
    assert artifact["schema"] == "ResearchSemanticDefinitionV1"
    assert control_store_module._canonical_json(payload, "payload") == json.dumps(
        payload, sort_keys=True, separators=(",", ":")
    )
    with pytest.raises(DataError, match="keys are not exact"):
        control_store_module._semantic_payload({**payload, "extra": True})


def test_semantic_ledger_append_and_read_rejects_tamper(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    _seed_semantic_dependencies(tmp_path)
    source = _semantic_source()
    monkeypatch.setattr(
        store,
        "_verified_semantic_source_locked",
        lambda _connection, _project_id: source,
    )
    head = control_store_module._semantic_empty_head_sha256(PROJECT_ID)
    payload = _semantic_definition_payload(source, head)
    artifact_id, artifact_sha, _ = control_store_module._semantic_artifact(source, payload, head)
    payload_sha = hashlib.sha256(
        control_store_module._canonical_json(payload, "payload").encode()
    ).hexdigest()
    connection = sqlite3.connect(tmp_path / "control" / control_store_module.DATABASE_NAME)
    try:
        connection.execute(
            """INSERT INTO owner_action_receipts VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )""",
            (
                "receipt-semantic-1",
                "challenge-semantic",
                "cred-semantic",
                "owner",
                "record_semantic_event",
                PROJECT_ID,
                artifact_sha,
                source["case_revision"],
                "record semantic definition",
                "owner test",
                payload_sha,
                "d" * 64,
                json.dumps(
                    {
                        "status": "semantic_event_recorded",
                        "semantic_event_id": "pending",
                        "semantic_event_sha256": "pending",
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                "2026-08-13T00:00:01.000000Z",
            ),
        )
        connection.commit()
    finally:
        connection.close()
    with (
        pytest.raises(DataError, match="receipt outcome"),
        store._transaction(write=True) as transaction,
    ):
        store.append_semantic_event(
            transaction,
            project_id=PROJECT_ID,
            payload=payload,
            receipt_id="receipt-semantic-1",
            actor="owner",
            reason="owner test",
            recorded_at="2026-08-13T00:00:01.000000Z",
        )


def test_semantic_ledger_append_and_persisted_read_are_hash_bound(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    _seed_semantic_dependencies(tmp_path)
    source = _semantic_source()
    monkeypatch.setattr(
        store,
        "_verified_semantic_source_locked",
        lambda _connection, _project_id: source,
    )
    head = control_store_module._semantic_empty_head_sha256(PROJECT_ID)
    payload = _semantic_definition_payload(source, head)
    event_id, artifact_id = _insert_semantic_receipt(
        tmp_path,
        source=source,
        payload=payload,
        receipt_id="receipt-semantic-success",
        sequence=1,
        prior_head=head,
    )
    with store._transaction(write=True) as connection:
        event = store.append_semantic_event(
            connection,
            project_id=PROJECT_ID,
            payload=payload,
            receipt_id="receipt-semantic-success",
            actor="owner",
            reason="owner test",
            recorded_at="2026-08-13T00:00:01.000000Z",
        )
    assert event["event_id"] == event_id
    assert event["semantic_artifact_id"] == artifact_id
    monkeypatch.setattr(
        store,
        "_verified_semantic_source_locked",
        lambda _connection, _project_id: pytest.fail(
            "persisted read must not require current source"
        ),
    )
    persisted = store.read_semantic_events(PROJECT_ID)
    assert len(persisted) == 1
    assert persisted[0]["event_id"] == event_id
    assert store.semantic_head_sha256(PROJECT_ID) == event_id[3:]

    database = tmp_path / "control" / control_store_module.DATABASE_NAME
    connection = sqlite3.connect(database)
    try:
        connection.execute("DROP TRIGGER research_semantic_events_no_update")
        connection.execute(
            "UPDATE research_semantic_events SET payload_json = '{\"tampered\":true}' "
            "WHERE event_id = ?",
            (event_id,),
        )
        connection.commit()
    finally:
        connection.close()
    with pytest.raises(DataError, match="protected schema object"):
        store.read_semantic_events(PROJECT_ID)


def test_semantic_persisted_read_rejects_orphan_record_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    _seed_semantic_dependencies(tmp_path)
    source = _semantic_source()
    monkeypatch.setattr(
        store,
        "_verified_semantic_source_locked",
        lambda _connection, _project_id: source,
    )
    head = control_store_module._semantic_empty_head_sha256(PROJECT_ID)
    _insert_semantic_receipt(
        tmp_path,
        source=source,
        payload=_semantic_definition_payload(source, head),
        receipt_id="receipt-semantic-orphan",
        sequence=1,
        prior_head=head,
    )
    with pytest.raises(DataError, match="bijective"):
        store.read_semantic_events(PROJECT_ID)


def test_verified_semantic_source_revalidates_current_d0_lineage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = ControlStore(tmp_path)
    contract_id = "rc_" + "1" * 64
    payload = {
        "schema": "ResearchContractV1",
        "scope": "exploration",
        "source_pack_id": "sp_" + "2" * 64,
    }
    monkeypatch.setattr(store, "_require_project", lambda _connection, _project_id: None)
    monkeypatch.setattr(
        store,
        "_latest_research_phase",
        lambda _connection, _project_id: {"contract_id": contract_id, "phase": "pilot"},
    )
    monkeypatch.setattr(
        store,
        "_latest_research_execution",
        lambda _connection, _project_id: {"state": "running"},
    )
    monkeypatch.setattr(
        store,
        "_require_research_contract",
        lambda _connection, _project_id, _contract_id: {
            "contract_id": contract_id,
            "scope": "exploration",
            "parent_contract_id": None,
            "payload_json": json.dumps(payload, separators=(",", ":")),
        },
    )
    monkeypatch.setattr(
        store,
        "_require_completed_d0_attempt",
        lambda *_args, **_kwargs: {"attempt": True},
    )
    monkeypatch.setattr(
        store,
        "_research_attempt_view",
        lambda _attempt: {"run_id": "0123456789abcdef", "config_fingerprint": "a" * 64},
    )
    manifest = {
        "artifacts": {
            filename: {"sha256": "a" * 64}
            for filename in control_store_module._SEMANTIC_READ_ARTIFACTS
        }
    }
    monkeypatch.setattr(
        store,
        "_verified_run",
        lambda _run_id: (tmp_path, manifest),
    )
    monkeypatch.setattr(
        store,
        "_read_verified_semantic_artifacts",
        lambda _run_dir, _manifest: {
            filename: b"{}" for filename in control_store_module._SEMANTIC_READ_ARTIFACTS
        },
    )
    projection_data = {
        "schema": "BlindSemanticProjectionV1",
        "schema_version": 1,
        "cutoff_confirmed_at": "2026-08-13T00:00:00.000000Z",
    }
    projection = SimpleNamespace(run_id="0123456789abcdef", to_dict=lambda: projection_data)
    monkeypatch.setattr(
        "alpha_cli.research_runtime.validate_d0_pilot_contract",
        lambda _contract: {
            "operator": {"name": "double_bottom"},
            "fixture": {"definition_fingerprint": "b" * 64},
            "fingerprint": "c" * 64,
        },
    )
    monkeypatch.setattr(
        "alpha_cli.research_runtime.validate_d0_acceptance_bytes",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr("alpha_study.project_blind_semantic_read", lambda **_kwargs: projection)

    class _Verified:
        content_sha256 = "d" * 64

        def __init__(self, *, run_id: str, projection: object) -> None:
            self.run_id = run_id
            self.projection = projection

    monkeypatch.setattr("alpha_cli.study_semantic.VerifiedBlindSemanticReadV1", _Verified)
    with store._transaction(write=False) as connection:
        source = store._verified_semantic_source_locked(connection, PROJECT_ID)
    assert source["case_contract_id"] == contract_id
    assert source["source_contract_id"] == contract_id
    assert source["verified_read_sha256"] == "d" * 64


def test_semantic_ledger_enforces_rejected_retry_and_approved_freeze(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    _seed_semantic_dependencies(tmp_path)
    source = _semantic_source()
    monkeypatch.setattr(
        store,
        "_verified_semantic_source_locked",
        lambda _connection, _project_id: source,
    )

    head = control_store_module._semantic_empty_head_sha256(PROJECT_ID)
    definition = _semantic_definition_payload(source, head)
    first_event, definition_id = _insert_semantic_receipt(
        tmp_path,
        source=source,
        payload=definition,
        receipt_id="receipt-transition-1",
        sequence=1,
        prior_head=head,
    )
    with store._transaction(write=True) as connection:
        store.append_semantic_event(
            connection,
            project_id=PROJECT_ID,
            payload=definition,
            receipt_id="receipt-transition-1",
            actor="owner",
            reason="owner test",
            recorded_at="2026-08-13T00:00:01.000000Z",
        )

    rejected = _semantic_review_payload(source, first_event[3:], definition_id, "reject")
    second_event, review_id = _insert_semantic_receipt(
        tmp_path,
        source=source,
        payload=rejected,
        receipt_id="receipt-transition-2",
        sequence=2,
        prior_head=first_event[3:],
    )
    with store._transaction(write=True) as connection:
        store.append_semantic_event(
            connection,
            project_id=PROJECT_ID,
            payload=rejected,
            receipt_id="receipt-transition-2",
            actor="owner",
            reason="owner test",
            recorded_at="2026-08-13T00:00:01.000000Z",
        )
    rejected_freeze = _semantic_freeze_payload(source, second_event[3:], definition_id, review_id)
    with (
        pytest.raises(DataError, match="rejected review"),
        store._transaction(write=True) as connection,
    ):
        store.append_semantic_event(
            connection,
            project_id=PROJECT_ID,
            payload=rejected_freeze,
            receipt_id="receipt-transition-rejected-freeze",
            actor="owner",
            reason="owner test",
            recorded_at="2026-08-13T00:00:01.000000Z",
        )

    retry_definition = _semantic_definition_payload(source, second_event[3:])
    retry_definition["definition_label"] = "Retried definition"
    retry_event, retry_definition_id = _insert_semantic_receipt(
        tmp_path,
        source=source,
        payload=retry_definition,
        receipt_id="receipt-transition-3",
        sequence=3,
        prior_head=second_event[3:],
    )
    with store._transaction(write=True) as connection:
        store.append_semantic_event(
            connection,
            project_id=PROJECT_ID,
            payload=retry_definition,
            receipt_id="receipt-transition-3",
            actor="owner",
            reason="owner test",
            recorded_at="2026-08-13T00:00:01.000000Z",
        )
    approved = _semantic_review_payload(source, retry_event[3:], retry_definition_id, "approve")
    approved_event, approved_review_id = _insert_semantic_receipt(
        tmp_path,
        source=source,
        payload=approved,
        receipt_id="receipt-transition-4",
        sequence=4,
        prior_head=retry_event[3:],
    )
    with store._transaction(write=True) as connection:
        store.append_semantic_event(
            connection,
            project_id=PROJECT_ID,
            payload=approved,
            receipt_id="receipt-transition-4",
            actor="owner",
            reason="owner test",
            recorded_at="2026-08-13T00:00:01.000000Z",
        )
    freeze = _semantic_freeze_payload(
        source, approved_event[3:], retry_definition_id, approved_review_id
    )
    _insert_semantic_receipt(
        tmp_path,
        source=source,
        payload=freeze,
        receipt_id="receipt-transition-5",
        sequence=5,
        prior_head=approved_event[3:],
    )
    with store._transaction(write=True) as connection:
        store.append_semantic_event(
            connection,
            project_id=PROJECT_ID,
            payload=freeze,
            receipt_id="receipt-transition-5",
            actor="owner",
            reason="owner test",
            recorded_at="2026-08-13T00:00:01.000000Z",
        )
    assert len(store.read_semantic_events(PROJECT_ID)) == 5


def _source_pack(store: ControlStore) -> str:
    source = store.create_research_source(
        PROJECT_ID,
        title="Technical patterns and subsequent returns",
        locator="doi:10.0000/example",
        provider="crossref",
        access_mode="metadata_only",
        metadata={"doi": "10.0000/example", "screening": "include"},
        at=START + timedelta(minutes=1),
    )
    pack = store.create_research_source_pack(
        PROJECT_ID,
        source_ids=[str(source["source_id"])],
        definition={"queries": ["double bottom forward returns"], "frozen": True},
        at=START + timedelta(minutes=2),
    )
    return str(pack["pack_id"])


def _boundary(seed: str, *, synthetic: bool = True) -> ResearchD2BoundaryV1:
    chart = (
        ResearchChartFingerprintV1(
            instrument="SYNTHETIC_SPY",
            provider="alpha_synthetic_fixture",
            venue="SYNTHETIC",
            timezone="UTC",
            session="synthetic_equal_duration",
            bar_construction=(
                "fixed_60_trading_minute_bars_with_240_trading_minute_pattern_window"
            ),
            bar_duration_seconds=3_600,
            anchor="SYNTHETIC_EPOCH",
            adjustment_basis="synthetic_not_applicable",
            timestamp_semantics="bar_end_available",
        )
        if synthetic
        else ResearchChartFingerprintV1(
            instrument="SPY",
            provider="licensed-test-provider",
            venue="ARCX",
            timezone="America/New_York",
            session="regular_hours",
            bar_construction="fixed_60_trading_minute_bars",
            bar_duration_seconds=3_600,
            anchor="09:30 America/New_York",
            adjustment_basis="point_in_time_split_and_dividend",
            timestamp_semantics="bar_close_available",
        )
    )
    return ResearchD2BoundaryV1.from_eligible_groups(
        dataset_fingerprint=hashlib.sha256(seed.encode("utf-8")).hexdigest(),
        eligible_groups=tuple(f"{seed}|2026-01-{day:02d}|RTH" for day in range(1, 11)),
        chart_fingerprint=chart,
        event_formula="confirmable second trough within 0.5 percent of first trough",
        event_availability_timestamp="second_trough_bar_close",
        primary_endpoint="event_minus_matched_control_arithmetic_return",
        primary_horizon="240_trading_minutes",
        outcome_overlap_embargo_groups=1,
    )


def _payload(
    pack_id: str,
    *,
    confirmation: bool = False,
    boundary_seed: str = "baseline-boundary",
    relation_to_prior: str | None = None,
) -> dict[str, object]:
    boundary = _boundary(boundary_seed)
    event_definition: dict[str, object] = {
        "name": "double_bottom",
        "availability": "second_trough_confirmable",
        "records_both_trough_times": True,
        "fires_only_when_confirmable": True,
        "right_pivot_moves_event_forward": True,
        "neckline_is_separate_variant": True,
        "overlapping_outcomes": "purge",
    }
    primary_claim: dict[str, object] = {
        "estimand": "event_minus_matched_control_arithmetic_return",
        "endpoint": "forward_arithmetic_return",
        "horizon_trading_minutes": 240,
        "direction": "positive",
        "minimum_effect_return": 0.0025,
    }
    protocol_chart_fingerprint = boundary.chart_fingerprint.to_dict()
    chart_fingerprint = (
        protocol_chart_fingerprint
        if confirmation
        else {
            "provider": "alpha_synthetic_fixture",
            "timezone": "UTC",
            "timestamp_semantics": "bar_end_available",
            "adjustment_basis": "synthetic_not_applicable",
            "instrument": "SYNTHETIC_SPY",
            "venue": "SYNTHETIC",
            "session": "synthetic_equal_duration",
            "bar_duration_minutes": 60,
            "pattern_window_trading_minutes": 240,
            "anchor": "SYNTHETIC_EPOCH",
            "label": "synthetic SPY-like 60-minute D0 fixture with a four-hour pattern window",
        }
    )
    d2: dict[str, object] = {
        "state": "sealed",
        "share": 0.20,
        "boundary_hash": boundary.boundary_sha256,
    }
    if relation_to_prior is not None:
        d2["relation_to_prior"] = relation_to_prior
    payload: dict[str, object] = {
        "schema": "ResearchContractV1",
        "scope": "exploration" if not confirmation else "confirmation",
        "approval_ready": True,
        "blocking_questions": [],
        "resolved_material_choices": {
            "chart_construction": "spy_rth_60m_four_hour_window",
            "event_availability": "second_trough_confirmable",
            "primary_outcome": "four_trading_hour_return_25bp",
        },
        "chart_fingerprint": chart_fingerprint,
        "event_definition": event_definition,
        "primary_claim": primary_claim,
        "thesis": {"primary_claims": [primary_claim]},
        "protocol": {
            "event": "causal confirmed double bottom",
            "event_definition": event_definition,
            "outcome": "forward return in elapsed trading minutes",
            "chart_fingerprint": protocol_chart_fingerprint,
            "primary_claims": [primary_claim],
            "boundary_authority": (
                {
                    "kind": "empirical_dataset",
                    "real_market_evidence": True,
                    "empirical_confirmation_authorized": True,
                }
                if confirmation
                else {
                    "kind": "synthetic_acceptance_fixture",
                    "real_market_evidence": False,
                    "empirical_confirmation_authorized": False,
                }
            ),
            "evidence_topology": {
                "boundary": boundary.to_dict(),
                "D0": {"share": 0.0},
                "D1": {"share": 0.60},
                "D2": d2,
                "D3": {"state": "sealed", "share": 0.20},
            },
        },
        "source_pack_id": pack_id,
        "budget": {"wall_seconds": 14_400, "source_requests": 60, "variants": 128},
        "hashes": {
            "code": "git:a1b2c3d4e5f60718",
            "environment": "uv-lock:1234abcd5678ef90",
            "evaluator": "event-study-v1.0.0",
            "data": _CONFIRMATION_DATA_SHA if confirmation else None,
        },
    }
    if confirmation:
        payload["confirmation"] = {
            "variant_count": 128,
            "multiplicity_count": 128,
            "familywise_alpha": 0.05,
            "target_power": 0.90,
            "power_report": {"achieved_power": 0.92},
            "fingerprints": {
                "detector": "double-bottom-v1.0.0",
                "variant_family": "variant-family-a1b2c3d4",
                "statistics": "event-study-stats-v1",
            },
        }
    else:
        protocol = cast(dict[str, object], payload["protocol"])
        protocol["d0_operator"] = registered_d0_operator(payload)
    return payload


@pytest.mark.parametrize(
    ("case", "message"),
    [
        ("topology", "evidence_topology"),
        ("boundary", "canonical boundary"),
        ("d2", "sealed D2"),
        ("hash", "boundary hash does not match"),
        ("d0", "requires D0"),
    ],
)
def test_research_topology_rejects_incomplete_boundary_contracts(case: str, message: str) -> None:
    payload = _payload("sp_" + "1" * 64)
    protocol = cast(dict[str, object], payload["protocol"])
    topology = cast(dict[str, object], protocol["evidence_topology"])
    if case == "topology":
        protocol.pop("evidence_topology")
    elif case == "boundary":
        topology.pop("boundary")
    elif case == "d2":
        topology.pop("D2")
    elif case == "hash":
        cast(dict[str, object], topology["D2"])["boundary_hash"] = "different-boundary-fingerprint"
    else:
        topology.pop("D0")
    with pytest.raises(DataError, match=message):
        control_store_module._research_d2_topology(payload)


def test_compact_v2_full_history_contract_persists_under_the_existing_json_limit(
    tmp_path: Path,
) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    pack_id = _source_pack(store)
    payload = _payload(pack_id)
    baseline = _boundary("compact-full-history")
    boundary = ResearchD2BoundaryV2.from_eligible_groups(
        dataset_fingerprint=baseline.dataset_fingerprint,
        eligible_groups=tuple(f"spy-session-{index:04d}" for index in range(3_774)),
        chart_fingerprint=baseline.chart_fingerprint,
        event_formula=baseline.event_formula,
        event_availability_timestamp=baseline.event_availability_timestamp,
        primary_endpoint=baseline.primary_endpoint,
        primary_horizon=baseline.primary_horizon,
        outcome_overlap_embargo_groups=baseline.outcome_overlap_embargo_groups,
    )
    protocol = cast(dict[str, object], payload["protocol"])
    topology = cast(dict[str, object], protocol["evidence_topology"])
    topology["boundary"] = boundary.to_dict()
    d2 = cast(dict[str, object], topology["D2"])
    d2["boundary_hash"] = boundary.boundary_sha256

    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    assert len(encoded) < 65_536
    contract = store.create_research_contract(
        PROJECT_ID,
        scope="exploration",
        payload=payload,
        created_by="codex",
        author_kind="agent",
    )
    assert cast(dict[str, object], contract["payload"]) == payload


def _approved_contracts(
    store: ControlStore,
    *,
    outcome: str = "SUPPORTED",
    disposition: str = "advance_to_strategy",
    record_confirmation_evidence: bool = True,
    record_decision: bool = True,
    d2_state: str = "consumed",
    transition_to_decision: bool = True,
) -> tuple[str, str]:
    pack_id = _source_pack(store)
    exploration = store.create_research_contract(
        PROJECT_ID,
        scope="exploration",
        payload=_payload(pack_id),
        created_by="codex",
        author_kind="agent",
        at=START + timedelta(minutes=3),
    )
    exploration_id = str(exploration["contract_id"])
    store.transition_research_phase(
        PROJECT_ID,
        to_phase="triage",
        contract_id=exploration_id,
        actor="codex",
        reason="The captured idea is ready for triage.",
        next_action="Prepare the exploration review.",
        responsibility="codex",
        at=START + timedelta(minutes=4),
    )
    store.transition_research_phase(
        PROJECT_ID,
        to_phase="exploration_review",
        contract_id=exploration_id,
        actor="codex",
        reason="The exploration contract is ready for owner review.",
        next_action="Approve or reject exploration.",
        responsibility="owner",
        at=START + timedelta(minutes=5),
    )
    store.review_research_contract(
        PROJECT_ID,
        exploration_id,
        scope="exploration",
        decision="approve",
        actor="owner",
        actor_kind="human",
        reason="D1 protocol is suitable for bounded exploration.",
        at=START + timedelta(minutes=6),
    )
    store.transition_research_phase(
        PROJECT_ID,
        to_phase="pilot",
        contract_id=exploration_id,
        actor="codex",
        reason="Exploration was approved.",
        next_action="Run the bounded pilot.",
        responsibility="codex",
        at=START + timedelta(minutes=7),
    )
    _record_completed_d0(
        store,
        exploration_id,
        _payload(pack_id),
        at=START + timedelta(minutes=7, seconds=30),
    )
    store.transition_research_phase(
        PROJECT_ID,
        to_phase="deep_research",
        contract_id=exploration_id,
        actor="codex",
        reason="The pilot completed.",
        next_action="Freeze the confirmation child.",
        responsibility="codex",
        at=START + timedelta(minutes=8),
    )
    confirmation_payload = _payload(pack_id, confirmation=True)
    confirmation = store.create_research_contract(
        PROJECT_ID,
        scope="confirmation",
        parent_contract_id=exploration_id,
        payload=confirmation_payload,
        created_by="codex",
        author_kind="agent",
        at=START + timedelta(minutes=9),
    )
    confirmation_id = str(confirmation["contract_id"])
    store.transition_research_phase(
        PROJECT_ID,
        to_phase="confirmation_review",
        contract_id=confirmation_id,
        actor="codex",
        reason="The confirmation child is ready for owner review.",
        next_action="Approve or reject D2 authorization.",
        responsibility="owner",
        at=START + timedelta(minutes=10),
    )
    store.review_research_contract(
        PROJECT_ID,
        confirmation_id,
        scope="confirmation",
        decision="approve",
        actor="owner",
        actor_kind="human",
        reason="The frozen confirmation family may consume D2 once.",
        at=START + timedelta(minutes=11),
    )
    store.transition_research_phase(
        PROJECT_ID,
        to_phase="sealed_confirmation",
        contract_id=confirmation_id,
        actor="codex",
        reason="Confirmation was approved.",
        next_action="Consume D2 once.",
        responsibility="codex",
        at=START + timedelta(minutes=12),
    )
    if d2_state != "authorized":
        # Owner confirmation approval already authorized D2; only the terminal
        # consume/contaminate transitions go through the API.
        store.transition_research_d2_state(
            PROJECT_ID,
            confirmation_id,
            to_state=d2_state,  # type: ignore[arg-type]
            actor="system",
            reason=f"The sealed confirmation boundary became {d2_state}.",
            at=START + timedelta(minutes=13),
        )
    if record_confirmation_evidence and d2_state == "consumed":
        run_id = _write_research_run(
            store._data_dir,
            run_id="ignored-content-derived-id",
            contract_id=confirmation_id,
            payload=confirmation_payload,
            evidence_zone="D2",
            d2_outcome=outcome,
        )
        store.record_research_attempt(
            PROJECT_ID,
            confirmation_id,
            kind="sealed-confirmation",
            status="completed",
            config_fingerprint="a" * 64,
            budget_used={"wall_seconds": 1, "source_requests": 0, "variants": 1},
            details={
                "evidence_zone": "D2",
                "real_market_evidence": True,
                "gate_packet_evidence_ref": _d2_evidence_ref(store._data_dir, run_id),
            },
            run_id=run_id,
            at=START + timedelta(minutes=13, seconds=30),
        )
    if transition_to_decision:
        store.transition_research_phase(
            PROJECT_ID,
            to_phase="research_decision",
            contract_id=confirmation_id,
            actor="codex",
            reason="Confirmation results are complete.",
            next_action="Record the owner research decision.",
            responsibility="owner",
            at=START + timedelta(minutes=14),
        )
    if record_decision:
        assert transition_to_decision
        store.record_research_decision(
            PROJECT_ID,
            confirmation_id,
            outcome=outcome,  # type: ignore[arg-type]
            disposition=disposition,  # type: ignore[arg-type]
            actor="owner",
            actor_kind="human",
            reason="The owner accepts the mechanical frozen-confirmation classification.",
            at=START + timedelta(minutes=15),
        )
    return exploration_id, confirmation_id


def _d2_evidence_ref(data_dir: Path, run_id: str) -> dict[str, object]:
    manifest = _artifacts.read_manifest(data_dir / "runs" / run_id)
    artifacts = cast(dict[str, object], manifest["artifacts"])
    metadata = cast(dict[str, object], artifacts["research_gate_evidence.json"])
    return {
        "artifact": "research_gate_evidence.json",
        "content_sha256": metadata["sha256"],
    }


def _approved_pilot(store: ControlStore) -> tuple[str, dict[str, object]]:
    pack_id = _source_pack(store)
    payload = _payload(pack_id)
    contract = store.create_research_contract(
        PROJECT_ID,
        scope="exploration",
        payload=payload,
        created_by="codex",
        author_kind="agent",
        at=START + timedelta(minutes=3),
    )
    contract_id = str(contract["contract_id"])
    for minute, phase, responsibility in (
        (4, "triage", "codex"),
        (5, "exploration_review", "owner"),
    ):
        store.transition_research_phase(
            PROJECT_ID,
            to_phase=phase,  # type: ignore[arg-type]
            contract_id=contract_id,
            actor="codex",
            reason=f"Advance the fixture to {phase}.",
            next_action="Continue the governed pilot fixture.",
            responsibility=responsibility,  # type: ignore[arg-type]
            at=START + timedelta(minutes=minute),
        )
    store.review_research_contract(
        PROJECT_ID,
        contract_id,
        scope="exploration",
        decision="approve",
        actor="owner",
        actor_kind="human",
        reason="Approve the exact pilot fixture.",
        at=START + timedelta(minutes=6),
    )
    store.transition_research_phase(
        PROJECT_ID,
        to_phase="pilot",
        contract_id=contract_id,
        actor="owner",
        reason="The pilot fixture is approved.",
        next_action="Run D0 only.",
        responsibility="codex",
        at=START + timedelta(minutes=7),
    )
    return contract_id, payload


def _d2_run_id(payload: dict[str, object], contract_id: str) -> str:
    """The content-derived sealed-confirmation run identity the store recomputes."""
    contract_hash = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    hashes = payload["hashes"]
    assert isinstance(hashes, dict)
    run_identity = {
        "command": "research_confirm",
        "project_id": PROJECT_ID,
        "research_contract_id": contract_id,
        "contract_hash": contract_hash,
        "dataset_hash": str(hashes["data"]),
        "execution_fingerprint": "a" * 64,
    }
    return hashlib.sha256(
        json.dumps(run_identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:16]


def _d2_matched_measurements(outcome: str) -> dict[str, object]:
    """Raw matched measurements that mechanically classify to the requested outcome."""
    numbers = {
        "SUPPORTED": {"estimate": 0.004, "ci_lower": 0.003, "ci_upper": 0.005, "p_value": 0.01},
        "CONTRADICTED": {
            "estimate": -0.003,
            "ci_lower": -0.005,
            "ci_upper": -0.001,
            "p_value": 0.6,
        },
        "INCONCLUSIVE": {
            "estimate": 0.001,
            "ci_lower": -0.001,
            "ci_upper": 0.003,
            "p_value": 0.2,
        },
    }[outcome]
    return {
        "counts": {"events": 60, "controls": 240},
        "matched": {
            **numbers,
            "confidence": 0.95,
            "sample_size": 60,
            "effective_event_count": 45,
            "low_cluster_count": False,
        },
        "matched_pairs": 60,
        "unadjusted": None,
    }


def _write_research_run(
    data_dir: Path,
    *,
    run_id: str,
    contract_id: str,
    payload: dict[str, object],
    override: tuple[str, object] | None = None,
    evidence_zone: str = "D0",
    gate_evidence: dict[str, object] | None = None,
    d2_outcome: str | None = None,
) -> str:
    contract_hash = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    hashes = payload["hashes"]
    assert isinstance(hashes, dict)
    dataset_hash: str | None = None
    if evidence_zone == "D0":
        protocol = payload["protocol"]
        assert isinstance(protocol, dict)
        operator = protocol["d0_operator"]
        assert isinstance(operator, dict)
        fixture = operator["fixture"]
        assert isinstance(fixture, dict)
        dataset_hash = str(fixture["definition_fingerprint"])
        run_identity = {
            "command": "research_pilot",
            "project_id": PROJECT_ID,
            "research_contract_id": contract_id,
            "contract_hash": contract_hash,
            "dataset_hash": dataset_hash,
            "execution_fingerprint": "a" * 64,
        }
        run_id = hashlib.sha256(
            json.dumps(run_identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()[:16]
    if evidence_zone == "D2":
        dataset_hash = str(hashes["data"])
        run_id = _d2_run_id(payload, contract_id)
    manifest: dict[str, object] = {
        "run_id": run_id,
        "run_identity_version": 3,
        "command": "research_confirm" if evidence_zone == "D2" else "research_pilot",
        "kind": "research",
        "project_id": PROJECT_ID,
        "research_contract_id": contract_id,
        "contract_hash": contract_hash,
        "source_pack_id": payload["source_pack_id"],
        "research_fingerprints": hashes,
        "evidence_zone": evidence_zone,
        "eligible_for_holdout_or_execution": False,
        "places_orders": False,
        "snapshot_id": None,
        "snapshot_hash": None,
        "execution_fingerprint": "a" * 64,
        "strategy_fingerprint": None,
        "source_fingerprint": contract_hash,
    }
    if evidence_zone == "D0":
        assert dataset_hash is not None
        manifest["dataset_hash"] = dataset_hash
        protocol = payload["protocol"]
        assert isinstance(protocol, dict)
        operator = protocol["d0_operator"]
        assert isinstance(operator, dict)
        manifest["d0_operator"] = operator
        manifest["d0_operator_fingerprint"] = operator["fingerprint"]
        manifest["d0_acceptance_artifact"] = "d0_acceptance.json"
    if evidence_zone == "D2":
        assert dataset_hash is not None
        manifest["dataset_hash"] = dataset_hash
        manifest["watermark"] = "REGISTERED CONFIRMATORY"
        manifest["real_market_evidence"] = True
        manifest["d2_evidence_artifact"] = "research_gate_evidence.json"
        manifest["d2_analyses_artifact"] = "d2_analyses.json"
    if override is not None:
        field, value = override
        if field.startswith("research_fingerprints."):
            fingerprints = dict(hashes)
            fingerprints[field.partition(".")[2]] = value
            manifest["research_fingerprints"] = fingerprints
        else:
            manifest[field] = value
    rdir = _artifacts.run_dir(data_dir, run_id)
    rdir.mkdir(parents=True)
    if evidence_zone == "D0":
        operator_fingerprint = manifest["d0_operator_fingerprint"]
        assert isinstance(operator_fingerprint, str)
        assert dataset_hash is not None
        measurements = _recomputed_d0_measurements(_GENERATION_60M)
        sidecars: dict[str, bytes] = {
            "events.json": b'[{"confirmation_index":8,"second_trough_index":6}]',
            "topology.json": b'{"schema_version":2}',
            "power.json": b'{"known_sigma_fixture_only":true}',
            "chart-data.json": b'{"watermark":"EXPLORATORY"}',
            "detector-validity.png": b"synthetic-d0-chart",
            "report.md": b"# D0 synthetic acceptance\n",
            "d0_acceptance.json": json.dumps(
                _d0_acceptance_payload(
                    generation=_GENERATION_60M,
                    run_id=run_id,
                    project_id=PROJECT_ID,
                    contract_id=contract_id,
                    contract_hash=contract_hash,
                    dataset_hash=dataset_hash,
                    execution_fingerprint="a" * 64,
                    d0_operator_fingerprint=operator_fingerprint,
                    measurements=measurements,
                ),
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8"),
        }
        for filename, content in sidecars.items():

            def write_sidecar(target: Path, *, body: bytes = content) -> None:
                target.write_bytes(body)

            _artifacts.publish_artifact(rdir / filename, write_sidecar)
    if d2_outcome is not None:
        assert gate_evidence is None
        measurements = _d2_matched_measurements(d2_outcome)
        analyses_bytes = json.dumps(
            {"schema": "ResearchD2AnalysesV1", "schema_version": 1, "measurements": measurements},
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")

        def write_analyses(target: Path) -> None:
            target.write_bytes(analyses_bytes)

        _artifacts.publish_artifact(rdir / "d2_analyses.json", write_analyses)
        gate_evidence = dict(
            derive_d2_findings(measurements, claim=_d2_claim(payload)),
            artifact_links=[
                {
                    "run_id": run_id,
                    "artifact_id": "d2_analyses.json",
                    "content_sha256": hashlib.sha256(analyses_bytes).hexdigest(),
                    "media_type": "application/json",
                }
            ],
        )
    if gate_evidence is not None:
        content = json.dumps(
            gate_evidence,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")

        def write_gate_evidence(target: Path) -> None:
            target.write_bytes(content)

        _artifacts.publish_artifact(rdir / "research_gate_evidence.json", write_gate_evidence)
    _artifacts.write_manifest(rdir, manifest)
    return run_id


def _run_only_payload() -> dict[str, object]:
    return {
        "source_pack_id": "sp_" + "1" * 64,
        "hashes": {
            "code": "git:a1b2c3d4e5f60718",
            "environment": "uv-lock:1234abcd5678ef90",
            "evaluator": "event-study-v1.0.0",
            "data": None,
        },
        "protocol": {
            "d0_operator": {
                "schema": "TestRegisteredOperatorV1",
                "fingerprint": "4" * 64,
                "fixture": {"definition_fingerprint": "5" * 64},
            }
        },
    }


def _record_completed_d0(
    store: ControlStore,
    contract_id: str,
    payload: dict[str, object],
    *,
    at: datetime,
) -> str:
    run_id = _write_research_run(
        store._data_dir,
        run_id="ignored-content-derived-id",
        contract_id=contract_id,
        payload=payload,
    )
    store.record_research_attempt(
        PROJECT_ID,
        contract_id,
        kind="d0-synthetic-pilot",
        status="completed",
        config_fingerprint="a" * 64,
        budget_used={"wall_seconds": 1, "source_requests": 0, "variants": 1},
        details={
            "evidence_zone": "D0",
            "d0_acceptance_ref": _d0_acceptance_ref(store._data_dir, run_id),
        },
        run_id=run_id,
        at=at,
    )
    return run_id


def _d0_acceptance_ref(data_dir: Path, run_id: str) -> dict[str, object]:
    manifest = _artifacts.read_manifest(data_dir / "runs" / run_id)
    artifacts = cast(dict[str, object], manifest["artifacts"])
    metadata = cast(dict[str, object], artifacts["d0_acceptance.json"])
    return {
        "artifact": "d0_acceptance.json",
        "content_sha256": metadata["sha256"],
    }


def _rewrite_d0_acceptance_and_manifest(data_dir: Path, run_id: str) -> None:
    run_dir = data_dir / "runs" / run_id
    acceptance_path = run_dir / "d0_acceptance.json"
    acceptance = json.loads(acceptance_path.read_text(encoding="utf-8"))
    acceptance["measurements"]["planted_events"] = []
    acceptance_path.write_text(
        json.dumps(acceptance, sort_keys=True, separators=(",", ":"), allow_nan=False),
        encoding="utf-8",
    )
    manifest_path = run_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["artifacts"]["d0_acceptance.json"] = artifact_metadata(acceptance_path)
    manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")


def test_schema_v1_migrates_additively_and_preserves_legacy_projection(tmp_path: Path) -> None:
    root = tmp_path / "control"
    root.mkdir()
    database = root / "workstation.sqlite3"
    connection = sqlite3.connect(database)
    connection.executescript(
        """
        CREATE TABLE projects (
            project_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            hypothesis TEXT NOT NULL,
            falsification_criterion TEXT NOT NULL,
            status TEXT NOT NULL,
            current_version_id TEXT,
            current_experiment_id TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        ) STRICT;
        """
    )
    expected = {
        "project_id": LEGACY_PROJECT_ID,
        "name": "Legacy project",
        "hypothesis": "Legacy hypothesis",
        "falsification_criterion": "Legacy criterion",
        "status": "active",
        "current_version_id": None,
        "current_experiment_id": None,
        "created_at": "2026-08-05T23:59:00.000000Z",
        "updated_at": "2026-08-05T23:59:00.000000Z",
    }
    post_launch_project_id = "a9fe8545-ac44-48d5-bb01-5517b96002c9"
    post_launch = {
        **expected,
        "project_id": post_launch_project_id,
        "name": "Post-launch v1 project",
        "created_at": "2026-08-06T00:00:00.000000Z",
        "updated_at": "2026-08-06T00:00:00.000000Z",
    }
    connection.execute(
        "INSERT INTO projects VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", tuple(expected.values())
    )
    connection.execute(
        "INSERT INTO projects VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", tuple(post_launch.values())
    )
    connection.execute("PRAGMA user_version = 1")
    connection.commit()
    connection.close()

    assert SCHEMA_VERSION == 5
    # The governance backfill drives the derived gate state: pre-launch rows are
    # grandfathered while post-launch v1 rows stay research-governed and open.
    assert ControlStore(tmp_path).list_projects() == [
        {**post_launch, "research_gate_state": "open"},
        {**expected, "research_gate_state": "not_required"},
    ]
    migrated = sqlite3.connect(database)
    governance = {
        str(row[0]): (int(row[1]), str(row[2]))
        for row in migrated.execute(
            "SELECT project_id, research_required, origin FROM project_research_governance"
        )
    }
    assert migrated.execute("PRAGMA user_version").fetchone() == (SCHEMA_VERSION,)
    tables = {
        str(row[0])
        for row in migrated.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    migrated.close()
    assert {
        "research_contracts",
        "research_contract_review_events",
        "research_phase_events",
        "research_execution_events",
        "research_source_records",
        "research_source_packs",
        "research_attempt_records",
        "research_launch_reservations",
        "research_launch_attempt_links",
    } <= tables
    assert governance == {
        LEGACY_PROJECT_ID: (0, "legacy_import"),
        post_launch_project_id: (1, "strategy_development"),
    }
    assert (root / "workstation.sqlite3.v1.bak").is_file()

    legacy_version = ControlStore(tmp_path).create_strategy_version(
        LEGACY_PROJECT_ID,
        strategy_name="legacy_mean_reversion",
        source_fingerprint="git:legacy-migration",
        definition={"window": 20},
        parameter_space={"window": [20]},
        at=START,
    )
    assert "research_contract_id" not in legacy_version
    with pytest.raises(DataError, match="research_contract_id"):
        ControlStore(tmp_path).create_strategy_version(
            post_launch_project_id,
            strategy_name="must_be_research_governed",
            source_fingerprint="git:post-launch-v1",
            definition={},
            parameter_space={},
            at=START,
        )


def test_fresh_store_is_v5_with_protected_semantic_ledger_and_closed_receipt_action(
    tmp_path: Path,
) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    database = tmp_path / "control" / "workstation.sqlite3"
    connection = sqlite3.connect(database)
    try:
        assert connection.execute("PRAGMA user_version").fetchone() == (5,)
        objects = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table', 'index', 'trigger')"
            )
        }
        assert {
            "research_semantic_events",
            "idx_research_semantic_events_contract",
            "idx_research_semantic_events_source",
            "idx_research_semantic_events_artifact",
            "idx_research_semantic_events_one_review",
            "idx_research_semantic_events_one_freeze",
            "research_semantic_events_no_update",
            "research_semantic_events_no_delete",
        } <= objects
        table_info = connection.execute("PRAGMA table_info(research_semantic_events)").fetchall()
        assert [str(row[1]) for row in table_info] == [
            "event_id",
            "event_sha256",
            "project_id",
            "sequence",
            "event_type",
            "case_contract_id",
            "source_contract_id",
            "case_revision",
            "prior_semantic_head_sha256",
            "semantic_artifact_id",
            "semantic_artifact_sha256",
            "verified_read_sha256",
            "projection_sha256",
            "run_id",
            "cutoff_confirmed_at",
            "definition_id",
            "review_id",
            "review_decision",
            "payload_json",
            "payload_sha256",
            "receipt_id",
            "actor",
            "reason",
            "recorded_at",
        ]
        receipt_sql = str(
            connection.execute(
                "SELECT sql FROM sqlite_master "
                "WHERE type = 'table' AND name = 'owner_action_receipts'"
            ).fetchone()[0]
        )
        assert "record_semantic_event" in receipt_sql
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        connection.close()


def test_v4_to_v5_rebuild_is_lossless_and_retains_exact_backup(tmp_path: Path) -> None:
    database, _ = _v4_database(tmp_path)
    before_rows = _insert_v4_receipt(database)
    before_connection = sqlite3.connect(database)
    try:
        before_digest = hashlib.sha256(
            json.dumps(before_rows, separators=(",", ":"), ensure_ascii=False).encode()
        ).hexdigest()
    finally:
        before_connection.close()

    assert ControlStore(tmp_path).list_projects()[0]["project_id"] == PROJECT_ID
    migrated = sqlite3.connect(database)
    backup = sqlite3.connect(database.with_name("workstation.sqlite3.v4.bak"))
    try:
        assert migrated.execute("PRAGMA user_version").fetchone() == (5,)
        after_rows = migrated.execute(
            "SELECT * FROM owner_action_receipts ORDER BY receipt_id"
        ).fetchall()
        after_digest = hashlib.sha256(
            json.dumps(after_rows, separators=(",", ":"), ensure_ascii=False).encode()
        ).hexdigest()
        assert after_rows == before_rows
        assert len(after_rows) == len(before_rows)
        assert after_digest == before_digest
        assert backup.execute("PRAGMA user_version").fetchone() == (4,)
        assert backup.execute("SELECT * FROM owner_action_receipts").fetchall() == before_rows
    finally:
        migrated.close()
        backup.close()


def test_v4_to_v5_failure_rolls_back_and_exact_retry_succeeds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database, _ = _v4_database(tmp_path)
    original = control_store_module._SCHEMA_V5
    monkeypatch.setattr(
        control_store_module,
        "_SCHEMA_V5",
        original + "\nTHIS IS AN INJECTED V5 MIGRATION FAILURE;",
    )
    with pytest.raises(DataError, match="cannot initialize control store"):
        ControlStore(tmp_path).list_projects()
    source = sqlite3.connect(database)
    backup = sqlite3.connect(database.with_name("workstation.sqlite3.v4.bak"))
    try:
        assert source.execute("PRAGMA user_version").fetchone() == (4,)
        assert backup.execute("PRAGMA user_version").fetchone() == (4,)
        assert (
            source.execute(
                "SELECT 1 FROM sqlite_master WHERE name = 'research_semantic_events'"
            ).fetchone()
            is None
        )
    finally:
        source.close()
        backup.close()
    monkeypatch.setattr(control_store_module, "_SCHEMA_V5", original)
    assert ControlStore(tmp_path).list_projects()[0]["project_id"] == PROJECT_ID


def test_v4_to_v5_rejects_unsafe_existing_backup(tmp_path: Path) -> None:
    database, _ = _v4_database(tmp_path)
    backup = database.with_name("workstation.sqlite3.v4.bak")
    backup.mkdir()
    with pytest.raises(DataError, match="backup is not a file"):
        ControlStore(tmp_path).list_projects()
    connection = sqlite3.connect(database)
    try:
        assert connection.execute("PRAGMA user_version").fetchone() == (4,)
    finally:
        connection.close()


def test_concurrent_v4_migrators_have_one_winner_and_one_backup(tmp_path: Path) -> None:
    database, _ = _v4_database(tmp_path)
    barrier = threading.Barrier(2)
    errors: list[BaseException] = []

    def migrate() -> None:
        try:
            barrier.wait(timeout=5)
            ControlStore(tmp_path).list_projects()
        except BaseException as exc:  # pragma: no cover - assertion reports any race failure
            errors.append(exc)

    threads = [threading.Thread(target=migrate) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    connection = sqlite3.connect(database)
    try:
        assert connection.execute("PRAGMA user_version").fetchone() == (5,)
    finally:
        connection.close()
    assert database.with_name("workstation.sqlite3.v4.bak").is_file()


def test_v5_missing_protected_semantic_object_fails_closed_without_healing(tmp_path: Path) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    database = tmp_path / "control" / "workstation.sqlite3"
    connection = sqlite3.connect(database)
    connection.execute("DROP INDEX idx_research_semantic_events_contract")
    connection.commit()
    connection.close()
    with pytest.raises(DataError, match="protected schema object"):
        ControlStore(tmp_path).list_projects()
    check = sqlite3.connect(database)
    try:
        assert (
            check.execute(
                "SELECT 1 FROM sqlite_master WHERE name = 'idx_research_semantic_events_contract'"
            ).fetchone()
            is None
        )
    finally:
        check.close()


def test_schema_v1_migration_failure_rolls_back_all_ddl_and_retries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "control"
    root.mkdir()
    database = root / "workstation.sqlite3"
    connection = sqlite3.connect(database)
    connection.executescript(
        """
        CREATE TABLE projects (
            project_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            hypothesis TEXT NOT NULL,
            falsification_criterion TEXT NOT NULL,
            status TEXT NOT NULL,
            current_version_id TEXT,
            current_experiment_id TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        ) STRICT;
        PRAGMA user_version = 1;
        """
    )
    expected = (
        LEGACY_PROJECT_ID,
        "Interrupted v1 project",
        "Interrupted migration preserves this hypothesis.",
        "Reject if a partial schema survives rollback.",
        "active",
        None,
        None,
        "2026-08-05T23:59:00.000000Z",
        "2026-08-05T23:59:00.000000Z",
    )
    connection.execute("INSERT INTO projects VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", expected)
    connection.commit()
    connection.close()

    schema_v2 = control_store_module._SCHEMA_V2
    monkeypatch.setattr(
        control_store_module,
        "_SCHEMA_V2",
        schema_v2 + "\nTHIS IS AN INJECTED MIGRATION FAILURE;",
    )
    with pytest.raises(DataError, match="cannot initialize control store"):
        ControlStore(tmp_path).list_projects()

    backup = root / "workstation.sqlite3.v1.bak"
    source = sqlite3.connect(database)
    retained_backup = sqlite3.connect(backup)
    try:
        assert source.execute("PRAGMA user_version").fetchone() == (1,)
        assert retained_backup.execute("PRAGMA user_version").fetchone() == (1,)
        assert control_store_module._logical_database_fingerprint(
            source
        ) == control_store_module._logical_database_fingerprint(retained_backup)
    finally:
        source.close()
        retained_backup.close()

    monkeypatch.setattr(control_store_module, "_SCHEMA_V2", schema_v2)
    assert ControlStore(tmp_path).list_projects()[0]["project_id"] == LEGACY_PROJECT_ID
    migrated = sqlite3.connect(database)
    try:
        assert migrated.execute("PRAGMA user_version").fetchone() == (SCHEMA_VERSION,)
    finally:
        migrated.close()


def _migration_v1_database(tmp_path: Path) -> tuple[Path, tuple[object, ...]]:
    root = tmp_path / "control"
    root.mkdir()
    database = root / "workstation.sqlite3"
    connection = sqlite3.connect(database)
    connection.executescript(
        """
        CREATE TABLE projects (
            project_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            hypothesis TEXT NOT NULL,
            falsification_criterion TEXT NOT NULL,
            status TEXT NOT NULL,
            current_version_id TEXT,
            current_experiment_id TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        ) STRICT;
        PRAGMA user_version = 1;
        """
    )
    legacy_row: tuple[object, ...] = (
        LEGACY_PROJECT_ID,
        "Migration guard project",
        "Migration preserves the exact locked v1 state.",
        "Reject if backup validation or transactional DDL fails.",
        "active",
        None,
        None,
        "2026-08-05T23:59:00.000000Z",
        "2026-08-05T23:59:00.000000Z",
    )
    connection.execute("INSERT INTO projects VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", legacy_row)
    connection.commit()
    connection.close()
    return database, legacy_row


@pytest.mark.parametrize(
    ("backup_kind", "message"),
    [
        pytest.param("symlink", "must not be a symlink", id="symlink"),
        pytest.param("directory", "is not a file", id="non-file"),
        pytest.param("invalid", "backup is invalid", id="invalid-sqlite"),
    ],
)
def test_schema_v1_migration_rejects_unsafe_existing_backup(
    tmp_path: Path,
    backup_kind: str,
    message: str,
) -> None:
    database, legacy_row = _migration_v1_database(tmp_path)
    backup = database.with_name(f"{database.name}.v1.bak")
    if backup_kind == "symlink":
        target = database.with_name("untrusted-backup-target")
        target.write_text("not a database", encoding="utf-8")
        backup.symlink_to(target)
    elif backup_kind == "directory":
        backup.mkdir()
    else:
        invalid = sqlite3.connect(backup)
        invalid.close()

    with pytest.raises(DataError, match=message):
        ControlStore(tmp_path).list_projects()

    source = sqlite3.connect(database)
    try:
        assert source.execute("PRAGMA user_version").fetchone() == (1,)
        assert source.execute("SELECT * FROM projects").fetchall() == [legacy_row]
    finally:
        source.close()


def test_new_schema_v1_backup_rejects_invalid_snapshot_and_cleans_temp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database, _ = _migration_v1_database(tmp_path)
    source = sqlite3.connect(database, isolation_level=None)
    source.execute("PRAGMA journal_mode = WAL")
    source.execute("BEGIN IMMEDIATE")
    original_connect = sqlite3.connect

    class CorruptingSnapshot:
        def __init__(self, delegate: sqlite3.Connection) -> None:
            self.delegate = delegate

        @property
        def in_transaction(self) -> bool:
            return self.delegate.in_transaction

        def execute(self, statement: str) -> sqlite3.Cursor:
            return self.delegate.execute(statement)

        def backup(self, target: sqlite3.Connection) -> None:
            self.delegate.backup(target)
            target.execute("PRAGMA user_version = 0")
            target.commit()

        def rollback(self) -> None:
            self.delegate.rollback()

        def close(self) -> None:
            self.delegate.close()

    def corrupt_snapshot_connect(path: Any, *args: Any, **kwargs: Any) -> Any:
        connected = original_connect(path, *args, **kwargs)
        if Path(path) == database:
            return CorruptingSnapshot(connected)
        return connected

    monkeypatch.setattr(sqlite3, "connect", corrupt_snapshot_connect)
    try:
        with pytest.raises(DataError, match="cannot verify control store v1 migration backup"):
            control_store_module._verified_v1_backup(source, database)
    finally:
        source.rollback()
        source.close()

    assert not database.with_name(f"{database.name}.v1.bak").exists()
    assert list(database.parent.glob(f".{database.name}.v1.bak.*.tmp")) == []


def test_new_schema_v1_backup_rejects_fingerprint_mismatch_and_cleans_temp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database, _ = _migration_v1_database(tmp_path)
    source = sqlite3.connect(database, isolation_level=None)
    source.execute("PRAGMA journal_mode = WAL")
    source.execute("BEGIN IMMEDIATE")
    original_fingerprint = control_store_module._logical_database_fingerprint
    fingerprint_calls = 0

    def mismatch_first_fingerprint(connection: sqlite3.Connection) -> str:
        nonlocal fingerprint_calls
        fingerprint_calls += 1
        fingerprint = original_fingerprint(connection)
        return "f" * 64 if fingerprint_calls == 1 else fingerprint

    monkeypatch.setattr(
        control_store_module, "_logical_database_fingerprint", mismatch_first_fingerprint
    )
    try:
        with pytest.raises(DataError, match="backup does not match the current database"):
            control_store_module._verified_v1_backup(source, database)
    finally:
        source.rollback()
        source.close()

    assert fingerprint_calls == 2
    assert not database.with_name(f"{database.name}.v1.bak").exists()
    assert list(database.parent.glob(f".{database.name}.v1.bak.*.tmp")) == []


def test_static_schema_helpers_fail_closed_and_rollback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    connection = sqlite3.connect(tmp_path / "helpers.sqlite3", isolation_level=None)
    try:
        with pytest.raises(sqlite3.OperationalError, match="active transaction"):
            control_store_module._apply_schema_v2_locked(connection)

        connection.execute("BEGIN IMMEDIATE")
        with pytest.raises(sqlite3.OperationalError, match="incomplete static"):
            control_store_module._execute_static_sql_script(
                connection, "CREATE TABLE incomplete (value TEXT"
            )
        connection.rollback()

        monkeypatch.setattr(
            control_store_module,
            "_SCHEMA_V2",
            "CREATE TABLE rolled_back (value TEXT);\nTHIS IS INVALID SQL;",
        )
        with pytest.raises(sqlite3.OperationalError):
            control_store_module._apply_schema_v2(connection)
        assert connection.in_transaction is False
        assert (
            connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'rolled_back'"
            ).fetchone()
            is None
        )
        assert connection.execute("PRAGMA user_version").fetchone() == (0,)
    finally:
        connection.close()


def test_locked_v1_migration_rejects_unsupported_version_and_rolls_back(tmp_path: Path) -> None:
    database = tmp_path / "unsupported.sqlite3"
    connection = sqlite3.connect(database, isolation_level=None)
    connection.execute("PRAGMA user_version = 99")
    with pytest.raises(DataError, match="unsupported control store schema version 99"):
        control_store_module._migrate_schema_v1(connection, database)
    assert connection.in_transaction is False
    assert connection.execute("PRAGMA user_version").fetchone() == (99,)
    connection.close()


@pytest.mark.parametrize(
    ("budget", "require_minimum", "message"),
    [
        pytest.param("not-an-object", False, "must be a JSON object", id="not-object"),
        pytest.param({}, True, "requires wall_seconds", id="missing-minimums"),
        pytest.param({"wall_seconds": -1}, False, "non-negative", id="negative"),
        pytest.param({"wall_seconds": float("inf")}, False, "finite JSON", id="infinite"),
    ],
)
def test_research_budget_validation_fails_closed(
    budget: object,
    require_minimum: bool,
    message: str,
) -> None:
    with pytest.raises(DataError, match=message):
        control_store_module._budget_values(budget, require_minimum=require_minimum)


def test_schema_v1_backup_and_migration_hold_one_writer_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "control"
    root.mkdir()
    database = root / "workstation.sqlite3"
    connection = sqlite3.connect(database)
    connection.executescript(
        """
        CREATE TABLE projects (
            project_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            hypothesis TEXT NOT NULL,
            falsification_criterion TEXT NOT NULL,
            status TEXT NOT NULL,
            current_version_id TEXT,
            current_experiment_id TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        ) STRICT;
        PRAGMA user_version = 1;
        """
    )
    legacy_row = (
        LEGACY_PROJECT_ID,
        "Locked legacy project",
        "The backup and migration share one serialized legacy snapshot.",
        "Reject if a writer can enter after backup creation.",
        "active",
        None,
        None,
        "2026-08-05T23:59:00.000000Z",
        "2026-08-05T23:59:00.000000Z",
    )
    connection.execute("INSERT INTO projects VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", legacy_row)
    connection.commit()
    expected_fingerprint = control_store_module._logical_database_fingerprint(connection)
    connection.close()

    backup_ready = threading.Event()
    release_migration = threading.Event()
    original_backup = control_store_module._verified_v1_backup

    def hold_after_backup(locked: sqlite3.Connection, path: Path) -> None:
        original_backup(locked, path)
        backup_ready.set()
        if not release_migration.wait(timeout=5):
            raise AssertionError("timed out waiting to release the migration lock")

    monkeypatch.setattr(control_store_module, "_verified_v1_backup", hold_after_backup)
    migration_errors: list[BaseException] = []
    concurrent_migration_errors: list[BaseException] = []
    concurrent_initial_versions: list[int] = []
    concurrent_begin = threading.Event()

    def migrate() -> None:
        try:
            ControlStore(tmp_path).list_projects()
        except BaseException as exc:  # pragma: no cover - asserted below for thread handoff.
            migration_errors.append(exc)

    def concurrent_migrate() -> None:
        connection = sqlite3.connect(database, timeout=5.0, isolation_level=None)
        try:
            version = connection.execute("PRAGMA user_version").fetchone()
            concurrent_initial_versions.append(int(version[0]))

            def observe_transaction(
                action: int,
                _arg1: str | None,
                _arg2: str | None,
                _database_name: str | None,
                _trigger_name: str | None,
            ) -> int:
                if action == sqlite3.SQLITE_TRANSACTION:
                    concurrent_begin.set()
                return sqlite3.SQLITE_OK

            connection.set_authorizer(observe_transaction)
            control_store_module._migrate_schema_v1(connection, database)
        except BaseException as exc:  # pragma: no cover - asserted below for thread handoff.
            concurrent_migration_errors.append(exc)
        finally:
            connection.close()

    migrator = threading.Thread(target=migrate)
    second_migrator = threading.Thread(target=concurrent_migrate)
    migrator.start()
    try:
        assert backup_ready.wait(timeout=5)
        writer = sqlite3.connect(database, timeout=0.05, isolation_level=None)
        try:
            writer.execute("PRAGMA busy_timeout = 50")
            with pytest.raises(sqlite3.OperationalError, match="locked"):
                writer.execute("BEGIN IMMEDIATE")
        finally:
            writer.close()
        second_migrator.start()
        assert concurrent_begin.wait(timeout=5)
    finally:
        release_migration.set()
        migrator.join(timeout=5)
        if second_migrator.ident is not None:
            second_migrator.join(timeout=5)

    assert not migrator.is_alive()
    assert not second_migrator.is_alive()
    assert migration_errors == []
    assert concurrent_migration_errors == []
    assert concurrent_initial_versions == [1]
    migrated = sqlite3.connect(database)
    backup = sqlite3.connect(root / "workstation.sqlite3.v1.bak")
    try:
        assert migrated.execute("PRAGMA user_version").fetchone() == (SCHEMA_VERSION,)
        assert control_store_module._logical_database_fingerprint(backup) == expected_fingerprint
        assert backup.execute("SELECT * FROM projects").fetchall() == [legacy_row]
    finally:
        migrated.close()
        backup.close()


def test_existing_schema_v2_reopen_adds_launch_reservation_tables(tmp_path: Path) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    database = tmp_path / "control" / "workstation.sqlite3"
    connection = sqlite3.connect(database)
    assert connection.execute("PRAGMA user_version").fetchone() == (SCHEMA_VERSION,)
    connection.execute("DROP TABLE research_launch_attempt_links")
    connection.execute("DROP TABLE research_launch_reservations")
    connection.commit()
    connection.close()

    assert ControlStore(tmp_path).get_project(PROJECT_ID)["project_id"] == PROJECT_ID
    reopened = sqlite3.connect(database)
    tables = {
        str(row[0])
        for row in reopened.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    reopened.close()
    assert {"research_launch_reservations", "research_launch_attempt_links"} <= tables


def test_new_projects_require_research_and_legacy_import_is_migration_only(
    tmp_path: Path,
) -> None:
    store = ControlStore(tmp_path)
    store.create_project(
        name="Fresh strategy project",
        hypothesis="A fresh strategy hypothesis.",
        falsification_criterion="Reject when confirmation is not economically meaningful.",
        project_id=PROJECT_ID,
        at=START,
    )
    with pytest.raises(DataError, match="research_contract_id"):
        store.create_strategy_version(
            PROJECT_ID,
            strategy_name="ungoverned_attempt",
            source_fingerprint="git:must-not-bypass",
            definition={},
            parameter_space={},
            at=START + timedelta(minutes=1),
        )

    with pytest.raises(DataError, match="unsupported project research origin"):
        store.create_project(
            name="Backdated fake legacy project",
            hypothesis="This record did not predate the research program.",
            falsification_criterion="Reject the forged grandfathering claim.",
            research_origin="legacy_import",  # type: ignore[arg-type]
            project_id=LEGACY_PROJECT_ID,
            at=datetime(2026, 8, 5, 23, 59, tzinfo=UTC),
        )
    store.create_project(
        name="Backdated governed project",
        hypothesis="A caller-controlled timestamp must not change governance.",
        falsification_criterion="Reject if a strategy can bypass research.",
        project_id=LEGACY_PROJECT_ID,
        at=datetime(2026, 8, 5, 23, 59, tzinfo=UTC),
    )
    with pytest.raises(DataError, match="research_contract_id"):
        store.create_strategy_version(
            LEGACY_PROJECT_ID,
            strategy_name="backdated_bypass_attempt",
            source_fingerprint="git:must-still-be-governed",
            definition={},
            parameter_space={},
            at=START + timedelta(minutes=2),
        )


def test_lost_governance_row_is_not_silently_recreated_on_reopen(tmp_path: Path) -> None:
    """A missing governance row must stay missing; reopen must not re-derive it from created_at."""
    store = ControlStore(tmp_path)
    store.create_project(
        name="Backdated governed project",
        hypothesis="Reopening the store must not re-derive governance from created_at.",
        falsification_criterion="Reject if schema scripts recreate governance rows.",
        project_id=PROJECT_ID,
        at=datetime(2026, 8, 5, 23, 59, tzinfo=UTC),
    )
    database = tmp_path / "control" / control_store_module.DATABASE_NAME
    connection = sqlite3.connect(database)
    try:
        deleted = connection.execute(
            "DELETE FROM project_research_governance WHERE project_id = ?", (PROJECT_ID,)
        )
        assert deleted.rowcount == 1
        connection.commit()
    finally:
        connection.close()

    with contextlib.suppress(DataError):
        ControlStore(tmp_path).list_projects()

    connection = sqlite3.connect(database)
    try:
        rows = connection.execute(
            "SELECT research_required, origin FROM project_research_governance"
            " WHERE project_id = ?",
            (PROJECT_ID,),
        ).fetchall()
    finally:
        connection.close()
    assert rows == []


def test_read_projection_does_not_take_the_writer_lock_at_open(tmp_path: Path) -> None:
    """Steady-state opens must issue no write-bearing statement, so reads never contend."""
    store = ControlStore(tmp_path)
    _project(store)
    database = tmp_path / "control" / control_store_module.DATABASE_NAME
    writer = sqlite3.connect(database)
    try:
        writer.execute("BEGIN IMMEDIATE")
        projects = ControlStore(tmp_path).list_projects()
    finally:
        writer.close()
    assert [row["project_id"] for row in projects] == [PROJECT_ID]


@pytest.mark.parametrize(
    "fault_label",
    ["project", "governance", "scope", "contract", "captured", "execution", "d2", "triage"],
)
def test_research_capture_is_atomic_and_retry_idempotent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault_label: str
) -> None:
    store = ControlStore(tmp_path)
    payload = draft_exploration_contract(
        "SPY double bottoms may precede positive four-hour returns."
    )
    kwargs = {
        "name": "Atomic capture fixture",
        "hypothesis": "SPY double bottoms may precede positive four-hour returns.",
        "falsification_criterion": "Reject when registered controls do not support the claim.",
        "draft_payload": payload,
        "created_by": "codex",
        "next_action": "Owner answers the material question batch.",
        "responsibility": "owner",
        "blocker": "The chart, event time, and outcome are unresolved.",
        "recovery": "Answer the bounded question batch.",
    }
    original = ControlStore._capture_fault_checkpoint

    def fail_at(label: str) -> None:
        if label == fault_label:
            raise DataError(f"fault after {label}")

    monkeypatch.setattr(ControlStore, "_capture_fault_checkpoint", staticmethod(fail_at))
    with pytest.raises(DataError, match=f"fault after {fault_label}"):
        store.capture_research_case(**kwargs)  # type: ignore[arg-type]
    assert store.list_projects() == []
    # Row-level proof of atomicity: no partial write survives in ANY capture-touched table.
    database = tmp_path / "control" / control_store_module.DATABASE_NAME
    connection = sqlite3.connect(database)
    try:
        for table in (
            "projects",
            "project_research_governance",
            "project_scope_events",
            "research_contracts",
            "research_phase_events",
            "research_execution_events",
            "research_d2_events",
        ):
            count = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()  # noqa: S608
            assert count == (0,), f"partial {table} row survived the {fault_label} fault"
    finally:
        connection.close()

    monkeypatch.setattr(ControlStore, "_capture_fault_checkpoint", staticmethod(original))
    first = store.capture_research_case(**kwargs)  # type: ignore[arg-type]
    replay = store.capture_research_case(**kwargs)  # type: ignore[arg-type]
    assert replay == first
    assert len(store.list_projects()) == 1
    assert cast(dict[str, object], first["case"])["phase"] == "triage"


def test_schema_v1_migration_rejects_a_stale_valid_backup(tmp_path: Path) -> None:
    root = tmp_path / "control"
    root.mkdir()
    database = root / "workstation.sqlite3"
    connection = sqlite3.connect(database)
    connection.executescript(
        """
        CREATE TABLE projects (
            project_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            hypothesis TEXT NOT NULL,
            falsification_criterion TEXT NOT NULL,
            status TEXT NOT NULL,
            current_version_id TEXT,
            current_experiment_id TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        ) STRICT;
        PRAGMA user_version = 1;
        """
    )
    first = (
        LEGACY_PROJECT_ID,
        "Original v1 project",
        "Original hypothesis",
        "Original falsifier",
        "active",
        None,
        None,
        "2026-08-05T23:58:00.000000Z",
        "2026-08-05T23:58:00.000000Z",
    )
    connection.execute("INSERT INTO projects VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", first)
    connection.commit()
    connection.close()
    backup = root / "workstation.sqlite3.v1.bak"
    shutil.copyfile(database, backup)

    connection = sqlite3.connect(database)
    second = (
        PROJECT_ID,
        "Later committed v1 project",
        "Later hypothesis",
        "Later falsifier",
        "active",
        None,
        None,
        "2026-08-05T23:59:00.000000Z",
        "2026-08-05T23:59:00.000000Z",
    )
    connection.execute("INSERT INTO projects VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", second)
    connection.commit()
    connection.close()

    with pytest.raises(DataError, match="backup does not match the current database"):
        ControlStore(tmp_path).list_projects()

    source = sqlite3.connect(database)
    retained_backup = sqlite3.connect(backup)
    try:
        assert source.execute("PRAGMA user_version").fetchone() == (1,)
        assert source.execute("SELECT COUNT(*) FROM projects").fetchone() == (2,)
        assert retained_backup.execute("SELECT COUNT(*) FROM projects").fetchone() == (1,)
    finally:
        source.close()
        retained_backup.close()


def test_sources_contracts_reuse_content_ids_and_owner_reviews_fail_closed(
    tmp_path: Path,
) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    pack_id = _source_pack(store)
    contract = store.create_research_contract(
        PROJECT_ID,
        scope="exploration",
        payload=_payload(pack_id),
        created_by="codex",
        author_kind="agent",
        at=START + timedelta(minutes=3),
    )
    reused = store.create_research_contract(
        PROJECT_ID,
        scope="exploration",
        payload=_payload(pack_id),
        created_by="codex",
        author_kind="agent",
        at=START + timedelta(minutes=30),
    )
    contract_id = str(contract["contract_id"])
    assert reused == contract
    assert contract_id.startswith("rc_")
    assert pack_id.startswith("sp_")

    with pytest.raises(DataError, match="owner review requires a human actor"):
        store.review_research_contract(
            PROJECT_ID,
            contract_id,
            scope="exploration",
            decision="approve",
            actor="codex",
            actor_kind="agent",
            reason="Agents cannot approve themselves.",
        )
    with pytest.raises(DataError, match="approved exploration parent"):
        store.create_research_contract(
            PROJECT_ID,
            scope="confirmation",
            parent_contract_id=contract_id,
            payload=_payload(pack_id, confirmation=True),
            created_by="codex",
            author_kind="agent",
        )

    store.transition_research_phase(
        PROJECT_ID,
        to_phase="triage",
        contract_id=contract_id,
        actor="codex",
        reason="The idea is ready for triage.",
        next_action="Prepare the review packet.",
        responsibility="codex",
        at=START + timedelta(minutes=31),
    )
    store.transition_research_phase(
        PROJECT_ID,
        to_phase="exploration_review",
        contract_id=contract_id,
        actor="codex",
        reason="The review packet is complete.",
        next_action="Approve or reject exploration.",
        responsibility="owner",
        at=START + timedelta(minutes=32),
    )
    review = store.review_research_contract(
        PROJECT_ID,
        contract_id,
        scope="exploration",
        decision="approve",
        actor="owner",
        actor_kind="human",
        reason="Approved for exploration.",
        at=START + timedelta(minutes=33),
    )
    assert review["decision"] == "approve"
    assert store.get_research_contract(contract_id)["review_state"] == "approved"


def test_phase_confirmation_and_d2_state_machines_are_distinct(tmp_path: Path) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    pack_id = _source_pack(store)
    payload = _payload(pack_id)
    exploration = store.create_research_contract(
        PROJECT_ID,
        scope="exploration",
        payload=payload,
        created_by="codex",
        author_kind="agent",
        at=START + timedelta(minutes=3),
    )
    exploration_id = str(exploration["contract_id"])
    store.transition_research_phase(
        PROJECT_ID,
        to_phase="triage",
        contract_id=exploration_id,
        actor="codex",
        reason="The idea has enough detail for triage.",
        next_action="Check data and literature feasibility.",
        responsibility="codex",
        at=START + timedelta(minutes=4),
    )
    store.transition_research_phase(
        PROJECT_ID,
        to_phase="exploration_review",
        contract_id=exploration_id,
        actor="codex",
        reason="The exploration protocol is ready for owner review.",
        next_action="Approve or reject the exploration contract.",
        responsibility="owner",
        at=START + timedelta(minutes=5),
    )
    with pytest.raises(DataError, match="exploration approval"):
        store.transition_research_phase(
            PROJECT_ID,
            to_phase="pilot",
            contract_id=exploration_id,
            actor="codex",
            reason="Must not skip D1 approval.",
            next_action="Run the pilot.",
            responsibility="codex",
        )
    store.review_research_contract(
        PROJECT_ID,
        exploration_id,
        scope="exploration",
        decision="approve",
        actor="owner",
        actor_kind="human",
        reason="Exploration approved.",
        at=START + timedelta(minutes=6),
    )
    store.transition_research_phase(
        PROJECT_ID,
        to_phase="pilot",
        contract_id=exploration_id,
        actor="codex",
        reason="Advance to pilot.",
        next_action="Execute pilot work.",
        responsibility="codex",
        at=START + timedelta(minutes=7),
    )
    _record_completed_d0(
        store,
        exploration_id,
        _payload(pack_id),
        at=START + timedelta(minutes=7, seconds=30),
    )
    store.transition_research_phase(
        PROJECT_ID,
        to_phase="deep_research",
        contract_id=exploration_id,
        actor="codex",
        reason="Advance to deep_research.",
        next_action="Execute deep_research work.",
        responsibility="codex",
        at=START + timedelta(minutes=8),
    )
    confirmation_payload = _payload(pack_id, confirmation=True)
    confirmation = store.create_research_contract(
        PROJECT_ID,
        scope="confirmation",
        parent_contract_id=exploration_id,
        payload=confirmation_payload,
        created_by="codex",
        author_kind="agent",
        at=START + timedelta(minutes=9),
    )
    confirmation_id = str(confirmation["contract_id"])
    store.transition_research_phase(
        PROJECT_ID,
        to_phase="confirmation_review",
        contract_id=confirmation_id,
        actor="codex",
        reason="The child confirmation contract is frozen for review.",
        next_action="Approve or reject D2 consumption.",
        responsibility="owner",
        at=START + timedelta(minutes=10),
    )
    summary = store.research_case_summary(PROJECT_ID)
    assert summary["d2_state"] == "sealed"
    assert summary["confirmation_review"]["state"] == "pending"  # type: ignore[index]

    store.review_research_contract(
        PROJECT_ID,
        confirmation_id,
        scope="confirmation",
        decision="approve",
        actor="owner",
        actor_kind="human",
        reason="Authorize the exact child contract, without consuming D2 yet.",
        at=START + timedelta(minutes=11),
    )
    assert store.research_case_summary(PROJECT_ID)["d2_state"] == "authorized"
    store.transition_research_phase(
        PROJECT_ID,
        to_phase="sealed_confirmation",
        contract_id=confirmation_id,
        actor="codex",
        reason="The child contract is approved and D2 remains sealed until execution.",
        next_action="Run the sealed confirmation once.",
        responsibility="codex",
        at=START + timedelta(minutes=12),
    )
    with pytest.raises(DataError, match="D2 must be consumed"):
        store.transition_research_phase(
            PROJECT_ID,
            to_phase="research_decision",
            contract_id=confirmation_id,
            actor="codex",
            reason="Cannot decide before confirmation executes.",
            next_action="Draft the research decision.",
            responsibility="codex",
        )
    store.transition_research_d2_state(
        PROJECT_ID,
        confirmation_id,
        to_state="consumed",
        actor="system",
        reason="The exact sealed confirmation job started.",
        at=START + timedelta(minutes=13),
    )
    run_id = _write_research_run(
        tmp_path,
        run_id="ignored-content-derived-id",
        contract_id=confirmation_id,
        payload=confirmation_payload,
        evidence_zone="D2",
        d2_outcome="SUPPORTED",
    )
    store.record_research_attempt(
        PROJECT_ID,
        confirmation_id,
        kind="sealed-confirmation",
        status="completed",
        config_fingerprint="a" * 64,
        budget_used={"wall_seconds": 1, "source_requests": 0, "variants": 1},
        details={
            "evidence_zone": "D2",
            "real_market_evidence": True,
            "gate_packet_evidence_ref": _d2_evidence_ref(tmp_path, run_id),
        },
        run_id=run_id,
        at=START + timedelta(minutes=13, seconds=30),
    )
    store.transition_research_phase(
        PROJECT_ID,
        to_phase="research_decision",
        contract_id=confirmation_id,
        actor="codex",
        reason="Confirmation results are ready for a decision.",
        next_action="Owner accepts, rejects, or revises the research conclusion.",
        responsibility="owner",
        at=START + timedelta(minutes=14),
    )
    final = store.research_case_summary(PROJECT_ID)
    assert final["phase"] == "research_decision"
    assert final["d2_state"] == "consumed"
    assert final["d3_state"] == "not_sealed"
    assert final["next_action"] == ("Owner accepts, rejects, or revises the research conclusion.")
    assert final["responsibility"] == "owner"


def test_execution_attempts_and_budget_projection_are_independent(tmp_path: Path) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    pack_id = _source_pack(store)
    payload = _payload(pack_id)
    exploration = store.create_research_contract(
        PROJECT_ID,
        scope="exploration",
        payload=payload,
        created_by="codex",
        author_kind="agent",
        at=START + timedelta(minutes=3),
    )
    exploration_id = str(exploration["contract_id"])
    store.transition_research_phase(
        PROJECT_ID,
        to_phase="triage",
        contract_id=exploration_id,
        actor="codex",
        reason="The idea is ready for triage.",
        next_action="Prepare exploration review.",
        responsibility="codex",
        at=START + timedelta(minutes=4),
    )
    store.transition_research_phase(
        PROJECT_ID,
        to_phase="exploration_review",
        contract_id=exploration_id,
        actor="codex",
        reason="The contract is ready for review.",
        next_action="Approve or reject exploration.",
        responsibility="owner",
        at=START + timedelta(minutes=5),
    )
    store.review_research_contract(
        PROJECT_ID,
        exploration_id,
        scope="exploration",
        decision="approve",
        actor="owner",
        actor_kind="human",
        reason="Approve the bounded pilot.",
        at=START + timedelta(minutes=6),
    )
    store.transition_research_phase(
        PROJECT_ID,
        to_phase="pilot",
        contract_id=exploration_id,
        actor="codex",
        reason="Exploration was approved.",
        next_action="Run the pilot.",
        responsibility="codex",
        at=START + timedelta(minutes=7),
    )
    store.transition_research_execution(
        PROJECT_ID,
        to_state="queued",
        contract_id=exploration_id,
        actor="codex",
        reason="The approved pilot is queued.",
        next_action="Acquire the research worker.",
        responsibility="codex",
        checkpoint="pilot:queued",
        at=START + timedelta(minutes=8),
    )
    store.transition_research_execution(
        PROJECT_ID,
        to_state="running",
        contract_id=exploration_id,
        actor="system",
        reason="The pilot worker started.",
        next_action="Evaluate the registered variants.",
        responsibility="codex",
        checkpoint="pilot:variant-1",
        at=START + timedelta(minutes=9),
    )
    run_id = _write_research_run(
        tmp_path,
        run_id="d000000000000001",
        contract_id=exploration_id,
        payload=payload,
    )
    attempt = store.record_research_attempt(
        PROJECT_ID,
        exploration_id,
        kind="d0-synthetic-pilot",
        status="completed",
        config_fingerprint="a" * 64,
        budget_used={"wall_seconds": 600, "source_requests": 4, "variants": 8},
        details={
            "effect": 0.0012,
            "evidence_zone": "D0",
            "d0_acceptance_ref": _d0_acceptance_ref(tmp_path, run_id),
        },
        run_id=run_id,
        at=START + timedelta(minutes=10),
    )
    assert str(attempt["attempt_id"]).startswith("ra_")
    store.transition_research_execution(
        PROJECT_ID,
        to_state="paused",
        contract_id=exploration_id,
        actor="codex",
        reason="Pause at the deterministic checkpoint for owner input.",
        next_action="Review the pilot confounder table.",
        responsibility="owner",
        checkpoint="pilot:variant-8",
        blocker="The weekday control changes the effect sign.",
        recovery="Owner chooses whether the mechanism remains plausible.",
        at=START + timedelta(minutes=11),
    )
    summary = store.research_case_summary(PROJECT_ID)
    assert summary["execution_state"] == "paused"
    assert summary["checkpoint"] == "pilot:variant-8"
    assert summary["blocker"] == "The weekday control changes the effect sign."
    assert summary["elapsed_budget"] == {
        "source_requests": 4,
        "variants": 8,
        "wall_seconds": 600,
    }
    assert summary["remaining_budget"] == {
        "source_requests": 56,
        "variants": 120,
        "wall_seconds": 13_800,
    }
    assert isinstance(summary["milestones"], list)


def test_governed_strategy_and_experiment_bind_exact_confirmation_contract(
    tmp_path: Path,
) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    _, confirmation_id = _approved_contracts(store)
    with pytest.raises(DataError, match="research_contract_id"):
        store.create_strategy_version(
            PROJECT_ID,
            strategy_name="double_bottom",
            source_fingerprint="git:3333333",
            definition={"detector": "causal-double-bottom-v1"},
            parameter_space={"tolerance": [0.005, 0.01]},
            at=START + timedelta(minutes=7),
        )
    version = store.create_strategy_version(
        PROJECT_ID,
        strategy_name="double_bottom",
        source_fingerprint="git:3333333",
        definition={"detector": "causal-double-bottom-v1"},
        parameter_space={"tolerance": [0.005, 0.01]},
        research_contract_id=confirmation_id,
        at=START + timedelta(minutes=7),
    )
    assert version["research_contract_id"] == confirmation_id
    version_id = str(version["version_id"])
    with pytest.raises(DataError, match="matching research_contract_id"):
        store.create_experiment_spec(
            PROJECT_ID,
            strategy_version_id=version_id,
            snapshot_id="snapshot-spy",
            universe=["SPY"],
            split_policy={"train": 504, "test": 63},
            costs={"fee_bps": 1},
            seeds={"master": 7},
        )
    experiment = store.create_experiment_spec(
        PROJECT_ID,
        strategy_version_id=version_id,
        snapshot_id="snapshot-spy",
        universe=["SPY"],
        split_policy={"train": 504, "test": 63},
        costs={"fee_bps": 1},
        seeds={"master": 7},
        research_contract_id=confirmation_id,
        at=START + timedelta(minutes=8),
    )
    assert experiment["research_contract_id"] == confirmation_id

    store.create_project(
        name="Grandfathered mean reversion",
        hypothesis="Large daily deviations mean-revert after costs.",
        falsification_criterion="Reject when locked OOS Sharpe is non-positive.",
        project_id=LEGACY_PROJECT_ID,
        at=datetime(2026, 8, 5, 23, 59, tzinfo=UTC),
    )
    mark_project_as_migrated_legacy(store, LEGACY_PROJECT_ID)
    legacy = store.create_strategy_version(
        LEGACY_PROJECT_ID,
        strategy_name="mean_reversion",
        source_fingerprint="git:legacy",
        definition={"window": 20},
        parameter_space={"window": [20]},
        at=START + timedelta(minutes=9),
    )
    identity = {
        "schema_version": 1,
        "strategy_name": "mean_reversion",
        "source_fingerprint": "git:legacy",
        "definition": {"window": 20},
        "parameter_space": {"window": [20]},
    }
    canonical = json.dumps(identity, sort_keys=True, separators=(",", ":"), allow_nan=False)
    expected_id = f"sv_{hashlib.sha256(canonical.encode('utf-8')).hexdigest()}"
    assert legacy["version_id"] == expected_id
    assert "research_contract_id" not in legacy


def test_incomplete_draft_cannot_cross_exploration_review(tmp_path: Path) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    draft = store.create_research_contract(
        PROJECT_ID,
        scope="exploration",
        payload={
            "schema": "ResearchContractV1",
            "approval_ready": False,
            "blocking_questions": ["What exactly counts as a bounce?"],
            "thesis": {"raw_idea": "SPY double bottoms bounce"},
            "source_pack_id": None,
        },
        created_by="codex",
        author_kind="agent",
        at=START + timedelta(minutes=1),
    )
    contract_id = str(draft["contract_id"])
    for minute, phase in ((2, "triage"), (3, "exploration_review")):
        store.transition_research_phase(
            PROJECT_ID,
            to_phase=phase,  # type: ignore[arg-type]
            contract_id=contract_id,
            actor="codex",
            reason=f"Move the draft to {phase}.",
            next_action="Resolve the blocking questions.",
            responsibility="owner",
            at=START + timedelta(minutes=minute),
        )
    with pytest.raises(DataError, match="approval_ready=true"):
        store.review_research_contract(
            PROJECT_ID,
            contract_id,
            scope="exploration",
            decision="approve",
            actor="owner",
            actor_kind="human",
            reason="An incomplete draft must not be approvable.",
        )
    summary = store.research_case_summary(PROJECT_ID)
    assert summary["exploration_review"]["state"] == "pending"  # type: ignore[index]
    assert summary["d2_state"] == "sealed"


@pytest.mark.parametrize("mutation", ["hash", "dataset", "share", "chart"])
def test_approval_recomputes_canonical_d2_boundary_semantics(tmp_path: Path, mutation: str) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    payload = _payload(_source_pack(store))
    protocol = cast(dict[str, object], payload["protocol"])
    topology = cast(dict[str, object], protocol["evidence_topology"])
    d2 = cast(dict[str, object], topology["D2"])
    boundary = cast(dict[str, object], topology["boundary"])
    if mutation == "hash":
        d2["boundary_hash"] = "f" * 64
    elif mutation == "dataset":
        boundary["dataset_fingerprint"] = "f" * 64
    elif mutation == "share":
        cast(dict[str, object], topology["D1"])["share"] = 0.50
    else:
        chart = cast(dict[str, object], protocol["chart_fingerprint"])
        chart["instrument"] = "ES"
    contract = store.create_research_contract(
        PROJECT_ID,
        scope="exploration",
        payload=payload,
        created_by="codex",
        author_kind="agent",
        at=START + timedelta(minutes=3),
    )
    contract_id = str(contract["contract_id"])
    for minute, phase in ((4, "triage"), (5, "exploration_review")):
        store.transition_research_phase(
            PROJECT_ID,
            to_phase=phase,  # type: ignore[arg-type]
            contract_id=contract_id,
            actor="codex",
            reason=f"Advance to {phase}.",
            next_action="Validate the canonical boundary.",
            responsibility="owner" if phase == "exploration_review" else "codex",
            at=START + timedelta(minutes=minute),
        )
    with pytest.raises(DataError, match="boundary|share|chart"):
        store.review_research_contract(
            PROJECT_ID,
            contract_id,
            scope="exploration",
            decision="approve",
            actor="owner",
            actor_kind="human",
            reason="A mutated boundary must fail closed.",
        )


@pytest.mark.parametrize("mutation", ["unregistered_family", "over_budget_grid", "not_object"])
def test_approval_validates_a_declared_analysis_plan(tmp_path: Path, mutation: str) -> None:
    """A frozen analysis_plan is validated at approval; invalid plans fail closed."""
    from alpha_cli.research_analysis_plan import default_analysis_plan

    store = ControlStore(tmp_path)
    _project(store)
    payload = _payload(_source_pack(store))
    plan = default_analysis_plan(horizon_bars=4)
    if mutation == "unregistered_family":
        families = cast(list[dict[str, object]], plan["families"])
        families[0] = {**families[0], "family": "kitchen_sink_scan"}
        payload["analysis_plan"] = plan
    elif mutation == "over_budget_grid":
        families = cast(list[dict[str, object]], plan["families"])
        families[0] = {
            **families[0],
            "grid": {"horizon_bars": list(range(1, 13)), "window": list(range(1, 13))},
        }
        payload["analysis_plan"] = plan
    else:
        payload["analysis_plan"] = "run everything"
    contract = store.create_research_contract(
        PROJECT_ID,
        scope="exploration",
        payload=payload,
        created_by="codex",
        author_kind="agent",
        at=START + timedelta(minutes=3),
    )
    contract_id = str(contract["contract_id"])
    for minute, phase in ((4, "triage"), (5, "exploration_review")):
        store.transition_research_phase(
            PROJECT_ID,
            to_phase=phase,  # type: ignore[arg-type]
            contract_id=contract_id,
            actor="codex",
            reason=f"Advance to {phase}.",
            next_action="Validate the frozen analysis plan.",
            responsibility="owner" if phase == "exploration_review" else "codex",
            at=START + timedelta(minutes=minute),
        )
    with pytest.raises(DataError, match="unregistered|budget|analysis_plan"):
        store.review_research_contract(
            PROJECT_ID,
            contract_id,
            scope="exploration",
            decision="approve",
            actor="owner",
            actor_kind="human",
            reason="An invalid analysis plan must fail closed.",
        )


def test_approval_accepts_the_registered_default_analysis_plan(tmp_path: Path) -> None:
    from alpha_cli.research_analysis_plan import default_analysis_plan

    store = ControlStore(tmp_path)
    _project(store)
    payload = _payload(_source_pack(store))
    payload["analysis_plan"] = default_analysis_plan(horizon_bars=4)
    protocol = cast(dict[str, object], payload["protocol"])
    protocol["d0_operator"] = registered_d0_operator(payload)
    contract = store.create_research_contract(
        PROJECT_ID,
        scope="exploration",
        payload=payload,
        created_by="codex",
        author_kind="agent",
        at=START + timedelta(minutes=3),
    )
    contract_id = str(contract["contract_id"])
    for minute, phase in ((4, "triage"), (5, "exploration_review")):
        store.transition_research_phase(
            PROJECT_ID,
            to_phase=phase,  # type: ignore[arg-type]
            contract_id=contract_id,
            actor="codex",
            reason=f"Advance to {phase}.",
            next_action="Approve the plan-bearing contract.",
            responsibility="owner" if phase == "exploration_review" else "codex",
            at=START + timedelta(minutes=minute),
        )
    review = store.review_research_contract(
        PROJECT_ID,
        contract_id,
        scope="exploration",
        decision="approve",
        actor="owner",
        actor_kind="human",
        reason="The registered default analysis plan is approvable.",
        at=START + timedelta(minutes=6),
    )
    assert review["decision"] == "approve"


def _approved_deep_case(store: ControlStore) -> tuple[str, dict[str, object]]:
    """Approve a plan-bearing exploration contract and advance it into deep_research."""
    from alpha_cli.research_analysis_plan import default_analysis_plan

    pack_id = _source_pack(store)
    payload = _payload(pack_id)
    payload["analysis_plan"] = default_analysis_plan(horizon_bars=4)
    contract = store.create_research_contract(
        PROJECT_ID,
        scope="exploration",
        payload=payload,
        created_by="codex",
        author_kind="agent",
        at=START + timedelta(minutes=3),
    )
    contract_id = str(contract["contract_id"])
    for minute, phase, responsibility in (
        (4, "triage", "codex"),
        (5, "exploration_review", "owner"),
    ):
        store.transition_research_phase(
            PROJECT_ID,
            to_phase=phase,  # type: ignore[arg-type]
            contract_id=contract_id,
            actor="codex",
            reason=f"Advance the deep fixture to {phase}.",
            next_action="Continue toward deep research.",
            responsibility=responsibility,  # type: ignore[arg-type]
            at=START + timedelta(minutes=minute),
        )
    store.review_research_contract(
        PROJECT_ID,
        contract_id,
        scope="exploration",
        decision="approve",
        actor="owner",
        actor_kind="human",
        reason="The plan-bearing exploration contract is approvable.",
        at=START + timedelta(minutes=6),
    )
    store.transition_research_phase(
        PROJECT_ID,
        to_phase="pilot",
        contract_id=contract_id,
        actor="codex",
        reason="Exploration was approved.",
        next_action="Run the bounded pilot.",
        responsibility="codex",
        at=START + timedelta(minutes=7),
    )
    _record_completed_d0(store, contract_id, payload, at=START + timedelta(minutes=8))
    store.transition_research_phase(
        PROJECT_ID,
        to_phase="deep_research",
        contract_id=contract_id,
        actor="codex",
        reason="D0 is complete and the analysis plan is frozen.",
        next_action="Launch the registered deep-research plan.",
        responsibility="codex",
        at=START + timedelta(minutes=9),
    )
    return contract_id, payload


def _published_d1_run(
    store: ControlStore, contract_id: str, payload: dict[str, object]
) -> dict[str, object]:
    from datetime import UTC as _UTC

    from alpha_cli.research_d1 import research_bars_from_lows, run_deep_research

    motif = (105.0, 103.0, 100.0, 95.0, 99.0, 101.0, 100.0, 95.5, 99.0, 101.0)
    lows: list[float] = []
    for _week in range(8):
        for day in range(7):
            if day == 0:
                lows.extend(motif)
                level = motif[-1]
                for hour in range(14):
                    level = level + 1.5 if hour < 6 else level
                    lows.append(level)
            else:
                lows.extend([100.0] * 24)
    bars = research_bars_from_lows(
        lows,
        dataset_id="d1-store-fixture",
        content_sha256="c" * 64,
        start=datetime(2020, 1, 6, tzinfo=_UTC),
    )
    return run_deep_research(
        store._data_dir,
        project_id=PROJECT_ID,
        contract_id=contract_id,
        contract=payload,
        bars=bars,
    )


def _d1_evidence_ref(store: ControlStore, manifest: dict[str, object]) -> dict[str, object]:
    artifacts = cast(dict[str, object], manifest["artifacts"])
    metadata = cast(dict[str, object], artifacts["research_gate_evidence.json"])
    return {"artifact": "research_gate_evidence.json", "content_sha256": metadata["sha256"]}


def test_d1_attempt_admission_reverifies_evidence_mechanically(tmp_path: Path) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    contract_id, payload = _approved_deep_case(store)
    manifest = _published_d1_run(store, contract_id, payload)
    attempt = store.record_research_attempt(
        PROJECT_ID,
        contract_id,
        kind="d1-deep-research",
        status="completed",
        config_fingerprint=str(manifest["execution_fingerprint"]),
        budget_used={"variants": 6},
        details={
            "evidence_zone": "D1",
            "finding": "The registered plan executed on the discovery share.",
            "gate_packet_evidence_ref": _d1_evidence_ref(store, manifest),
        },
        run_id=str(manifest["run_id"]),
        at=START + timedelta(minutes=10),
    )
    assert attempt["status"] == "completed"
    verified = store.verified_research_attempt(PROJECT_ID, str(attempt["attempt_id"]))
    assert cast("dict[str, object]", verified["manifest"])["evidence_zone"] == "D1"

    # Rewrite a finding status with a consistent manifest hash: the mechanical
    # recomputation from raw measurements must still fail closed.
    run_dir = store._data_dir / "runs" / str(manifest["run_id"])
    evidence_path = run_dir / "research_gate_evidence.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    evidence["negative_controls"] = {"status": "PASSED", "summary": "forged"}
    forged = json.dumps(evidence, sort_keys=True, separators=(",", ":"), allow_nan=False)
    evidence_path.write_text(forged, encoding="utf-8")
    manifest_path = run_dir / "manifest.json"
    stored_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entry = stored_manifest["artifacts"]["research_gate_evidence.json"]
    entry["sha256"] = hashlib.sha256(forged.encode("utf-8")).hexdigest()
    entry["size_bytes"] = len(forged.encode("utf-8"))
    manifest_path.write_text(
        json.dumps(stored_manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    with pytest.raises(DataError, match="recomputation|manifest"):
        store.verified_research_attempt(PROJECT_ID, str(attempt["attempt_id"]))


def test_d1_attempts_pin_kind_and_require_typed_evidence(tmp_path: Path) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    contract_id, payload = _approved_deep_case(store)
    manifest = _published_d1_run(store, contract_id, payload)
    with pytest.raises(DataError, match="d1-deep-research"):
        store.record_research_attempt(
            PROJECT_ID,
            contract_id,
            kind="event-study",
            status="completed",
            config_fingerprint=str(manifest["execution_fingerprint"]),
            budget_used={},
            details={"evidence_zone": "D1"},
            run_id=str(manifest["run_id"]),
            at=START + timedelta(minutes=10),
        )
    with pytest.raises(DataError, match="typed gate evidence"):
        store.record_research_attempt(
            PROJECT_ID,
            contract_id,
            kind="d1-deep-research",
            status="completed",
            config_fingerprint=str(manifest["execution_fingerprint"]),
            budget_used={},
            details={"evidence_zone": "D1"},
            run_id=str(manifest["run_id"]),
            at=START + timedelta(minutes=10),
        )


def test_research_job_creation_is_governed_and_capacity_bound(tmp_path: Path) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    with pytest.raises(DataError, match="governed internal executor"):
        store.create_job(kind="research:event-study", request={"stage": "deep"})
    contract_id, _payload_unused = _approved_deep_case(store)
    job = store.create_research_job(
        PROJECT_ID,
        contract_id=contract_id,
        request={"stage": "deep", "contract_id": contract_id},
        at=START + timedelta(minutes=10),
    )
    assert job["kind"] == "research:event-study"
    with pytest.raises(DataError, match="capacity"):
        store.create_research_job(
            PROJECT_ID,
            contract_id=contract_id,
            request={"stage": "deep", "second": True},
            at=START + timedelta(minutes=11),
        )


def test_early_inconclusive_decision_keeps_d2_sealed_and_cannot_advance(
    tmp_path: Path,
) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    pack_id = _source_pack(store)
    exploration = store.create_research_contract(
        PROJECT_ID,
        scope="exploration",
        payload=_payload(pack_id),
        created_by="codex",
        author_kind="agent",
        at=START + timedelta(minutes=3),
    )
    contract_id = str(exploration["contract_id"])
    for minute, phase, responsibility in (
        (4, "triage", "codex"),
        (5, "exploration_review", "owner"),
    ):
        store.transition_research_phase(
            PROJECT_ID,
            to_phase=phase,  # type: ignore[arg-type]
            contract_id=contract_id,
            actor="codex",
            reason=f"Advance to {phase}.",
            next_action="Complete the current gate.",
            responsibility=responsibility,  # type: ignore[arg-type]
            at=START + timedelta(minutes=minute),
        )
    store.review_research_contract(
        PROJECT_ID,
        contract_id,
        scope="exploration",
        decision="approve",
        actor="owner",
        actor_kind="human",
        reason="Approve the pilot only.",
        at=START + timedelta(minutes=6),
    )
    store.transition_research_phase(
        PROJECT_ID,
        to_phase="pilot",
        contract_id=contract_id,
        actor="codex",
        reason="The pilot is authorized.",
        next_action="Run the power diagnostic.",
        responsibility="codex",
        at=START + timedelta(minutes=7),
    )
    store.transition_research_phase(
        PROJECT_ID,
        to_phase="research_decision",
        contract_id=contract_id,
        actor="codex",
        reason="The pilot cannot reach the preregistered power target.",
        next_action="Park the idea or obtain more qualified data.",
        responsibility="owner",
        blocker="Insufficient independent events for target power.",
        recovery="Acquire more history without opening D2 or park the idea.",
        at=START + timedelta(minutes=8),
    )
    decision = store.record_research_decision(
        PROJECT_ID,
        contract_id,
        outcome="INCONCLUSIVE",
        disposition="park",
        actor="owner",
        actor_kind="human",
        reason="Power is insufficient; D2 remains sealed.",
        at=START + timedelta(minutes=9),
    )
    assert decision["outcome"] == "INCONCLUSIVE"
    summary = store.research_case_summary(PROJECT_ID)
    assert summary["d2_state"] == "sealed"
    assert summary["confirmation_contract_id"] is None
    with pytest.raises(DataError, match="approved confirmation contract"):
        store.create_strategy_version(
            PROJECT_ID,
            strategy_name="double_bottom",
            source_fingerprint="git:abcdef123456",
            definition={"detector": "v1"},
            parameter_space={},
            research_contract_id=contract_id,
        )


def test_evidence_free_and_d0_only_paths_cannot_claim_contradicted(tmp_path: Path) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    contract_id, _ = _approved_pilot(store)

    with pytest.raises(DataError, match="only as INCONCLUSIVE or INVALID"):
        store.close_early_research_case(
            PROJECT_ID,
            outcome="CONTRADICTED",
            disposition="reject",
            actor="owner",
            reason="No typed non-synthetic evidence exists.",
            at=START + timedelta(minutes=8),
        )

    store.transition_research_phase(
        PROJECT_ID,
        to_phase="research_decision",
        contract_id=contract_id,
        actor="system",
        reason="Stop before any empirical evidence is available.",
        next_action="Owner records an inconclusive or invalid early disposition.",
        responsibility="owner",
        at=START + timedelta(minutes=9),
    )
    with pytest.raises(DataError, match="typed non-synthetic evidence"):
        store.record_research_decision(
            PROJECT_ID,
            contract_id,
            outcome="CONTRADICTED",
            disposition="reject",
            actor="owner",
            actor_kind="human",
            reason="D0 cannot contradict a market thesis.",
            at=START + timedelta(minutes=10),
        )

    summary = store.research_case_summary(PROJECT_ID)
    assert summary["research_decision"] is None
    assert summary["d2_state"] == "sealed"


def test_generic_research_jobs_remain_reserved(tmp_path: Path) -> None:
    with pytest.raises(DataError, match="reserved"):
        ControlStore(tmp_path).create_job(kind="research:event-study", request={})


def test_confirmation_decision_requires_one_mechanically_classified_d2_attempt(
    tmp_path: Path,
) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    _, confirmation_id = _approved_contracts(
        store,
        record_confirmation_evidence=False,
        record_decision=False,
        transition_to_decision=False,
    )

    with pytest.raises(DataError, match="typed D2 evidence"):
        store.transition_research_phase(
            PROJECT_ID,
            to_phase="research_decision",
            contract_id=confirmation_id,
            actor="owner",
            reason="A consumed boundary alone cannot establish support.",
            next_action="Do not present an evidence-free decision.",
            responsibility="owner",
            at=START + timedelta(minutes=15),
        )


def test_confirmation_decision_cannot_override_mechanical_d2_classification(
    tmp_path: Path,
) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    _, confirmation_id = _approved_contracts(
        store,
        outcome="INCONCLUSIVE",
        disposition="park",
        record_decision=False,
    )

    with pytest.raises(DataError, match="mechanical D2 classification"):
        store.record_research_decision(
            PROJECT_ID,
            confirmation_id,
            outcome="SUPPORTED",
            disposition="advance_to_strategy",
            actor="owner",
            actor_kind="human",
            reason="The owner cannot relabel an inconclusive result as support.",
            at=START + timedelta(minutes=15),
        )


def test_contaminated_confirmation_can_close_only_as_invalid(tmp_path: Path) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    _, confirmation_id = _approved_contracts(
        store,
        record_confirmation_evidence=False,
        record_decision=False,
        d2_state="contaminated",
    )

    decision = store.record_research_decision(
        PROJECT_ID,
        confirmation_id,
        outcome="INVALID",
        disposition="park",
        actor="owner",
        actor_kind="human",
        reason="The contaminated lineage cannot answer the claim.",
        at=START + timedelta(minutes=15),
    )
    assert decision["outcome"] == "INVALID"


def _promotion_packets(store: ControlStore) -> list[dict[str, object]]:
    return [
        packet
        for packet in store.list_research_context_packets(PROJECT_ID)
        if packet["packet_kind"] == "strategy_promotion"
    ]


def _close_decided_case(store: ControlStore, confirmation_id: str) -> None:
    store.transition_research_phase(
        PROJECT_ID,
        to_phase="closed",
        contract_id=confirmation_id,
        actor="owner",
        reason="owner recorded the terminal research disposition",
        next_action="Research case is closed; any revision starts a new contract lineage.",
        responsibility="owner",
        at=START + timedelta(minutes=16),
    )


def test_advance_decision_records_lossless_promotion_packet_atomically(tmp_path: Path) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    _, confirmation_id = _approved_contracts(store)
    assert _promotion_packets(store) == []  # decision alone is not yet the terminal state
    _close_decided_case(store, confirmation_id)

    packets = _promotion_packets(store)
    assert len(packets) == 1
    payload = packets[0]["payload"]
    assert isinstance(payload, dict)
    assert payload["packet_schema"] == "StrategyPromotionPacketV1"

    decision = payload["decision"]
    assert isinstance(decision, dict)
    assert decision["contract_id"] == confirmation_id
    assert decision["outcome"] == "SUPPORTED"
    assert decision["disposition"] == "advance_to_strategy"

    # The reference binds the exact deterministic terminal gate packet, byte for byte.
    terminal = build_research_gate_packet(store.research_gate_packet_inputs(PROJECT_ID)).to_dict()
    assert payload["gate_packet_reference"] == {
        "packet_id": terminal["packet_id"],
        "packet_hash": terminal["packet_hash"],
    }

    card = payload["hypothesis_card"]
    assert isinstance(card, dict)
    assert card["card_schema"] == "HypothesisCardV1"
    for section in (
        "registered_datasets",
        "screened_source_claims",
        "confounder_ledger",
        "falsification",
        "stability_findings",
        "known_failure_conditions",
        "assumptions_limitations",
        "headline_chart_references",
        "negative_attempt_summary",
        "open_questions",
    ):
        assert section in payload

    charts = payload["headline_chart_references"]
    assert isinstance(charts, list)
    expected_chart_sha = hashlib.sha256(b'{"watermark":"EXPLORATORY"}').hexdigest()
    assert any(
        chart["artifact"] == "chart-data.json" and chart["content_sha256"] == expected_chart_sha
        for chart in charts
        if isinstance(chart, dict)
    )

    summary = payload["negative_attempt_summary"]
    assert isinstance(summary, dict)
    assert summary["total_attempts"] == 2  # the completed D0 pilot plus the sealed D2 attempt
    assert summary["by_status"] == {"completed": 2}
    assert summary["non_completed_attempt_ids"] == []

    fetched = store.get_research_context_packet(str(packets[0]["packet_id"]))
    assert fetched["payload"] == payload


def test_non_advance_decisions_record_no_promotion_packet(tmp_path: Path) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    _, confirmation_id = _approved_contracts(store, outcome="INCONCLUSIVE", disposition="park")
    _close_decided_case(store, confirmation_id)

    assert _promotion_packets(store) == []


def test_promotion_packet_is_idempotent_across_decision_replay(tmp_path: Path) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    _, confirmation_id = _approved_contracts(store)

    # Crash-between-decide-and-close recovery: the decision replay returns the stored row
    # without a packet, and exactly one close records exactly one promotion dossier.
    replay = store.record_research_decision(
        PROJECT_ID,
        confirmation_id,
        outcome="SUPPORTED",
        disposition="advance_to_strategy",
        actor="owner",
        actor_kind="human",
        reason="The owner accepts the mechanical frozen-confirmation classification.",
        at=START + timedelta(minutes=20),
    )
    assert replay["outcome"] == "SUPPORTED"
    assert _promotion_packets(store) == []

    _close_decided_case(store, confirmation_id)
    first = _promotion_packets(store)
    assert len(first) == 1
    with pytest.raises(DataError, match="invalid research phase transition"):
        _close_decided_case(store, confirmation_id)
    packets = _promotion_packets(store)
    assert len(packets) == 1
    assert packets[0]["packet_id"] == first[0]["packet_id"]


def test_agent_brief_embeds_promotion_reference_and_survives_as_of(tmp_path: Path) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    _, confirmation_id = _approved_contracts(store)
    _close_decided_case(store, confirmation_id)
    store.create_strategy_version(
        PROJECT_ID,
        strategy_name="double_bottom",
        source_fingerprint="git:3333333",
        definition={"detector": "causal-double-bottom-v1"},
        parameter_space={"tolerance": [0.005, 0.01]},
        research_contract_id=confirmation_id,
        at=START + timedelta(minutes=17),
    )

    context = store.get_agent_brief_context(PROJECT_ID)
    promotion = context["research_promotion"]
    assert isinstance(promotion, dict)
    assert promotion["contract_id"] == confirmation_id
    assert str(promotion["packet_id"]).startswith("cp_")
    terminal = build_research_gate_packet(store.research_gate_packet_inputs(PROJECT_ID)).to_dict()
    assert promotion["gate_packet_id"] == terminal["packet_id"]
    assert promotion["gate_packet_hash"] == terminal["packet_hash"]

    # Point-in-time reads never inherit a later strategy selection or its promotion packet.
    before = store.get_agent_brief_context(
        PROJECT_ID, as_of=START + timedelta(minutes=16, seconds=30)
    )
    assert before["research_promotion"] is None
    after = store.get_agent_brief_context(PROJECT_ID, as_of=START + timedelta(minutes=17))
    assert after["research_promotion"] == promotion


def _legacy_project(store: ControlStore) -> None:
    store.create_project(
        name="Pre-program momentum project",
        hypothesis="A grandfathered strategy project predating the research program.",
        falsification_criterion="Reject when the legacy edge stops clearing costs.",
        project_id=LEGACY_PROJECT_ID,
        at=datetime(2026, 8, 5, 23, 59, tzinfo=UTC),
    )
    mark_project_as_migrated_legacy(store, LEGACY_PROJECT_ID)


def test_research_gate_state_derivation_covers_all_states(tmp_path: Path) -> None:
    store = ControlStore(tmp_path)
    _legacy_project(store)
    assert store.research_gate_state(LEGACY_PROJECT_ID) == "not_required"

    _project(store)
    assert store.research_gate_state(PROJECT_ID) == "open"

    store.record_research_gate_override(
        PROJECT_ID,
        actor="owner",
        reason="Owner accepts exploratory-only engine work before research completes.",
        at=START + timedelta(minutes=1),
    )
    assert store.research_gate_state(PROJECT_ID) == "overridden"

    # A completed research pass supersedes any earlier override.
    _approved_contracts(store)
    assert store.research_gate_state(PROJECT_ID) == "passed"

    states = {row["project_id"]: row["research_gate_state"] for row in store.list_projects()}
    assert states[PROJECT_ID] == "passed"
    assert states[LEGACY_PROJECT_ID] == "not_required"
    assert store.get_project(PROJECT_ID)["research_gate_state"] == "passed"
    assert store.get_project(LEGACY_PROJECT_ID)["research_gate_state"] == "not_required"

    with pytest.raises(DataError, match="unknown strategy project"):
        store.research_gate_state("11111111-2222-4333-8444-555555555555")


def test_research_gate_override_is_append_only_and_fails_closed(tmp_path: Path) -> None:
    store = ControlStore(tmp_path)
    _legacy_project(store)
    with pytest.raises(DataError, match="no research gate"):
        store.record_research_gate_override(
            LEGACY_PROJECT_ID,
            actor="owner",
            reason="A grandfathered project has nothing to override.",
        )

    _project(store)
    first = store.record_research_gate_override(
        PROJECT_ID,
        actor="owner",
        reason="Owner accepts exploratory-only engine work before research completes.",
        at=START + timedelta(minutes=1),
    )
    second = store.record_research_gate_override(
        PROJECT_ID,
        actor="owner",
        reason="Re-affirmed after the adversarial review of the open case.",
        at=START + timedelta(minutes=2),
    )
    assert (first["sequence"], second["sequence"]) == (1, 2)

    overrides = store.get_project(PROJECT_ID)["research_gate_overrides"]
    assert isinstance(overrides, list)
    assert [row["sequence"] for row in overrides] == [1, 2]
    assert overrides[0]["actor"] == "owner"
    assert overrides[0]["reason"] == (
        "Owner accepts exploratory-only engine work before research completes."
    )
    assert overrides[1]["recorded_at"] == "2026-08-06T09:02:00.000000Z"

    active = store.list_active_research_gate_overrides()
    assert [(row["project_id"], row["sequence"]) for row in active] == [
        (PROJECT_ID, 2),
        (PROJECT_ID, 1),
    ]
    assert active[0]["project_name"] == "SPY four-hour double bottom"

    with pytest.raises(DataError, match="reason"):
        store.record_research_gate_override(PROJECT_ID, actor="owner", reason="   ")

    # A passed gate can no longer be overridden, and its overrides go inactive.
    _approved_contracts(store)
    with pytest.raises(DataError, match="already passed"):
        store.record_research_gate_override(
            PROJECT_ID,
            actor="owner",
            reason="An override after the pass would only muddy the ledger.",
        )
    assert store.list_active_research_gate_overrides() == []
    recorded = store.get_project(PROJECT_ID)["research_gate_overrides"]
    assert isinstance(recorded, list)
    assert [row["sequence"] for row in recorded] == [1, 2]


def test_overridden_gate_permits_unlinked_strategy_version(tmp_path: Path) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    with pytest.raises(DataError, match="research_contract_id"):
        store.create_strategy_version(
            PROJECT_ID,
            strategy_name="premature_probe",
            source_fingerprint="git:blocked-before-override",
            definition={},
            parameter_space={},
            at=START + timedelta(minutes=1),
        )

    store.record_research_gate_override(
        PROJECT_ID,
        actor="owner",
        reason="Owner accepts exploratory-only engine work before research completes.",
        at=START + timedelta(minutes=1),
    )
    version = store.create_strategy_version(
        PROJECT_ID,
        strategy_name="exploratory_probe",
        source_fingerprint="git:override-watermarked",
        definition={"detector": "exploratory-probe-v1"},
        parameter_space={"lookback": [20, 60]},
        at=START + timedelta(minutes=2),
    )
    version_id = str(version["version_id"])
    assert version_id.startswith("sv_")
    # The overridden path never forges research linkage.
    assert "research_contract_id" not in version
    spec = store.create_experiment_spec(
        PROJECT_ID,
        strategy_version_id=version_id,
        snapshot_id="snap-override",
        universe=["SPY"],
        split_policy={"train": 504, "test": 63},
        costs={"fee_bps": 1.0},
        seeds={"root": 7},
        at=START + timedelta(minutes=2, seconds=30),
    )
    assert str(spec["experiment_id"]).startswith("ex_")

    # Once research passes, unlinked versions re-lock: linkage becomes mandatory.
    _approved_contracts(store)
    with pytest.raises(DataError, match="research_contract_id"):
        store.create_strategy_version(
            PROJECT_ID,
            strategy_name="post_pass_unlinked",
            source_fingerprint="git:must-link-after-pass",
            definition={},
            parameter_space={},
            at=START + timedelta(minutes=30),
        )


def test_research_attempt_accepts_only_exact_contract_bound_run(tmp_path: Path) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    contract_id, payload = _approved_pilot(store)
    run_id = _write_research_run(
        tmp_path,
        run_id="a100000000000001",
        contract_id=contract_id,
        payload=payload,
    )

    attempt = store.record_research_attempt(
        PROJECT_ID,
        contract_id,
        kind="d0-synthetic-pilot",
        status="completed",
        config_fingerprint="a" * 64,
        budget_used={"wall_seconds": 1, "source_requests": 0, "variants": 1},
        details={
            "evidence_zone": "D0",
            "d0_acceptance_ref": _d0_acceptance_ref(tmp_path, run_id),
        },
        run_id=run_id,
        at=START + timedelta(minutes=8),
    )

    assert attempt["run_id"] == run_id


def test_verified_blind_semantic_resolver_reads_registered_d0_without_writing(
    tmp_path: Path,
) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    contract_id, payload = _approved_pilot(store)
    run_id = _record_completed_d0(store, contract_id, payload, at=START + timedelta(minutes=8))
    database = tmp_path / "control" / control_store_module.DATABASE_NAME
    before = database.read_bytes()

    resolved = store.verified_blind_semantic_artifacts(PROJECT_ID)

    assert resolved["run_id"] == run_id
    assert isinstance(resolved["acceptance_bytes"], bytes)
    assert isinstance(resolved["events_bytes"], bytes)
    assert isinstance(resolved["chart_data_bytes"], bytes)
    assert database.read_bytes() == before


def test_verified_semantic_selected_read_uses_one_descriptor_and_hard_cap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    contents = {
        "d0_acceptance.json": b"acceptance",
        "events.json": b"events",
        "chart-data.json": b"chart",
    }
    manifest_artifacts: dict[str, object] = {}
    for filename, content in contents.items():
        (run_dir / filename).write_bytes(content)
        manifest_artifacts[filename] = {
            "size_bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        }
    calls: list[int] = []
    original_read = os.read

    def bounded_read(descriptor: int, amount: int) -> bytes:
        calls.append(amount)
        return original_read(descriptor, amount)

    monkeypatch.setattr(os, "read", bounded_read)
    resolved = ControlStore._read_verified_semantic_artifacts(
        run_dir, {"artifacts": manifest_artifacts}
    )

    assert resolved["events.json"] == b"events"
    assert calls
    assert max(calls) <= max(len(content) for content in contents.values()) + 1


def test_research_run_admission_rejects_legacy_manifest_downgrade(tmp_path: Path) -> None:
    store = ControlStore(tmp_path)
    contract_id = "rc_" + "2" * 64
    payload = _run_only_payload()
    run_id = _write_research_run(
        tmp_path,
        run_id="a100000000000002",
        contract_id=contract_id,
        payload=payload,
    )
    manifest_path = tmp_path / "runs" / run_id / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["schema_version"] = 1
    manifest["run_identity_version"] = 1
    manifest.pop("artifact_contract_version")
    manifest.pop("artifacts")
    manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")

    with pytest.raises(DataError, match="immutable v3"):
        store._require_research_run(
            run_id,
            project_id=PROJECT_ID,
            contract_id=contract_id,
            contract_payload=payload,
            phase="pilot",
            config_fingerprint="a" * 64,
        )


def test_research_run_admission_rejects_self_consistent_but_underived_run_id(
    tmp_path: Path,
) -> None:
    store = ControlStore(tmp_path)
    contract_id = "rc_" + "6" * 64
    payload = _run_only_payload()
    derived_run_id = _write_research_run(
        tmp_path,
        run_id="ignored-content-derived-id",
        contract_id=contract_id,
        payload=payload,
    )
    forged_run_id = "f" * 16
    assert forged_run_id != derived_run_id
    source = tmp_path / "runs" / derived_run_id
    target = tmp_path / "runs" / forged_run_id
    source.rename(target)
    manifest_path = target / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["run_id"] = forged_run_id
    manifest_path.write_text(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )

    with pytest.raises(DataError, match="content-derived identity"):
        store._require_research_run(
            forged_run_id,
            project_id=PROJECT_ID,
            contract_id=contract_id,
            contract_payload=payload,
            phase="pilot",
            config_fingerprint="a" * 64,
        )


def test_generic_evidence_ledger_rejects_research_runs(tmp_path: Path) -> None:
    store = ControlStore(tmp_path)
    contract_id = "rc_" + "3" * 64
    payload = _run_only_payload()
    run_id = _write_research_run(
        tmp_path,
        run_id="a100000000000003",
        contract_id=contract_id,
        payload=payload,
    )

    with pytest.raises(DataError, match="research runs cannot enter the generic evidence ledger"):
        store.create_evidence(
            claim="Synthetic double-bottom acceptance predicts real SPY returns.",
            assets=["SPY"],
            frozen_universe=["SPY"],
            timeframe="4h",
            method="synthetic_fixture",
            knowledge_at=START + timedelta(minutes=8),
            author="codex",
            author_kind="agent",
            source_run_id=run_id,
            source_artifact="manifest.json",
            source_field="outcomes.planted_pattern.passed",
            at=START + timedelta(minutes=8),
        )

    assert store.list_evidence() == []


def test_pilot_rejects_typed_d1_evidence_without_linking_an_attempt(tmp_path: Path) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    contract_id, payload = _approved_pilot(store)
    run_id = _write_research_run(
        tmp_path,
        run_id="d100000000000001",
        contract_id=contract_id,
        payload=payload,
    )
    manifest = _artifacts.read_manifest(tmp_path / "runs" / run_id)
    acceptance_metadata = manifest["artifacts"]["d0_acceptance.json"]

    with pytest.raises(DataError, match="D0 pilot cannot carry typed D1 or D2"):
        store.record_research_attempt(
            PROJECT_ID,
            contract_id,
            kind="d0-synthetic-pilot",
            status="completed",
            config_fingerprint="a" * 64,
            budget_used={"wall_seconds": 1, "source_requests": 0, "variants": 1},
            details={
                "evidence_zone": "D0",
                "gate_packet_evidence_ref": {
                    "artifact": "d0_acceptance.json",
                    "content_sha256": acceptance_metadata["sha256"],
                },
            },
            run_id=run_id,
            at=START + timedelta(minutes=8),
        )
    assert store.research_case_summary(PROJECT_ID)["attempt_count"] == 0


def test_pilot_cannot_forge_completion_or_advance_without_passing_run(tmp_path: Path) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    contract_id, payload = _approved_pilot(store)
    with pytest.raises(DataError, match="exactly one completed immutable D0"):
        store.transition_research_phase(
            PROJECT_ID,
            to_phase="deep_research",
            contract_id=contract_id,
            actor="codex",
            reason="A direct transition must fail.",
            next_action="Keep D1 closed.",
            responsibility="codex",
        )
    with pytest.raises(DataError, match="only the registered d0-synthetic-pilot"):
        store.record_research_attempt(
            PROJECT_ID,
            contract_id,
            kind="arbitrary-pilot",
            status="failed",
            config_fingerprint="a" * 64,
            budget_used={"wall_seconds": 1},
            details={"evidence_zone": "D0"},
            error="expected fixture rejection",
        )
    with pytest.raises(DataError, match="immutable run_id"):
        store.record_research_attempt(
            PROJECT_ID,
            contract_id,
            kind="d0-synthetic-pilot",
            status="completed",
            config_fingerprint="a" * 64,
            budget_used={"wall_seconds": 1},
            details={"evidence_zone": "D0"},
        )

    run_id = _write_research_run(
        tmp_path,
        run_id="d100000000000002",
        contract_id=contract_id,
        payload=payload,
    )
    run_dir = tmp_path / "runs" / run_id
    acceptance_path = run_dir / "d0_acceptance.json"
    acceptance = json.loads(acceptance_path.read_text(encoding="utf-8"))
    acceptance["measurements"]["planted_events"] = []
    acceptance_path.write_text(
        json.dumps(acceptance, sort_keys=True, separators=(",", ":"), allow_nan=False),
        encoding="utf-8",
    )
    manifest_path = run_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["artifacts"]["d0_acceptance.json"] = artifact_metadata(acceptance_path)
    manifest["outcomes"] = {
        "planted_pattern": {"passed": True},
        "monotonic_null": {"passed": True},
        "single_trough_null": {"passed": True},
        "prospective_power_fixture": {"passed": True},
    }
    manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
    with pytest.raises(DataError, match="exact deterministic recomputation"):
        store.record_research_attempt(
            PROJECT_ID,
            contract_id,
            kind="d0-synthetic-pilot",
            status="completed",
            config_fingerprint="a" * 64,
            budget_used={"wall_seconds": 1},
            details={"evidence_zone": "D0"},
            run_id=run_id,
        )
    assert store.research_case_summary(PROJECT_ID)["attempt_count"] == 0


def test_post_admission_d0_rewrite_fails_recovery_summary_and_packet_reads(
    tmp_path: Path,
) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    contract_id, payload = _approved_pilot(store)
    run_id = _record_completed_d0(
        store,
        contract_id,
        payload,
        at=START + timedelta(minutes=8),
    )
    before = store.research_case_summary(PROJECT_ID)
    attempt_id = cast(str, before["latest_attempt_id"])

    store.transition_research_phase(
        PROJECT_ID,
        to_phase="research_decision",
        contract_id=contract_id,
        actor="system",
        reason="Simulate recovery after the completed D0 attempt was recorded.",
        next_action="Owner records an evidence-bounded disposition.",
        responsibility="owner",
        at=START + timedelta(minutes=9),
    )
    store.record_research_decision(
        PROJECT_ID,
        contract_id,
        outcome="INCONCLUSIVE",
        disposition="park",
        actor="owner",
        actor_kind="human",
        reason="D0 alone cannot answer the market claim.",
        at=START + timedelta(minutes=10),
    )
    store.transition_research_phase(
        PROJECT_ID,
        to_phase="closed",
        contract_id=contract_id,
        actor="owner",
        reason="Close the synthetic-only case.",
        next_action="Revise only through a new immutable lineage.",
        responsibility="owner",
        at=START + timedelta(minutes=11),
    )

    database = sqlite3.connect(tmp_path / "control" / "workstation.sqlite3")
    stored_details = cast(
        str,
        database.execute(
            "SELECT details_json FROM research_attempt_records WHERE attempt_id = ?",
            (attempt_id,),
        ).fetchone()[0],
    )
    mismatched_details = json.loads(stored_details)
    mismatched_details["d0_acceptance_ref"]["content_sha256"] = "f" * 64
    database.execute(
        "UPDATE research_attempt_records SET details_json = ? WHERE attempt_id = ?",
        (
            json.dumps(mismatched_details, sort_keys=True, separators=(",", ":")),
            attempt_id,
        ),
    )
    database.commit()
    with pytest.raises(DataError, match="exact typed acceptance artifact provenance"):
        store.verified_research_attempt(PROJECT_ID, attempt_id)
    database.execute(
        "UPDATE research_attempt_records SET details_json = ? WHERE attempt_id = ?",
        (stored_details, attempt_id),
    )
    database.commit()
    database.close()

    _rewrite_d0_acceptance_and_manifest(tmp_path, run_id)

    with pytest.raises(DataError, match="exact deterministic recomputation"):
        store.verified_research_attempt(PROJECT_ID, attempt_id)
    with pytest.raises(DataError, match="exact deterministic recomputation"):
        store.research_case_summary(PROJECT_ID)
    with pytest.raises(DataError, match="exact deterministic recomputation"):
        store.research_gate_packet_inputs(PROJECT_ID)


def test_pilot_advancement_requires_idle_execution_after_passing_run(tmp_path: Path) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    contract_id, payload = _approved_pilot(store)
    _record_completed_d0(
        store,
        contract_id,
        payload,
        at=START + timedelta(minutes=8),
    )
    store.transition_research_execution(
        PROJECT_ID,
        to_state="queued",
        contract_id=contract_id,
        actor="codex",
        reason="Keep the worker active during the adversarial transition.",
        next_action="Do not advance while work is queued.",
        responsibility="codex",
        checkpoint="d0:complete",
        at=START + timedelta(minutes=9),
    )
    with pytest.raises(DataError, match="requires idle execution"):
        store.transition_research_phase(
            PROJECT_ID,
            to_phase="deep_research",
            contract_id=contract_id,
            actor="codex",
            reason="A queued worker cannot advance authority.",
            next_action="Return execution to idle first.",
            responsibility="codex",
            at=START + timedelta(minutes=10),
        )


def test_confirmation_attempt_rejects_inline_or_missing_evidence_artifacts(
    tmp_path: Path,
) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    _, confirmation_id = _approved_contracts(
        store,
        record_confirmation_evidence=False,
        record_decision=False,
        transition_to_decision=False,
    )
    contract = store.get_research_contract(confirmation_id)
    payload = cast(dict[str, object], contract["payload"])
    # One immutable D2 run with NO published evidence artifacts serves both rejections:
    # the inline check fires before any run read, and the selector then finds nothing.
    run_id = _write_research_run(
        tmp_path,
        run_id="ignored-content-derived-id",
        contract_id=confirmation_id,
        payload=payload,
        evidence_zone="D2",
    )
    inline_evidence = {"schema": "ResearchGateEvidenceV1", "evidence_zone": "D2"}
    with pytest.raises(DataError, match="inline gate_packet_evidence"):
        store.record_research_attempt(
            PROJECT_ID,
            confirmation_id,
            kind="sealed-confirmation",
            status="completed",
            config_fingerprint="a" * 64,
            budget_used={"wall_seconds": 1, "source_requests": 0, "variants": 1},
            details={"evidence_zone": "D2", "gate_packet_evidence": inline_evidence},
            run_id=run_id,
            at=START + timedelta(minutes=14),
        )

    with pytest.raises(DataError, match="declared immutable artifact"):
        store.record_research_attempt(
            PROJECT_ID,
            confirmation_id,
            kind="sealed-confirmation",
            status="completed",
            config_fingerprint="a" * 64,
            budget_used={"wall_seconds": 1, "source_requests": 0, "variants": 1},
            details={
                "evidence_zone": "D2",
                "gate_packet_evidence_ref": {
                    "artifact": "research_gate_evidence.json",
                    "content_sha256": "f" * 64,
                },
            },
            run_id=run_id,
            at=START + timedelta(minutes=14),
        )


def test_confirmation_decision_reverifies_evidence_artifact_bytes(tmp_path: Path) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    _, confirmation_id = _approved_contracts(store, record_decision=False)
    contract = store.get_research_contract(confirmation_id)
    payload = cast(dict[str, object], contract["payload"])
    run_id = _d2_run_id(payload, confirmation_id)
    evidence_path = tmp_path / "runs" / run_id / "research_gate_evidence.json"
    evidence_path.write_text("{}", encoding="utf-8")

    with pytest.raises(DataError, match="artifact"):
        store.record_research_decision(
            PROJECT_ID,
            confirmation_id,
            outcome="SUPPORTED",
            disposition="advance_to_strategy",
            actor="owner",
            actor_kind="human",
            reason="Tampered analytical evidence must fail closed.",
            at=START + timedelta(minutes=15),
        )


def test_identical_research_attempt_replay_is_idempotent_before_budget_debit(
    tmp_path: Path,
) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    contract_id, payload = _approved_pilot(store)
    run_id = _write_research_run(
        tmp_path,
        run_id="d000000000000002",
        contract_id=contract_id,
        payload=payload,
    )
    kwargs = {
        "kind": "d0-synthetic-pilot",
        "status": "completed",
        "config_fingerprint": "a" * 64,
        "budget_used": {"wall_seconds": 14_400, "source_requests": 60, "variants": 128},
        "details": {
            "evidence_zone": "D0",
            "d0_acceptance_ref": _d0_acceptance_ref(tmp_path, run_id),
        },
        "run_id": run_id,
    }

    first = store.record_research_attempt(
        PROJECT_ID,
        contract_id,
        **kwargs,  # type: ignore[arg-type]
        at=START + timedelta(minutes=8),
    )
    replay = store.record_research_attempt(
        PROJECT_ID,
        contract_id,
        **kwargs,  # type: ignore[arg-type]
        at=START + timedelta(minutes=9),
    )
    assert replay == first


def test_reserved_d0_terminalization_debits_once_and_blocks_unlinked_bypass(
    tmp_path: Path,
) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    contract_id, payload = _approved_pilot(store)
    store.transition_research_execution(
        PROJECT_ID,
        to_state="queued",
        contract_id=contract_id,
        actor="codex",
        reason="Queue the reserved D0 fixture.",
        next_action="Reserve before computing.",
        responsibility="codex",
        checkpoint="d0:queued",
        at=START + timedelta(minutes=8),
    )
    fingerprint = d0_execution_fingerprint(payload)
    reservation = store.reserve_d0_research_launch(
        PROJECT_ID,
        contract_id,
        config_fingerprint=fingerprint,
        at=START + timedelta(minutes=9),
    )
    assert reservation["launch_number"] == 1
    reserved = store.research_case_summary(PROJECT_ID)
    assert reserved["attempt_count"] == 1
    assert reserved["terminal_attempt_count"] == 0
    assert reserved["unfinalized_launch_count"] == 1
    assert reserved["elapsed_budget"] == {
        "source_requests": 0,
        "variants": 3,
        "wall_seconds": 1,
    }

    with pytest.raises(DataError, match="requires its durable launch reservation"):
        store.record_research_attempt(
            PROJECT_ID,
            contract_id,
            kind="d0-synthetic-pilot",
            status="failed",
            config_fingerprint=fingerprint,
            budget_used={"wall_seconds": 1},
            details={"attempt_number": 1, "evidence_zone": "D0"},
            error="unlinked terminal bypass",
            at=START + timedelta(minutes=10),
        )

    attempt = store.record_research_attempt(
        PROJECT_ID,
        contract_id,
        kind="d0-synthetic-pilot",
        status="failed",
        config_fingerprint=fingerprint,
        budget_used={},
        details={"attempt_number": 1, "evidence_zone": "D0"},
        error="registered D0 failure",
        launch_reservation_id=str(reservation["reservation_id"]),
        at=START + timedelta(minutes=10),
    )
    assert attempt["budget_used"] == {}
    linked = store.research_case_summary(PROJECT_ID)
    assert linked["attempt_count"] == 1
    assert linked["terminal_attempt_count"] == 1
    assert linked["unfinalized_launch_count"] == 0
    assert linked["elapsed_budget"] == reserved["elapsed_budget"]


def test_unreserved_legacy_d0_attempts_are_capped_at_three(tmp_path: Path) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    contract_id, _ = _approved_pilot(store)
    recorded: list[dict[str, object]] = []
    for attempt_number in range(1, 4):
        recorded.append(
            store.record_research_attempt(
                PROJECT_ID,
                contract_id,
                kind="d0-synthetic-pilot",
                status="failed",
                config_fingerprint=str(attempt_number) * 64,
                budget_used={"wall_seconds": 1, "source_requests": 0, "variants": 1},
                details={"attempt_number": attempt_number, "evidence_zone": "D0"},
                error=f"legacy direct failure {attempt_number}",
                at=START + timedelta(minutes=7 + attempt_number),
            )
        )
    with pytest.raises(DataError, match="initial attempt and two safe retries"):
        store.record_research_attempt(
            PROJECT_ID,
            contract_id,
            kind="d0-synthetic-pilot",
            status="failed",
            config_fingerprint="4" * 64,
            budget_used={"wall_seconds": 1, "source_requests": 0, "variants": 1},
            details={"attempt_number": 4, "evidence_zone": "D0"},
            error="forbidden fourth direct failure",
            at=START + timedelta(minutes=12),
        )
    assert (
        store.record_research_attempt(
            PROJECT_ID,
            contract_id,
            kind="d0-synthetic-pilot",
            status="failed",
            config_fingerprint="3" * 64,
            budget_used={"wall_seconds": 1, "source_requests": 0, "variants": 1},
            details={"attempt_number": 3, "evidence_zone": "D0"},
            error="legacy direct failure 3",
            at=START + timedelta(minutes=20),
        )
        == recorded[-1]
    )


def test_running_reconciliation_requires_explicit_orphan_acknowledgement(
    tmp_path: Path,
) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    contract_id, _ = _approved_pilot(store)
    for state in ("queued", "running"):
        store.transition_research_execution(
            PROJECT_ID,
            to_state=state,
            contract_id=contract_id,
            actor="codex",
            reason=f"Move fixture to {state}.",
            next_action="Continue the deterministic pilot.",
            responsibility="codex",
            checkpoint="d0:prepared",
            at=START + timedelta(minutes=8),
        )

    with pytest.raises(DataError, match="orphan reconciliation acknowledgement"):
        store.transition_research_execution(
            PROJECT_ID,
            to_state="queued",
            contract_id=contract_id,
            actor="owner",
            reason="The prior process was killed.",
            next_action="Retry from the durable checkpoint.",
            responsibility="codex",
            checkpoint="d0:prepared",
            at=START + timedelta(minutes=9),
        )
    reconciled = store.transition_research_execution(
        PROJECT_ID,
        to_state="queued",
        contract_id=contract_id,
        actor="owner",
        reason="The owner verified that the prior process is gone.",
        next_action="Retry from the durable checkpoint.",
        responsibility="codex",
        checkpoint="d0:prepared",
        reconcile_running=True,
        at=START + timedelta(minutes=9),
    )
    assert reconciled["state"] == "queued"


@pytest.mark.parametrize(
    ("field", "wrong_value"),
    [
        ("project_id", LEGACY_PROJECT_ID),
        ("research_contract_id", "rc_" + "f" * 64),
        ("contract_hash", "b" * 64),
        ("source_pack_id", "sp_" + "e" * 64),
        ("research_fingerprints.code", "wrong-code-fingerprint"),
        ("research_fingerprints.environment", "wrong-environment-fingerprint"),
        ("research_fingerprints.evaluator", "wrong-evaluator-fingerprint"),
        ("research_fingerprints.data", "wrong-dataset-fingerprint"),
        ("evidence_zone", "D1"),
        ("eligible_for_holdout_or_execution", True),
        ("places_orders", True),
    ],
)
def test_research_attempt_rejects_wrong_run_lineage_or_authority(
    tmp_path: Path, field: str, wrong_value: object
) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    contract_id, payload = _approved_pilot(store)
    run_id = _write_research_run(
        tmp_path,
        run_id="b200000000000002",
        contract_id=contract_id,
        payload=payload,
        override=(field, wrong_value),
    )

    with pytest.raises(DataError, match="research run"):
        store.record_research_attempt(
            PROJECT_ID,
            contract_id,
            kind="d0-synthetic-pilot",
            status="completed",
            config_fingerprint="a" * 64,
            budget_used={"wall_seconds": 1, "source_requests": 0, "variants": 1},
            details={"evidence_zone": "D0"},
            run_id=run_id,
            at=START + timedelta(minutes=8),
        )


def test_gate_packet_inputs_are_complete_deterministic_and_public(tmp_path: Path) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    exploration_id, confirmation_id = _approved_contracts(store)
    store.transition_research_phase(
        PROJECT_ID,
        to_phase="closed",
        contract_id=confirmation_id,
        actor="codex",
        reason="The owner decision is recorded and the research case is closed.",
        next_action="Create a strategy only through the governed linkage.",
        responsibility="owner",
        at=START + timedelta(minutes=16),
    )

    packet = store.research_gate_packet_inputs(PROJECT_ID)
    assert packet == store.research_gate_packet_inputs(PROJECT_ID)
    assert packet["phase"] == "closed"
    assert packet["lineage_contract_ids"] == [exploration_id, confirmation_id]
    contracts = packet["contracts"]
    sources = packet["sources"]
    source_packs = packet["source_packs"]
    review_events = packet["review_events"]
    d2_events = packet["d2_events"]
    decision_events = packet["decision_events"]
    assert isinstance(contracts, list)
    assert isinstance(sources, list)
    assert isinstance(source_packs, list)
    assert isinstance(review_events, list)
    assert isinstance(d2_events, list)
    assert isinstance(decision_events, list)
    assert [contract["contract_id"] for contract in contracts] == [
        exploration_id,
        confirmation_id,
    ]
    assert len(sources) == 1
    assert len(source_packs) == 1
    assert [event["scope"] for event in review_events] == [
        "exploration",
        "confirmation",
    ]
    assert [event["state"] for event in d2_events][-2:] == [
        "authorized",
        "consumed",
    ]
    assert decision_events[0]["disposition"] == "advance_to_strategy"
    with pytest.raises(DataError, match="ledger_limit"):
        store.research_gate_packet_inputs(PROJECT_ID, ledger_limit=1)
    for invalid_limit in (True, 1.5, "10"):
        with pytest.raises(DataError, match="ledger_limit"):
            store.research_gate_packet_inputs(PROJECT_ID, ledger_limit=cast(int, invalid_limit))


def test_revise_reopens_with_new_d2_boundary_without_erasing_consumed_history(
    tmp_path: Path,
) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    exploration_id, confirmation_id = _approved_contracts(
        store, outcome="INCONCLUSIVE", disposition="revise"
    )
    old_contract = store.get_research_contract(exploration_id)
    old_payload = old_contract["payload"]
    assert isinstance(old_payload, dict)
    pack_id = str(old_payload["source_pack_id"])

    overlapping = store.create_research_contract(
        PROJECT_ID,
        scope="exploration",
        parent_contract_id=exploration_id,
        payload=_payload(
            pack_id,
            boundary_seed="baseline-boundary",
            relation_to_prior="non_overlapping_future",
        ),
        created_by="codex",
        author_kind="agent",
        at=START + timedelta(minutes=16),
    )
    with pytest.raises(DataError, match="distinct D2 boundary"):
        store.reopen_research_revision(
            PROJECT_ID,
            str(overlapping["contract_id"]),
            actor="codex",
            reason="This revision accidentally reuses consumed observations.",
            next_action="Reject the overlapping revision.",
            at=START + timedelta(minutes=17),
        )

    revision_payload = _payload(
        pack_id,
        boundary_seed="future-2027-boundary",
        relation_to_prior="non_overlapping_future",
    )
    revision = store.create_research_contract(
        PROJECT_ID,
        scope="exploration",
        parent_contract_id=exploration_id,
        payload=revision_payload,
        created_by="codex",
        author_kind="agent",
        at=START + timedelta(minutes=18),
    )
    revision_id = str(revision["contract_id"])
    reopened = store.reopen_research_revision(
        PROJECT_ID,
        revision_id,
        actor="codex",
        reason="The owner requested a revised protocol on future observations.",
        next_action="Approve or reject the revised exploration contract.",
        at=START + timedelta(minutes=19),
    )
    assert reopened["phase"] == "exploration_review"
    assert reopened["contract_id"] == revision_id

    summary = store.research_case_summary(PROJECT_ID)
    assert summary["phase"] == "exploration_review"
    assert summary["d2_state"] == "sealed"
    assert summary["d2_boundary_hash"] == _boundary("future-2027-boundary").boundary_sha256
    history = summary["d2_history"]
    assert isinstance(history, list)
    assert {
        "contract_id": confirmation_id,
        "state": "consumed",
        "boundary_hash": _boundary("baseline-boundary").boundary_sha256,
    } in [
        {
            "contract_id": event["contract_id"],
            "state": event["state"],
            "boundary_hash": event["boundary_hash"],
        }
        for event in history
    ]
    store.review_research_contract(
        PROJECT_ID,
        revision_id,
        scope="exploration",
        decision="approve",
        actor="owner",
        actor_kind="human",
        reason="The future observation boundary is acceptable.",
        at=START + timedelta(minutes=20),
    )
    store.transition_research_phase(
        PROJECT_ID,
        to_phase="pilot",
        contract_id=revision_id,
        actor="codex",
        reason="Advance the revised study to pilot.",
        next_action="Run the revised D0 pilot.",
        responsibility="codex",
        at=START + timedelta(minutes=21),
    )
    _record_completed_d0(
        store,
        revision_id,
        revision_payload,
        at=START + timedelta(minutes=21, seconds=30),
    )
    store.transition_research_phase(
        PROJECT_ID,
        to_phase="deep_research",
        contract_id=revision_id,
        actor="codex",
        reason="Advance the revised study to deep_research.",
        next_action="Prepare the revised confirmation child.",
        responsibility="codex",
        at=START + timedelta(minutes=22),
    )
    overlapping_confirmation = store.create_research_contract(
        PROJECT_ID,
        scope="confirmation",
        parent_contract_id=revision_id,
        payload=_payload(
            pack_id,
            confirmation=True,
            boundary_seed="baseline-boundary",
        ),
        created_by="codex",
        author_kind="agent",
        at=START + timedelta(minutes=23),
    )
    overlapping_confirmation_id = str(overlapping_confirmation["contract_id"])
    store.transition_research_phase(
        PROJECT_ID,
        to_phase="confirmation_review",
        contract_id=overlapping_confirmation_id,
        actor="codex",
        reason="Present the mistakenly overlapping child for fail-closed review.",
        next_action="Reject the mismatched confirmation boundary.",
        responsibility="owner",
        at=START + timedelta(minutes=24),
    )
    with pytest.raises(DataError, match="must match its approved exploration"):
        store.review_research_contract(
            PROJECT_ID,
            overlapping_confirmation_id,
            scope="confirmation",
            decision="approve",
            actor="owner",
            actor_kind="human",
            reason="This must fail because it recycles the prior D2 boundary.",
            at=START + timedelta(minutes=25),
        )

    parked_store = ControlStore(tmp_path / "parked")
    _project(parked_store)
    parked_exploration_id, parked_confirmation_id = _approved_contracts(
        parked_store, outcome="INCONCLUSIVE", disposition="park"
    )
    parked_store.transition_research_phase(
        PROJECT_ID,
        to_phase="closed",
        contract_id=parked_confirmation_id,
        actor="codex",
        reason="The owner parked and closed this research case.",
        next_action="Keep the case closed unless a new idea is captured separately.",
        responsibility="owner",
        at=START + timedelta(minutes=16),
    )
    parked_contract = parked_store.get_research_contract(parked_exploration_id)
    parked_payload = parked_contract["payload"]
    assert isinstance(parked_payload, dict)
    parked_revision = parked_store.create_research_contract(
        PROJECT_ID,
        scope="exploration",
        parent_contract_id=parked_exploration_id,
        payload=_payload(
            str(parked_payload["source_pack_id"]),
            boundary_seed="external-replication-boundary",
            relation_to_prior="external_replication",
        ),
        created_by="codex",
        author_kind="agent",
        at=START + timedelta(minutes=17),
    )
    with pytest.raises(DataError, match="owner disposition 'revise'"):
        parked_store.reopen_research_revision(
            PROJECT_ID,
            str(parked_revision["contract_id"]),
            actor="codex",
            reason="Parked research must remain closed.",
            next_action="Do not reopen.",
            at=START + timedelta(minutes=18),
        )


def _captured_case(store: ControlStore, index: int, *, at: datetime) -> str:
    """Capture one distinct research case and return its project id."""

    result = store.capture_research_case(
        name=f"Backlog case {index}",
        hypothesis=f"Observation {index} may precede positive four-hour returns.",
        falsification_criterion="Reject when registered controls do not support the claim.",
        draft_payload=draft_exploration_contract(
            f"Observation {index} may precede positive four-hour returns."
        ),
        created_by="codex",
        next_action="Owner answers the material question batch.",
        responsibility="owner",
        blocker="The chart, event time, and outcome are unresolved.",
        recovery="Answer the bounded question batch.",
        at=at,
    )
    case = result["case"]
    assert isinstance(case, dict)
    return str(case["project_id"])


def test_list_research_cases_is_bounded_newest_activity_first(tmp_path: Path) -> None:
    store = ControlStore(tmp_path)
    project_ids = [
        _captured_case(store, index, at=START + timedelta(minutes=index)) for index in range(3)
    ]
    # A strategy-only project without a research case never appears in the backlog.
    store.create_project(
        name="Strategy-only project",
        hypothesis="Not a research case.",
        falsification_criterion="Not applicable.",
        project_id=LEGACY_PROJECT_ID,
        at=START + timedelta(minutes=30),
    )

    rows = store.list_research_cases()
    assert [cast(dict[str, object], row["case"])["project_id"] for row in rows] == list(
        reversed(project_ids)
    )
    for row in rows:
        assert set(row) == {"case", "updated_at"}
        case = row["case"]
        assert isinstance(case, dict)
        # The per-case shape is byte-identical to the canonical single-case summary.
        assert case == store.research_case_summary(str(case["project_id"]))
        assert isinstance(row["updated_at"], str) and row["updated_at"]

    # Later research activity (an execution transition) moves that case to the front.
    oldest = project_ids[0]
    summary = store.research_case_summary(oldest)
    store.transition_research_execution(
        oldest,
        to_state="blocked",
        contract_id=str(summary["active_contract_id"]),
        actor="owner",
        reason="Owner paused triage pending data access.",
        next_action="Restore data access before continuing triage.",
        responsibility="owner",
        blocker="Data access is unavailable.",
        recovery="Restore data access.",
        at=START + timedelta(hours=1),
    )
    reordered = store.list_research_cases()
    assert str(cast(dict[str, object], reordered[0]["case"])["project_id"]) == oldest

    # Bounded paging with the documented research limit.
    assert store.list_research_cases(limit=1) == reordered[:1]
    assert store.list_research_cases(limit=1, offset=1) == reordered[1:2]
    assert store.list_research_cases(limit=1, offset=99) == []
    with pytest.raises(DataError, match="limit"):
        store.list_research_cases(limit=0)
    with pytest.raises(DataError, match="limit"):
        store.list_research_cases(limit=201)
    with pytest.raises(DataError, match="offset"):
        store.list_research_cases(offset=-1)


def test_context_packet_build_is_content_addressed_append_only_and_deterministic(
    tmp_path: Path,
) -> None:
    store = ControlStore(tmp_path)
    project_id = _captured_case(store, 0, at=START)

    first = store.build_research_context_packet(
        project_id,
        kind="research_case",
        created_by="codex",
        at=START + timedelta(minutes=5),
    )
    packet_id = str(first["packet_id"])
    assert packet_id.startswith("cp_") and len(packet_id) == 3 + 64
    assert first["packet_kind"] == "research_case"
    assert first["protocol_id"] is None and first["protocol_content_hash"] is None
    payload = first["payload"]
    assert isinstance(payload, dict)
    assert payload["packet_schema"] == "ResearchContextPacketV1"
    assert payload["project_id"] == project_id
    assert payload["packet_kind"] == "research_case"
    # Bounded collections carry explicit truncation flags — no invisible context dumps.
    assert payload["attempts_truncated"] is False
    assert payload["sources_truncated"] is False
    assert payload["notes_truncated"] is False
    # Identical inputs produce the identical content-addressed packet (idempotent record).
    replay = store.build_research_context_packet(
        project_id,
        kind="research_case",
        created_by="codex",
        at=START + timedelta(minutes=9),
    )
    assert replay["packet_id"] == packet_id
    assert replay["payload"] == payload
    assert len(store.list_research_context_packets(project_id)) == 1

    # A different kind is a different packet; recording is visibility.
    validation = store.build_research_context_packet(
        project_id,
        kind="validation",
        created_by="codex",
        protocol_id="research-critic",
        protocol_content_hash="c" * 64,
        at=START + timedelta(minutes=10),
    )
    assert validation["packet_id"] != packet_id
    assert validation["protocol_id"] == "research-critic"
    assert validation["protocol_content_hash"] == "c" * 64
    listed = store.list_research_context_packets(project_id)
    assert [row["packet_id"] for row in listed] == [validation["packet_id"], packet_id]
    fetched = store.get_research_context_packet(str(validation["packet_id"]))
    assert fetched == validation

    with pytest.raises(DataError, match="packet kind"):
        store.build_research_context_packet(project_id, kind="chat", created_by="codex")
    with pytest.raises(DataError, match="symbol"):
        store.build_research_context_packet(project_id, kind="asset", created_by="codex")
    with pytest.raises(DataError, match="unknown research context packet"):
        store.get_research_context_packet("cp_" + "0" * 64)


def test_research_notes_are_append_only_and_structurally_outside_evidence(
    tmp_path: Path,
) -> None:
    store = ControlStore(tmp_path)
    project_id = _captured_case(store, 0, at=START)
    packet = store.build_research_context_packet(
        project_id, kind="research_case", created_by="codex", at=START + timedelta(minutes=1)
    )
    before = json.dumps(
        store.research_gate_packet_inputs(project_id), sort_keys=True, allow_nan=False
    )

    critique = store.add_research_note(
        project_id,
        note_kind="critique",
        body="The volatility-regime confounder is not yet matched.",
        author="codex",
        author_kind="agent",
        context_packet_id=str(packet["packet_id"]),
        at=START + timedelta(minutes=2),
    )
    assert str(critique["note_id"]).startswith("rn_")
    assert critique["author_kind"] == "agent"
    assert critique["context_packet_id"] == packet["packet_id"]
    synthesis = store.add_research_note(
        project_id,
        note_kind="synthesis",
        body="Established: nothing. Speculative: everything pre-D1.",
        author="owner",
        author_kind="owner",
        at=START + timedelta(minutes=3),
    )
    notes = store.list_research_notes(project_id)
    assert [row["note_id"] for row in notes] == [synthesis["note_id"], critique["note_id"]]

    # Structural evidence exclusion: the gate-packet inputs are byte-identical with notes.
    after = json.dumps(
        store.research_gate_packet_inputs(project_id), sort_keys=True, allow_nan=False
    )
    assert after == before

    with pytest.raises(DataError, match="note kind"):
        store.add_research_note(
            project_id, note_kind="evidence", body="x", author="codex", author_kind="agent"
        )
    with pytest.raises(DataError, match="author kind"):
        store.add_research_note(
            project_id, note_kind="critique", body="x", author="codex", author_kind="human"
        )
    with pytest.raises(DataError, match="unknown research context packet"):
        store.add_research_note(
            project_id,
            note_kind="critique",
            body="x",
            author="codex",
            author_kind="agent",
            context_packet_id="cp_" + "1" * 64,
        )


def test_research_brief_reports_only_deltas_since_the_previous_brief(tmp_path: Path) -> None:
    store = ControlStore(tmp_path)
    project_id = _captured_case(store, 0, at=START)

    first = store.research_brief(project_id, created_by="codex", at=START + timedelta(minutes=4))
    assert first["brief_schema"] == "ResearchBriefV1"
    case = first["case"]
    assert isinstance(case, dict) and case["project_id"] == project_id
    changes = first["changes"]
    assert isinstance(changes, dict)
    # The first brief reports the complete history as new.
    assert len(cast(list[object], changes["phase_events"])) == 2  # captured + triage
    assert len(cast(list[object], changes["execution_events"])) == 1  # initial idle
    assert changes["attempts"] == [] and changes["decisions"] == []
    assert isinstance(first["packet_id"], str) and str(first["packet_id"]).startswith("cp_")

    summary = store.research_case_summary(project_id)
    store.transition_research_execution(
        project_id,
        to_state="blocked",
        contract_id=str(summary["active_contract_id"]),
        actor="owner",
        reason="Owner paused triage pending data access.",
        next_action="Restore data access before continuing triage.",
        responsibility="owner",
        blocker="Data access is unavailable.",
        recovery="Restore data access.",
        at=START + timedelta(minutes=6),
    )
    second = store.research_brief(project_id, created_by="codex", at=START + timedelta(minutes=7))
    second_changes = second["changes"]
    assert isinstance(second_changes, dict)
    assert second_changes["phase_events"] == []
    execution_events = cast(list[dict[str, object]], second_changes["execution_events"])
    assert len(execution_events) == 1
    assert execution_events[0]["state"] == "blocked"
    assert second["packet_id"] != first["packet_id"]

    third = store.research_brief(project_id, created_by="codex", at=START + timedelta(minutes=8))
    third_changes = third["changes"]
    assert isinstance(third_changes, dict)
    assert all(third_changes[key] == [] for key in third_changes)


def test_research_dataset_registration_is_fail_closed_and_content_addressed(
    tmp_path: Path,
) -> None:
    store = ControlStore(tmp_path)
    ref = store.register_research_dataset(
        dataset_kind="snapshot",
        instrument="AAPL",
        provider="fake",
        start_ts="2020-08-28",
        end_ts="2020-09-02",
        bar_duration_minutes=None,
        origin={"snapshot_id": "snap-a", "manifest_sha256": "a" * 64},
        registered_by="owner",
        at=START,
    )
    ref_id = str(ref["ref_id"])
    assert ref_id.startswith("rd_") and len(ref_id) == 3 + 64
    assert ref["research_only"] is True
    assert ref["dataset_kind"] == "snapshot"
    # Idempotent re-registration of identical bytes.
    replay = store.register_research_dataset(
        dataset_kind="snapshot",
        instrument="AAPL",
        provider="fake",
        start_ts="2020-08-28",
        end_ts="2020-09-02",
        bar_duration_minutes=None,
        origin={"snapshot_id": "snap-a", "manifest_sha256": "a" * 64},
        registered_by="owner",
        at=START + timedelta(minutes=5),
    )
    assert replay["ref_id"] == ref_id
    rows = store.list_research_datasets()
    assert [row["ref_id"] for row in rows] == [ref_id]
    assert rows[0]["latest_audit"] is None
    assert store.get_research_dataset(ref_id)["origin"] == {
        "snapshot_id": "snap-a",
        "manifest_sha256": "a" * 64,
    }
    assert store.list_research_datasets(instrument="AAPL") == rows
    assert store.list_research_datasets(instrument="SPY") == []

    # Fail-closed origins: a registration without its exact binding is refused.
    with pytest.raises(DataError, match="manifest_sha256"):
        store.register_research_dataset(
            dataset_kind="snapshot",
            instrument="AAPL",
            provider="fake",
            start_ts="2020-08-28",
            end_ts="2020-09-02",
            bar_duration_minutes=None,
            origin={"snapshot_id": "snap-a"},
            registered_by="owner",
        )
    with pytest.raises(DataError, match="provenance_sha256"):
        store.register_research_dataset(
            dataset_kind="store_slice",
            instrument="AAPL",
            provider="fake",
            start_ts="2020-08-28",
            end_ts="2020-09-02",
            bar_duration_minutes=None,
            origin={},
            registered_by="owner",
        )
    with pytest.raises(DataError, match="receipt"):
        store.register_research_dataset(
            dataset_kind="quantpad_receipt",
            instrument="AAPL",
            provider="quantpad",
            start_ts="2020-08-28",
            end_ts="2020-09-02",
            bar_duration_minutes=60,
            origin={"response_sha256": "b" * 64},
            registered_by="owner",
        )
    with pytest.raises(DataError, match="dataset kind"):
        store.register_research_dataset(
            dataset_kind="csv_upload",
            instrument="AAPL",
            provider="fake",
            start_ts="2020-08-28",
            end_ts="2020-09-02",
            bar_duration_minutes=None,
            origin={},
            registered_by="owner",
        )


def test_research_dataset_audits_bind_ref_project_and_run(tmp_path: Path) -> None:
    store = ControlStore(tmp_path)
    project_id = _captured_case(store, 0, at=START)
    ref = store.register_research_dataset(
        dataset_kind="store_slice",
        instrument="AAPL",
        provider="fake",
        start_ts="2020-08-28",
        end_ts="2020-09-02",
        bar_duration_minutes=None,
        origin={"provenance_sha256": "c" * 64},
        registered_by="owner",
        at=START,
    )
    ref_id = str(ref["ref_id"])
    audit = store.record_research_dataset_audit(
        ref_id,
        project_id=project_id,
        run_id="deadbeefdeadbeef",
        summary={
            "audit_schema": "ResearchDataAuditV1",
            "blocking_count": 0,
            "limiting_count": 1,
            "notes": ["One calendar gap over a holiday."],
        },
        at=START + timedelta(minutes=10),
    )
    assert audit["ref_id"] == ref_id and audit["project_id"] == project_id
    listed = store.list_research_dataset_audits(ref_id)
    assert [row["run_id"] for row in listed] == ["deadbeefdeadbeef"]
    enriched = store.list_research_datasets()
    latest = enriched[0]["latest_audit"]
    assert isinstance(latest, dict)
    assert latest["summary"]["limiting_count"] == 1

    with pytest.raises(DataError, match="unknown research dataset"):
        store.record_research_dataset_audit(
            "rd_" + "0" * 64,
            project_id=project_id,
            run_id="deadbeefdeadbeef",
            summary={
                "audit_schema": "ResearchDataAuditV1",
                "blocking_count": 0,
                "limiting_count": 0,
                "notes": [],
            },
        )
    with pytest.raises(DataError, match="audit summary"):
        store.record_research_dataset_audit(
            ref_id,
            project_id=project_id,
            run_id="deadbeefdeadbeef",
            summary={"blocking_count": 0},
        )


def test_data_audit_refuses_drifted_bytes_and_unsupported_kinds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The audit loader is fail-closed: registered hashes must still match the disk."""
    from alpha_cli.research_data_audit import run_data_audit

    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    project_id = _captured_case(ControlStore(tmp_path), 0, at=START)

    def _ref(kind: str, origin: dict[str, object]) -> dict[str, object]:
        return {
            "ref_id": "rd_" + "1" * 64,
            "dataset_kind": kind,
            "instrument": "AAPL",
            "provider": "fake",
            "start_ts": "2020-01-01",
            "end_ts": "2020-06-01",
            "bar_duration_minutes": None,
            "origin": origin,
        }

    with pytest.raises(DataError, match="canonical project_id"):
        run_data_audit(tmp_path, project_id="not-a-uuid", ref=_ref("snapshot", {}))
    with pytest.raises(DataError, match="registered dataset ref"):
        run_data_audit(tmp_path, project_id=project_id, ref={"ref_id": "nope"})
    with pytest.raises(DataError, match="missing its manifest"):
        run_data_audit(
            tmp_path,
            project_id=project_id,
            ref=_ref("snapshot", {"snapshot_id": "ghost", "manifest_sha256": "a" * 64}),
        )
    snapshot_dir = tmp_path / "snapshots" / "snap-x"
    snapshot_dir.mkdir(parents=True)
    (snapshot_dir / "manifest.json").write_text("{}", encoding="utf-8")
    with pytest.raises(DataError, match="no longer matches its registered manifest hash"):
        run_data_audit(
            tmp_path,
            project_id=project_id,
            ref=_ref("snapshot", {"snapshot_id": "snap-x", "manifest_sha256": "a" * 64}),
        )
    with pytest.raises(DataError, match="no provenance sidecar"):
        run_data_audit(
            tmp_path,
            project_id=project_id,
            ref=_ref("store_slice", {"provenance_sha256": "b" * 64}),
        )
    with pytest.raises(DataError, match="qualified-loading lane"):
        run_data_audit(
            tmp_path,
            project_id=project_id,
            ref=_ref("quantpad_receipt", {"receipt_id": "c" * 32, "response_sha256": "d" * 64}),
        )
    with pytest.raises(DataError, match="end at or after"):
        bad_range = _ref("snapshot", {"snapshot_id": "snap-x", "manifest_sha256": "a" * 64})
        bad_range["start_ts"] = "2021-01-01"
        bad_range["end_ts"] = "2020-01-01"
        run_data_audit(tmp_path, project_id=project_id, ref=bad_range)


def test_data_audit_reverifies_registered_crypto_crowding_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from alpha_cli import crypto_data_cmds
    from alpha_cli.research_data_audit import run_data_audit

    store = ControlStore(tmp_path)
    project_id = _captured_case(store, 0, at=START)
    snapshot_id = "a" * 64
    manifest_path = tmp_path / "crypto" / "snapshots" / f"{snapshot_id}.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text("{}", encoding="utf-8")
    observations = tuple(
        SimpleNamespace(
            funding_time=START + timedelta(hours=8 * index),
            funding_rate=(-1 if index % 2 else 1) * (index + 1) / 100_000,
        )
        for index in range(40)
    )
    monkeypatch.setattr(
        crypto_data_cmds,
        "crypto_crowding_observations",
        lambda requested: observations if requested == snapshot_id else (),
    )
    snapshot_hash = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    ref = {
        "ref_id": "rd_" + "2" * 64,
        "dataset_kind": "snapshot",
        "instrument": "BTC",
        "provider": "crypto-data-house",
        "start_ts": START.isoformat(),
        "end_ts": (START + timedelta(hours=8 * 39)).isoformat(),
        "bar_duration_minutes": None,
        "origin": {
            "snapshot_id": snapshot_id,
            "snapshot_schema": "CryptoSnapshotV1",
            "manifest_sha256": snapshot_hash,
        },
    }

    result = run_data_audit(tmp_path, project_id=project_id, ref=ref)

    assert result["summary"]["blocking_count"] == 0
    assert result["manifest"]["snapshot_id"] == snapshot_id
    assert result["manifest"]["snapshot_hash"] == snapshot_hash
    run_dir = tmp_path / "runs" / result["manifest"]["run_id"]
    descriptives = json.loads((run_dir / "descriptives.json").read_text(encoding="utf-8"))
    assert descriptives["funding_rate_distribution"]["n"] == 40
    assert "return_distribution" not in descriptives


def test_source_records_gain_typed_doi_year_authors_columns(tmp_path: Path) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    source = store.create_research_source(
        PROJECT_ID,
        title="Technical patterns and subsequent returns",
        locator="doi:10.0000/example",
        provider="crossref",
        access_mode="metadata_only",
        doi="10.0000/EXAMPLE",
        year=2019,
        authors=["A. Author", "B. Author"],
        at=START,
    )
    # The DOI normalizes to lowercase; authors round-trip as a typed list.
    assert source["doi"] == "10.0000/example"
    assert source["year"] == 2019
    assert source["authors"] == ["A. Author", "B. Author"]
    fetched = store.get_research_source(str(source["source_id"]))
    assert fetched["doi"] == "10.0000/example"
    assert fetched["year"] == 2019
    assert fetched["authors"] == ["A. Author", "B. Author"]

    with pytest.raises(DataError, match="year"):
        store.create_research_source(
            PROJECT_ID,
            title="Bad year",
            locator="doi:10.0000/bad",
            provider="crossref",
            access_mode="metadata_only",
            year=99,
        )
    with pytest.raises(DataError, match="authors"):
        store.create_research_source(
            PROJECT_ID,
            title="Bad authors",
            locator="doi:10.0000/bad2",
            provider="crossref",
            access_mode="metadata_only",
            authors=["", "ok"],
        )


def test_source_claims_are_append_only_and_owner_screened(tmp_path: Path) -> None:
    store = ControlStore(tmp_path)
    project_id = _captured_case(store, 0, at=START)
    summary = store.research_case_summary(project_id)
    contract_id = str(summary["active_contract_id"])
    source = store.create_research_source(
        project_id,
        title="Technical patterns and subsequent returns",
        locator="doi:10.0000/example",
        provider="crossref",
        access_mode="metadata_only",
        doi="10.0000/example",
        year=2019,
        at=START + timedelta(minutes=1),
    )
    source_id = str(source["source_id"])

    claim = store.draft_source_claim(
        project_id,
        source_id=source_id,
        contract_id=contract_id,
        claim_text="Double-bottom patterns show small positive drift pre-2005 that decays.",
        direction="supports",
        strength="weak",
        method_summary="Event study over daily US equities with matched controls.",
        sample_summary="1962-2004, ~2,000 events.",
        markets=["US_EQUITY"],
        limitations="Pre-decimalization microstructure; publication-era decay likely.",
        author="codex",
        author_kind="agent",
        at=START + timedelta(minutes=2),
    )
    claim_id = str(claim["claim_id"])
    assert claim_id.startswith("sc_")
    assert claim["status"] == "draft"
    assert claim["revision"] == 1

    direction = store.record_source_claim_owner_direction(
        project_id,
        claim_id=claim_id,
        decision="revise",
        actor="owner",
        reason="Clarify the sample-period limitation.",
        payload={"requested_field": "limitations"},
        at=START + timedelta(minutes=2, seconds=30),
    )
    assert direction["sequence"] == 1
    assert direction["decision"] == "revise"
    with pytest.raises(DataError, match="unknown research claim"):
        store.record_source_claim_owner_direction(
            project_id,
            claim_id="sc_" + "f" * 64,
            decision="reject",
            actor="owner",
            reason="Unknown claim fixture.",
        )

    # Screening appends a new revision; the draft row survives unchanged (append-only).
    screened = store.screen_source_claim(
        project_id,
        claim_id=claim_id,
        actor="owner",
        at=START + timedelta(minutes=3),
    )
    assert screened["status"] == "screened"
    assert screened["revision"] == 2
    assert screened["screened_by"] == "owner"
    with pytest.raises(DataError, match="screened claim"):
        store.record_source_claim_owner_direction(
            project_id,
            claim_id=claim_id,
            decision="reject",
            actor="owner",
            reason="Cannot rewrite screened evidence.",
        )
    rows = store.list_source_claims(project_id)
    assert [(row["claim_id"], row["revision"], row["status"]) for row in rows] == [
        (claim_id, 2, "screened"),
    ]
    history = store.list_source_claims(project_id, include_history=True)
    assert [(row["revision"], row["status"]) for row in history if row["claim_id"] == claim_id] == [
        (2, "screened"),
        (1, "draft"),
    ]

    with pytest.raises(DataError, match="already screened"):
        store.screen_source_claim(project_id, claim_id=claim_id, actor="owner")
    with pytest.raises(DataError, match="claim direction"):
        store.draft_source_claim(
            project_id,
            source_id=source_id,
            contract_id=contract_id,
            claim_text="x",
            direction="proves",
            strength="weak",
            method_summary="m",
            sample_summary="s",
            markets=[],
            limitations="l",
            author="codex",
            author_kind="agent",
        )


def test_full_text_claim_requires_and_reverifies_source_anchor(tmp_path: Path) -> None:
    store = ControlStore(tmp_path)
    project_id = _captured_case(store, 0, at=START)
    contract_id = str(store.research_case_summary(project_id)["active_contract_id"])
    source_sha = hashlib.sha256(b"acquired-pdf").hexdigest()
    source = store.create_research_source(
        project_id,
        title="Anchored paper",
        locator="https://arxiv.org/pdf/1234.5678",
        provider="arxiv",
        access_mode="open_access",
        content_hash=source_sha,
        at=START + timedelta(minutes=1),
    )
    text = "The event study reports a small positive effect with wide uncertainty."
    extraction_id = "rx_" + hashlib.sha256(b"extraction").hexdigest()
    artifact = {
        "extraction_id": extraction_id,
        "schema": "ResearchDocumentTextV1",
        "source_sha256": source_sha,
        "parser": "pypdf",
        "parser_version": "6.14.2",
        "config_hash": hashlib.sha256(b"config").hexdigest(),
        "normalization": "NFC_LF_RSTRIP_V1",
        "status": "extracted",
        "pages": [
            {
                "page": 1,
                "text": text,
                "character_count": len(text),
                "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
            }
        ],
        "page_count": 1,
        "character_count": len(text),
        "warnings": [],
        "trust_label": "UNTRUSTED_SOURCE",
    }
    store.record_research_document_text(str(source["source_id"]), artifact=artifact)
    context = store.get_research_source_context(str(source["source_id"]), excerpt_limit=24)
    assert context["document"] is not None
    previews = cast(list[dict[str, object]], context["page_previews"])
    assert previews[0]["excerpt"] == text[:24]
    assert previews[0]["excerpt_truncated"] is True
    assert previews[0]["trust_label"] == "UNTRUSTED_SOURCE"
    with pytest.raises(DataError, match="excerpt limit"):
        store.get_research_source_context(str(source["source_id"]), excerpt_limit=0)

    with pytest.raises(DataError, match="SourceAnchorV1"):
        store.draft_source_claim(
            project_id,
            source_id=str(source["source_id"]),
            contract_id=contract_id,
            claim_text="Small positive effect with uncertainty.",
            direction="supports",
            strength="weak",
            method_summary="Event study.",
            sample_summary="Reported sample.",
            markets=["US_EQUITY"],
            limitations="Wide uncertainty.",
            author="codex",
            author_kind="agent",
        )

    excerpt = "small positive effect"
    start = text.index(excerpt)
    claim = store.draft_source_claim(
        project_id,
        source_id=str(source["source_id"]),
        contract_id=contract_id,
        claim_text="Small positive effect with uncertainty.",
        direction="supports",
        strength="weak",
        method_summary="Event study.",
        sample_summary="Reported sample.",
        markets=["US_EQUITY"],
        limitations="Wide uncertainty.",
        author="codex",
        author_kind="agent",
        source_anchor={
            "extraction_id": extraction_id,
            "page": 1,
            "char_start": start,
            "char_end": start + len(excerpt),
            "exact_text_sha256": hashlib.sha256(excerpt.encode()).hexdigest(),
        },
    )
    assert claim["anchor_state"] == "verified"
    assert cast(dict[str, object], claim["source_anchor"])["excerpt"] == excerpt
    screened = store.screen_source_claim(project_id, claim_id=str(claim["claim_id"]), actor="owner")
    assert screened["anchor_state"] == "verified"

    extraction_path = next((tmp_path / "research" / "literature" / "extractions").glob("*.json"))
    extraction_path.write_text("{}", encoding="utf-8")
    with pytest.raises(DataError, match="integrity"):
        store.list_source_claims(project_id)
    with pytest.raises(DataError, match="unknown research source"):
        store.draft_source_claim(
            project_id,
            source_id="rs_" + "0" * 64,
            contract_id=contract_id,
            claim_text="x",
            direction="supports",
            strength="weak",
            method_summary="m",
            sample_summary="s",
            markets=[],
            limitations="l",
            author="codex",
            author_kind="agent",
        )


def test_source_search_is_bounded_and_local_only(tmp_path: Path) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    for index, title in enumerate(
        ("Momentum everywhere", "Double bottoms revisited", "Double tops and bottoms")
    ):
        store.create_research_source(
            PROJECT_ID,
            title=title,
            locator=f"doi:10.0000/s{index}",
            provider="crossref",
            access_mode="metadata_only",
            doi=f"10.0000/s{index}",
            at=START + timedelta(minutes=index),
        )
    hits = store.search_research_sources("double bottom")
    assert [row["title"] for row in hits] == [
        "Double bottoms revisited",
        "Double tops and bottoms",
    ]
    by_doi = store.search_research_sources("10.0000/s0")
    assert [row["title"] for row in by_doi] == ["Momentum everywhere"]
    assert store.search_research_sources("nonexistent topic") == []
    with pytest.raises(DataError, match="query"):
        store.search_research_sources("")


def test_source_record_columns_heal_on_a_pre_r4_store(tmp_path: Path) -> None:
    """A schema-v2 store predating the typed columns gains them idempotently on open."""
    store = ControlStore(tmp_path)
    _project(store)
    database = tmp_path / "control" / control_store_module.DATABASE_NAME
    connection = sqlite3.connect(database)
    try:
        for column in ("doi", "year", "authors_json"):
            connection.execute(f"ALTER TABLE research_source_records DROP COLUMN {column}")
        connection.commit()
        present = {
            str(row[1]) for row in connection.execute("PRAGMA table_info(research_source_records)")
        }
        assert "doi" not in present
    finally:
        connection.close()

    healed = ControlStore(tmp_path)
    source = healed.create_research_source(
        PROJECT_ID,
        title="Post-heal typed source",
        locator="doi:10.0000/healed",
        provider="crossref",
        access_mode="metadata_only",
        doi="10.0000/healed",
        year=2020,
        authors=["A. Author"],
        at=START,
    )
    assert source["doi"] == "10.0000/healed"
    assert healed.get_research_source(str(source["source_id"]))["year"] == 2020


def test_list_research_decisions_returns_append_only_history(tmp_path: Path) -> None:
    store = ControlStore(tmp_path)
    _project(store)
    assert store.list_research_decisions(PROJECT_ID) == []
    _, confirmation_id = _approved_contracts(store, outcome="INCONCLUSIVE", disposition="park")
    history = store.list_research_decisions(PROJECT_ID)
    assert len(history) == 1
    event = history[0]
    assert event["contract_id"] == confirmation_id
    assert event["outcome"] == "INCONCLUSIVE"
    assert event["disposition"] == "park"
    assert event["actor"] == "owner"
    assert event["actor_kind"] == "human"
    assert isinstance(event["sequence"], int)
    assert isinstance(event["occurred_at"], str) and event["occurred_at"]
    assert isinstance(event["reason"], str) and event["reason"]
    # The reader is bounded to recorded decision columns; no payloads ride along.
    assert set(event) == {
        "sequence",
        "contract_id",
        "outcome",
        "disposition",
        "actor",
        "actor_kind",
        "occurred_at",
        "reason",
    }
    with pytest.raises(DataError, match="unknown"):
        store.list_research_decisions("00000000-0000-4000-8000-00000000ffff")
