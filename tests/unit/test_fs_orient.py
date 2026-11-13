"""Orientation is computed from directory listings, bounded, and routes to real documents."""

from __future__ import annotations

import json
from pathlib import Path

import fs
import fs_orient
import gate
import pytest

from tests.unit._harness_support import REPO_ROOT as ROOT


def test_default_orientation_is_bounded_and_current() -> None:
    result = fs_orient.orientation(ROOT)
    assert len(json.dumps(result).encode()) <= fs_orient.DEFAULT_SIZE_CAP
    assert result["authority"] == "none"
    assert any(row["id"] == "alpha-cli" for row in result["components"])
    assert result["module_count"] == sum(row["modules"] for row in result["components"])
    assert result["module_count"] > 0
    assert "modules" not in result


def test_documents_are_the_routing_files_and_exist() -> None:
    documents = fs_orient.orientation(ROOT)["documents"]
    assert documents == list(fs_orient.ROUTING_DOCUMENTS)
    assert all((ROOT / rel).is_file() for rel in documents)


def test_component_orientation_is_explicit_and_rejects_unknown() -> None:
    result = fs_orient.orientation(ROOT, component="alpha-core")
    assert result["modules"]
    assert all(row["id"].startswith("alpha_core") for row in result["modules"])
    assert all((ROOT / row["path"]).is_file() for row in result["modules"])
    with pytest.raises(ValueError, match="unknown component"):
        fs_orient.orientation(ROOT, component="../../data")


def test_modules_are_counted_per_source_package(tmp_path: Path) -> None:
    package = tmp_path / "packages/alpha-x/src/alpha_x"
    (package / "sub").mkdir(parents=True)
    (tmp_path / "packages/alpha-x/pyproject.toml").write_text("")
    for rel in ("__init__.py", "a.py", "sub/__init__.py", "sub/b.py"):
        (package / rel).write_text("")
    (package / "__pycache__").mkdir()
    (package / "__pycache__/a.py").write_text("")
    (tmp_path / "workers/empty").mkdir(parents=True)
    (tmp_path / "workers/empty/pyproject.toml").write_text("")
    (tmp_path / "apps/not-a-component").mkdir(parents=True)
    result = fs_orient.orientation(tmp_path, component="alpha-x")
    assert [row["id"] for row in result["modules"]] == [
        "alpha_x",
        "alpha_x.a",
        "alpha_x.sub",
        "alpha_x.sub.b",
    ]
    assert [(row["id"], row["modules"]) for row in result["components"]] == [
        ("alpha-x", 4),
        ("empty", 0),
    ]
    assert result["documents"] == []


def test_orientation_reads_no_file_contents(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(path: Path, *args: object, **kwargs: object) -> object:
        raise AssertionError(f"orientation read {path}")

    monkeypatch.setattr(Path, "read_bytes", refuse)
    monkeypatch.setattr(Path, "read_text", refuse)
    monkeypatch.setattr(Path, "open", refuse)
    assert fs_orient.orientation(ROOT)["module_count"] > 0


def test_gate_orient_and_fs_orient_print_the_same(capsys: pytest.CaptureFixture[str]) -> None:
    assert fs.main(["orient"]) == 0
    from_fs = capsys.readouterr().out
    assert gate.main(["orient"]) == 0
    assert capsys.readouterr().out == from_fs
    assert from_fs.startswith("Repository orientation (source index; authority: none)")
    assert "Documents: CLAUDE.md, docs/README.md" in from_fs
    assert fs.main(["orient", "--component", "nope"]) == 2
