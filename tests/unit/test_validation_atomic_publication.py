"""Atomic text publication preserves complete files and reports failed writes."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from alpha_validation import _atomic


def test_publishes_utf8_text_to_new_parent_directories(tmp_path: Path) -> None:
    destination = tmp_path / "nested/reports/result.html"
    _atomic.write_text(destination, "Résumé — Δ\n")
    assert destination.read_bytes() == "Résumé — Δ\n".encode()
    assert list(destination.parent.iterdir()) == [destination]


def test_replacement_observes_complete_old_and_new_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination = tmp_path / "result.html"
    destination.write_text("previous complete report", encoding="utf-8")
    original_replace = os.replace
    observed: list[tuple[str, str]] = []

    def observe_replace(source: Path, target: Path) -> None:
        assert target == destination
        observed.append((destination.read_text(), source.read_text()))
        original_replace(source, target)

    monkeypatch.setattr(os, "replace", observe_replace)
    _atomic.write_text(destination, "replacement complete report")
    assert observed == [("previous complete report", "replacement complete report")]
    assert destination.read_text() == "replacement complete report"
    assert list(tmp_path.iterdir()) == [destination]


def test_partial_write_failure_preserves_original_and_removes_temporary_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination = tmp_path / "result.html"
    destination.write_text("previous complete report", encoding="utf-8")
    original_write = Path.write_text

    def partial_write(path: Path, content: str, *args: object, **kwargs: object) -> int:
        original_write(path, content[:4], encoding="utf-8")
        raise OSError("injected partial write failure")

    monkeypatch.setattr(Path, "write_text", partial_write)
    with pytest.raises(OSError, match="injected partial write failure"):
        _atomic.write_text(destination, "replacement complete report")
    assert destination.read_text() == "previous complete report"
    assert list(tmp_path.iterdir()) == [destination]


def test_replacement_failure_preserves_original_and_removes_temporary_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination = tmp_path / "result.html"
    destination.write_text("previous complete report", encoding="utf-8")

    def deny_replace(source: Path, target: Path) -> None:
        raise PermissionError("injected publication denial")

    monkeypatch.setattr(os, "replace", deny_replace)
    with pytest.raises(PermissionError, match="injected publication denial"):
        _atomic.write_text(destination, "replacement complete report")
    assert destination.read_text() == "previous complete report"
    assert list(tmp_path.iterdir()) == [destination]
