"""Advisory investigation cases retain scope, failed attempts and budgets across restart."""

from pathlib import Path

import pytest

from alpha_cli.investigation_case import Case
from alpha_core import DataError
from tests.unit.test_research_execution import run_fixture


def make_case(tmp_path: Path, *, max_calls: int = 6) -> Case:
    run = run_fixture(tmp_path)
    return Case.create(
        tmp_path / "case", run, "2020-01-02", "Explain the loss", "gpt-6-astra", max_calls
    )


def test_create_resume_and_cached_receipt(tmp_path: Path) -> None:
    case = make_case(tmp_path)
    receipt = case.call("inspect_execution")
    assert receipt["status"] == "succeeded"
    assert receipt["authority"] == "none"
    assert receipt["result"]["run_id"] == "1234567890abcdef"
    resumed = Case.open(tmp_path / "case")
    assert resumed.call("inspect_execution") == receipt
    assert len(resumed.receipts()) == 1
    assert resumed.context()["calls_remaining"] == 5
    assert resumed.context()["admitted"] is False
    assert resumed.context()["request_limit"] == 12
    assert resumed.context()["requests_remaining"] == 10


def test_cached_requests_exhaust_total_budget_across_reopen(tmp_path: Path) -> None:
    case = make_case(tmp_path)
    original = case.call("inspect_execution")
    for _ in range(11):
        assert Case.open(case.path).call("inspect_execution") == original
    with pytest.raises(DataError, match="request budget"):
        Case.open(case.path).call("inspect_execution")
    assert case.context()["requests_remaining"] == 0
    assert case.context()["calls_remaining"] == 5
    assert len(case.receipts()) == 1


def test_denied_prerequisites_consume_request_budget(tmp_path: Path) -> None:
    case = make_case(tmp_path)
    for _ in range(12):
        with pytest.raises(DataError, match="inspect_execution"):
            case.call("inspect_losses")
    with pytest.raises(DataError, match="request budget"):
        case.call("inspect_execution")
    assert case.context()["requests_remaining"] == 0
    assert case.receipts() == []


def test_missing_request_ledger_cannot_be_reinitialized(tmp_path: Path) -> None:
    import sqlite3

    case = make_case(tmp_path)
    with sqlite3.connect(case.path / "case.sqlite3") as connection:
        connection.execute("DROP TABLE requests")
    with pytest.raises(DataError, match="request ledger"):
        Case.open(case.path)
    with pytest.raises(DataError, match="request ledger"):
        Case.create(
            case.path,
            tmp_path / "1234567890abcdef",
            "2020-01-02",
            "Explain the loss",
            "gpt-6-astra",
        )


def test_processes_compete_for_last_cached_request(tmp_path: Path) -> None:
    import subprocess
    import sys

    case = make_case(tmp_path)
    for _ in range(11):
        case.call("inspect_execution")
    program = """import sys
from pathlib import Path
from alpha_cli.investigation_case import Case
from alpha_core import DataError
try:
 print(Case.open(Path(sys.argv[1])).call("inspect_execution")["status"])
except DataError as exc:
 print(str(exc))
"""
    processes = [
        subprocess.Popen(
            [sys.executable, "-c", program, str(case.path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for _ in range(2)
    ]
    outputs = [process.communicate(timeout=30) for process in processes]
    assert all(process.returncode == 0 for process in processes), outputs
    assert sorted(out.strip() for out, _ in outputs) == [
        "investigation request budget exhausted",
        "succeeded",
    ]
    assert case.context()["requests_remaining"] == 0
    assert len(case.receipts()) == 1


def test_budget_cannot_be_replenished_or_scope_changed(tmp_path: Path) -> None:
    case = make_case(tmp_path, max_calls=1)
    case.call("inspect_execution")
    with pytest.raises(DataError, match="budget"):
        Case.open(tmp_path / "case").call("inspect_losses")
    with pytest.raises(DataError, match="identity"):
        Case.create(
            tmp_path / "case",
            tmp_path / "1234567890abcdef",
            "2020-01-02",
            "Changed",
            "gpt-6-astra",
            1,
        )


def test_unknown_actions_never_dispatch(tmp_path: Path) -> None:
    case = make_case(tmp_path)
    with pytest.raises(DataError, match="action"):
        case.call("research approve")
    assert case.receipts() == []


def test_cache_revalidates_original_evidence(tmp_path: Path) -> None:
    case = make_case(tmp_path)
    case.call("inspect_execution")
    (tmp_path / "1234567890abcdef" / "fills.parquet").write_bytes(b"broken")
    with pytest.raises(DataError):
        case.call("inspect_execution")


@pytest.mark.parametrize("budget", [True, 0, 101, "6"])
def test_strict_budget(tmp_path: Path, budget: object) -> None:
    with pytest.raises((DataError, ValueError)):
        make_case(tmp_path, max_calls=budget)  # type: ignore[arg-type]


def test_integrity_prerequisite_and_all_outputs(tmp_path: Path) -> None:
    case = make_case(tmp_path)
    with pytest.raises(DataError, match="inspect_execution"):
        case.call("inspect_losses")
    assert not case.receipts()
    case.call("inspect_execution")
    assert case.call("inspect_losses")["result"]["macro_cause"] == "not_tested"
    assert case.call("suggest_followups")["result"]["executed_experiments"] == []
    assert case.verify()["basis_sha256"] == case.context()["basis_sha256"]


def test_failures_retained_without_retry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    case = make_case(tmp_path)
    calls = []

    def fail(*args: object, **kwargs: object) -> object:
        calls.append(1)
        raise DataError("evidence unavailable")

    monkeypatch.setattr("alpha_cli.investigation_case.suggest_investigations", fail)
    receipt = case.call("inspect_execution")
    assert receipt["status"] == "failed"
    assert "evidence unavailable" in receipt["error"]
    assert Case.open(case.path).call("inspect_execution") == receipt
    assert calls == [1]
    assert len(case.receipts()) == 1


def test_interrupted_reservation_survives_restart(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = make_case(tmp_path)

    def interrupt(*args: object, **kwargs: object) -> object:
        raise KeyboardInterrupt

    monkeypatch.setattr("alpha_cli.investigation_case.suggest_investigations", interrupt)
    with pytest.raises(KeyboardInterrupt):
        case.call("inspect_execution")
    receipt = Case.open(case.path).call("inspect_execution")
    assert receipt["status"] == "reserved"
    assert len(case.receipts()) == 1


def test_processes_share_budget_and_reservations(tmp_path: Path) -> None:
    import subprocess
    import sys

    case = make_case(tmp_path, max_calls=2)
    case.call("inspect_execution")
    program = """import sys
from pathlib import Path
from alpha_cli.investigation_case import Case
from alpha_core import DataError
try:
 print(Case.open(Path(sys.argv[1])).call(sys.argv[2])["status"])
except DataError as exc:
 print(str(exc))
"""
    processes = [
        subprocess.Popen(
            [sys.executable, "-c", program, str(case.path), action],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for action in ("inspect_losses", "suggest_followups")
    ]
    outputs = [process.communicate(timeout=30) for process in processes]
    assert all(process.returncode == 0 for process in processes), outputs
    assert sorted(out.strip() for out, _ in outputs) == [
        "investigation tool budget exhausted",
        "succeeded",
    ]
    assert len(Case.open(case.path).receipts()) == 2
    assert case.context()["calls_remaining"] == 0


def test_receipt_corruption_fails_closed(tmp_path: Path) -> None:
    import json
    import sqlite3

    case = make_case(tmp_path)
    receipt = case.call("inspect_execution")
    receipt["result"]["closed_trades"] = 999
    with sqlite3.connect(case.path / "case.sqlite3") as connection:
        connection.execute("UPDATE attempts SET receipt=?", (json.dumps(receipt),))
    with pytest.raises(DataError, match="receipt"):
        case.receipts()
