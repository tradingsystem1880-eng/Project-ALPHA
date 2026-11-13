"""Actual backfill orchestration with explicit disposable dispatch accounting, no providers."""

from __future__ import annotations

import sqlite3
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest

from alpha_cli._crypto_backfill import Ledger, run_backfill
from alpha_cli._crypto_backfill_accounting import (
    FixtureAccountingBlocked,
    FixtureBackfillAccounting,
)
from alpha_cli._market_data_acquisition_accounting import (
    FIXTURE_DDL,
    AcquisitionTransactions,
    Charge,
    Dimension,
    FixturePolicy,
)

from .test_crypto_backfill_resume_cli import environment as environment

NOW = datetime(2026, 9, 10, tzinfo=UTC)
POLICY = FixturePolicy(
    "campaign", "synthetic_generation", (Dimension("dispatches", "total", 2, None, None, 1),)
)
CHARGES = (Charge("dispatches", "total", 1),)


def setup(path: Path, policy: FixturePolicy = POLICY) -> sqlite3.Connection:
    conn = sqlite3.connect(path, timeout=0.5, isolation_level=None)
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=FULL")
    conn.executescript(FIXTURE_DDL)
    conn.execute("BEGIN IMMEDIATE")
    AcquisitionTransactions(conn).record_fixture_scope("scope", policy, history_available=True)
    conn.commit()
    return conn


def bridge(conn: sqlite3.Connection, **overrides: Any) -> FixtureBackfillAccounting:
    return FixtureBackfillAccounting(
        connection=conn,
        scope_id="scope",
        policy=overrides.pop("policy", POLICY),
        charges=overrides.pop("charges", CHARGES),
        attempt_label=overrides.pop("attempt_label", "try1"),
        bookkeeping_clock_ms=overrides.pop("bookkeeping_clock_ms", lambda: 10),
        cancelled=overrides.pop("cancelled", lambda: False),
        busy_timeout_ms=500,
        allowance_basis=overrides.pop("allowance_basis", "synthetic_window_dispatch"),
        **overrides,
    )


def run(
    root: Path, account: FixtureBackfillAccounting | None, acquire: Any, **overrides: Any
) -> dict[str, object]:
    return run_backfill(
        provider="bybit",
        family="funding",
        symbols=overrides.pop("symbols", ["BTCUSDT"]),
        quote="USDT",
        category="linear",
        frequency="1h",
        start=date(2024, 1, 1),
        end=date(2024, 2, 1),
        ledger_path=root / "progress.json",
        acquire=acquire,
        now=NOW,
        pause_seconds=0,
        verify_completed=overrides.pop("verify_completed", lambda *args: None),
        fixture_accounting=account,
        **overrides,
    )


def attempt_rows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    conn.execute("BEGIN")
    try:
        return AcquisitionTransactions(conn).scope_attempts("scope")
    finally:
        conn.rollback()


def test_real_orchestrator_commits_dispatch_before_callback_and_reopens_without_double_charge(
    tmp_path: Path,
) -> None:
    conn = setup(tmp_path / "account.sqlite")
    calls = []

    def acquire(*args: Any, **kwargs: Any) -> dict[str, object]:
        assert not conn.in_transaction
        assert attempt_rows(conn)[0]["state"] == "intent"
        calls.append(args)
        return {"normalized_manifest_id": "a" * 64, "state": "qualified"}

    result = run(tmp_path, bridge(conn), acquire)
    assert result["done"] == 1 and len(calls) == 1
    assert attempt_rows(conn)[0]["state"] == "success"
    conn.close()
    conn = sqlite3.connect(tmp_path / "account.sqlite", timeout=0.5, isolation_level=None)
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA synchronous=FULL")
    resumed = run(tmp_path, bridge(conn), acquire)
    assert resumed["skipped"] == 1 and len(calls) == 1
    assert conn.execute("SELECT sum(units) FROM md_acquisition_debits").fetchone()[0] == 1
    conn.close()


def test_callback_failure_is_fatal_unknown_not_ordinary_split_retry_or_secret_persistence(
    tmp_path: Path,
) -> None:
    conn = setup(tmp_path / "account.sqlite")
    calls = []

    def acquire(*args: Any, **kwargs: Any) -> Any:
        calls.append(args)
        raise ValueError("SECRET_CANARY fills one provider page")

    with pytest.raises(FixtureAccountingBlocked) as failure:
        run(tmp_path, bridge(conn), acquire, symbols=["BTCUSDT", "ETHUSDT"])
    assert len(calls) == 1 and "SECRET_CANARY" not in str(failure.value)
    assert not (tmp_path / "progress.json").exists()
    assert attempt_rows(conn)[0]["state"] == "unknown"
    assert "SECRET_CANARY" not in str(
        conn.execute("SELECT payload FROM md_acquisition_events").fetchall()
    )
    with pytest.raises(FixtureAccountingBlocked):
        run(tmp_path, bridge(conn), acquire)
    assert len(calls) == 1
    conn.close()


def test_idle_supplied_connection_is_checked_before_any_progress_lock(tmp_path: Path) -> None:
    conn = setup(tmp_path / "account.sqlite")
    account = bridge(conn)
    conn.execute("BEGIN IMMEDIATE")
    with pytest.raises(FixtureAccountingBlocked, match="IDLE_CONNECTION_OWNER_REQUIRED"):
        run(tmp_path, account, lambda *a, **k: pytest.fail("no dispatch"))
    assert conn.in_transaction and not (tmp_path / "progress.json.lock").exists()
    conn.rollback()
    conn.close()


@pytest.mark.parametrize("change", ["policy", "charges", "missing_accounting"])
def test_completed_progress_requires_matching_accounting_not_just_success(
    tmp_path: Path, change: str
) -> None:
    conn = setup(tmp_path / "account.sqlite")
    calls = []

    def acquire(*a: Any, **k: Any) -> dict[str, object]:
        calls.append(a)
        return {"normalized_manifest_id": "a" * 64, "state": "qualified"}

    run(tmp_path, bridge(conn) if change != "missing_accounting" else None, acquire)
    altered = (
        FixturePolicy("campaign", "changed", POLICY.dimensions) if change == "policy" else POLICY
    )
    charges = (Charge("dispatches", "total", 2),) if change == "charges" else CHARGES
    with pytest.raises(FixtureAccountingBlocked):
        run(tmp_path, bridge(conn, policy=altered, charges=charges), acquire)
    assert len(calls) == 1
    conn.close()


@pytest.mark.parametrize(
    "stage", ["before", "after_intent", "after_callback", "external_cancel", "history_lost"]
)
def test_cancellation_and_history_changes_never_publish_done_or_refund(
    tmp_path: Path, stage: str
) -> None:
    conn = setup(tmp_path / "account.sqlite")
    calls = []
    checks = []

    def cancelled() -> bool:
        checks.append(1)
        return (
            stage == "before"
            or (stage == "after_intent" and len(checks) >= 2)
            or (stage == "after_callback" and len(checks) >= 3)
        )

    def acquire(*a: Any, **k: Any) -> dict[str, object]:
        calls.append(a)
        if stage in {"external_cancel", "history_lost"}:
            conn.execute("BEGIN IMMEDIATE")
            tx = AcquisitionTransactions(conn)
            if stage == "external_cancel":
                tx.request_cancel("external_cancel", tx.scope_attempts("scope")[0]["attempt_id"])
            else:
                tx.record_unavailable_history("lost", "scope", "missing_later_history")
            conn.commit()
        return {"normalized_manifest_id": "a" * 64, "state": "qualified"}

    with pytest.raises(FixtureAccountingBlocked):
        run(tmp_path, bridge(conn, cancelled=cancelled), acquire)
    rows = attempt_rows(conn)
    if stage == "before":
        assert rows == []
    else:
        assert len(rows) == 1 and rows[0]["state"] in {"cancelled", "unknown"}
        assert conn.execute("SELECT sum(units) FROM md_acquisition_debits").fetchone()[0] == 1
    assert len(calls) == (
        1 if stage in {"after_callback", "external_cancel", "history_lost"} else 0
    )
    assert not (tmp_path / "progress.json").exists()
    conn.close()


@pytest.mark.parametrize("label", ["try1", "try2"])
def test_progress_publication_failure_cannot_refetch_successfully_charged_dispatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, label: str
) -> None:
    conn = setup(tmp_path / "account.sqlite")
    calls = []

    def acquire(*a: Any, **k: Any) -> dict[str, object]:
        calls.append(a)
        return {"normalized_manifest_id": "a" * 64, "state": "qualified"}

    original = Ledger.record
    monkeypatch.setattr(
        Ledger, "record", lambda *a, **k: (_ for _ in ()).throw(OSError("publication failed"))
    )
    with pytest.raises(OSError):
        run(tmp_path, bridge(conn), acquire)
    monkeypatch.setattr(Ledger, "record", original)
    assert attempt_rows(conn)[0]["state"] == "success"
    with pytest.raises(FixtureAccountingBlocked, match="REQUIRES_EVIDENCE"):
        run(tmp_path, bridge(conn, attempt_label=label), acquire)
    assert len(calls) == 1
    conn.close()


def test_actual_native_acquisition_pipeline_and_completed_hash_verification(
    environment: Any, tmp_path: Path
) -> None:
    from alpha_cli import crypto_data_cmds
    from alpha_cli._crypto_backfill_evidence import verify_completed_window

    store, root, calls = environment
    conn = setup(tmp_path / "account.sqlite")

    def verify(symbol: str, window: Any, entry: Any) -> None:
        assert not conn.in_transaction
        verify_completed_window(
            store,
            symbol,
            window,
            entry,
            provider="bybit",
            family="funding",
            category="linear",
            frequency="1h",
            quote="USDT",
            now=NOW,
        )

    first = run(root, bridge(conn), crypto_data_cmds._backfill_acquire, verify_completed=verify)
    resumed = run(root, bridge(conn), crypto_data_cmds._backfill_acquire, verify_completed=verify)
    assert first["done"] == 1 and resumed["skipped"] == 1 and len(calls) == 1
    assert len(store.inventory()) == 2
    assert conn.execute("SELECT sum(units) FROM md_acquisition_debits").fetchone()[0] == 1
    conn.close()


def test_callback_cannot_redirect_original_scope_settlement(tmp_path: Path) -> None:
    conn = setup(tmp_path / "account.sqlite")
    conn.execute("BEGIN IMMEDIATE")
    AcquisitionTransactions(conn).record_fixture_scope("other", POLICY, history_available=True)
    conn.commit()
    account = bridge(conn)

    def acquire(*a: Any, **k: Any) -> dict[str, object]:
        conn.execute("BEGIN IMMEDIATE")
        AcquisitionTransactions(conn).record_unavailable_history("lost", "scope", "missing_history")
        conn.commit()
        attribute_to_change = "scope_id"
        setattr(account, attribute_to_change, "other")
        return {"normalized_manifest_id": "a" * 64, "state": "qualified"}

    with pytest.raises(FixtureAccountingBlocked):
        run(tmp_path, account, acquire)
    assert not (tmp_path / "progress.json").exists()
    conn.close()


def test_changed_connection_settings_refuse_settlement_without_refunding(tmp_path: Path) -> None:
    conn = setup(tmp_path / "account.sqlite")
    account = bridge(conn)
    calls = []

    def acquire(*a: Any, **k: Any) -> dict[str, object]:
        calls.append(a)
        conn.execute("PRAGMA synchronous=OFF")
        return {"normalized_manifest_id": "a" * 64, "state": "qualified"}

    with pytest.raises(FixtureAccountingBlocked) as failure:
        run(tmp_path, account, acquire)
    assert failure.value.reconciliation_persisted is False
    assert len(calls) == 1 and not (tmp_path / "progress.json").exists()
    conn.execute("PRAGMA synchronous=FULL")
    assert attempt_rows(conn)[0]["state"] == "intent"
    with pytest.raises(FixtureAccountingBlocked):
        run(tmp_path, bridge(conn, attempt_label="try2"), acquire)
    assert (
        len(calls) == 1
        and conn.execute("SELECT sum(units) FROM md_acquisition_debits").fetchone()[0] == 1
    )
    conn.close()


@pytest.mark.parametrize(
    "override",
    [
        {"policy": None},
        {"charges": ()},
        {"attempt_label": ""},
        {"allowance_basis": "http_requests"},
    ],
)
def test_required_explicit_fixture_inputs_fail_closed(
    tmp_path: Path, override: dict[str, Any]
) -> None:
    conn = setup(tmp_path / "account.sqlite")
    with pytest.raises(FixtureAccountingBlocked):
        bridge(conn, **override)
    assert attempt_rows(conn) == [] and not (tmp_path / "progress.json.lock").exists()
    conn.close()


def test_tampered_accounting_schema_is_not_initialized_or_healed(tmp_path: Path) -> None:
    conn = setup(tmp_path / "account.sqlite")
    conn.execute("DROP TABLE md_acquisition_meta")
    with pytest.raises(FixtureAccountingBlocked):
        run(tmp_path, bridge(conn), lambda *a, **k: pytest.fail("no dispatch"))
    assert (
        conn.execute(
            "SELECT count(*) FROM sqlite_master WHERE name='md_acquisition_meta'"
        ).fetchone()[0]
        == 0
    )
    conn.close()


def test_default_unaccounted_behavior_does_not_touch_the_fragment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        AcquisitionTransactions,
        "__init__",
        lambda *a, **k: pytest.fail("inactive default must not query accounting"),
    )
    result = run(
        tmp_path, None, lambda *a, **k: {"normalized_manifest_id": "a" * 64, "state": "qualified"}
    )
    assert result["done"] == 1


def test_unowned_direct_dispatch_refuses_before_sql_debit(tmp_path: Path) -> None:
    conn = setup(tmp_path / "account.sqlite")
    account = bridge(conn)
    ledger = Ledger.open(
        tmp_path / "progress.json",
        provider="bybit",
        family="funding",
        category="linear",
        frequency="1h",
    )
    with pytest.raises(FixtureAccountingBlocked, match="LEDGER_OWNER_REQUIRED"):
        account.dispatch(
            ledger, lambda *a, **k: pytest.fail("no dispatch"), ("bybit", "funding", "BTCUSDT"), {}
        )
    assert attempt_rows(conn) == []
    conn.close()
