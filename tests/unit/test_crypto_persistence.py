"""Characterize immutable crypto documents through the existing CLI wrappers."""

from __future__ import annotations

import hashlib
import os
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

from alpha_cli import crypto_data_cmds as commands
from alpha_core import DataError


class Document:
    profile_id = version = snapshot_id = "a" * 64

    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def to_dict(self) -> dict[str, object]:
        return self.payload


@pytest.fixture(params=["coverage_profile", "asset_master", "snapshot"])
def writer(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> tuple[Callable[[Document], None], Path, str]:
    kind = str(request.param)
    root = tmp_path / "documents"
    root_name = {
        "coverage_profile": "_coverage_profile_root",
        "asset_master": "_asset_master_root",
        "snapshot": "_snapshot_root",
    }[kind]
    monkeypatch.setattr(commands, root_name, lambda: root)
    return (
        cast(Callable[[Document], None], getattr(commands, f"_write_{kind}")),
        root / f"{'a' * 64}.json",
        kind.replace("_", "-"),
    )


def test_exact_bytes_and_repeat_does_not_replace(
    writer: tuple[Callable[[Document], None], Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    write, path, _ = writer
    document = Document({"z": "é", "a": [True, None, 1.25]})
    write(document)
    expected = b'{\n  "a": [\n    true,\n    null,\n    1.25\n  ],\n  "z": "\\u00e9"\n}\n'
    assert path.read_bytes() == expected
    digest = hashlib.sha256(path.read_bytes()).hexdigest()

    def unexpected_replace(source: object, target: object) -> None:
        pytest.fail("idempotent document write must not replace existing bytes")

    monkeypatch.setattr(os, "replace", unexpected_replace)
    write(document)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
    assert not path.with_suffix(".json.tmp").exists()


@pytest.mark.parametrize("existing", ['{\n  "value": 1\n}\n', '{"value":2}', "{"])
def test_collision_preserves_existing_bytes(
    writer: tuple[Callable[[Document], None], Path, str],
    existing: str,
) -> None:
    write, path, kind = writer
    write(Document({"value": 1}))
    path.write_text(existing, encoding="utf-8")
    original = path.read_bytes()
    with pytest.raises(DataError) as error:
        write(Document({"value": 2}))
    assert str(error.value) == f"crypto {kind} identity collision"
    assert path.read_bytes() == original


def test_nonfinite_payload_never_publishes(
    writer: tuple[Callable[[Document], None], Path, str],
) -> None:
    write, path, _ = writer
    with pytest.raises(ValueError, match="Out of range float"):
        write(Document({"value": float("nan")}))
    assert path.parent.is_dir()
    assert not path.exists()
    assert not path.with_suffix(".json.tmp").exists()


def test_replace_failure_preserves_destination(
    writer: tuple[Callable[[Document], None], Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    write, path, _ = writer

    def failed_replace(source: object, target: object) -> None:
        assert Path(str(source)).is_file()
        assert Path(str(target)) == path
        raise OSError("replacement unavailable")

    monkeypatch.setattr(os, "replace", failed_replace)
    with pytest.raises(OSError, match="replacement unavailable"):
        write(Document({"value": 1}))
    assert not path.exists()
    assert path.with_suffix(".json.tmp").exists()


def test_extracted_sources_remain_in_execution_identity() -> None:
    from alpha_cli._identity import _source_files

    labels = {label for label, _ in _source_files("alpha_cli")}
    assert "alpha_cli/_crypto_persistence.py" in labels
    assert "alpha_cli/_control_json.py" in labels
