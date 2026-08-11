"""Thin Workstation v3 control-plane projections over ``alpha ... --json``.

The web process never opens the CLI-owned SQLite database. Every read and mutation is expressed as
one typed CLI command; this module only bounds and shapes those JSON projections for HTTP.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast

from alpha_web._catalog import _run_json


def _object(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise RuntimeError(f"alpha returned an invalid {label} projection")
    return cast(dict[str, object], value)


def _objects(value: object, label: str) -> list[dict[str, object]]:
    if not isinstance(value, list):
        raise RuntimeError(f"alpha returned an invalid {label} projection")
    return [_object(item, label) for item in value]


def _json(value: Mapping[str, object]) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("control-plane request must contain finite JSON values") from exc


def _page(rows: list[dict[str, object]], *, limit: int, offset: int) -> dict[str, object]:
    return {
        "items": rows[:limit],
        "limit": limit,
        "offset": offset,
        "has_more": len(rows) > limit,
    }


def list_projects(*, data_dir: Path, limit: int, offset: int) -> dict[str, object]:
    rows = _objects(
        _run_json(
            [
                "project",
                "list",
                "--limit",
                str(limit + 1),
                "--offset",
                str(offset),
                "--json",
            ],
            data_dir=data_dir,
        ),
        "project list",
    )
    return _page(rows, limit=limit, offset=offset)


def create_project(
    *,
    data_dir: Path,
    name: str,
    hypothesis: str,
    falsification_criterion: str,
) -> dict[str, object]:
    return _object(
        _run_json(
            [
                "project",
                "create",
                name,
                "--hypothesis",
                hypothesis,
                "--falsification",
                falsification_criterion,
                "--json",
            ],
            data_dir=data_dir,
        ),
        "project",
    )


def project_detail(project_id: str, *, data_dir: Path, lineage_limit: int) -> dict[str, object]:
    project = _object(
        _run_json(
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
    upstream_truncation = _object(project.get("truncated"), "project truncation")
    truncation: dict[str, bool] = {}
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
        rows = _objects(project.get(key), f"project {key}")
        truncation[key] = bool(upstream_truncation.get(key, False)) or len(rows) > lineage_limit
        project[key] = rows[-lineage_limit:]
    links = _objects(project["stage_run_links"], "stage links")
    for link in links:
        history = _objects(link.get("state_history"), "stage state history")
        link["state_history_truncated"] = (
            bool(link.get("state_history_truncated", False)) or len(history) > lineage_limit
        )
        link["state_history"] = history[-lineage_limit:]
    project["stage_run_links"] = links
    stages = _objects(project["stage_states"], "experiment stage states")
    for stage in stages:
        history = _objects(stage.get("state_history"), "experiment stage state history")
        stage["state_history_truncated"] = (
            bool(stage.get("state_history_truncated", False)) or len(history) > lineage_limit
        )
        stage["state_history"] = history[-lineage_limit:]
    project["stage_states"] = stages
    project["truncated"] = truncation
    return project


def active_research_gate_overrides(
    *, data_dir: Path, limit: int, offset: int
) -> list[dict[str, object]]:
    return _objects(
        _run_json(
            [
                "project",
                "research-gate-overrides",
                "--limit",
                str(limit),
                "--offset",
                str(offset),
                "--json",
            ],
            data_dir=data_dir,
        ),
        "active research gate overrides",
    )


def strategy_version(project_id: str, version_id: str, *, data_dir: Path) -> dict[str, object]:
    return _object(
        _run_json(
            ["project", "version-show", project_id, version_id, "--json"],
            data_dir=data_dir,
        ),
        "strategy version",
    )


def experiment_spec(project_id: str, experiment_id: str, *, data_dir: Path) -> dict[str, object]:
    return _object(
        _run_json(
            ["project", "experiment-show", project_id, experiment_id, "--json"],
            data_dir=data_dir,
        ),
        "experiment",
    )


def create_version(
    project_id: str,
    *,
    data_dir: Path,
    strategy_name: str,
    source_fingerprint: str,
    definition: Mapping[str, object],
    parameter_space: Mapping[str, object],
) -> dict[str, object]:
    return _object(
        _run_json(
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
) -> dict[str, object]:
    return _object(
        _run_json(
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


def link_stage_run(
    project_id: str,
    *,
    data_dir: Path,
    experiment_id: str,
    stage: str,
    state: str,
    run_id: str,
) -> dict[str, object]:
    row = _object(
        _run_json(
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


def update_stage_state(
    link_id: str, *, data_dir: Path, state: str, reason: str
) -> dict[str, object]:
    row = _object(
        _run_json(
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


def update_experiment_stage_state(
    project_id: str,
    experiment_id: str,
    stage: str,
    *,
    data_dir: Path,
    state: str,
    reason: str,
) -> dict[str, object]:
    """Append a legal lifecycle transition before or without a completed run link."""
    row = _object(
        _run_json(
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
    *,
    data_dir: Path,
    experiment_id: str,
    stage: str,
    status: str,
    config_fingerprint: str,
    run_id: str | None,
    error: str | None,
    details: Mapping[str, object],
) -> dict[str, object]:
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
    return _object(_run_json(args, data_dir=data_dir), "attempt")


def seal_holdout(
    project_id: str,
    *,
    data_dir: Path,
    experiment_id: str,
    actor: str,
    reason: str,
    start_date: str,
    end_date: str,
) -> dict[str, object]:
    return _object(
        _run_json(
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
) -> dict[str, object]:
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
    return _object(_run_json(args, data_dir=data_dir), "AgentBrief")


def list_jobs(*, data_dir: Path, limit: int, offset: int) -> dict[str, object]:
    rows = _objects(
        _run_json(
            [
                "project",
                "job-list",
                "--limit",
                str(limit + 1),
                "--offset",
                str(offset),
                "--json",
            ],
            data_dir=data_dir,
        ),
        "development job list",
    )
    return _page(rows, limit=limit, offset=offset)


def create_job(
    *,
    data_dir: Path,
    kind: str,
    request: Mapping[str, object],
    project_id: str | None,
    experiment_id: str | None,
) -> dict[str, object]:
    args = ["project", "job-create", kind, "--request-json", _json(request)]
    if project_id is not None:
        args += ["--project-id", project_id]
    if experiment_id is not None:
        args += ["--experiment-id", experiment_id]
    args.append("--json")
    return _object(_run_json(args, data_dir=data_dir), "development job")


def job_detail(
    job_id: str,
    *,
    data_dir: Path,
    event_limit: int,
    event_offset: int,
    event_tail: bool = False,
) -> dict[str, object]:
    args = [
        "project",
        "job-show",
        job_id,
        "--event-limit",
        str(event_limit),
        "--event-offset",
        str(event_offset),
    ]
    if event_tail:
        args.append("--event-tail")
    args.append("--json")
    return _object(
        _run_json(args, data_dir=data_dir),
        "development job",
    )


def suite_plan(
    project_id: str,
    experiment_id: str,
    action: str,
    *,
    data_dir: Path,
) -> dict[str, object]:
    """Resolve an allowlisted immutable suite plan through the CLI composer."""
    return _object(
        _run_json(
            ["suite", "plan", project_id, experiment_id, action, "--json"],
            data_dir=data_dir,
        ),
        "suite plan",
    )


def reserve_suite(
    project_id: str,
    experiment_id: str,
    action: str,
    job_id: str,
    *,
    data_dir: Path,
) -> dict[str, object]:
    """Persist the exact queued journal before the web transport starts its worker."""
    return _object(
        _run_json(
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


def cancel_job(job_id: str, *, data_dir: Path) -> dict[str, object]:
    return _object(
        _run_json(
            [
                "project",
                "job-cancel",
                job_id,
                "--actor",
                "workstation-owner",
                "--reason",
                "owner requested cancellation",
                "--json",
            ],
            data_dir=data_dir,
        ),
        "durable job cancellation",
    )


def cancel_suite_job(job_id: str, *, data_dir: Path) -> dict[str, object]:
    """Compatibility wrapper for the suite-specific cancellation route."""
    return cancel_job(job_id, data_dir=data_dir)


def fail_job_launch(job_id: str, *, data_dir: Path, error: str) -> dict[str, object]:
    return _object(
        _run_json(
            [
                "project",
                "job-status",
                job_id,
                "failed",
                "--terminal-error",
                error,
                "--json",
            ],
            data_dir=data_dir,
        ),
        "failed suite launch",
    )


def reconcile_jobs(*, data_dir: Path, stale_after_seconds: int) -> dict[str, object]:
    rows = _objects(
        _run_json(
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


def list_evidence(
    *,
    data_dir: Path,
    asset: str | None,
    project_id: str | None,
    status: str | None,
    as_of: str | None,
    limit: int,
    offset: int,
) -> dict[str, object]:
    args = [
        "evidence",
        "list",
        "--limit",
        str(limit + 1),
        "--offset",
        str(offset),
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
    rows = _objects(_run_json(args, data_dir=data_dir), "evidence list")
    return _page(rows, limit=limit, offset=offset)


def draft_evidence(body: Mapping[str, object], *, data_dir: Path) -> dict[str, object]:
    assets = cast(list[str], body["assets"])
    universe = cast(list[str], body["frozen_universe"])
    args = [
        "evidence",
        "add",
        str(body["claim"]),
        "--assets",
        ",".join(assets),
        "--frozen-universe",
        ",".join(universe),
        "--method",
        str(body["method"]),
        "--knowledge-at",
        str(body["knowledge_at"]),
        "--author",
        str(body["author"]),
        "--author-kind",
        str(body["author_kind"]),
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
    for value in cast(list[str], body["counterevidence"]):
        args += ["--counterevidence", value]
    for value in cast(list[str], body["contradiction_ids"]):
        args += ["--contradiction-id", value]
    args.append("--json")
    return _object(_run_json(args, data_dir=data_dir), "evidence draft")


def evidence_detail(
    evidence_id: str, *, data_dir: Path, revision_limit: int, revision_offset: int
) -> dict[str, object]:
    row = _object(
        _run_json(["evidence", "show", evidence_id, "--json"], data_dir=data_dir),
        "evidence",
    )
    revisions = _objects(row.get("revisions"), "evidence revisions")
    row["revisions"] = revisions[revision_offset : revision_offset + revision_limit]
    row["revisions_truncated"] = revision_offset + revision_limit < len(revisions)
    row["revision_limit"] = revision_limit
    row["revision_offset"] = revision_offset
    return row


def review_evidence(
    evidence_id: str, body: Mapping[str, object], *, data_dir: Path
) -> dict[str, object]:
    args = [
        "evidence",
        "revise",
        evidence_id,
        "--status",
        str(body["status"]),
        "--author",
        str(body["author"]),
        "--author-kind",
        str(body["author_kind"]),
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
    counterevidence = body.get("counterevidence")
    if counterevidence is not None:
        for value in cast(list[str], counterevidence):
            args += ["--counterevidence", value]
    contradictions = body.get("contradiction_ids")
    if contradictions is not None:
        for value in cast(list[str], contradictions):
            args += ["--contradiction-id", value]
    args.append("--json")
    return _object(_run_json(args, data_dir=data_dir), "evidence revision")


def freeze_decision(
    project_id: str,
    experiment_id: str,
    body: Mapping[str, object],
    *,
    data_dir: Path,
) -> dict[str, object]:
    """Freeze one owner decision through the CLI; no broker or order action is available."""
    args = [
        "project",
        "decide",
        project_id,
        experiment_id,
        "--verdict",
        str(body["verdict"]),
        "--actor",
        str(body["actor"]),
        "--reason",
        str(body["reason"]),
        "--acknowledge-negative-results",
        "--json",
    ]
    return _object(_run_json(args, data_dir=data_dir), "decision packet")


__all__ = [
    "agent_brief",
    "cancel_job",
    "cancel_suite_job",
    "create_experiment",
    "create_job",
    "create_project",
    "create_version",
    "draft_evidence",
    "evidence_detail",
    "experiment_spec",
    "freeze_decision",
    "fail_job_launch",
    "job_detail",
    "link_stage_run",
    "list_evidence",
    "list_jobs",
    "list_projects",
    "project_detail",
    "reconcile_jobs",
    "record_attempt",
    "review_evidence",
    "reserve_suite",
    "seal_holdout",
    "strategy_version",
    "suite_plan",
    "update_stage_state",
    "update_experiment_stage_state",
]
