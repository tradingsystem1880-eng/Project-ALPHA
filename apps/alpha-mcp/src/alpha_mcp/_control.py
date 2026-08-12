"""Bounded MCP helpers for CLI-owned projects, jobs, AgentBrief, and evidence."""

from __future__ import annotations

import json
import os
import subprocess
import uuid
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

from alpha_mcp import _invoke

_SUITE_ACTIONS = frozenset(
    {
        "baseline",
        "inner_oos",
        "three_null_families",
        "monte_carlo",
        "optimize_grid",
        "fixed_stress",
        "portfolio_cross_asset",
        "qlib",
        "kronos",
        "holdout_reveal",
        "paper_preflight",
    }
)
_AGENT_RUNNABLE_SUITE_ACTIONS = _SUITE_ACTIONS - {"holdout_reveal"}
_RESEARCH_ANSWER_KEYS = frozenset({"chart_construction", "event_availability", "primary_outcome"})
# The D0 pilot computes and publishes a run; a projection-class timeout would kill it
# mid-compute and permanently consume one of the three lifetime launch reservations.
# Matches the launch-class ceiling used by alpha_web/_research.py::launch.
_RESEARCH_LAUNCH_TIMEOUT_S = 120.0


def bound(name: str, value: int, maximum: int) -> int:
    if isinstance(value, bool) or not 1 <= value <= maximum:
        raise ValueError(f"{name} must be in 1..{maximum}")
    return value


def offset(value: int) -> int:
    if isinstance(value, bool) or value < 0:
        raise ValueError("offset must be non-negative")
    return value


def _object(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise RuntimeError(f"alpha returned an invalid {label} projection")
    return cast(dict[str, Any], value)


def _objects(value: object, label: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise RuntimeError(f"alpha returned an invalid {label} projection")
    return [_object(item, label) for item in value]


def _json(value: Mapping[str, object]) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("control request must contain finite JSON values") from exc


def _page(rows: list[dict[str, Any]], *, limit: int, start: int) -> dict[str, Any]:
    return {
        "items": rows[:limit],
        "limit": limit,
        "offset": start,
        "has_more": len(rows) > limit,
    }


def research_capture(
    idea: str,
    *,
    data_dir: Path,
    name: str | None = None,
) -> dict[str, Any]:
    """Capture a raw idea; this cannot approve a contract or launch work."""
    args = ["research", "capture", idea, "--json"]
    if name is not None:
        args += ["--name", name]
    return _object(_invoke.run_json(args, data_dir=data_dir), "research capture")


def research_get(project_id: str, *, data_dir: Path) -> dict[str, Any]:
    """Read one complete bounded Research Case summary."""
    return _object(
        _invoke.run_json(["research", "status", project_id, "--json"], data_dir=data_dir),
        "research case",
    )


def research_propose(
    project_id: str,
    source_pack_id: str,
    answers: Mapping[str, str],
    *,
    data_dir: Path,
) -> dict[str, Any]:
    """Materialize an owner-reviewable contract; approval remains unavailable to MCP."""
    if set(answers) != _RESEARCH_ANSWER_KEYS or len(answers) != 3:
        raise ValueError("research answers must resolve exactly the three material questions")
    args = [
        "research",
        "draft",
        project_id,
        "--source-pack-id",
        source_pack_id,
    ]
    for key in sorted(answers):
        value = answers[key]
        if not isinstance(value, str) or not value or len(value) > 128:
            raise ValueError("research answer values must be non-empty and at most 128 characters")
        args += ["--answer", f"{key}={value}"]
    args += ["--json"]
    return _object(_invoke.run_json(args, data_dir=data_dir), "research proposal")


def research_launch(project_id: str, stage: str, *, data_dir: Path) -> dict[str, Any]:
    """Launch only the shipped D0 pilot; D1 and D2 workers are intentionally absent."""
    if stage != "pilot":
        raise ValueError("Gate-1 research launch stage must be pilot")
    return _object(
        _invoke.run_json(
            ["research", "run", stage, project_id, "--json"],
            data_dir=data_dir,
            timeout_seconds=_RESEARCH_LAUNCH_TIMEOUT_S,
        ),
        "research launch",
    )


def research_report(project_id: str, *, data_dir: Path) -> dict[str, Any]:
    """Read the progress report or terminal packet projection without changing state."""
    return _object(
        _invoke.run_json(["research", "report", project_id, "--json"], data_dir=data_dir),
        "research report",
    )


def research_context_build(
    project_id: str,
    kind: str,
    *,
    data_dir: Path,
    protocol_id: str | None = None,
    symbol: str | None = None,
) -> dict[str, Any]:
    """Record one bounded, content-addressed context packet; recording is visibility."""
    args = ["research", "context", "build", project_id, "--kind", kind, "--created-by", "codex"]
    if protocol_id is not None:
        args += ["--protocol", protocol_id]
    if symbol is not None:
        args += ["--symbol", symbol]
    args += ["--json"]
    return _object(_invoke.run_json(args, data_dir=data_dir), "research context packet")


def research_context_get(packet_id: str, *, data_dir: Path) -> dict[str, Any]:
    """Return one recorded packet byte-identically."""
    return _object(
        _invoke.run_json(["research", "context", "show", packet_id, "--json"], data_dir=data_dir),
        "research context packet",
    )


def research_note_add(
    project_id: str,
    note_kind: str,
    body: str,
    *,
    data_dir: Path,
    context_packet_id: str | None = None,
) -> dict[str, Any]:
    """Append agent commentary; MCP notes can never claim owner authorship."""
    args = [
        "research",
        "note",
        "add",
        project_id,
        "--kind",
        note_kind,
        "--body",
        body,
        "--author",
        "codex",
        "--author-kind",
        "agent",
    ]
    if context_packet_id is not None:
        args += ["--packet", context_packet_id]
    args += ["--json"]
    return _object(_invoke.run_json(args, data_dir=data_dir), "research note")


def research_brief(project_id: str, *, data_dir: Path) -> dict[str, Any]:
    """Build the "Resume with Codex" delta brief (recorded as a packet)."""
    return _object(
        _invoke.run_json(
            ["research", "brief", project_id, "--created-by", "codex", "--json"],
            data_dir=data_dir,
        ),
        "research brief",
    )


def research_protocols_list(*, data_dir: Path) -> dict[str, Any]:
    """List the Git-owned protocol library (index↔file drift fails loud)."""
    return _object(
        _invoke.run_json(["research", "protocols", "list", "--json"], data_dir=data_dir),
        "research protocols",
    )


def research_protocol_get(protocol_id: str, *, data_dir: Path) -> dict[str, Any]:
    """Read one protocol entry plus its exact content."""
    return _object(
        _invoke.run_json(
            ["research", "protocols", "show", protocol_id, "--json"], data_dir=data_dir
        ),
        "research protocol",
    )


def research_sources_search(query: str, *, data_dir: Path, limit: int = 50) -> dict[str, Any]:
    """Local-records-only source search; the network stays behind the isolated worker."""
    limit = bound("limit", limit, 200)
    return _object(
        _invoke.run_json(
            ["research", "sources", "search", query, "--limit", str(limit), "--json"],
            data_dir=data_dir,
        ),
        "research source search",
    )


def research_source_get(source_id: str, *, data_dir: Path) -> dict[str, Any]:
    """Read one immutable source record (the ``sources screen`` read projection)."""
    return _object(
        _invoke.run_json(["research", "sources", "screen", source_id, "--json"], data_dir=data_dir),
        "research source",
    )


def source_claim_draft(
    project_id: str,
    *,
    data_dir: Path,
    source_id: str,
    contract_id: str,
    claim_text: str,
    direction: str,
    strength: str,
    method_summary: str,
    sample_summary: str,
    markets: Sequence[str],
    limitations: str,
    source_anchor: Mapping[str, object] | None = None,
) -> dict[str, Any]:
    """Draft one claim; MCP claims are always agent-authored and never screened here."""
    args = [
        "research",
        "sources",
        "claim",
        "add",
        project_id,
        "--source-id",
        source_id,
        "--contract-id",
        contract_id,
        "--text",
        claim_text,
        "--direction",
        direction,
        "--strength",
        strength,
        "--method",
        method_summary,
        "--sample",
        sample_summary,
        "--limitations",
        limitations,
        "--author",
        "codex",
        "--author-kind",
        "agent",
    ]
    for market in markets:
        args += ["--market", market]
    if source_anchor is not None:
        args += ["--anchor-json", _json(source_anchor)]
    args += ["--json"]
    return _object(_invoke.run_json(args, data_dir=data_dir), "research source claim")


def data_inventory(*, data_dir: Path) -> dict[str, Any]:
    """Every stored symbol — the starting point of data feasibility."""
    return _object(_invoke.run_json(["data", "symbols", "--json"], data_dir=data_dir), "symbols")


def data_quality(symbol: str, *, data_dir: Path) -> dict[str, Any]:
    """One symbol's source/qualification/promotion status (read-only)."""
    return _object(
        _invoke.run_json(["data", "source-status", symbol, "--json"], data_dir=data_dir),
        "source status",
    )


def data_candles(
    symbol: str,
    *,
    data_dir: Path,
    start: str | None = None,
    end: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    """Bounded point-in-time candle preview (last ``limit`` bars, ≤500 like discovery)."""
    limit = bound("limit", limit, 500)
    args = ["data", "candles", symbol]
    if start is not None:
        args += ["--start", start]
    if end is not None:
        args += ["--end", end]
    args += ["--json"]
    payload = _object(_invoke.run_json(args, data_dir=data_dir), "candles")
    bars = payload.get("bars")
    if not isinstance(bars, list):
        raise RuntimeError("alpha returned an invalid candles projection")
    truncated = len(bars) > limit
    return {**payload, "bars": bars[-limit:], "truncated": truncated}


def snapshots(*, data_dir: Path) -> dict[str, Any]:
    """Every immutable snapshot's manifest summary."""
    return _object(
        _invoke.run_json(["data", "snapshots", "--json"], data_dir=data_dir), "snapshots"
    )


def provider_registry(*, data_dir: Path) -> dict[str, Any]:
    """The redacted provider capability/limitation registry (never probes the network)."""
    rows = _objects(
        _invoke.run_json(["info", "providers", "--json"], data_dir=data_dir), "providers"
    )
    return {"providers": rows}


def list_projects(*, data_dir: Path, limit: int, start: int) -> dict[str, Any]:
    limit = bound("limit", limit, 100)
    start = offset(start)
    rows = _objects(
        _invoke.run_json(
            [
                "project",
                "list",
                "--limit",
                str(limit + 1),
                "--offset",
                str(start),
                "--json",
            ],
            data_dir=data_dir,
        ),
        "project list",
    )
    return _page(rows, limit=limit, start=start)


def get_project(project_id: str, *, data_dir: Path, lineage_limit: int) -> dict[str, Any]:
    lineage_limit = bound("lineage_limit", lineage_limit, 200)
    row = _object(
        _invoke.run_json(
            [
                "project",
                "show",
                project_id,
                "--lineage-limit",
                str(lineage_limit),
                "--json",
            ],
            data_dir=data_dir,
        ),
        "project",
    )
    upstream_truncated = _object(row.get("truncated"), "project truncation")
    truncated: dict[str, bool] = {}
    for key in (
        "versions",
        "experiments",
        "stage_states",
        "stage_run_links",
        "attempts",
        "holdouts",
        "holdout_audit",
        "decision_packets",
        "monte_carlo_reviews",
        "research_gate_overrides",
    ):
        values = _objects(row.get(key), f"project {key}")
        truncated[key] = bool(upstream_truncated.get(key, False)) or len(values) > lineage_limit
        row[key] = values[-lineage_limit:]
    for link in _objects(row["stage_run_links"], "stage links"):
        history = _objects(link.get("state_history"), "stage state history")
        link["state_history"] = history[-lineage_limit:]
        link["state_history_truncated"] = (
            bool(link.get("state_history_truncated", False)) or len(history) > lineage_limit
        )
    for stage in _objects(row["stage_states"], "experiment stage states"):
        history = _objects(stage.get("state_history"), "experiment stage state history")
        stage["state_history"] = history[-lineage_limit:]
        stage["state_history_truncated"] = (
            bool(stage.get("state_history_truncated", False)) or len(history) > lineage_limit
        )
    row["truncated"] = truncated
    return row


def get_version(project_id: str, version_id: str, *, data_dir: Path) -> dict[str, Any]:
    return _object(
        _invoke.run_json(
            ["project", "version-show", project_id, version_id, "--json"],
            data_dir=data_dir,
        ),
        "strategy version",
    )


def get_experiment(project_id: str, experiment_id: str, *, data_dir: Path) -> dict[str, Any]:
    return _object(
        _invoke.run_json(
            ["project", "experiment-show", project_id, experiment_id, "--json"],
            data_dir=data_dir,
        ),
        "experiment",
    )


def create_project(
    *, data_dir: Path, name: str, hypothesis: str, falsification: str
) -> dict[str, Any]:
    return _object(
        _invoke.run_json(
            [
                "project",
                "create",
                name,
                "--hypothesis",
                hypothesis,
                "--falsification",
                falsification,
                "--json",
            ],
            data_dir=data_dir,
        ),
        "project",
    )


def create_version(
    project_id: str,
    *,
    data_dir: Path,
    strategy_name: str,
    source_fingerprint: str,
    definition: Mapping[str, object],
    parameter_space: Mapping[str, object],
) -> dict[str, Any]:
    return _object(
        _invoke.run_json(
            [
                "project",
                "version",
                project_id,
                "--strategy",
                strategy_name,
                "--source-fingerprint",
                source_fingerprint,
                "--definition-json",
                _json(definition),
                "--parameter-space-json",
                _json(parameter_space),
                "--json",
            ],
            data_dir=data_dir,
        ),
        "strategy version",
    )


def create_experiment(
    project_id: str,
    *,
    data_dir: Path,
    version_id: str,
    snapshot_id: str,
    universe: Sequence[str],
    split_policy: Mapping[str, object],
    costs: Mapping[str, object],
    seeds: Mapping[str, object],
    stage_config: Mapping[str, object],
) -> dict[str, Any]:
    return _object(
        _invoke.run_json(
            [
                "project",
                "experiment",
                project_id,
                "--version-id",
                version_id,
                "--snapshot",
                snapshot_id,
                "--universe",
                ",".join(universe),
                "--split-policy-json",
                _json(split_policy),
                "--costs-json",
                _json(costs),
                "--seeds-json",
                _json(seeds),
                "--stage-config-json",
                _json(stage_config),
                "--json",
            ],
            data_dir=data_dir,
        ),
        "experiment",
    )


def link_run(
    project_id: str,
    experiment_id: str,
    stage: str,
    state: str,
    run_id: str,
    *,
    data_dir: Path,
) -> dict[str, Any]:
    row = _object(
        _invoke.run_json(
            [
                "project",
                "link-run",
                project_id,
                experiment_id,
                run_id,
                "--stage",
                stage,
                "--state",
                state,
                "--json",
            ],
            data_dir=data_dir,
        ),
        "stage link",
    )
    row["state_history_truncated"] = False
    return row


def advance_stage(link_id: str, state: str, reason: str, *, data_dir: Path) -> dict[str, Any]:
    row = _object(
        _invoke.run_json(
            [
                "project",
                "stage-state",
                link_id,
                state,
                "--reason",
                reason,
                "--json",
            ],
            data_dir=data_dir,
        ),
        "stage link",
    )
    row["state_history_truncated"] = False
    return row


def advance_experiment_stage(
    project_id: str,
    experiment_id: str,
    stage: str,
    state: str,
    reason: str,
    *,
    data_dir: Path,
) -> dict[str, Any]:
    """Append a legal lifecycle transition independent of any completed run link."""
    row = _object(
        _invoke.run_json(
            [
                "project",
                "stage-transition",
                project_id,
                experiment_id,
                stage,
                state,
                "--reason",
                reason,
                "--json",
            ],
            data_dir=data_dir,
        ),
        "experiment stage state",
    )
    row["state_history_truncated"] = False
    return row


def record_attempt(
    project_id: str,
    experiment_id: str,
    stage: str,
    status: str,
    config_fingerprint: str,
    *,
    data_dir: Path,
    run_id: str | None,
    error: str | None,
    details: Mapping[str, object],
) -> dict[str, Any]:
    args = [
        "project",
        "attempt",
        project_id,
        experiment_id,
        "--stage",
        stage,
        "--status",
        status,
        "--config-fingerprint",
        config_fingerprint,
        "--details-json",
        _json(details),
    ]
    if run_id is not None:
        args += ["--run-id", run_id]
    if error is not None:
        args += ["--error", error]
    args.append("--json")
    return _object(_invoke.run_json(args, data_dir=data_dir), "attempt")


def seal_holdout(
    project_id: str,
    experiment_id: str,
    actor: str,
    reason: str,
    start_date: str,
    end_date: str,
    *,
    data_dir: Path,
) -> dict[str, Any]:
    return _object(
        _invoke.run_json(
            [
                "project",
                "seal-holdout",
                project_id,
                experiment_id,
                "--actor",
                actor,
                "--reason",
                reason,
                "--start-date",
                start_date,
                "--end-date",
                end_date,
                "--json",
            ],
            data_dir=data_dir,
        ),
        "holdout seal",
    )


def agent_brief(
    project_id: str,
    *,
    data_dir: Path,
    evidence_limit: int,
    as_of: str | None,
) -> dict[str, Any]:
    evidence_limit = bound("evidence_limit", evidence_limit, 100)
    args = [
        "project",
        "agent-brief",
        project_id,
        "--evidence-limit",
        str(evidence_limit),
    ]
    if as_of is not None:
        args += ["--as-of", as_of]
    args.append("--json")
    return _object(_invoke.run_json(args, data_dir=data_dir), "AgentBrief")


def create_job(
    kind: str,
    request: Mapping[str, object],
    *,
    data_dir: Path,
    project_id: str | None,
    experiment_id: str | None,
) -> dict[str, Any]:
    args = ["project", "job-create", kind, "--request-json", _json(request)]
    if project_id is not None:
        args += ["--project-id", project_id]
    if experiment_id is not None:
        args += ["--experiment-id", experiment_id]
    args.append("--json")
    return _object(_invoke.run_json(args, data_dir=data_dir), "development job")


def list_jobs(*, data_dir: Path, limit: int, start: int) -> dict[str, Any]:
    limit = bound("limit", limit, 100)
    start = offset(start)
    rows = _objects(
        _invoke.run_json(
            [
                "project",
                "job-list",
                "--limit",
                str(limit + 1),
                "--offset",
                str(start),
                "--json",
            ],
            data_dir=data_dir,
        ),
        "development jobs",
    )
    return _page(rows, limit=limit, start=start)


def get_job(
    job_id: str, *, data_dir: Path, event_limit: int, event_offset: int = 0
) -> dict[str, Any]:
    event_limit = bound("event_limit", event_limit, 200)
    event_offset = offset(event_offset)
    row = _object(
        _invoke.run_json(
            [
                "project",
                "job-show",
                job_id,
                "--event-limit",
                str(event_limit),
                "--event-offset",
                str(event_offset),
                "--event-tail",
                "--json",
            ],
            data_dir=data_dir,
        ),
        "development job",
    )
    row["events"] = _objects(row.get("events"), "development job events")
    return row


def suite_plan(
    project_id: str,
    experiment_id: str,
    action: str,
    *,
    data_dir: Path,
) -> dict[str, Any]:
    if action not in _SUITE_ACTIONS:
        raise ValueError(f"unsupported suite action {action!r}")
    return _object(
        _invoke.run_json(
            ["suite", "plan", project_id, experiment_id, action, "--json"],
            data_dir=data_dir,
        ),
        "suite plan",
    )


def launch_suite(
    project_id: str,
    experiment_id: str,
    action: str,
    *,
    data_dir: Path,
) -> dict[str, Any]:
    """Launch only a fixed safe suite action; owner-only holdout reveal is never callable."""
    if action not in _AGENT_RUNNABLE_SUITE_ACTIONS:
        if action == "holdout_reveal":
            raise ValueError("holdout_reveal is owner-only and unavailable through MCP")
        raise ValueError(f"unsupported suite action {action!r}")
    job_id = str(uuid.uuid4())
    reservation = _object(
        _invoke.run_json(
            [
                "suite",
                "reserve",
                project_id,
                experiment_id,
                action,
                "--job-id",
                job_id,
                "--json",
            ],
            data_dir=data_dir,
        ),
        "suite reservation",
    )
    plan = _object(reservation.get("plan"), "suite reservation plan")
    env = {**os.environ, "ALPHA_DATA_DIR": str(data_dir)}
    try:
        subprocess.Popen(
            [
                "alpha",
                "suite",
                "run",
                project_id,
                experiment_id,
                action,
                "--job-id",
                job_id,
                "--json",
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
            start_new_session=True,
        )
    except OSError as exc:
        failure = "allowlisted alpha suite worker could not be launched"
        try:
            _invoke.run_json(
                [
                    "project",
                    "job-status",
                    job_id,
                    "failed",
                    "--terminal-error",
                    failure,
                    "--json",
                ],
                data_dir=data_dir,
            )
        except RuntimeError as mark_exc:
            raise RuntimeError(
                f"{failure}; durable reservation also could not be failed"
            ) from mark_exc
        raise RuntimeError("could not launch the allowlisted alpha suite worker") from exc
    return {"job_id": job_id, "status": "starting", "plan": plan}


def cancel_job(job_id: str, *, data_dir: Path, reason: str) -> dict[str, Any]:
    job = get_job(job_id, data_dir=data_dir, event_limit=1)
    if not str(job.get("kind", "")).startswith("suite:"):
        raise ValueError("only resolved suite jobs can be cancelled through MCP")
    return _object(
        _invoke.run_json(
            [
                "project",
                "job-cancel",
                job_id,
                "--actor",
                "mcp-agent",
                "--reason",
                reason,
                "--json",
            ],
            data_dir=data_dir,
        ),
        "job cancellation",
    )


def reconcile_jobs(*, data_dir: Path, stale_after_seconds: int) -> dict[str, Any]:
    if isinstance(stale_after_seconds, bool) or not 30 <= stale_after_seconds <= 86_400:
        raise ValueError("stale_after_seconds must be in 30..86400")
    rows = _objects(
        _invoke.run_json(
            [
                "project",
                "job-reconcile",
                "--stale-after-seconds",
                str(stale_after_seconds),
                "--json",
            ],
            data_dir=data_dir,
        ),
        "reconciled jobs",
    )
    return {"items": rows, "count": len(rows)}


def search_evidence(
    *,
    data_dir: Path,
    asset: str | None,
    project_id: str | None,
    status: str | None,
    as_of: str | None,
    limit: int,
    start: int,
) -> dict[str, Any]:
    limit = bound("limit", limit, 100)
    start = offset(start)
    args = [
        "evidence",
        "list",
        "--limit",
        str(limit + 1),
        "--offset",
        str(start),
    ]
    for flag, value in (
        ("--asset", asset),
        ("--project-id", project_id),
        ("--status", status),
        ("--as-of", as_of),
    ):
        if value is not None:
            args += [flag, value]
    args.append("--json")
    rows = _objects(_invoke.run_json(args, data_dir=data_dir), "evidence list")
    return _page(rows, limit=limit, start=start)


def get_evidence(evidence_id: str, *, data_dir: Path, revision_limit: int) -> dict[str, Any]:
    revision_limit = bound("revision_limit", revision_limit, 200)
    row = _object(
        _invoke.run_json(["evidence", "show", evidence_id, "--json"], data_dir=data_dir),
        "evidence",
    )
    revisions = _objects(row.get("revisions"), "evidence revisions")
    row["revisions"] = revisions[-revision_limit:]
    row["revisions_truncated"] = len(revisions) > revision_limit
    return row


def draft_evidence(body: Mapping[str, object], *, data_dir: Path) -> dict[str, Any]:
    args = [
        "evidence",
        "add",
        str(body["claim"]),
        "--assets",
        ",".join(cast(Sequence[str], body["assets"])),
        "--frozen-universe",
        ",".join(cast(Sequence[str], body["frozen_universe"])),
        "--method",
        str(body["method"]),
        "--knowledge-at",
        str(body["knowledge_at"]),
        "--author",
        str(body["author"]),
        "--author-kind",
        "agent",
        "--timeframe",
        str(body["timeframe"]),
        "--source-run-id",
        str(body["source_run_id"]),
        "--source-artifact",
        str(body["source_artifact"]),
        "--source-field",
        str(body["source_field"]),
        "--row-selector-json",
        _json(cast(dict[str, object], body["row_selector"])),
    ]
    for flag, key in (
        ("--market-data-cutoff", "market_data_cutoff"),
        ("--project-id", "project_id"),
        ("--strategy-version-id", "strategy_version_id"),
        ("--experiment-id", "experiment_id"),
        ("--metric-name", "metric_name"),
        ("--metric-value", "metric_value"),
        ("--metric-unit", "metric_unit"),
    ):
        value = body.get(key)
        if value is not None:
            args += [flag, str(value)]
    for value in cast(Sequence[str], body["counterevidence"]):
        args += ["--counterevidence", value]
    for value in cast(Sequence[str], body["contradiction_ids"]):
        args += ["--contradiction-id", value]
    args.append("--json")
    return _object(_invoke.run_json(args, data_dir=data_dir), "evidence draft")


def review_evidence(
    evidence_id: str, body: Mapping[str, object], *, data_dir: Path
) -> dict[str, Any]:
    if body.get("status") == "corroborated":
        raise ValueError("agent evidence revisions cannot grant corroborated status")
    args = [
        "evidence",
        "revise",
        evidence_id,
        "--status",
        str(body["status"]),
        "--author",
        str(body["author"]),
        "--author-kind",
        "agent",
    ]
    for flag, key in (
        ("--claim", "claim"),
        ("--source-run-id", "source_run_id"),
        ("--source-artifact", "source_artifact"),
        ("--source-field", "source_field"),
    ):
        value = body.get(key)
        if value is not None:
            args += [flag, str(value)]
    selector = body.get("row_selector")
    if selector is not None:
        args += ["--row-selector-json", _json(cast(dict[str, object], selector))]
    for flag, key in (
        ("--counterevidence", "counterevidence"),
        ("--contradiction-id", "contradiction_ids"),
    ):
        values = body.get(key)
        if values is not None:
            clean_values = cast(Sequence[str], values)
            if not clean_values:
                raise ValueError(f"{key} must be omitted or contain at least one value")
            for value in clean_values:
                args += [flag, value]
    args.append("--json")
    return _object(_invoke.run_json(args, data_dir=data_dir), "evidence revision")


__all__ = [
    "advance_experiment_stage",
    "advance_stage",
    "agent_brief",
    "bound",
    "cancel_job",
    "create_experiment",
    "create_job",
    "create_project",
    "create_version",
    "draft_evidence",
    "get_evidence",
    "get_experiment",
    "get_job",
    "get_project",
    "get_version",
    "link_run",
    "list_jobs",
    "list_projects",
    "launch_suite",
    "offset",
    "record_attempt",
    "reconcile_jobs",
    "review_evidence",
    "search_evidence",
    "seal_holdout",
    "suite_plan",
]
