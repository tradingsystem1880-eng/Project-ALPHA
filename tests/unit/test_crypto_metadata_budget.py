from __future__ import annotations

import json
from pathlib import Path

import pytest

from alpha_core import DataError
from alpha_data.crypto.verification import MetadataVerificationBudget


def test_exact_fit_and_repeated_read_share_one_allowance(tmp_path: Path) -> None:
    path = tmp_path / "metadata.json"
    payload = b'{"ok":true}'
    path.write_bytes(payload)
    budget = MetadataVerificationBudget(2 * len(payload))
    assert budget.read_json(path) == {"ok": True}
    assert budget.read_json(path) == {"ok": True}
    assert budget.bytes_read == budget.reserved_bytes == 2 * len(payload)
    with pytest.raises(DataError, match="metadata"):
        budget.read_json(path)
    assert budget.failed


def test_oversized_file_is_refused_before_body_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import os

    path = tmp_path / "metadata.json"
    path.write_bytes(b" " * 1000)

    def fail(*args: object, **kwargs: object) -> int:
        pytest.fail("oversized metadata must not be opened for body reading")

    monkeypatch.setattr(os, "open", fail)
    budget = MetadataVerificationBudget(20)
    with pytest.raises(DataError):
        budget.read_json(path)
    assert budget.bytes_read == budget.reserved_bytes == 0
    assert budget.failed


@pytest.mark.parametrize(
    "payload",
    [b"", b"{", b"SECRET_CANARY", b"[" * 2000 + b"]" * 2000, b"\xff"],
    ids=["empty", "truncated", "invalid", "deep", "invalid_utf8"],
)
def test_malformed_json_retains_consumption(tmp_path: Path, payload: bytes) -> None:
    path = tmp_path / "metadata.json"
    path.write_bytes(payload)
    budget = MetadataVerificationBudget(10000)
    with pytest.raises(DataError):
        budget.read_json(path)
    assert budget.failed
    assert budget.reserved_bytes == budget.bytes_read == len(payload)
    assert path.read_bytes() == payload


def test_depth_guard_ignores_brackets_and_escaped_quotes_inside_strings(tmp_path: Path) -> None:
    path = tmp_path / "metadata.json"
    value = {"literal": '[{"escaped": "quote\\""}]' * 100}
    payload = json.dumps(value).encode()
    path.write_bytes(payload)
    assert MetadataVerificationBudget(len(payload), max_depth=1).read_json(path) == value


@pytest.mark.parametrize("change", ["short_read", "replace", "truncate", "grow"])
def test_changed_or_incomplete_metadata_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    import os

    path = tmp_path / "metadata.json"
    payload = b'{"ok":true}'
    path.write_bytes(payload)
    read = os.read
    acted = False

    def changed_read(fd: int, size: int) -> bytes:
        nonlocal acted
        if acted:
            return read(fd, size)
        acted = True
        if change == "short_read":
            return b""
        body = read(fd, size)
        if change == "replace":
            replacement = tmp_path / "replacement.json"
            replacement.write_bytes(payload)
            os.replace(replacement, path)
        elif change == "truncate":
            path.write_bytes(b"{")
        else:
            with path.open("ab") as stream:
                stream.write(b" ")
        return body

    monkeypatch.setattr(os, "read", changed_read)
    budget = MetadataVerificationBudget(1000)
    with pytest.raises(DataError):
        budget.read_json(path)
    assert budget.failed and budget.reserved_bytes == len(payload)
    assert budget.bytes_read <= budget.reserved_bytes


@pytest.mark.parametrize("kind", ["symlink", "fifo", "directory"])
def test_nonregular_metadata_is_rejected_without_reading(tmp_path: Path, kind: str) -> None:
    import os

    path = tmp_path / "metadata.json"
    if kind == "symlink":
        original = tmp_path / "original.json"
        original.write_bytes(b"{}")
        path.symlink_to(original)
    elif kind == "fifo":
        os.mkfifo(path)
    else:
        path.mkdir()
    budget = MetadataVerificationBudget(100)
    with pytest.raises(DataError):
        budget.read_json(path)
    assert budget.failed and budget.bytes_read == 0


def test_cancellation_closes_descriptor_and_retains_reservation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import os

    path = tmp_path / "metadata.json"
    path.write_bytes(b"{}")
    closed = []
    close = os.close

    def record_close(fd: int) -> None:
        closed.append(fd)
        close(fd)

    def cancel(fd: int, size: int) -> bytes:
        raise KeyboardInterrupt

    monkeypatch.setattr(os, "close", record_close)
    monkeypatch.setattr(os, "read", cancel)
    budget = MetadataVerificationBudget(100)
    with pytest.raises(KeyboardInterrupt):
        budget.read_json(path)
    assert (
        len(closed) == 1 and budget.failed and budget.reserved_bytes == 2 and budget.bytes_read == 0
    )


@pytest.mark.parametrize("encoding", ["utf-16", "utf-32", "utf-8-sig"])
def test_bounded_reader_keeps_legacy_utf8_json_encoding_contract(
    tmp_path: Path, encoding: str
) -> None:
    path = tmp_path / "metadata.json"
    payload = '{"ok":true}'.encode(encoding)
    path.write_bytes(payload)
    budget = MetadataVerificationBudget(1000)
    with pytest.raises(DataError):
        budget.read_json(path)
    assert budget.failed and budget.bytes_read == len(payload)
