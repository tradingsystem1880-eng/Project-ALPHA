"""The Git-owned Codex protocol library: index↔file consistency fails loud on drift."""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

from alpha_cli.research_protocols import (
    PROTOCOL_LIBRARY_DIR,
    load_research_protocols,
    read_research_protocol,
)
from alpha_core import DataError

_SPEC_PROTOCOL_IDS = [
    "new-idea-intake",
    "hypothesis-formalisation",
    "data-discovery",
    "data-audit",
    "literature-review",
    "mechanism-analysis",
    "exploratory-analysis",
    "falsification-design",
    "event-study-design",
    "robustness-review",
    "research-critic",
    "evidence-synthesis",
    "strategy-promotion-review",
]

_PACKET_KINDS = {
    "asset",
    "research_case",
    "experiment",
    "chart",
    "validation",
    "strategy_promotion",
}


def test_library_ships_the_thirteen_spec_protocols_with_matching_hashes() -> None:
    protocols = load_research_protocols()
    assert [entry["id"] for entry in protocols] == _SPEC_PROTOCOL_IDS
    for entry in protocols:
        assert set(entry) == {
            "id",
            "title",
            "purpose",
            "packet_kind",
            "output_contract",
            "file",
            "sha256",
        }
        assert entry["packet_kind"] in _PACKET_KINDS
        assert isinstance(entry["purpose"], str) and entry["purpose"]
        assert isinstance(entry["output_contract"], str) and entry["output_contract"]
        content = (PROTOCOL_LIBRARY_DIR / str(entry["file"])).read_text(encoding="utf-8")
        assert str(entry["title"]) in content


def test_protocol_read_returns_entry_plus_exact_content() -> None:
    protocol = read_research_protocol("new-idea-intake")
    assert protocol["id"] == "new-idea-intake"
    assert protocol["packet_kind"] == "research_case"
    content = protocol["content"]
    assert isinstance(content, str)
    # The intake protocol must never ask for trading rules.
    assert "entry rule" not in content.casefold() or "never" in content.casefold()
    with pytest.raises(DataError, match="unknown research protocol"):
        read_research_protocol("build-me-a-strategy")


def test_tampered_protocol_content_fails_loud(tmp_path: Path) -> None:
    library = tmp_path / "protocols"
    shutil.copytree(PROTOCOL_LIBRARY_DIR, library)
    target = json.loads((library / "protocols.json").read_text(encoding="utf-8"))
    first_file = library / str(target["protocols"][0]["file"])
    first_file.write_text(
        first_file.read_text(encoding="utf-8") + "\nInjected drift.", encoding="utf-8"
    )
    with pytest.raises(DataError, match="does not match its indexed hash"):
        load_research_protocols(library)


def test_missing_indexed_file_fails_loud(tmp_path: Path) -> None:
    library = tmp_path / "protocols"
    shutil.copytree(PROTOCOL_LIBRARY_DIR, library)
    index = json.loads((library / "protocols.json").read_text(encoding="utf-8"))
    (library / str(index["protocols"][0]["file"])).unlink()
    with pytest.raises(DataError, match="missing protocol file"):
        load_research_protocols(library)


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda index: index.update({"library_schema": "V2"}), "unsupported schema"),
        (lambda index: index.update({"protocols": []}), "lists no protocols"),
        (
            lambda index: index["protocols"][0].pop("purpose"),
            "unexpected fields",
        ),
        (
            lambda index: index["protocols"][0].update({"id": ""}),
            "unique non-empty",
        ),
        (
            lambda index: index["protocols"][0].update({"packet_kind": "chat"}),
            "unknown packet kind",
        ),
        (
            lambda index: index["protocols"][0].update({"file": "../escape.md"}),
            "invalid file name",
        ),
    ],
)
def test_corrupt_index_entries_fail_loud(tmp_path: Path, mutate: object, message: str) -> None:
    library = tmp_path / "protocols"
    shutil.copytree(PROTOCOL_LIBRARY_DIR, library)
    index_path = library / "protocols.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    cast("Callable[[dict[str, list[dict[str, str]]]], None]", mutate)(index)
    index_path.write_text(json.dumps(index), encoding="utf-8")
    with pytest.raises(DataError, match=message):
        load_research_protocols(library)


def test_missing_library_and_unreadable_index_fail_loud(tmp_path: Path) -> None:
    with pytest.raises(DataError, match="library missing"):
        load_research_protocols(tmp_path / "does-not-exist")
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(DataError, match="index unreadable"):
        load_research_protocols(empty)
    (empty / "protocols.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(DataError, match="not valid JSON"):
        load_research_protocols(empty)
