"""Atomic publication preserves the previous file until a successful write."""

from pathlib import Path

import pytest

from alpha_core.atomic import publish, write_text


def test_success_replaces_file(tmp_path: Path) -> None:
    path = tmp_path / "record.txt"
    path.write_text("old", encoding="utf-8")

    def writer(temporary: Path) -> None:
        assert temporary.parent == path.parent
        assert temporary != path
        assert path.read_text(encoding="utf-8") == "old"
        temporary.write_text("new", encoding="utf-8")

    publish(path, writer)

    assert path.read_text(encoding="utf-8") == "new"
    assert list(tmp_path.iterdir()) == [path]


def test_writer_failure_preserves_file_and_removes_temporary_sibling(tmp_path: Path) -> None:
    path = tmp_path / "record.txt"
    path.write_text("old", encoding="utf-8")

    def writer(temporary: Path) -> None:
        temporary.write_text("partial", encoding="utf-8")
        raise RuntimeError("writer failed")

    with pytest.raises(RuntimeError, match="^writer failed$"):
        publish(path, writer)

    assert path.read_text(encoding="utf-8") == "old"
    assert list(tmp_path.iterdir()) == [path]


def test_write_text_creates_parents(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "parent" / "record.txt"

    write_text(path, "café")

    assert path.read_bytes() == "café".encode()
    assert list(path.parent.iterdir()) == [path]
