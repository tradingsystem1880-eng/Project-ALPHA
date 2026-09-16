"""Orientation uses the same current source extraction as the optional Atlas viewer."""

import json
from pathlib import Path

import pytest

from alpha_atlas.developer_index import developer_index


def test_default_index_is_bounded_and_current(repo_root: Path) -> None:
    result = developer_index(repo_root)
    assert len(json.dumps(result).encode()) <= 6_000
    assert result["authority"] == "none"
    assert any(row["id"] == "alpha-cli" for row in result["components"])
    assert "research" in result["documents"]
    assert "explore" not in result["documents"]
    assert result["module_count"] > 0
    assert "modules" not in result


def test_component_index_is_explicit_and_rejects_unknown(repo_root: Path) -> None:
    result = developer_index(repo_root, component="alpha-core")
    assert result["modules"]
    assert all(row["id"].startswith("alpha_core") for row in result["modules"])
    with pytest.raises(ValueError, match="unknown component"):
        developer_index(repo_root, component="../../data")


def test_index_does_not_read_owner_or_hidden_test_data(
    repo_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = Path.read_bytes

    def checked_read(path: Path) -> bytes:
        relative = path.relative_to(repo_root).as_posix()
        assert not relative.startswith(("data/", "tests/holdout/", ".claude/state/"))
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", checked_read)
    assert developer_index(repo_root)["module_count"] > 0
