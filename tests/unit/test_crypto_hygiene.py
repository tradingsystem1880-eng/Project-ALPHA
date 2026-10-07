"""Retirement reference scans cannot silently omit retained evidence."""

from pathlib import Path

import pytest

from alpha_core import DataError
from scripts.crypto_data_hygiene import references


def test_reference_audit_finds_json_ids_and_sqlite_keys(tmp_path: Path) -> None:
    import sqlite3

    ident = "a" * 64
    key = "normalized/old.parquet"
    (tmp_path / "snapshot.json").write_text('{"manifest_id": "' + ident + '"}')
    with sqlite3.connect(tmp_path / "control.sqlite") as db:
        db.execute("create table refs (value text)")
        db.execute("insert into refs values (?)", (key,))
    refs = references(tmp_path, tmp_path / "manifests", {ident: key})
    assert set(refs[ident]) == {"snapshot.json", "control.sqlite:refs"}


def test_reference_audit_refuses_linked_directory(tmp_path: Path) -> None:
    target = tmp_path / "real"
    target.mkdir()
    (tmp_path / "linked").symlink_to(target, target_is_directory=True)
    with pytest.raises(DataError, match="linked directories"):
        references(tmp_path, tmp_path / "manifests", {})


def test_reference_audit_raises_on_unreadable_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def denied(*args: object, **kwargs: object) -> tuple[()]:
        callback = kwargs["onerror"]
        assert callable(callback)
        callback(PermissionError("blocked"))
        return ()

    monkeypatch.setattr("scripts.crypto_data_hygiene.os.walk", denied)
    with pytest.raises(DataError, match="cannot read"):
        references(tmp_path, tmp_path / "manifests", {})
