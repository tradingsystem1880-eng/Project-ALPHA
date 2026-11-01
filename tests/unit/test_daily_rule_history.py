"""Read-only engineering fixtures; none is a real study or transferable authority."""

from __future__ import annotations

import contextlib
import json
import sqlite3
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest

from alpha_cli.control_store import ControlStore
from alpha_core import DataError

PROJECT = "00000000-0000-4000-8000-000000000001"
DAILY = "binance_btcusdt_daily_rule_control"


def _store(root: Path, project: str = PROJECT) -> ControlStore:
    store = ControlStore(root)
    store.create_project(
        name="PRIVATE-PROJECT-PROSE",
        hypothesis="PRIVATE-HYPOTHESIS",
        falsification_criterion="PRIVATE-FALSIFICATION",
        project_id=project,
        at=datetime(2026, 10, 31, tzinfo=UTC),
    )
    return store


def _contract(root: Path, identifier: str, payload: str, project: str = PROJECT) -> None:
    with sqlite3.connect(root / "control/workstation.sqlite3") as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute(
            "INSERT INTO research_contracts VALUES (?, ?, 'exploration', NULL, ?, ?, 'human', ?)",
            (identifier, project, payload, "PRIVATE-ACTOR", "2026-10-31T00:00:00+00:00"),
        )


def _daily_payload() -> str:
    return json.dumps(
        {"protocol": {"d0_operator": {"name": DAILY}}, "private_prose": "PRIVATE-CONTRACT"}
    )


def test_missing_history_is_not_created_or_reported_empty(tmp_path: Path) -> None:
    with pytest.raises(DataError, match="directory does not exist"):
        ControlStore(tmp_path).daily_rule_history()
    assert not (tmp_path / "control").exists()


def test_history_reads_metadata_without_mutating_store_or_leaking_prose(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = _store(tmp_path)
    _contract(tmp_path, "rc_" + "a" * 64, _daily_payload())
    database = tmp_path / "control/workstation.sqlite3"
    before = database.read_bytes()
    monkeypatch.setattr(store, "_open", lambda: pytest.fail("write-capable opener called"))

    first = store.daily_rule_history()
    assert first == store.daily_rule_history()
    assert first["daily_contract_count"] == 1
    assert first["daily_deep_reservation_count"] == 0
    assert first["authority"] == "none"
    assert first["new_root_authorized"] is False
    contracts = cast(list[dict[str, object]], first["contracts"])
    assert contracts[0]["contract_id"] == "rc_" + "a" * 64
    assert "PRIVATE" not in json.dumps(first)
    assert database.read_bytes() == before


def test_missing_database_is_not_created_in_existing_control_directory(tmp_path: Path) -> None:
    control = tmp_path / "control"
    control.mkdir()
    with pytest.raises(DataError, match="database does not exist"):
        ControlStore(tmp_path).daily_rule_history()
    assert list(control.iterdir()) == []


def test_corrupt_database_is_not_replaced_or_repaired(tmp_path: Path) -> None:
    control = tmp_path / "control"
    control.mkdir()
    database = control / "workstation.sqlite3"
    original = b"synthetic corrupt database; never real history"
    database.write_bytes(original)
    with pytest.raises(DataError, match="cannot read control store without changing it"):
        ControlStore(tmp_path).daily_rule_history()
    assert database.read_bytes() == original
    assert list(control.iterdir()) == [database]


def test_live_uncommitted_write_is_invisible_and_reader_does_not_write(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _contract(tmp_path, "rc_" + "a" * 64, _daily_payload())
    database = tmp_path / "control/workstation.sqlite3"
    with sqlite3.connect(database, isolation_level=None) as writer:
        writer.execute("BEGIN IMMEDIATE")
        writer.execute("UPDATE research_contracts SET payload_json='{}'")
        before = database.read_bytes()
        wal = database.with_name(database.name + "-wal")
        before_wal = wal.read_bytes()
        assert store.daily_rule_history()["daily_contract_count"] == 1
        assert database.read_bytes() == before
        assert wal.read_bytes() == before_wal
        assert writer.in_transaction
        writer.rollback()
    assert store.daily_rule_history()["daily_contract_count"] == 1


def test_unclassified_contract_metadata_never_becomes_a_clean_empty_history(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _contract(tmp_path, "rc_" + "b" * 64, "{}")

    history = store.daily_rule_history()
    assert history["daily_contract_count"] == 0
    assert history["unclassified_contract_count"] == 1
    assert history["routing_metadata_complete"] is False
    assert history["new_root_authorized"] is False


def test_other_routed_reservations_remain_visible_without_becoming_daily(tmp_path: Path) -> None:
    store = _store(tmp_path)
    contract = "rc_" + "b" * 64
    _contract(tmp_path, contract, '{"protocol":{"d0_operator":{"name":"ordinary"}}}')
    _reservation(tmp_path, contract, PROJECT)
    history = store.daily_rule_history()
    assert history["contract_count"] == history["reservation_count"] == 1
    assert history["daily_deep_reservation_count"] == 0
    assert history["contracts"] == []
    assert history["new_root_authorized"] is False


def _reservation(root: Path, contract: str, project: str) -> None:
    with sqlite3.connect(root / "control/workstation.sqlite3") as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute(
            """INSERT INTO research_execution_events
            (project_id, sequence, contract_id, state, occurred_at, actor, reason,
             next_action, responsibility)
            VALUES (?, 1, ?, 'failed', ?, 'fixture', 'fixture', 'none', 'owner')""",
            (project, contract, "2026-10-31T00:00:00+00:00"),
        )
        connection.execute(
            """INSERT INTO research_launch_reservations VALUES
            (?, ?, ?, 'deep_research', 'fixture-kind', 1, ?, '{}', 1, ?)""",
            ("rr_" + "c" * 64, project, contract, "f" * 64, "2026-10-31T00:00:00+00:00"),
        )


def test_reservation_count_covers_other_projects_and_contracts_outside_page(tmp_path: Path) -> None:
    store = _store(tmp_path)
    other = "00000000-0000-4000-8000-000000000002"
    _store(tmp_path, other)
    _contract(tmp_path, "rc_" + "a" * 64, _daily_payload())
    _contract(tmp_path, "rc_" + "b" * 64, _daily_payload(), other)
    _reservation(tmp_path, "rc_" + "b" * 64, other)

    history = store.daily_rule_history(limit=1)
    assert history["daily_contract_count"] == 2
    assert history["daily_deep_reservation_count"] == 1
    assert history["truncated"] is True
    assert history["routing_metadata_complete"] is False
    assert history["new_root_authorized"] is False
    page = store.daily_rule_history(limit=1, offset=100)
    assert page["contracts"] == []
    assert page["daily_deep_reservation_count"] == 1
    assert page["routing_metadata_complete"] is False


@pytest.mark.parametrize(
    "payload",
    ["broken-json", "[]", "{}", '{"protocol":[]}', '"' + "x" * 1_048_577 + '"'],
    ids=["invalid-json", "array", "missing-routing", "invalid-routing", "oversized"],
)
def test_invalid_or_oversized_routing_metadata_is_unknown(tmp_path: Path, payload: str) -> None:
    store = _store(tmp_path)
    contract = "rc_" + "b" * 64
    _contract(tmp_path, contract, payload)
    _reservation(tmp_path, contract, PROJECT)

    history = store.daily_rule_history()
    assert history["unclassified_contract_count"] == 1
    assert history["unclassified_deep_reservation_count"] == 1
    assert history["routing_metadata_complete"] is False


@pytest.mark.parametrize(
    "payload",
    [
        '{"protocol":{"d0_operator":{"name":"ordinary"}},'
        '"protocol":{"d0_operator":{"name":"' + DAILY + '"}}}',
        '{"protocol":{"d0_operator":{"name":"ordinary"},"d0_operator":{"name":"' + DAILY + '"}}}',
        '{"protocol":{"d0_operator":{"name":"ordinary","name":"' + DAILY + '"}}}',
        _daily_payload() + "\x00" + "x" * 1000,
        '{"protocol":{"d0_operator":{"name":"' + DAILY + '\\u0000suffix"}}}',
    ],
    ids=["duplicate-protocol", "duplicate-operator", "duplicate-name", "nul-json", "nul-name"],
)
def test_ambiguous_routing_never_hides_a_possible_prior_exposure(
    tmp_path: Path, payload: str
) -> None:
    store = _store(tmp_path)
    contract = "rc_" + "b" * 64
    _contract(tmp_path, contract, payload)
    _reservation(tmp_path, contract, PROJECT)
    history = store.daily_rule_history()
    assert history["unclassified_contract_count"] == 1
    assert history["unclassified_deep_reservation_count"] == 1
    assert history["routing_metadata_complete"] is False


def test_orphan_event_study_job_is_visible_without_reading_request(tmp_path: Path) -> None:
    store = _store(tmp_path)
    with sqlite3.connect(tmp_path / "control/workstation.sqlite3") as connection:
        connection.execute(
            """INSERT INTO jobs VALUES
            ('fixture-job', 'research:event-study', 'failed', ?, NULL,
             ?, ?, ?, ?, NULL, NULL, 0)""",
            (PROJECT, '{"private":"PRIVATE-REQUEST"}', *["2026-10-31T00:00:00+00:00"] * 3),
        )
    history = store.daily_rule_history()
    assert history["event_study_job_count"] == 1
    assert history["reservation_count"] == 0
    assert history["new_root_authorized"] is False
    assert "PRIVATE" not in json.dumps(history)


@pytest.mark.parametrize("limit,offset", [(0, 0), (201, 0), (True, 0), (1, -1), (1, True)])
def test_pagination_is_validated_before_opening_missing_store(
    tmp_path: Path, limit: int, offset: int
) -> None:
    with pytest.raises(DataError, match="daily history"):
        ControlStore(tmp_path).daily_rule_history(limit=limit, offset=offset)
    assert not (tmp_path / "control").exists()


@pytest.mark.parametrize("offset", [2**63, 2**80])
def test_sqlite_offset_overflow_is_a_typed_input_error(tmp_path: Path, offset: int) -> None:
    store = _store(tmp_path)
    with pytest.raises(DataError, match="daily history offset"):
        store.daily_rule_history(offset=offset)


def test_largest_sqlite_offset_keeps_global_reservation_count(tmp_path: Path) -> None:
    store = _store(tmp_path)
    contract = "rc_" + "b" * 64
    _contract(tmp_path, contract, _daily_payload())
    _reservation(tmp_path, contract, PROJECT)
    history = store.daily_rule_history(offset=2**63 - 1)
    assert history["contracts"] == []
    assert history["daily_deep_reservation_count"] == 1
    assert history["routing_metadata_complete"] is False


def test_script_reports_oversized_offset_without_a_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from inspect_daily_rule_history import main

    _store(tmp_path)
    with pytest.raises(SystemExit) as exc:
        main(["--data-dir", str(tmp_path), "--offset", str(2**80)])
    assert exc.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "daily history offset" in captured.err
    assert "Traceback" not in captured.err


def test_old_schema_is_not_migrated(tmp_path: Path) -> None:
    store = _store(tmp_path)
    database = tmp_path / "control/workstation.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA user_version=6")
    before = database.read_bytes()
    with pytest.raises(DataError, match="requires schema version"):
        store.daily_rule_history()
    assert database.read_bytes() == before


def test_large_history_is_unknown_instead_of_truncated_to_no_consumption(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from alpha_cli import _native_daily_rule_history

    store = _store(tmp_path)
    _contract(tmp_path, "rc_" + "a" * 64, _daily_payload())
    _contract(tmp_path, "rc_" + "b" * 64, _daily_payload())
    monkeypatch.setattr(_native_daily_rule_history, "_MAX_HISTORY_RECORDS", 1)
    with pytest.raises(DataError, match="history is unknown"):
        store.daily_rule_history()


def test_oversized_identifiers_fail_before_returning_unbounded_metadata(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _contract(tmp_path, "r" * 101, _daily_payload())
    with pytest.raises(DataError, match="identifier metadata"):
        store.daily_rule_history()


def test_total_contract_bytes_are_bounded_before_json_classification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from alpha_cli import _native_daily_rule_history

    store = _store(tmp_path)
    _contract(tmp_path, "rc_" + "a" * 64, _daily_payload())
    monkeypatch.setattr(_native_daily_rule_history, "_MAX_METADATA_BYTES", 1)
    with pytest.raises(DataError, match="byte budget; history is unknown"):
        store.daily_rule_history()


@pytest.mark.parametrize(
    "identifier",
    ["rc_\x00suffix", "rc_\x00" + "x" * 1000, "é" * 60],
    ids=["nul-short", "nul-long", "utf8-byte-bound"],
)
def test_identifier_byte_bounds_and_nul_are_checked(tmp_path: Path, identifier: str) -> None:
    store = _store(tmp_path)
    _contract(tmp_path, identifier, _daily_payload())
    with pytest.raises(DataError, match="identifier metadata"):
        store.daily_rule_history()


def test_missing_projection_columns_are_not_repaired(tmp_path: Path) -> None:
    store = _store(tmp_path)
    database = tmp_path / "control/workstation.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute("ALTER TABLE jobs RENAME COLUMN kind TO missing_kind")
    before = database.read_bytes()
    with pytest.raises(DataError, match="required columns"):
        store.daily_rule_history()
    assert database.read_bytes() == before


def test_symlinked_control_root_is_not_followed(tmp_path: Path) -> None:
    other = tmp_path / "other"
    _store(other)
    root = tmp_path / "selected"
    root.mkdir()
    (root / "control").symlink_to(other / "control", target_is_directory=True)
    with pytest.raises(DataError, match="must not be a symlink"):
        ControlStore(root).daily_rule_history()


def test_projection_does_not_read_private_columns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = _store(tmp_path)
    _contract(tmp_path, "rc_" + "a" * 64, _daily_payload())
    original = store._readonly_transaction
    forbidden = {
        ("projects", "name"),
        ("projects", "hypothesis"),
        ("jobs", "request_json"),
        ("jobs", "terminal_error"),
        ("research_attempt_records", "details_json"),
        ("research_launch_reservations", "budget_reserved_json"),
    }

    @contextlib.contextmanager
    def guarded() -> Iterator[sqlite3.Connection]:
        with original() as connection:
            connection.set_authorizer(
                lambda action, table, column, _db, _trigger: (
                    sqlite3.SQLITE_DENY
                    if action == sqlite3.SQLITE_READ and (table, column) in forbidden
                    else sqlite3.SQLITE_OK
                )
            )
            yield connection

    monkeypatch.setattr(store, "_readonly_transaction", guarded)
    assert store.daily_rule_history()["daily_contract_count"] == 1


def test_one_snapshot_covers_counts_and_rows_during_concurrent_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = _store(tmp_path)
    _contract(tmp_path, "rc_" + "a" * 64, _daily_payload())
    original = store._readonly_transaction

    @contextlib.contextmanager
    def concurrent() -> Iterator[sqlite3.Connection]:
        with original() as connection:
            assert connection.execute("PRAGMA query_only").fetchone()[0] == 1
            _contract(tmp_path, "rc_" + "b" * 64, _daily_payload())
            yield connection

    with monkeypatch.context() as patch:
        patch.setattr(store, "_readonly_transaction", concurrent)
        history = store.daily_rule_history()
    assert history["daily_contract_count"] == 1
    assert len(cast(list[object], history["contracts"])) == 1
    assert store.daily_rule_history()["daily_contract_count"] == 2


def test_operator_script_uses_only_explicit_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from inspect_daily_rule_history import main

    _store(tmp_path)
    _contract(tmp_path, "rc_" + "a" * 64, _daily_payload())
    wrong_root = tmp_path / "environment-root"
    monkeypatch.setenv("ALPHA_DATA_DIR", str(wrong_root))
    assert main(["--data-dir", str(tmp_path)]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["daily_contract_count"] == 1
    assert output["new_root_authorized"] is False
    assert not wrong_root.exists()


def test_operator_script_reports_unknown_missing_history_with_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from inspect_daily_rule_history import main

    with pytest.raises(SystemExit) as exc:
        main(["--data-dir", str(tmp_path)])
    assert exc.value.code == 2
    output = capsys.readouterr()
    assert output.out == ""
    assert "History inspection blocked" in output.err
    assert not (tmp_path / "control").exists()
