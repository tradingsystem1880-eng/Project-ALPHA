"""Owned-process, temporary-ledger cooperation tests; all callbacks are synthetic."""

from __future__ import annotations

import json
import multiprocessing
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest

from alpha_cli._crypto_backfill import Ledger, run_backfill
from alpha_core import DataError


def _open(path: str) -> Ledger:
    return Ledger.open(
        Path(path), provider="bybit", family="funding", category="linear", frequency="1h"
    )


def _run(path: str, symbol: str, acquire: Any, **kwargs: Any) -> dict[str, object]:
    return run_backfill(
        provider="bybit",
        family="funding",
        symbols=[symbol],
        quote="USDT",
        category="linear",
        frequency="1h",
        start=date(2024, 1, 1),
        end=date(2024, 2, 1),
        ledger_path=Path(path),
        now=datetime(2026, 9, 10, tzinfo=UTC),
        pause_seconds=0,
        acquire=acquire,
        verify_completed=lambda *a: None,
        **kwargs,
    )


def _owner(path: str, pipe: Any, release: Any) -> None:
    def acquire(*args: Any, **kwargs: Any) -> dict[str, object]:
        pipe.send("in_callback")
        if not release.wait(15):
            raise RuntimeError("fixture owner release timeout")
        return {"normalized_manifest_id": "synthetic_first", "state": "qualified"}

    try:
        _run(path, "BTCUSDT", acquire)
        pipe.send("done")
    finally:
        pipe.close()


def _contender(path: str, pipe: Any) -> None:
    def acquire(*args: Any, **kwargs: Any) -> dict[str, object]:
        pipe.send("UNEXPECTED_CALLBACK")
        return {"normalized_manifest_id": "bad", "state": "qualified"}

    try:
        _run(path, "ETHUSDT", acquire)
        pipe.send("UNEXPECTED_SUCCESS")
    except DataError as exc:
        pipe.send("owned" if "already owned" in str(exc) else "other_error")
    finally:
        pipe.close()


def _stale(path: str, pipe: Any, write: Any) -> None:
    ledger = _open(path)
    pipe.send("loaded")
    if not write.wait(15):
        raise RuntimeError("fixture stale writer timeout")
    try:
        ledger.record("stale", {"state": "failed"})
        pipe.send("UNEXPECTED_SUCCESS")
    except DataError as exc:
        pipe.send("stale" if "stale" in str(exc) else "other_error")
    finally:
        pipe.close()


def _forked_mutator(ledger: Ledger, pipe: Any) -> None:
    try:
        ledger.record("inherited", {"state": "failed"})
        pipe.send("UNEXPECTED_SUCCESS")
    except DataError as exc:
        pipe.send("refused" if "transferable" in str(exc) else "other_error")
    finally:
        pipe.close()


def _stop(process: Any) -> None:
    if process.is_alive():
        process.kill()
    process.join(10)
    assert not process.is_alive()


def test_competing_windows_refuse_then_reopen_without_lost_updates(
    tmp_path: Path,
    owned_test_process: None,
) -> None:
    path = str(tmp_path / "progress.json")
    ctx = multiprocessing.get_context("spawn")
    owner_read, owner_write = ctx.Pipe(duplex=False)
    contender_read, contender_write = ctx.Pipe(duplex=False)
    release = ctx.Event()
    first = ctx.Process(target=_owner, args=(path, owner_write, release))
    other = ctx.Process(target=_contender, args=(path, contender_write))
    try:
        first.start()
        assert owner_read.poll(10) and owner_read.recv() == "in_callback"
        other.start()
        assert contender_read.poll(5) and contender_read.recv() == "owned"
        other.join(5)
        assert other.exitcode == 0
        release.set()
        assert owner_read.poll(10) and owner_read.recv() == "done"
        first.join(5)
        assert first.exitcode == 0
        result = _run(
            path,
            "ETHUSDT",
            lambda *a, **k: {"normalized_manifest_id": "synthetic_second", "state": "qualified"},
        )
        assert result["done"] == 1
        retained = json.loads(Path(path).read_bytes())["windows"]
        assert len(retained) == 2
        assert {entry["manifest_id"] for entry in retained.values()} == {
            "synthetic_first",
            "synthetic_second",
        }
    finally:
        release.set()
        for child in (first, other):
            if child.pid is not None:
                _stop(child)
        for stream in (owner_read, owner_write, contender_read, contender_write):
            stream.close()


def test_process_stale_reader_refuses_and_fresh_reopen_preserves_both(
    tmp_path: Path, owned_test_process: None
) -> None:
    path = str(tmp_path / "progress.json")
    ctx = multiprocessing.get_context("spawn")
    read, write_pipe = ctx.Pipe(duplex=False)
    write = ctx.Event()
    child = ctx.Process(target=_stale, args=(path, write_pipe, write))
    try:
        child.start()
        assert read.poll(10) and read.recv() == "loaded"
        _open(path).record("first", {"state": "failed"})
        write.set()
        assert read.poll(10) and read.recv() == "stale"
        child.join(5)
        assert child.exitcode == 0
        _open(path).record("second", {"state": "failed"})
        assert set(json.loads(Path(path).read_bytes())["windows"]) == {"first", "second"}
    finally:
        write.set()
        if child.pid is not None:
            _stop(child)
        read.close()
        write_pipe.close()


def test_killed_owner_releases_kernel_lock_for_reopen(
    tmp_path: Path, owned_test_process: None
) -> None:
    path = str(tmp_path / "progress.json")
    ctx = multiprocessing.get_context("spawn")
    read, write = ctx.Pipe(duplex=False)
    release = ctx.Event()
    child = ctx.Process(target=_owner, args=(path, write, release))
    try:
        child.start()
        assert read.poll(10) and read.recv() == "in_callback"
        _stop(child)
        assert not Path(path).exists()  # no synthetic callback result was published
        assert Path(path + ".lock").is_file()
        _run(
            path,
            "BTCUSDT",
            lambda *a, **k: {"normalized_manifest_id": "after_kill", "state": "qualified"},
        )
        assert len(json.loads(Path(path).read_bytes())["windows"]) == 1
    finally:
        if child.pid is not None:
            _stop(child)
        read.close()
        write.close()


def test_fork_does_not_transfer_mutation_or_unlock_parent(
    tmp_path: Path, owned_test_process: None
) -> None:
    path = str(tmp_path / "progress.json")
    ctx = multiprocessing.get_context("fork")
    read, write = ctx.Pipe(duplex=False)
    ledger = _open(path)
    with ledger.exclusive():
        child = ctx.Process(target=_forked_mutator, args=(ledger, write))
        try:
            child.start()
            assert read.poll(5) and read.recv() == "refused"
            child.join(5)
            assert child.exitcode == 0
            with pytest.raises(DataError, match="owned"):
                _open(path).record("other", {"state": "failed"})
            ledger.record("parent", {"state": "failed"})
        finally:
            if child.pid is not None:
                _stop(child)
            read.close()
            write.close()
    assert set(json.loads(Path(path).read_bytes())["windows"]) == {"parent"}


@pytest.mark.parametrize("stage", ["acquire", "preflight"])
def test_cancel_releases_run_ownership_without_rewriting_progress(
    tmp_path: Path, stage: str
) -> None:
    path = str(tmp_path / "progress.json")
    if stage == "preflight":
        _run(
            path,
            "BTCUSDT",
            lambda *a, **k: {"normalized_manifest_id": "retained", "state": "qualified"},
        )
    before = Path(path).read_bytes() if Path(path).exists() else None

    def cancel(*args: Any, **kwargs: Any) -> Any:
        raise KeyboardInterrupt

    if stage == "acquire":
        with pytest.raises(KeyboardInterrupt):
            _run(path, "BTCUSDT", cancel)
    else:
        with pytest.raises(KeyboardInterrupt):
            run_backfill(
                provider="bybit",
                family="funding",
                symbols=["BTCUSDT"],
                quote="USDT",
                category="linear",
                frequency="1h",
                start=date(2024, 1, 1),
                end=date(2024, 2, 1),
                ledger_path=Path(path),
                acquire=cancel,
                now=datetime(2026, 9, 10, tzinfo=UTC),
                pause_seconds=0,
                verify_completed=cancel,
            )
    assert (Path(path).read_bytes() if Path(path).exists() else None) == before
    _open(path).record("after_cancel", {"state": "failed"})


def test_dry_run_does_not_contend_with_owner_or_create_sidecars(tmp_path: Path) -> None:
    path = str(tmp_path / "progress.json")
    fresh = tmp_path / "missing" / "progress.json"

    def fail(*args: Any, **kwargs: Any) -> Any:
        pytest.fail("dry-run must not acquire")

    _run(str(fresh), "BTCUSDT", fail, dry_run=True)
    assert not fresh.parent.exists()
    with _open(path).exclusive():
        before = list(tmp_path.iterdir())
        assert _run(path, "BTCUSDT", fail, dry_run=True)["dry_run"] is True
        assert list(tmp_path.iterdir()) == before
