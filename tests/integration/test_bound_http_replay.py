"""Actual native acquisition → immutable bindings → fresh-process resume, synthetic only."""

from __future__ import annotations

import io
import json
import multiprocessing
import sqlite3
from collections.abc import Iterator
from datetime import UTC, date, datetime
from email.message import Message
from pathlib import Path
from typing import Any
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request

import pytest

from alpha_cli import crypto_data_cmds
from alpha_cli._crypto_acquisition import bybit_plan
from alpha_cli._crypto_backfill import Ledger, run_backfill
from alpha_cli._crypto_backfill_accounting import FixtureAccountingBlocked
from alpha_cli._crypto_backfill_evidence import verify_completed_window
from alpha_cli._crypto_http_replay import _KIND, FixtureBoundHttpAccounting, _digest
from alpha_cli._market_data_acquisition_accounting import AcquisitionTransactions
from alpha_core import DataError
from alpha_data.crypto.providers.bybit import fetch_bybit_public
from alpha_data.crypto.storage import Capacity, CryptoBulkStore
from alpha_data.crypto.verification import ArtifactVerificationBudget, MetadataVerificationBudget

from ..unit.test_crypto_http_response_evidence import Response
from .test_accounted_backfill import attempt_rows, setup
from .test_accounted_backfill_process import connect
from .test_accounted_http import CHARGES, POLICY

NOW = datetime(2026, 9, 10, tzinfo=UTC)
START = "2024-01-01T00:00:00Z"
END = "2024-01-02T00:00:00Z"


def store_at(root: Path) -> CryptoBulkStore:
    return CryptoBulkStore(
        bulk_root=root / "bulk",
        manifest_root=root / "manifests",
        expected_volume_uuid="SYNTHETIC",
        volume_uuid=lambda _: "SYNTHETIC",
        capacity=lambda _: Capacity(2_000_000_000_000, 1_500_000_000_000),
    )


def bound(
    conn: sqlite3.Connection, store: CryptoBulkStore, **kwargs: Any
) -> FixtureBoundHttpAccounting:
    dataset = bybit_plan(
        "open_interest",
        "BTCUSDT",
        base="BTC",
        quote="USDT",
        category="linear",
        frequency="1h",
        start=START,
        end=END,
        fetched_at=NOW,
    ).dataset
    return FixtureBoundHttpAccounting(
        connection=conn,
        scope_id="scope",
        policy=kwargs.pop("policy", POLICY),
        charges=CHARGES,
        attempt_label="run1",
        bookkeeping_clock_ms=lambda: 10,
        cancelled=kwargs.pop("cancelled", lambda: False),
        busy_timeout_ms=500,
        allowance_basis="synthetic_http_send",
        store=store,
        dataset=dataset,
        fetched_at=NOW,
        retry_429=True,
        hash_byte_limit=100_000_000,
        metadata_byte_limit=32 * 1024 * 1024,
        **kwargs,
    )


def run(
    root: Path,
    account: FixtureBoundHttpAccounting,
    acquire: Any = crypto_data_cmds._backfill_acquire,
) -> dict[str, object]:
    def verify(symbol: str, window: Any, entry: Any) -> None:
        verify_completed_window(
            account.store,
            symbol,
            window,
            entry,
            provider="bybit",
            family="open_interest",
            category="linear",
            frequency="1h",
            quote="USDT",
            now=NOW,
        )

    return run_backfill(
        provider="bybit",
        family="open_interest",
        symbols=["BTCUSDT"],
        quote="USDT",
        category="linear",
        frequency="1h",
        start=date(2024, 1, 1),
        end=date(2024, 1, 2),
        ledger_path=root / "progress.json",
        acquire=acquire,
        now=NOW,
        pause_seconds=0,
        verify_completed=verify,
        fixture_http_accounting=account,
    )


def native(store: CryptoBulkStore, sends: list[str], *, rate_limit: bool = True) -> Any:
    class Opener:
        def open(self, request: Request, **kwargs: Any) -> Response:
            sends.append(request.full_url)
            if rate_limit and len(sends) == 1:
                body = b'{"retCode":10006}'
                headers = Message()
                headers["Content-Length"] = str(len(body))
                headers["Content-Type"] = "application/json"
                raise HTTPError(request.full_url, 429, "synthetic rate", headers, io.BytesIO(body))
            params = parse_qs(urlsplit(request.full_url).query)
            second = "cursor" in params
            raw = json.dumps(
                {
                    "retCode": 0,
                    "result": {
                        "category": "linear",
                        "symbol": "BTCUSDT",
                        "list": [
                            {
                                "timestamp": str(1704067200000 + (7200000 if second else 3600000)),
                                "openInterest": "100",
                            }
                        ],
                        "nextPageCursor": "" if second else "next",
                    },
                }
            ).encode()
            response = Response(raw, length=str(len(raw)))
            response.url = request.full_url
            return response

    from contextlib import ExitStack

    stack = ExitStack()
    stack.enter_context(patch.object(crypto_data_cmds, "_bulk_store", lambda: store))
    stack.enter_context(patch.object(crypto_data_cmds, "_now", lambda: NOW))
    stack.enter_context(patch.object(crypto_data_cmds, "fetch_bybit_public", fetch_bybit_public))
    stack.enter_context(patch("urllib.request.build_opener", lambda *a: Opener()))
    stack.enter_context(
        patch("urllib.request.urlopen", lambda *a, **k: pytest.fail("no direct network"))
    )
    stack.enter_context(patch("time.sleep", lambda *a: None))
    return stack


@pytest.fixture
def work(tmp_path: Path) -> Iterator[tuple[sqlite3.Connection, CryptoBulkStore, list[str]]]:
    (tmp_path / "bulk").mkdir()
    conn = setup(tmp_path / "account.sqlite", POLICY)
    store = store_at(tmp_path)
    sends: list[str] = []
    yield conn, store, sends
    conn.close()


def events(conn: sqlite3.Connection) -> tuple[int, int, int]:
    return tuple(
        conn.execute(sql).fetchone()[0]
        for sql in [
            "SELECT count(*) FROM md_acquisition_events",
            "SELECT count(*) FROM md_acquisition_attempts",
            "SELECT sum(units) FROM md_acquisition_debits",
        ]
    )


def replay_worker(root: str, out: Any) -> None:
    path = Path(root)
    conn = connect(str(path / "account.sqlite"))
    store = store_at(path)
    try:
        before = events(conn)
        with patch(
            "urllib.request.build_opener",
            lambda *a: pytest.fail("completed resume must not build transport"),
        ):
            result = run(
                path,
                bound(conn, store),
                lambda *a, **k: pytest.fail("completed resume must not acquire"),
            )
        out.put({"result": result, "before": before, "after": events(conn)})
    except BaseException as error:
        out.put({"error": type(error).__name__ + ":" + str(error)})
    finally:
        conn.close()


@pytest.mark.usefixtures("owned_test_process")
def test_native_two_pages_429_then_fresh_process_verified_resume_zero_opens_or_charges(
    work: Any, tmp_path: Path
) -> None:
    conn, store, sends = work
    with native(store, sends):
        first = run(tmp_path, bound(conn, store))
    assert first["done"] == 1 and len(sends) == 3
    rows = attempt_rows(conn)
    assert sorted(r["reason"][:4] for r in rows) == ["b200", "b429", "w200"]
    entry = next(iter(json.loads((tmp_path / "progress.json").read_text())["windows"].values()))
    root = entry["http_replay_manifest_id"]
    assert any(r["reason"] == "w200_" + root for r in rows)
    before = (tmp_path / "progress.json").read_bytes()
    usage = events(conn)
    ctx = multiprocessing.get_context("spawn")
    out = ctx.Queue()
    child = ctx.Process(target=replay_worker, args=(str(tmp_path), out))
    try:
        child.start()
        reply = out.get(timeout=15)
        child.join(5)
        assert child.exitcode == 0 and "error" not in reply, reply
        assert reply["result"]["skipped"] == reply["result"]["verified_completed"] == 1
        assert reply["before"] == reply["after"] == usage
    finally:
        if child.is_alive():
            child.kill()
        child.join(5)
    assert (tmp_path / "progress.json").read_bytes() == before and len(sends) == 3


@pytest.mark.parametrize(
    "change",
    ["raw_truncate", "metadata_tamper", "missing_response", "ledger_output", "legacy_completion"],
)
def test_missing_tampered_or_unbound_evidence_cannot_resume(
    work: Any, tmp_path: Path, change: str
) -> None:
    conn, store, sends = work
    with native(store, sends):
        run(tmp_path, bound(conn, store))
    usage = events(conn)
    raw = next(
        m
        for m in store.inventory()
        if m.get("receipt", {}).get("provider_schema") == "alpha-http-response-binding-v1"
    )
    if change == "raw_truncate":
        (store.bulk_root / raw["artifact_key"]).write_bytes(b"")
    elif change == "missing_response":
        (store.manifest_root / (raw["manifest_id"] + ".json")).unlink()
    elif change == "metadata_tamper":
        raw["receipt"]["request"][0][1] = "tampered"
        (store.manifest_root / (raw["manifest_id"] + ".json")).write_text(json.dumps(raw))
    else:
        path = tmp_path / "progress.json"
        body = json.loads(path.read_text())
        entry = next(iter(body["windows"].values()))
        if change == "ledger_output":
            entry["manifest_id"] = "f" * 64
        else:
            entry.pop("http_replay_manifest_id")
        path.write_text(json.dumps(body))
    with native(store, sends), pytest.raises((FixtureAccountingBlocked, DataError)):
        run(tmp_path, bound(conn, store), lambda *a, **k: pytest.fail("no redispatch"))
    assert len(sends) == 3 and events(conn) == usage


@pytest.mark.parametrize("change", ["reorder", "omit429"])
def test_forged_reordered_or_partial_root_has_no_durable_accounting_anchor(
    work: Any, tmp_path: Path, change: str
) -> None:
    conn, store, sends = work
    with native(store, sends):
        run(tmp_path, bound(conn, store))
    account = bound(conn, store)
    body = json.loads((tmp_path / "progress.json").read_text())
    entry = next(iter(body["windows"].values()))
    data = account._root(
        entry["http_replay_manifest_id"],
        ArtifactVerificationBudget(100_000_000),
        MetadataVerificationBudget(32 * 1024 * 1024),
    )
    if change == "reorder":
        data["attempts"].reverse()
    else:
        data["attempts"] = data["attempts"][1:]
    import polars as pl

    payload = io.BytesIO()
    pl.DataFrame(
        {"binding_json": [json.dumps(data, sort_keys=True, separators=(",", ":"))]}
    ).write_parquet(payload)
    forged = store.publish_derived(
        payload.getvalue(),
        derived_kind=_KIND,
        input_manifest_ids=(data["normalized"],),
        metadata={
            "binding_schema": _KIND,
            "window_sha256": _digest(data["window"]),
            "binding_sha256": _digest(data),
        },
    )
    entry["http_replay_manifest_id"] = forged["manifest_id"]
    (tmp_path / "progress.json").write_text(json.dumps(body))
    usage = events(conn)
    with pytest.raises(FixtureAccountingBlocked):
        run(tmp_path, account, lambda *a, **k: pytest.fail("no acquire"))
    assert events(conn) == usage and len(sends) == 3


@pytest.mark.parametrize("phase", ["before_derived", "after_derived", "after_anchor"])
def test_publication_gaps_never_redispatch_and_only_committed_anchor_recovers(
    work: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, phase: str
) -> None:
    conn, store, sends = work
    publish = store.publish_derived
    record = Ledger.record

    def broken_publish(*args: Any, **kwargs: Any) -> dict[str, object]:
        if phase == "before_derived":
            raise OSError("synthetic before publication")
        result = publish(*args, **kwargs)
        if phase == "after_derived":
            raise OSError("synthetic after publication")
        assert isinstance(result, dict)
        return result

    def broken_record(self: Ledger, key: str, entry: dict[str, Any]) -> None:
        if phase == "after_anchor" and entry["state"] == "done":
            raise OSError("synthetic after anchor")
        record(self, key, entry)

    with monkeypatch.context() as patcher:
        patcher.setattr(store, "publish_derived", broken_publish)
        patcher.setattr(Ledger, "record", broken_record)
        with native(store, sends), pytest.raises((FixtureAccountingBlocked, OSError)):
            run(tmp_path, bound(conn, store))
    count = len(sends)
    usage = events(conn)
    with native(store, sends):
        if phase == "after_anchor":
            assert run(tmp_path, bound(conn, store))["done"] == 1
        else:
            with pytest.raises(FixtureAccountingBlocked):
                run(tmp_path, bound(conn, store))
    assert len(sends) == count and events(conn) == usage


def test_prior_response_tamper_stops_before_next_open_or_debit(
    work: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    conn, store, sends = work

    def tamper_after_return(endpoint: str, params: dict[str, Any], **kwargs: Any) -> bytes:
        body = fetch_bybit_public(endpoint, params, **kwargs)
        if "cursor" not in params:
            raw = next(
                m
                for m in store.inventory()
                if m.get("receipt", {}).get("provider_schema") == "alpha-http-response-binding-v1"
                and dict(m["receipt"]["request"])["status"] == "200"
            )
            (store.bulk_root / raw["artifact_key"]).write_bytes(b"tampered")
        return body

    with (
        native(store, sends),
        patch.object(crypto_data_cmds, "fetch_bybit_public", tamper_after_return),
        pytest.raises(FixtureAccountingBlocked),
    ):
        run(tmp_path, bound(conn, store))
    assert len(sends) == 2 and len(attempt_rows(conn)) == 2


def test_oversized_compressed_binding_rejected_before_polars_decode(
    work: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import polars as pl

    conn, store, sends = work
    with native(store, sends):
        run(tmp_path, bound(conn, store))
    entry = next(iter(json.loads((tmp_path / "progress.json").read_text())["windows"].values()))
    payload = io.BytesIO()
    pl.DataFrame({"binding_json": ["x" * (512 * 1024)]}).write_parquet(payload)
    assert len(payload.getvalue()) < 1024 * 1024
    forged = store.publish_derived(
        payload.getvalue(),
        derived_kind=_KIND,
        input_manifest_ids=(entry["manifest_id"],),
        metadata={},
    )
    monkeypatch.setattr(
        pl, "read_parquet", lambda *a, **k: pytest.fail("must reject metadata before decode")
    )
    with pytest.raises(FixtureAccountingBlocked):
        bound(conn, store)._root(
            forged["manifest_id"],
            ArtifactVerificationBudget(100_000_000),
            MetadataVerificationBudget(32 * 1024 * 1024),
        )


@pytest.mark.parametrize("phase", ["before", "after429", "after200"])
def test_cancelled_partial_window_never_refunds_reopens_or_claims_complete(
    work: Any, tmp_path: Path, phase: str
) -> None:
    conn, store, sends = work
    flag = [phase == "before"]

    def after_body(endpoint: str, params: dict[str, Any], **kwargs: Any) -> bytes:
        body = fetch_bybit_public(endpoint, params, **kwargs)
        if phase == "after200":
            flag[0] = True
        return body

    with (
        native(store, sends),
        patch.object(crypto_data_cmds, "fetch_bybit_public", after_body),
        patch("time.sleep", lambda *a: flag.__setitem__(0, phase == "after429")),
        pytest.raises(FixtureAccountingBlocked),
    ):
        run(tmp_path, bound(conn, store, cancelled=lambda: flag[0]))
    assert len(sends) == {"before": 0, "after429": 1, "after200": 2}[phase]
    assert not (tmp_path / "progress.json").exists()
    if phase != "before":
        usage = events(conn)
        flag[0] = False
        with native(store, sends), pytest.raises(FixtureAccountingBlocked):
            run(tmp_path, bound(conn, store))
        assert events(conn) == usage


def test_unavailable_history_remains_blocked_even_with_committed_valid_root(
    work: Any, tmp_path: Path
) -> None:
    conn, store, sends = work
    with native(store, sends):
        run(tmp_path, bound(conn, store))
    conn.execute("BEGIN IMMEDIATE")
    AcquisitionTransactions(conn).record_unavailable_history(
        "lost_history", "scope", "later_history_unavailable"
    )
    conn.commit()
    usage = events(conn)
    with native(store, sends), pytest.raises(FixtureAccountingBlocked):
        run(tmp_path, bound(conn, store))
    assert len(sends) == 3 and events(conn) == usage


def test_legacy_unbound_accounting_is_not_reconstructed_as_zero_or_upgraded(
    work: Any, tmp_path: Path
) -> None:
    from .test_accounted_http import account as plain_account

    conn, store, sends = work
    with native(store, sends, rate_limit=False):
        result = run_backfill(
            provider="bybit",
            family="open_interest",
            symbols=["BTCUSDT"],
            quote="USDT",
            category="linear",
            frequency="1h",
            start=date(2024, 1, 1),
            end=date(2024, 1, 2),
            ledger_path=tmp_path / "legacy.json",
            acquire=crypto_data_cmds._backfill_acquire,
            now=NOW,
            pause_seconds=0,
            fixture_http_accounting=plain_account(conn),
        )
    assert result["done"] == 1 and len(sends) == 2
    usage = events(conn)
    with native(store, sends), pytest.raises(FixtureAccountingBlocked, match="BOUND_LEGACY"):
        run(tmp_path, bound(conn, store))
    assert len(sends) == 2 and events(conn) == usage and not (tmp_path / "progress.json").exists()


def test_unsupported_429_framing_is_charged_unknown_and_never_complete(
    work: Any, tmp_path: Path
) -> None:
    conn, store, sends = work
    body = io.BytesIO(b"not framed")

    class Opener:
        def open(self, request: Request, **kwargs: Any) -> Response:
            sends.append(request.full_url)
            raise HTTPError(request.full_url, 429, "synthetic", Message(), body)

    with (
        native(store, sends),
        patch("urllib.request.build_opener", lambda *a: Opener()),
        pytest.raises(FixtureAccountingBlocked),
    ):
        run(tmp_path, bound(conn, store))
    assert len(sends) == 1 and body.closed and attempt_rows(conn)[0]["state"] == "unknown"
    assert not store.inventory() and not (tmp_path / "progress.json").exists()
