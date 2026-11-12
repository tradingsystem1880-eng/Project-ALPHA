"""Strict complete-body evidence at the real acquisition boundary; replay remains blocked."""

from __future__ import annotations

import io
import multiprocessing
from email.message import Message
from pathlib import Path
from typing import Any
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request

import pytest

from alpha_cli import crypto_data_cmds
from alpha_cli._crypto_backfill_accounting import FixtureAccountingBlocked
from alpha_data.crypto.providers._wire import CompleteHttpResponse, fetch_bounded
from alpha_data.crypto.providers.bybit import fetch_bybit_public

from ..unit.test_crypto_http_response_evidence import Response
from .test_accounted_backfill import attempt_rows, run, setup
from .test_accounted_backfill_process import connect
from .test_accounted_http import HOST, POLICY, URL, account, ledger
from .test_crypto_backfill_resume_cli import _funding_response
from .test_crypto_backfill_resume_cli import environment as environment


def test_native_path_complete_evidence_precedes_settlement_and_completed_replay_stays_blocked(
    environment: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, root, calls = environment
    conn = setup(tmp_path / "a.sqlite", POLICY)
    evidence: list[CompleteHttpResponse] = []

    class Opener:
        def open(self, request: Request, **kwargs: Any) -> Response:
            params = {k: v[0] for k, v in parse_qs(urlsplit(request.full_url).query).items()}
            body = _funding_response("funding", params, calls)
            response = Response(body, length=str(len(body)))
            response.url = request.full_url
            return response

    monkeypatch.setattr("urllib.request.build_opener", lambda *a: Opener())
    monkeypatch.setattr(
        "urllib.request.urlopen", lambda *a, **k: pytest.fail("no unaccounted opener")
    )
    monkeypatch.setattr(crypto_data_cmds, "fetch_bybit_public", fetch_bybit_public)

    def observe(item: CompleteHttpResponse) -> None:
        assert not conn.in_transaction and attempt_rows(conn)[0]["state"] == "intent"
        evidence.append(item)

    result = run(
        root,
        None,
        crypto_data_cmds._backfill_acquire,
        fixture_http_accounting=account(conn),
        fixture_http_response_evidence=observe,
    )
    assert result["done"] == 1 and len(evidence) == 1 and calls == ["BTCUSDT"]
    rows = attempt_rows(conn)
    assert rows[0]["state"] == "success" and rows[0]["reason"] == "read_operation_closed"
    manifests = store.inventory()
    assert len(manifests) == 2
    assert any(
        store.verify_manifest(m["manifest_id"])["artifact_sha256"] == evidence[0].body_sha256
        for m in manifests
    )
    conn.close()
    conn = connect(str(tmp_path / "a.sqlite"))
    with pytest.raises(
        FixtureAccountingBlocked, match="HTTP_COMPLETED_RESPONSE_BINDING_UNAVAILABLE"
    ):
        run(
            root,
            None,
            crypto_data_cmds._backfill_acquire,
            fixture_http_accounting=account(conn),
            fixture_http_response_evidence=evidence.append,
        )
    assert calls == ["BTCUSDT"] and len(evidence) == 1
    assert conn.execute("SELECT sum(units) FROM md_acquisition_debits").fetchone()[0] == 1
    conn.close()


@pytest.mark.parametrize("failure", ["truncated", "observer_failure"])
def test_accounted_incomplete_or_unretained_evidence_is_unknown_never_done(
    environment: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    store, root, calls = environment
    conn = setup(tmp_path / "a.sqlite", POLICY)
    observed: list[CompleteHttpResponse] = []

    class Opener:
        def open(self, request: Request, **kwargs: Any) -> Response:
            response = Response(b"{}", length="3" if failure == "truncated" else "2")
            response.url = request.full_url
            return response

    monkeypatch.setattr("urllib.request.build_opener", lambda *a: Opener())
    monkeypatch.setattr(crypto_data_cmds, "fetch_bybit_public", fetch_bybit_public)

    def observe(item: CompleteHttpResponse) -> None:
        observed.append(item)
        raise OSError("synthetic publication failure")

    with pytest.raises(FixtureAccountingBlocked):
        run(
            root,
            None,
            crypto_data_cmds._backfill_acquire,
            fixture_http_accounting=account(conn),
            fixture_http_response_evidence=observe,
        )
    assert attempt_rows(conn)[0]["state"] == "unknown" and not (root / "progress.json").exists()
    assert len(observed) == int(failure == "observer_failure") and not store.inventory()
    conn.close()


def reopen_worker(path: str, root: str, out: Any) -> None:
    class NoSend:
        def open(self, *args: object, **kwargs: object) -> Response:
            pytest.fail("no replay network")

    conn = connect(path)
    owner = ledger(Path(root))
    observed: list[CompleteHttpResponse] = []
    try:
        with (
            owner.exclusive(),
            patch("urllib.request.build_opener", lambda *a: NoSend()),
        ):
            fetch_bounded(
                URL,
                provider="synthetic",
                host_prefix=HOST,
                content_types=frozenset({"application/json"}),
                max_bytes=1024,
                timeout_seconds=1,
                retry_429=True,
                attempt_hook=account(conn).bind(owner),
                response_evidence=observed.append,
            )
        out.put("unexpected_success")
    except FixtureAccountingBlocked:
        out.put(("blocked", len(observed)))
    finally:
        conn.close()


@pytest.mark.usefixtures("owned_test_process")
def test_429_unbound_response_cannot_be_promoted_to_fresh_process_replay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    conn = setup(tmp_path / "a.sqlite", POLICY)
    owner = ledger(tmp_path)
    sends = []
    observed: list[CompleteHttpResponse] = []
    error_body = io.BytesIO(b"429 body not retained")

    class Opener:
        def open(self, request: Request, **kwargs: Any) -> Response:
            sends.append(1)
            if len(sends) == 1:
                raise HTTPError(URL, 429, "rate", Message(), error_body)
            response = Response()
            response.url = URL
            return response

    monkeypatch.setattr("urllib.request.build_opener", lambda *a: Opener())
    monkeypatch.setattr("time.sleep", lambda *a: None)
    with owner.exclusive():
        assert (
            fetch_bounded(
                URL,
                provider="synthetic",
                host_prefix=HOST,
                content_types=frozenset({"application/json"}),
                max_bytes=1024,
                timeout_seconds=1,
                retry_429=True,
                attempt_hook=account(conn).bind(owner),
                response_evidence=observed.append,
            )
            == b"{}"
        )
    assert sends == [1, 1] and len(observed) == 1 and error_body.closed
    assert {r["state"] for r in attempt_rows(conn)} == {"success", "failure"}
    ctx = multiprocessing.get_context("spawn")
    out = ctx.Queue()
    child = ctx.Process(target=reopen_worker, args=(str(tmp_path / "a.sqlite"), str(tmp_path), out))
    try:
        child.start()
        assert out.get(timeout=10) == ("blocked", 0)
        child.join(5)
        assert child.exitcode == 0
    finally:
        if child.is_alive():
            child.kill()
        child.join(5)
    assert (
        len(attempt_rows(conn)) == 2
        and conn.execute("SELECT sum(units) FROM md_acquisition_debits").fetchone()[0] == 2
    )
    conn.close()
