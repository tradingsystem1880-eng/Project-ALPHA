"""Thin, bounded subprocess projections for governed ``alpha research`` workflows.

The web process never opens the CLI-owned research database.  This module exposes the Gate-1
capture/read/propose/pilot/report subset only; contract approval, owner disposition, D2/D3 reveal,
arbitrary code, and trading capabilities intentionally have no wrapper.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from alpha_web._catalog import _run_json


def _object(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise RuntimeError(f"alpha returned an invalid {label} projection")
    return cast(dict[str, Any], value)


def compare(
    *,
    data_dir: Path,
    symbol: str,
    strategies: str = "",
    run_context: dict[str, object],
) -> dict[str, Any]:
    """Rank the registered strategies on ``symbol`` by a full backtest of each."""
    args = ["research", "compare", symbol, "--json"]
    if strategies:
        args += ["--strategies", strategies]
    # compare runs a full engine backtest per registered strategy — allow well past the default
    # projection bound, but stay finite so a hung CLI can never pin the request thread.
    result: dict[str, Any] = _run_json(
        args,
        data_dir=data_dir,
        timeout_seconds=600.0,
        run_context=run_context,
    )
    return result


def capture(*, data_dir: Path, idea: str, name: str | None = None) -> dict[str, Any]:
    """Capture exact owner wording without approving a contract or launching compute."""
    args = ["research", "capture", idea, "--json"]
    if name is not None:
        args += ["--name", name]
    return _object(_run_json(args, data_dir=data_dir), "research capture")


def get(project_id: str, *, data_dir: Path) -> dict[str, Any]:
    """Read one bounded Research Case summary."""
    return _object(
        _run_json(["research", "status", project_id, "--json"], data_dir=data_dir),
        "research case",
    )


def propose(
    project_id: str,
    *,
    data_dir: Path,
    source_pack_id: str,
    answer_bundle_id: str,
    dataset_ref_id: str | None,
    expected_case_revision: str,
) -> dict[str, Any]:
    """Materialize a reviewable contract; approval remains owner-only and CLI-only."""
    args = [
        "research",
        "draft",
        project_id,
        "--source-pack-id",
        source_pack_id,
        "--answer-bundle",
        answer_bundle_id,
        "--expected-case-revision",
        expected_case_revision,
    ]
    if dataset_ref_id is not None:
        args += ["--dataset", dataset_ref_id]
    args += ["--json"]
    return _object(_run_json(args, data_dir=data_dir), "research proposal")


def proposal_options(project_id: str, *, data_dir: Path) -> dict[str, Any]:
    """Read server-authoritative executable proposal choices and current blockers."""

    return _object(
        _run_json(["research", "proposal-options", project_id, "--json"], data_dir=data_dir),
        "research proposal options",
    )


def launch(project_id: str, *, data_dir: Path, stage: str) -> dict[str, Any]:
    """Run only the Gate-1 deterministic D0 pilot; D1/D2 workers remain unavailable."""
    if stage != "pilot":
        raise ValueError("Gate-1 research launch stage must be pilot")
    return _object(
        _run_json(
            ["research", "run", "pilot", project_id, "--json"],
            data_dir=data_dir,
            timeout_seconds=120.0,
        ),
        "research launch",
    )


def status(project_id: str, *, data_dir: Path) -> dict[str, Any]:
    """Read phase, execution state, next action, budget, and evidence-firewall state."""
    return _object(
        _run_json(["research", "status", project_id, "--json"], data_dir=data_dir),
        "research status",
    )


def list_cases(*, data_dir: Path, limit: int = 50, offset: int = 0) -> dict[str, Any]:
    """Read the bounded research-case backlog page (ADR-0021 read plane)."""
    return _object(
        _run_json(
            ["research", "list", "--limit", str(limit), "--offset", str(offset), "--json"],
            data_dir=data_dir,
        ),
        "research case list",
    )


def evidence_hub(project_id: str, *, data_dir: Path) -> dict[str, Any]:
    """Read the eleven-section Evidence Hub projection for one case."""
    return _object(
        _run_json(["research", "evidence-hub", project_id, "--json"], data_dir=data_dir),
        "research evidence hub",
    )


def discover_literature(
    project_id: str,
    *,
    data_dir: Path,
    query: str,
    unpaywall_email: str,
    max_candidates: int,
    max_full_texts: int,
) -> dict[str, Any]:
    """Run one explicit bounded discovery through the isolated worker."""
    return _object(
        _run_json(
            [
                "research",
                "sources",
                "discover",
                project_id,
                "--query",
                query,
                "--unpaywall-email",
                unpaywall_email,
                "--max-candidates",
                str(max_candidates),
                "--max-full-texts",
                str(max_full_texts),
                "--json",
            ],
            data_dir=data_dir,
            timeout_seconds=240.0,
        ),
        "literature discovery",
    )


def acquire_literature(
    project_id: str,
    *,
    data_dir: Path,
    discovery_id: str,
    candidate_id: str,
) -> dict[str, Any]:
    """Acquire and extract one exact candidate; this grants no evidence authority."""
    return _object(
        _run_json(
            [
                "research",
                "sources",
                "acquire",
                project_id,
                discovery_id,
                candidate_id,
                "--json",
            ],
            data_dir=data_dir,
            timeout_seconds=240.0,
        ),
        "literature acquisition",
    )


def context_packets(
    project_id: str, *, data_dir: Path, limit: int = 50, offset: int = 0
) -> dict[str, Any]:
    """Read this case's recorded Codex context packets, newest first."""
    return _object(
        _run_json(
            [
                "research",
                "context",
                "list",
                project_id,
                "--limit",
                str(limit),
                "--offset",
                str(offset),
                "--json",
            ],
            data_dir=data_dir,
        ),
        "research context packets",
    )


def context_packet(packet_id: str, *, data_dir: Path) -> dict[str, Any]:
    """Read one recorded packet byte-identically (recording is visibility)."""
    return _object(
        _run_json(["research", "context", "show", packet_id, "--json"], data_dir=data_dir),
        "research context packet",
    )


def notes(project_id: str, *, data_dir: Path, limit: int = 100, offset: int = 0) -> dict[str, Any]:
    """Read this case's commentary notes — displayed as commentary, never evidence."""
    return _object(
        _run_json(
            [
                "research",
                "note",
                "list",
                project_id,
                "--limit",
                str(limit),
                "--offset",
                str(offset),
                "--json",
            ],
            data_dir=data_dir,
        ),
        "research notes",
    )


def datasets(
    *, data_dir: Path, symbol: str | None = None, limit: int = 100, offset: int = 0
) -> dict[str, Any]:
    """Read registered research dataset refs with their latest audit (ADR-0023)."""
    args = ["research", "data", "list"]
    if symbol is not None:
        args += ["--symbol", symbol]
    args += ["--limit", str(limit), "--offset", str(offset), "--json"]
    return _object(_run_json(args, data_dir=data_dir), "research datasets")


def protocols(*, data_dir: Path) -> dict[str, Any]:
    """Read the Git-owned protocol library index (drift fails loud in the CLI)."""
    return _object(
        _run_json(["research", "protocols", "list", "--json"], data_dir=data_dir),
        "research protocols",
    )


def scorecard(project_id: str, *, data_dir: Path) -> dict[str, Any]:
    """Read the readiness scorecard riding on the status projection."""
    row = _object(
        _run_json(["research", "status", project_id, "--json"], data_dir=data_dir),
        "research status",
    )
    value = row.get("scorecard")
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise RuntimeError("alpha returned an invalid research scorecard projection")
    return cast(dict[str, Any], value)


def decision_view(project_id: str, *, data_dir: Path) -> dict[str, Any]:
    """Read the owner decision view: checklist, full scorecard, packet, and history."""
    return _object(
        _run_json(["research", "decision-view", project_id, "--json"], data_dir=data_dir),
        "research decision view",
    )


def report(project_id: str, *, data_dir: Path) -> dict[str, Any]:
    """Read progress or project a terminal packet from already-recorded authority state."""
    return _object(
        _run_json(["research", "report", project_id, "--json"], data_dir=data_dir),
        "research report",
    )
