from __future__ import annotations

import json
from pathlib import Path

import pytest

from alpha_cli._crypto_backfill import Ledger
from alpha_core import DataError


def _open(path: Path) -> Ledger:
    return Ledger.open(path, provider="bybit", family="funding", category="linear", frequency="1h")


def test_stale_writer_cannot_discard_another_window(tmp_path: Path) -> None:
    path = tmp_path / "progress.json"
    stale, first = _open(path), _open(path)
    first.record("first", {"state": "failed"})
    before = path.read_bytes()
    with pytest.raises(DataError, match="stale"):
        stale.record("second", {"state": "failed"})
    assert path.read_bytes() == before
    fresh = _open(path)
    fresh.record("second", {"state": "failed"})
    assert set(json.loads(path.read_bytes())["windows"]) == {"first", "second"}


def test_exclusive_reload_and_nested_save_do_not_unlock(tmp_path: Path) -> None:
    path = tmp_path / "progress.json"
    stale = _open(path)
    _open(path).record("first", {"state": "failed"})
    with stale.exclusive(refresh=True):
        stale.record("second", {"state": "failed"})
        stale.save()
        with pytest.raises(DataError, match="owned"):
            _open(path).record("third", {"state": "failed"})
    _open(path).record("third", {"state": "failed"})
    assert set(json.loads(path.read_bytes())["windows"]) == {"first", "second", "third"}


def test_stale_save_and_deleted_progress_do_not_overwrite(tmp_path: Path) -> None:
    path = tmp_path / "progress.json"
    first = _open(path)
    first.record("first", {"state": "failed"})
    stale = _open(path)
    first.record("second", {"state": "failed"})
    stale.body["windows"]["old"] = {"state": "failed"}
    before = path.read_bytes()
    with pytest.raises(DataError, match="stale"):
        stale.save()
    assert path.read_bytes() == before
    path.unlink()
    with pytest.raises(DataError, match="stale"):
        first.save()
    assert not path.exists()


@pytest.mark.parametrize("after_replace", [False, True])
@pytest.mark.parametrize("interruption", [OSError, KeyboardInterrupt])
def test_replace_failure_leaves_complete_json_and_no_owned_temp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    after_replace: bool,
    interruption: type[BaseException],
) -> None:
    import os

    path = tmp_path / "progress.json"
    _open(path).record("first", {"state": "failed"})
    replace = os.replace

    def fail_replace(source: Path, destination: Path) -> None:
        if after_replace:
            replace(source, destination)
        raise interruption("synthetic interruption")

    with monkeypatch.context() as patch:
        patch.setattr(os, "replace", fail_replace)
        with pytest.raises(interruption):
            _open(path).record("second", {"state": "failed"})
    expected = {"first", "second"} if after_replace else {"first"}
    assert set(json.loads(path.read_bytes())["windows"]) == expected
    assert not list(tmp_path.glob("progress.json.*.tmp"))
    _open(path).record("third", {"state": "failed"})
    assert (tmp_path / "progress.json.lock").is_file()


def test_canonical_parent_aliases_share_lock(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(real, target_is_directory=True)
    path = real / "progress.json"
    with _open(path).exclusive(), pytest.raises(DataError, match="owned"):
        _open(alias / "progress.json").record("other", {"state": "failed"})
    _open(alias / "progress.json").record("ok", {"state": "failed"})
    assert (real / "progress.json.lock").exists()
    assert not (tmp_path / "progress.json.lock").exists()


@pytest.mark.parametrize("kind", ["symlink", "hardlink", "fifo"])
@pytest.mark.parametrize("target", ["ledger", "lock"])
def test_unsafe_leaf_objects_are_refused(tmp_path: Path, kind: str, target: str) -> None:
    import os

    path = tmp_path / "progress.json"
    leaf = path if target == "ledger" else path.with_name(path.name + ".lock")
    original = tmp_path / "original"
    original.write_text("unchanged")
    if kind == "symlink":
        leaf.symlink_to(original)
    elif kind == "hardlink":
        os.link(original, leaf)
    else:
        os.mkfifo(leaf)
    with pytest.raises(DataError):
        _open(path).record("bad", {"state": "failed"})
    assert original.read_text() == "unchanged"


def test_replaced_lock_identity_refuses_owned_mutation(tmp_path: Path) -> None:
    path = tmp_path / "progress.json"
    ledger = _open(path)
    with ledger.exclusive():
        lock = path.with_name(path.name + ".lock")
        lock.unlink()
        lock.write_bytes(b"")
        with pytest.raises(DataError, match="identity"):
            ledger.record("bad", {"state": "failed"})
    assert not path.exists()
    _open(path).record("new", {"state": "failed"})


def test_separate_thread_cannot_reuse_object_ownership(tmp_path: Path) -> None:
    from concurrent.futures import ThreadPoolExecutor

    path = tmp_path / "progress.json"
    ledger = _open(path)
    with ledger.exclusive(), ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(ledger.record, "bad", {"state": "failed"})
        with pytest.raises(DataError, match="transferable"):
            future.result(timeout=5)
    assert not path.exists()


def test_losing_thread_cannot_clear_a_newly_acquired_owner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import os
    import threading
    from concurrent.futures import ThreadPoolExecutor
    from typing import Any

    path = tmp_path / "progress.json"
    ledger = _open(path)
    lock_path = path.with_name(path.name + ".lock")
    entered, proceed = threading.Event(), threading.Event()
    main_thread = threading.get_ident()
    original_open = os.open

    def delayed_open(candidate: Any, *args: Any, **kwargs: Any) -> int:
        if threading.get_ident() != main_thread and Path(candidate) == lock_path:
            entered.set()
            if not proceed.wait(5):
                raise RuntimeError("synthetic thread handoff timed out")
        return original_open(candidate, *args, **kwargs)

    monkeypatch.setattr(os, "open", delayed_open)
    with ThreadPoolExecutor(max_workers=1) as pool:
        loser = pool.submit(ledger.record, "loser", {"state": "failed"})
        try:
            assert entered.wait(5)  # loser passed the initially-unowned check
            with ledger.exclusive():
                proceed.set()
                with pytest.raises(DataError, match="owned"):
                    loser.result(timeout=5)
                ledger.record("owner", {"state": "failed"})
        finally:
            proceed.set()
    assert set(json.loads(path.read_bytes())["windows"]) == {"owner"}
