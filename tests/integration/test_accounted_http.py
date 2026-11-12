"""Actual transport retries and funding pagination over disposable accounting, no network."""

from __future__ import annotations

import io
import sqlite3
from email.message import Message
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request

import pytest

from alpha_cli._crypto_backfill import Ledger
from alpha_cli._crypto_backfill_accounting import FixtureAccountingBlocked
from alpha_cli._crypto_http_accounting import FixtureHttpAccounting
from alpha_cli._market_data_acquisition_accounting import Charge, Dimension, FixturePolicy
from alpha_data.crypto.providers._wire import fetch_bounded, http_request_hash
from alpha_data.crypto.providers.bybit import fetch_bybit_public
from alpha_data.crypto.providers.bybit_funding import collect_funding_pages

from ..unit.test_bybit_funding_pagination import END, NOW, START, page
from .test_accounted_backfill import attempt_rows, run, setup
from .test_crypto_backfill_resume_cli import environment as environment

HOST = "https://api.bybit.com/v5/"
URL = HOST + "market/test"
POLICY = FixturePolicy(
    "http_campaign", "explicit_test", (Dimension("http_attempts", "declared", 8, None, None, 1),)
)
CHARGES = (Charge("http_attempts", "declared", 1),)


def account(conn: sqlite3.Connection, **kwargs: Any) -> FixtureHttpAccounting:
    return FixtureHttpAccounting(
        connection=conn,
        scope_id="scope",
        policy=kwargs.pop("policy", POLICY),
        charges=CHARGES,
        attempt_label=kwargs.pop("attempt_label", "run1"),
        bookkeeping_clock_ms=lambda: 10,
        cancelled=kwargs.pop("cancelled", lambda: False),
        busy_timeout_ms=500,
        allowance_basis=kwargs.pop("allowance_basis", "synthetic_http_send"),
        **kwargs,
    )


def ledger(root: Path) -> Ledger:
    return Ledger.open(
        root / "progress.json",
        provider="bybit",
        family="funding",
        category="linear",
        frequency="1h",
    )


class Response:
    def __init__(self, url: str, body: bytes = b"{}") -> None:
        self.url, self.body = url, body
        self.headers = {"Content-Type": "application/json"}
        self.closed = False

    def __enter__(self) -> Response:
        return self

    def __exit__(self, *args: object) -> None:
        self.closed = True

    def geturl(self) -> str:
        return self.url

    def read(self, size: int) -> bytes:
        return self.body[:size]


def fake_open(monkeypatch: pytest.MonkeyPatch, callback: Any) -> None:
    class Opener:
        def open(self, request: Request, **kwargs: Any) -> Response:
            response = callback(request)
            assert isinstance(response, Response)
            return response

    def build(*handlers: object) -> Opener:
        from alpha_data.crypto.providers._wire import _NoBudgetRedirect

        assert len(handlers) == 1 and isinstance(handlers[0], _NoBudgetRedirect)
        return Opener()

    monkeypatch.setattr("urllib.request.build_opener", build)
    monkeypatch.setattr(
        "urllib.request.urlopen", lambda *args, **kwargs: pytest.fail("unaccounted send")
    )
    monkeypatch.setattr("time.sleep", lambda *args: None)


def fetch(hook: Any, url: str = URL, retry: bool = False) -> bytes:
    return fetch_bounded(
        url,
        provider="synthetic",
        host_prefix=HOST,
        content_types=frozenset({"application/json"}),
        max_bytes=4096,
        timeout_seconds=1,
        retry_429=retry,
        attempt_hook=hook,
    )


def test_exact_send_commit_then_close_settle_and_replay_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    conn = setup(tmp_path / "a.sqlite", POLICY)
    owner = ledger(tmp_path)
    calls = []
    response = Response(URL)

    def open_(request: Request) -> Response:
        assert not conn.in_transaction
        assert attempt_rows(conn)[0]["state"] == "intent"
        calls.append(request.full_url)
        return response

    fake_open(monkeypatch, open_)
    with owner.exclusive():
        hook = account(conn).bind(owner, http_request_hash(Request(URL)))
        assert fetch(hook) == b"{}"
        assert response.closed and attempt_rows(conn)[0]["state"] == "success"
        for label in ["run1", "run2"]:
            with pytest.raises(FixtureAccountingBlocked):
                fetch(account(conn, attempt_label=label).bind(owner))
    assert calls == [URL]
    assert conn.execute("SELECT sum(units) FROM md_acquisition_debits").fetchone()[0] == 1
    conn.close()


def test_real_429_retry_each_open_has_distinct_committed_intent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    conn = setup(tmp_path / "a.sqlite", POLICY)
    owner = ledger(tmp_path)
    sends = []
    error_body = io.BytesIO(b"too many")

    def open_(request: Request) -> Response:
        rows = attempt_rows(conn)
        assert len([r for r in rows if r["state"] == "intent"]) == 1
        sends.append(len(rows))
        if len(sends) == 1:
            raise HTTPError(URL, 429, "too many", Message(), error_body)
        return Response(URL)

    fake_open(monkeypatch, open_)
    with owner.exclusive():
        assert fetch(account(conn).bind(owner), retry=True) == b"{}"
    rows = sorted(attempt_rows(conn), key=lambda r: r["ordinal"])
    assert sends == [1, 2] and error_body.closed
    assert [(r["state"], r["reason"]) for r in rows] == [
        ("failure", "http_429"),
        ("success", "read_operation_closed"),
    ]
    assert conn.execute("SELECT sum(units) FROM md_acquisition_debits").fetchone()[0] == 2
    conn.close()


def test_actual_bybit_wrapper_and_backward_pages_are_not_one_window_charge(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    conn = setup(tmp_path / "a.sqlite", POLICY)
    owner = ledger(tmp_path)
    bodies = iter([page(END), page()])
    sends = []

    def open_(request: Request) -> Response:
        sends.append(request.full_url)
        return Response(request.full_url, next(bodies))

    fake_open(monkeypatch, open_)
    with owner.exclusive():
        hook = account(conn).bind(owner)
        result = collect_funding_pages(
            lambda params, allowance: fetch_bybit_public("funding", params, attempt_hook=hook),
            symbol="BTCUSDT",
            category="linear",
            fetched_at=NOW,
            start_ms=START,
            end_ms=END,
        )
    assert result.calls_used == 2 and len(sends) == 2 and result.coverage_complete is False
    assert len({r["request_hash"] for r in attempt_rows(conn)}) == 2
    assert conn.execute("SELECT sum(units) FROM md_acquisition_debits").fetchone()[0] == 2
    conn.close()


@pytest.mark.parametrize("failure", ["open", "read", "close", "overflow"])
def test_uncertain_operation_blocks_replay_and_never_refunds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    conn = setup(tmp_path / "a.sqlite", POLICY)
    owner = ledger(tmp_path)
    calls = []

    class Broken(Response):
        def read(self, size: int) -> bytes:
            if failure == "read":
                raise TimeoutError("SENSITIVE_CANARY")
            return b"x" * 5000 if failure == "overflow" else b"{}"

        def __exit__(self, *args: object) -> None:
            self.closed = True
            if failure == "close":
                raise OSError("SENSITIVE_CANARY")

    def open_(request: Request) -> Response:
        calls.append(1)
        if failure == "open":
            raise URLError("SENSITIVE_CANARY")
        return Broken(URL)

    fake_open(monkeypatch, open_)
    with owner.exclusive():
        for _ in range(2):
            with pytest.raises(FixtureAccountingBlocked):
                fetch(account(conn).bind(owner), retry=True)
    assert calls == [1] and attempt_rows(conn)[0]["state"] == "unknown"
    assert "SENSITIVE_CANARY" not in str(
        conn.execute("SELECT payload FROM md_acquisition_events").fetchall()
    )
    assert conn.execute("SELECT sum(units) FROM md_acquisition_debits").fetchone()[0] == 1
    conn.close()


@pytest.mark.parametrize("stage", ["before", "after_intent", "after_send"])
def test_cancellation_no_refund_or_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stage: str
) -> None:
    conn = setup(tmp_path / "a.sqlite", POLICY)
    owner = ledger(tmp_path)
    checks = []
    calls = []

    def cancelled() -> bool:
        checks.append(1)
        return len(checks) >= {"before": 1, "after_intent": 2, "after_send": 3}[stage]

    def open_(request: Request) -> Response:
        calls.append(1)
        return Response(URL)

    fake_open(monkeypatch, open_)
    with owner.exclusive(), pytest.raises(FixtureAccountingBlocked):
        fetch(account(conn, cancelled=cancelled).bind(owner))
    assert len(calls) == int(stage == "after_send")
    rows = attempt_rows(conn)
    assert not rows if stage == "before" else rows[0]["state"] == "cancelled"
    conn.close()


def test_retry_exhaustion_and_explicit_request_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    policy = FixturePolicy(
        "http_campaign", "limited", (Dimension("http_attempts", "declared", 1, None, None, 1),)
    )
    conn = setup(tmp_path / "a.sqlite", policy)
    owner = ledger(tmp_path)
    calls = []

    def open_(request: Request) -> Response:
        calls.append(1)
        raise HTTPError(URL, 429, "limited", Message(), io.BytesIO())

    fake_open(monkeypatch, open_)
    with owner.exclusive():
        hook = account(conn, policy=policy).bind(owner, http_request_hash(Request(URL)))
        with pytest.raises(FixtureAccountingBlocked):
            fetch(hook, url=URL + "changed")
        assert attempt_rows(conn) == []
        with pytest.raises(FixtureAccountingBlocked):
            fetch(hook, retry=True)
    assert calls == [1] and len(attempt_rows(conn)) == 1
    conn.close()


def test_real_orchestrator_supplies_hook_and_preserves_fatal_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    conn = setup(tmp_path / "a.sqlite", POLICY)
    calls = []

    def open_(request: Request) -> Response:
        calls.append(1)
        return Response(request.full_url, page(END))

    fake_open(monkeypatch, open_)

    def acquire(*args: Any, **kwargs: Any) -> dict[str, object]:
        fetch_bybit_public(
            "funding",
            {"symbol": "BTCUSDT", "category": "linear"},
            attempt_hook=kwargs["http_attempt_hook"],
        )
        return {"normalized_manifest_id": "a" * 64, "state": "qualified"}

    result = run(tmp_path, None, acquire, fixture_http_accounting=account(conn))
    assert result["done"] == 1 and calls == [1]
    with pytest.raises(
        FixtureAccountingBlocked, match="HTTP_COMPLETED_RESPONSE_BINDING_UNAVAILABLE"
    ):
        run(tmp_path, None, acquire, fixture_http_accounting=account(conn))
    assert calls == [1]
    conn.close()


def test_actual_native_pipeline_retains_real_bytes_but_no_http_qualification(
    environment: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from urllib.parse import parse_qs, urlsplit

    from alpha_cli import crypto_data_cmds

    from .test_crypto_backfill_resume_cli import _funding_response

    store, root, calls = environment
    conn = setup(tmp_path / "a.sqlite", POLICY)
    monkeypatch.setattr(crypto_data_cmds, "fetch_bybit_public", fetch_bybit_public)

    def open_(request: Request) -> Response:
        params = {
            key: values[0] for key, values in parse_qs(urlsplit(request.full_url).query).items()
        }
        return Response(request.full_url, _funding_response("funding", params, calls))

    fake_open(monkeypatch, open_)
    result = run(
        root, None, crypto_data_cmds._backfill_acquire, fixture_http_accounting=account(conn)
    )
    assert result["done"] == 1 and calls == ["BTCUSDT"] and len(store.inventory()) == 2
    assert attempt_rows(conn)[0]["state"] == "success"
    conn.close()


def test_opted_in_callback_cannot_ignore_missing_history_or_hook(tmp_path: Path) -> None:
    conn = setup(tmp_path / "a.sqlite", POLICY)
    with pytest.raises(FixtureAccountingBlocked, match="HTTP_HOOK_NOT_USED"):
        run(
            tmp_path,
            None,
            lambda *a, **k: {"normalized_manifest_id": "a" * 64, "state": "qualified"},
            fixture_http_accounting=account(conn),
        )
    assert not (tmp_path / "progress.json").exists() and attempt_rows(conn) == []
    conn.execute("DROP TABLE md_acquisition_events")
    with pytest.raises(FixtureAccountingBlocked, match="HTTP_SCOPE_OR_HISTORY_UNAVAILABLE"):
        run(
            tmp_path,
            None,
            lambda *a, **k: pytest.fail("no callback on missing history"),
            fixture_http_accounting=account(conn),
        )
    conn.close()


def test_request_and_window_units_cannot_share_scope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from .test_accounted_backfill import bridge

    conn = setup(tmp_path / "a.sqlite", POLICY)
    # Window adapter given the same explicit dimensions must not reinterpret HTTP history.
    owner = ledger(tmp_path)
    fake_open(monkeypatch, lambda request: Response(URL))
    with owner.exclusive():
        fetch(account(conn).bind(owner))
    with pytest.raises(FixtureAccountingBlocked, match="WINDOW_SCOPE_UNIT_MISMATCH"):
        run(
            tmp_path,
            bridge(conn, policy=POLICY, charges=CHARGES),
            lambda *a, **k: pytest.fail("unit mixing"),
        )
    assert len(attempt_rows(conn)) == 1
    conn.close()


@pytest.mark.parametrize("change", ["cancel", "history"])
def test_external_durable_change_after_intent_prevents_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    from alpha_cli._market_data_acquisition_accounting import AcquisitionTransactions

    conn = setup(tmp_path / "a.sqlite", POLICY)
    owner = ledger(tmp_path)
    checks = []
    calls = []

    def cancelled() -> bool:
        checks.append(1)
        if len(checks) == 2:
            row = attempt_rows(conn)[0]
            conn.execute("BEGIN IMMEDIATE")
            tx = AcquisitionTransactions(conn)
            if change == "cancel":
                tx.request_cancel("external_cancel", row["attempt_id"])
            else:
                tx.record_unavailable_history("external_history", "scope", "history_lost")
            conn.commit()
        return False

    def open_(request: Request) -> Response:
        calls.append(1)
        return Response(URL)

    fake_open(monkeypatch, open_)
    with owner.exclusive(), pytest.raises(FixtureAccountingBlocked):
        fetch(account(conn, cancelled=cancelled).bind(owner))
    assert calls == []
    conn.close()


@pytest.mark.parametrize("change", ["cancel", "history", "invalid_result"])
def test_after_callback_rechecks_before_progress_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    from alpha_cli._market_data_acquisition_accounting import AcquisitionTransactions

    conn = setup(tmp_path / "a.sqlite", POLICY)
    cancelled = [False]
    fake_open(monkeypatch, lambda request: Response(URL))

    def acquire(*args: Any, **kwargs: Any) -> dict[str, object]:
        fetch(kwargs["http_attempt_hook"])
        if change == "cancel":
            cancelled[0] = True
        if change == "history":
            conn.execute("BEGIN IMMEDIATE")
            AcquisitionTransactions(conn).record_unavailable_history(
                "lost", "scope", "lost_after_read"
            )
            conn.commit()
        return {
            "normalized_manifest_id": "invalid" if change == "invalid_result" else "a" * 64,
            "state": "qualified",
        }

    with pytest.raises(FixtureAccountingBlocked):
        run(
            tmp_path,
            None,
            acquire,
            fixture_http_accounting=account(conn, cancelled=lambda: cancelled[0]),
        )
    assert not (tmp_path / "progress.json").exists()
    assert attempt_rows(conn)[0]["state"] == "success"
    conn.close()


@pytest.mark.parametrize("commit_number", [1, 2, 3])
def test_http_commit_ack_uncertainty_has_no_second_send(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, commit_number: int
) -> None:
    from .test_accounted_backfill_process import LostAck, connect

    path = tmp_path / "a.sqlite"
    setup(path, POLICY).close()
    conn = connect(str(path), LostAck)
    assert isinstance(conn, LostAck)
    conn.fail_on = commit_number
    owner = ledger(tmp_path)
    calls = []

    def open_(request: Request) -> Response:
        calls.append(1)
        return Response(URL)

    fake_open(monkeypatch, open_)
    with owner.exclusive():
        with pytest.raises(FixtureAccountingBlocked):
            fetch(account(conn).bind(owner))
        with pytest.raises(FixtureAccountingBlocked):
            fetch(account(conn, attempt_label="newlabel").bind(owner))
    assert len(calls) == int(commit_number == 3)
    assert len(attempt_rows(conn)) == 1
    assert conn.execute("SELECT sum(units) FROM md_acquisition_debits").fetchone()[0] == 1
    conn.close()


def test_hook_rejects_body_and_actual_redirect_handler_blocks_followups(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from alpha_core import DataError

    conn = setup(tmp_path / "a.sqlite", POLICY)
    owner = ledger(tmp_path)
    with owner.exclusive():
        hook = account(conn).bind(owner)
        with pytest.raises(DataError, match="body-free GET"):
            fetch_bounded(
                Request(URL, data=b"x"),
                provider="synthetic",
                host_prefix=HOST,
                content_types=frozenset({"application/json"}),
                max_bytes=20,
                timeout_seconds=1,
                attempt_hook=hook,
            )
    assert attempt_rows(conn) == []
    conn.close()
