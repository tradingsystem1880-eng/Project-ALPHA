"""Deterministic Markdown projections for governed research cases.

Markdown is never parsed back into control state.  Verification regenerates the complete expected
byte stream from SQLite projections and compares it with the exported file.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from alpha_core import DataError

_PROJECT_ID: Final = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}"
)
_CONTRACT_ID: Final = re.compile(r"rc_[0-9a-f]{64}")


@dataclass(frozen=True, slots=True)
class DossierReceipt:
    path: Path
    sha256: str
    size_bytes: int


def _canonical(value: Mapping[str, object], label: str) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise DataError(f"research dossier {label} must contain finite JSON values") from exc


def _pretty(value: Mapping[str, object], label: str) -> str:
    _canonical(value, label)
    return json.dumps(value, sort_keys=True, indent=2, allow_nan=False)


def _identifier(value: str, *, pattern: re.Pattern[str], label: str) -> str:
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise DataError(f"research dossier has an invalid {label}")
    return value


def _mapping(value: object) -> Mapping[str, object]:
    if isinstance(value, Mapping) and all(isinstance(key, str) for key in value):
        return value
    return {}


def _text(value: object, fallback: str = "Not yet defined.") -> str:
    return value if isinstance(value, str) and value else fallback


def _bullets(values: object) -> str:
    if not isinstance(values, list) or not values:
        return "- None recorded."
    return "\n".join(f"- {_text(value)}" for value in values)


def render_research_dossier(
    *,
    project_id: str,
    contract_id: str,
    contract: Mapping[str, object],
    summary: Mapping[str, object],
) -> bytes:
    """Render the complete deterministic human-readable projection."""

    pid = _identifier(project_id, pattern=_PROJECT_ID, label="project_id")
    cid = _identifier(contract_id, pattern=_CONTRACT_ID, label="contract_id")
    canonical_contract = _canonical(contract, "contract")
    canonical_summary = _canonical(summary, "summary")
    contract_sha = hashlib.sha256(canonical_contract.encode("utf-8")).hexdigest()
    summary_sha = hashlib.sha256(canonical_summary.encode("utf-8")).hexdigest()
    thesis = _mapping(contract.get("thesis"))
    primary = _mapping(contract.get("primary_claim"))
    phase = _text(summary.get("phase"), "not_started")
    execution = _text(summary.get("execution_state"), "idle")
    owner = _text(summary.get("responsibility"), "unassigned")
    next_action = _text(summary.get("next_action"))
    raw_idea = _text(contract.get("raw_idea"))
    lines = [
        "<!-- GENERATED PROJECTION — DO NOT EDIT -->",
        f"<!-- project_id: {pid} -->",
        f"<!-- research_contract_id: {cid} -->",
        f"<!-- canonical_contract_sha256: {contract_sha} -->",
        f"<!-- research_summary_sha256: {summary_sha} -->",
        "",
        "# Research Dossier",
        "",
        "This file is a deterministic view of SQLite control state and immutable research "
        "artifacts. It is not accepted as control input.",
        "",
        "## Current decision",
        "",
        f"- Phase: `{phase}`",
        f"- Execution: `{execution}`",
        f"- Next action owner: `{owner}`",
        f"- Next action: {next_action}",
        "",
        "## Raw idea",
        "",
        raw_idea,
        "",
        "## Thesis",
        "",
        f"- Mechanism: {_text(thesis.get('mechanism'))}",
        f"- Prediction: {_text(thesis.get('prediction'))}",
        f"- Interpretation: {_text(thesis.get('interpretation'))}",
        "",
        "### Alternative explanations",
        "",
        _bullets(thesis.get("alternatives")),
        "",
        "## Primary claim",
        "",
        "```json",
        _pretty(primary, "primary claim"),
        "```",
        "",
        "## Required falsifiers",
        "",
        _bullets(contract.get("required_falsifiers")),
        "",
        "## Material questions",
        "",
        "```json",
        json.dumps(contract.get("blocking_questions", []), sort_keys=True, indent=2),
        "```",
        "",
        "## Canonical Contract (reference only)",
        "",
        "```json",
        json.dumps(contract, sort_keys=True, indent=2, allow_nan=False),
        "```",
        "",
        "## Current Case Summary (reference only)",
        "",
        "```json",
        json.dumps(summary, sort_keys=True, indent=2, allow_nan=False),
        "```",
        "",
    ]
    return "\n".join(lines).encode("utf-8")


def _reject_symlink_chain(path: Path) -> None:
    for candidate in (path, *path.parents):
        if candidate.exists() and candidate.is_symlink():
            raise DataError(f"research dossier output must not traverse a symlink: {candidate}")


def _receipt(path: Path, content: bytes) -> DossierReceipt:
    return DossierReceipt(
        path=path,
        sha256=hashlib.sha256(content).hexdigest(),
        size_bytes=len(content),
    )


def export_research_dossier(
    output_dir: Path,
    *,
    project_id: str,
    contract_id: str,
    contract: Mapping[str, object],
    summary: Mapping[str, object],
) -> DossierReceipt:
    """Atomically export one content-addressed generated dossier."""

    content = render_research_dossier(
        project_id=project_id,
        contract_id=contract_id,
        contract=contract,
        summary=summary,
    )
    destination_dir = Path(output_dir)
    _reject_symlink_chain(destination_dir)
    destination_dir.mkdir(parents=True, exist_ok=True)
    _reject_symlink_chain(destination_dir)
    destination = destination_dir / f"research-contract-{contract_id}.md"
    if destination.is_symlink():
        raise DataError(f"research dossier target must not be a symlink: {destination}")
    temporary = destination_dir / f".{destination.name}.{uuid.uuid4().hex}.tmp"
    try:
        with temporary.open("xb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
        directory_fd = os.open(destination_dir, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except OSError as exc:
        if temporary.exists():
            temporary.unlink()
        raise DataError("research dossier export failed") from exc
    return _receipt(destination, content)


def verify_research_dossier(
    path: Path,
    *,
    project_id: str,
    contract_id: str,
    contract: Mapping[str, object],
    summary: Mapping[str, object],
) -> DossierReceipt:
    """Regenerate and byte-compare a dossier without parsing it as authority."""

    dossier_path = Path(path)
    if dossier_path.is_symlink() or not dossier_path.is_file():
        raise DataError("research dossier verification requires a regular file")
    expected = render_research_dossier(
        project_id=project_id,
        contract_id=contract_id,
        contract=contract,
        summary=summary,
    )
    try:
        actual = dossier_path.read_bytes()
    except OSError as exc:
        raise DataError("research dossier could not be read") from exc
    if actual != expected:
        raise DataError("research dossier does not match its deterministic projection")
    return _receipt(dossier_path, expected)
