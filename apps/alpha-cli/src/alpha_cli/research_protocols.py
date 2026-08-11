"""Git-owned Codex research protocol library (spec §14, ADR-0022).

Protocol content lives in the repository at ``.agents/skills/alpha-research-protocols/`` so
it stays owner-reviewed and agents cannot self-modify it; the control store records only
usage (``protocol_id`` + ``protocol_content_hash`` on each context packet). The loader
verifies index↔file consistency by hash and fails loud on any drift.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Final

from alpha_core import DataError

PROTOCOL_LIBRARY_DIR: Final = (
    Path(__file__).resolve().parents[4] / ".agents" / "skills" / "alpha-research-protocols"
)

_ENTRY_KEYS: Final = frozenset(
    {"id", "title", "purpose", "packet_kind", "output_contract", "file", "sha256"}
)
_PACKET_KINDS: Final = frozenset(
    {"asset", "research_case", "experiment", "chart", "validation", "strategy_promotion"}
)


def _library_root(library_dir: Path | None) -> Path:
    root = PROTOCOL_LIBRARY_DIR if library_dir is None else Path(library_dir)
    if not root.is_dir():
        raise DataError(
            f"research protocol library missing at {root}; protocols are repository content "
            "and are unavailable outside a checked-out working tree"
        )
    return root


def load_research_protocols(library_dir: Path | None = None) -> list[dict[str, object]]:
    """Return the validated protocol index; any index↔file drift fails loud."""
    root = _library_root(library_dir)
    index_path = root / "protocols.json"
    try:
        raw = index_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise DataError(f"research protocol library index unreadable at {index_path}") from exc
    try:
        index = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise DataError("research protocol library index is not valid JSON") from exc
    if not isinstance(index, dict) or index.get("library_schema") != "AlphaResearchProtocolsV1":
        raise DataError("research protocol library index has an unsupported schema")
    entries = index.get("protocols")
    if not isinstance(entries, list) or not entries:
        raise DataError("research protocol library index lists no protocols")
    validated: list[dict[str, object]] = []
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != _ENTRY_KEYS:
            raise DataError("research protocol index entry has unexpected fields")
        protocol_id = entry["id"]
        if not isinstance(protocol_id, str) or not protocol_id or protocol_id in seen:
            raise DataError("research protocol index ids must be unique non-empty strings")
        seen.add(protocol_id)
        if entry["packet_kind"] not in _PACKET_KINDS:
            raise DataError(f"research protocol {protocol_id!r} names an unknown packet kind")
        file_name = entry["file"]
        if not isinstance(file_name, str) or "/" in file_name or file_name.startswith("."):
            raise DataError(f"research protocol {protocol_id!r} has an invalid file name")
        path = root / file_name
        if not path.is_file():
            raise DataError(f"missing protocol file {file_name!r} for {protocol_id!r}")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != entry["sha256"]:
            raise DataError(
                f"protocol file {file_name!r} does not match its indexed hash; regenerate "
                "protocols.json after any owner-reviewed edit"
            )
        validated.append(dict(entry))
    return validated


def read_research_protocol(protocol_id: str, library_dir: Path | None = None) -> dict[str, object]:
    """Return one protocol entry plus its exact content."""
    root = _library_root(library_dir)
    for entry in load_research_protocols(root):
        if entry["id"] == protocol_id:
            content = (root / str(entry["file"])).read_text(encoding="utf-8")
            return {**entry, "content": content}
    raise DataError(f"unknown research protocol {protocol_id!r}")


__all__ = ["PROTOCOL_LIBRARY_DIR", "load_research_protocols", "read_research_protocol"]
