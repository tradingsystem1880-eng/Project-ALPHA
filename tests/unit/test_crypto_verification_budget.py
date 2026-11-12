from __future__ import annotations

import hashlib
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest

from alpha_core import DataError
from alpha_data.crypto import verification
from alpha_data.crypto.verification import ArtifactVerificationBudget


def _hash(budget: ArtifactVerificationBudget, path: Path, payload: bytes) -> str:
    return budget.hash_file(
        path, expected_bytes=len(payload), expected_sha256=hashlib.sha256(payload).hexdigest()
    )


@pytest.mark.parametrize("cap", [0, -1, True, 1.5, None])
def test_limit_requires_an_explicit_positive_integer(cap: object) -> None:
    with pytest.raises(DataError):
        ArtifactVerificationBudget(cap)  # type: ignore[arg-type]


def test_exact_fit_has_no_overflow_probe_and_exhaustion_never_opens_next_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "artifact"
    path.write_bytes(b"abc")
    budget = ArtifactVerificationBudget(3)
    assert _hash(budget, path, b"abc") == hashlib.sha256(b"abc").hexdigest()
    assert budget.bytes_read == budget.reserved_bytes == 3
    monkeypatch.setattr(
        "alpha_data.crypto.verification.os.open",
        lambda *a, **k: pytest.fail("reject before artifact open"),
    )
    with pytest.raises(DataError, match="budget exhausted"):
        _hash(budget, path, b"abc")
    assert budget.bytes_read == budget.reserved_bytes == 3


def test_oversize_reservation_stops_before_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    budget = ArtifactVerificationBudget(2)
    monkeypatch.setattr(
        "alpha_data.crypto.verification.os.open", lambda *a, **k: pytest.fail("must not open")
    )
    with pytest.raises(DataError, match="budget exhausted"):
        _hash(budget, tmp_path / "not-opened", b"abc")
    assert budget.bytes_read == budget.reserved_bytes == 0


def test_short_or_wrong_hash_retains_reservation_and_aborts_reuse(tmp_path: Path) -> None:
    path = tmp_path / "artifact"
    path.write_bytes(b"ab")
    budget = ArtifactVerificationBudget(10)
    with pytest.raises(DataError):
        _hash(budget, path, b"abc")
    assert budget.failed and budget.reserved_bytes == 3 and budget.bytes_read == 0
    with pytest.raises(DataError, match="aborted"):
        _hash(budget, path, b"ab")
    fresh = ArtifactVerificationBudget(10)
    with pytest.raises(DataError, match="integrity"):
        _hash(fresh, path, b"cd")
    assert fresh.failed and fresh.reserved_bytes == fresh.bytes_read == 2


@pytest.mark.parametrize("change", ["shrink", "grow", "same_size"])
def test_mutating_file_is_not_verified(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    path = tmp_path / "artifact"
    path.write_bytes(b"abcdef")
    real_read = os.read
    reads = 0
    monkeypatch.setattr(verification, "_CHUNK_BYTES", 2)

    def read(fd: int, size: int) -> bytes:
        nonlocal reads
        chunk = real_read(fd, size)
        reads += 1
        if reads == 1:
            path.write_bytes({"shrink": b"a", "grow": b"abcdefgh", "same_size": b"zzzzzz"}[change])
        return chunk

    monkeypatch.setattr("alpha_data.crypto.verification.os.read", read)
    budget = ArtifactVerificationBudget(6)
    with pytest.raises(DataError):
        _hash(budget, path, b"abcdef")
    assert budget.failed and budget.reserved_bytes == 6 and budget.bytes_read <= 6


@pytest.mark.parametrize("interrupt", [OSError("synthetic read failure"), KeyboardInterrupt()])
def test_failed_or_cancelled_read_never_refunds_local_reservation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, interrupt: BaseException
) -> None:
    path = tmp_path / "artifact"
    path.write_bytes(b"abcdef")
    real_read = os.read
    reads = 0
    monkeypatch.setattr(verification, "_CHUNK_BYTES", 2)

    def read(fd: int, size: int) -> bytes:
        nonlocal reads
        reads += 1
        if reads == 2:
            raise interrupt
        return real_read(fd, size)

    monkeypatch.setattr("alpha_data.crypto.verification.os.read", read)
    budget = ArtifactVerificationBudget(6)
    with pytest.raises((DataError, KeyboardInterrupt)):
        _hash(budget, path, b"abcdef")
    assert budget.failed and budget.reserved_bytes == 6 and budget.bytes_read == 2
    # A fresh process/session has a fresh local I/O cap, never a reset provider allowance.
    monkeypatch.setattr("alpha_data.crypto.verification.os.read", real_read)
    assert _hash(ArtifactVerificationBudget(6), path, b"abcdef")


def test_symlink_or_fifo_never_yields_artifact_bytes(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.write_bytes(b"abc")
    link = tmp_path / "link"
    link.symlink_to(target)
    fifo = tmp_path / "fifo"
    os.mkfifo(fifo)
    for path in (link, fifo):
        budget = ArtifactVerificationBudget(3)
        with pytest.raises(DataError):
            _hash(budget, path, b"abc")
        assert budget.failed and budget.bytes_read == 0


def test_shared_budget_reserves_atomically_for_simultaneous_local_readers(tmp_path: Path) -> None:
    path = tmp_path / "artifact"
    path.write_bytes(b"abc")
    budget = ArtifactVerificationBudget(3)
    barrier = Barrier(2)

    def contender() -> str:
        barrier.wait(timeout=5)
        try:
            _hash(budget, path, b"abc")
            return "verified"
        except DataError:
            return "stopped"

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(contender) for _ in range(2)]
        assert sorted(f.result(timeout=5) for f in futures) == ["stopped", "verified"]
    assert budget.bytes_read == budget.reserved_bytes == 3
