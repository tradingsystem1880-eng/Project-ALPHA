"""Thin, bounded subprocess projections for governed ``alpha research`` workflows.

The web process never opens the CLI-owned research database.  This module exposes the Gate-1
capture/read/propose/pilot/report subset only; contract approval, owner disposition, D2/D3 reveal,
arbitrary code, and trading capabilities intentionally have no wrapper.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from alpha_web._catalog import _run_json

_RESEARCH_ANSWER_OPTIONS = {
    "chart_construction": frozenset({"spy_rth_60m_four_hour_window"}),
    "event_availability": frozenset({"second_trough_confirmable"}),
    "primary_outcome": frozenset({"four_trading_hour_return_25bp"}),
}


def _object(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise RuntimeError(f"alpha returned an invalid {label} projection")
    return cast(dict[str, Any], value)


def compare(*, data_dir: Path, symbol: str, strategies: str = "") -> dict[str, Any]:
    """Rank the registered strategies on ``symbol`` by a full backtest of each."""
    args = ["research", "compare", symbol, "--json"]
    if strategies:
        args += ["--strategies", strategies]
    # compare runs a full engine backtest per registered strategy — allow well past the default
    # projection bound, but stay finite so a hung CLI can never pin the request thread.
    result: dict[str, Any] = _run_json(args, data_dir=data_dir, timeout_seconds=600.0)
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
    answers: Mapping[str, str],
) -> dict[str, Any]:
    """Materialize a reviewable contract; approval remains owner-only and CLI-only."""
    if set(answers) != set(_RESEARCH_ANSWER_OPTIONS):
        raise ValueError("research proposal requires exactly the three material answers")
    args = ["research", "draft", project_id, "--source-pack-id", source_pack_id]
    for key in sorted(_RESEARCH_ANSWER_OPTIONS):
        value = answers[key]
        if value not in _RESEARCH_ANSWER_OPTIONS[key]:
            raise ValueError(f"unsupported {key} research answer {value!r}")
        args += ["--answer", f"{key}={value}"]
    args += ["--json"]
    return _object(_run_json(args, data_dir=data_dir), "research proposal")


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


def report(project_id: str, *, data_dir: Path) -> dict[str, Any]:
    """Read progress or project a terminal packet from already-recorded authority state."""
    return _object(
        _run_json(["research", "report", project_id, "--json"], data_dir=data_dir),
        "research report",
    )
