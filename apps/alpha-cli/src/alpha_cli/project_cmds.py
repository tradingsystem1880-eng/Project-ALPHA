"""``alpha project`` — typed Workstation v3 strategy-development control plane."""

from __future__ import annotations

import json
from typing import cast

import typer

from alpha_cli.control_store import (
    AttemptStatus,
    ControlStore,
    DecisionVerdict,
    JobStatus,
    StageState,
    parse_timestamp,
)
from alpha_cli.research_intake import draft_exploration_contract
from alpha_core import DataError
from alpha_core.config import AlphaSettings

project_app = typer.Typer(
    help="Strategy projects, immutable versions, experiments, and audit links."
)


def _store() -> ControlStore:
    return ControlStore(AlphaSettings().data_dir)


def _object(raw: str, label: str) -> dict[str, object]:
    try:
        value: object = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(f"{label} must be a valid JSON object") from exc
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise typer.BadParameter(f"{label} must be a valid JSON object")
    return cast(dict[str, object], value)


def _emit(value: object, *, json_out: bool, fallback: str) -> None:
    if json_out:
        typer.echo(json.dumps(value, sort_keys=True, allow_nan=False))
    else:
        typer.echo(fallback)


@project_app.command("create")
def create(
    name: str,
    hypothesis: str = typer.Option(..., help="testable strategy hypothesis"),
    falsification: str = typer.Option(..., help="criterion that rejects the hypothesis"),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Create a governed strategy project and immediately capture its research case."""
    try:
        store = _store()
        draft = draft_exploration_contract(hypothesis)
        questions = draft["blocking_questions"]
        if not isinstance(questions, list):  # pragma: no cover - intake invariant.
            raise DataError("research intake returned invalid blocking questions")
        captured = store.capture_research_case(
            name=name,
            hypothesis=hypothesis,
            falsification_criterion=falsification,
            draft_payload=draft,
            created_by="codex",
            next_action=(
                f"Owner answers the {len(questions)} material definition questions in one batch."
                if questions
                else "Codex checks source and data feasibility."
            ),
            responsibility="owner" if questions else "codex",
            blocker=(
                "The primary chart, event timestamp, or outcome is materially ambiguous."
                if questions
                else None
            ),
            recovery=(
                "Answer the single bounded question batch; Codex handles technical defaults."
                if questions
                else None
            ),
        )
        row = cast(dict[str, object], captured["project"])
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit(row, json_out=json_out, fallback=f"created project {row['project_id']} {row['name']}")


@project_app.command("list")
def list_projects(
    limit: int = typer.Option(100, min=1, max=500),
    offset: int = typer.Option(0, min=0),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """List strategy projects."""
    try:
        rows = _store().list_projects(limit=limit, offset=offset)
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    if json_out:
        _emit(rows, json_out=True, fallback="")
        return
    if not rows:
        typer.echo("no strategy projects")
        return
    for row in rows:
        typer.echo(f"{row['project_id']} {row['status']} {row['name']}")


@project_app.command("show")
def show(
    project_id: str,
    lineage_limit: int = typer.Option(100, min=1, max=500),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Show bounded version, experiment, attempt, run-link, and holdout lineage."""
    try:
        row = _store().get_project(project_id)
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
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
        "research_gate_overrides",
    ):
        values = cast(list[dict[str, object]], row[key])
        truncated[key] = len(values) > lineage_limit
        row[key] = values[-lineage_limit:]
    links = cast(list[dict[str, object]], row["stage_run_links"])
    for link in links:
        history = cast(list[dict[str, object]], link["state_history"])
        link["state_history_truncated"] = len(history) > lineage_limit
        link["state_history"] = history[-lineage_limit:]
    stages = cast(list[dict[str, object]], row["stage_states"])
    for stage in stages:
        history = cast(list[dict[str, object]], stage["state_history"])
        stage["state_history_truncated"] = len(history) > lineage_limit
        stage["state_history"] = history[-lineage_limit:]
    row["truncated"] = truncated
    _emit(row, json_out=json_out, fallback=f"{row['project_id']} {row['status']} {row['name']}")


def _linked_item(
    store: ControlStore,
    project_id: str,
    *,
    collection: str,
    id_field: str,
    item_id: str,
    label: str,
) -> dict[str, object]:
    project = store.get_project(project_id)
    rows = cast(list[dict[str, object]], project[collection])
    row = next((candidate for candidate in rows if candidate[id_field] == item_id), None)
    if row is None:
        raise DataError(f"unknown {label} {item_id!r} for project {project_id!r}")
    return row


@project_app.command("version-show")
def version_show(
    project_id: str,
    version_id: str,
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Show one immutable strategy version linked to a project."""
    try:
        row = _linked_item(
            _store(),
            project_id,
            collection="versions",
            id_field="version_id",
            item_id=version_id,
            label="strategy version",
        )
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit(row, json_out=json_out, fallback=f"strategy version {row['version_id']}")


@project_app.command("experiment-show")
def experiment_show(
    project_id: str,
    experiment_id: str,
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Show one immutable experiment specification linked to a project."""
    try:
        row = _linked_item(
            _store(),
            project_id,
            collection="experiments",
            id_field="experiment_id",
            item_id=experiment_id,
            label="experiment",
        )
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit(row, json_out=json_out, fallback=f"experiment {row['experiment_id']}")


def _agent_brief(
    store: ControlStore,
    project_id: str,
    *,
    evidence_limit: int,
    as_of: str | None,
) -> dict[str, object]:
    cutoff = None if as_of is None else parse_timestamp(as_of, "as_of")
    context = store.get_agent_brief_context(
        project_id,
        as_of=cutoff,
        evidence_limit=evidence_limit + 1,
    )
    version_id = context["version_id"]
    experiment_id = context["experiment_id"]
    version = cast(dict[str, object] | None, context["strategy_version"])
    experiment = cast(dict[str, object] | None, context["experiment"])
    evidence = cast(list[dict[str, object]], context["evidence"])
    warnings: list[str] = []
    if version is None:
        warnings.append("no immutable strategy version is selected")
    if experiment is None:
        warnings.append("no immutable experiment specification is selected")
    elif experiment.get("strategy_version_id") != version_id:
        warnings.append(
            "selected experiment belongs to a prior strategy version and its stages are stale"
        )
    if context["scope_history_complete"] is not True:
        warnings.append("point-in-time project scope is unavailable before the recorded lineage")
    research_promotion = cast(dict[str, object] | None, context["research_promotion"])
    if (
        version is not None
        and version.get("research_contract_id") is not None
        and research_promotion is None
    ):
        warnings.append(
            "the linked research case has no recorded promotion dossier (pre-R6f decision)"
        )
    holdout_events = cast(list[dict[str, object]], context["holdout_events"])
    holdout_event_names = {str(row["event"]) for row in holdout_events}
    if "revealed" in holdout_event_names:
        warnings.append("final holdout is visible and must not be used for model selection")
    if "contaminated" in holdout_event_names:
        warnings.append("final holdout is contaminated for this lineage")
    scope = {
        "version_id": version_id,
        "experiment_id": experiment_id,
        "snapshot_id": None if experiment is None else experiment["snapshot_id"],
        "universe": [] if experiment is None else experiment["universe"],
    }
    return {
        "schema_version": 1,
        "project_id": context["project_id"],
        "project_name": context["project_name"],
        "hypothesis": context["hypothesis"],
        "falsification_criterion": context["falsification_criterion"],
        "allowed_scope": scope,
        "strategy_version": version,
        "experiment": experiment,
        "research_promotion": research_promotion,
        "stage_statuses": context["stage_statuses"],
        "evidence": evidence[:evidence_limit],
        "evidence_truncated": len(evidence) > evidence_limit,
        "knowledge_cutoff": as_of,
        "required_tests": [
            "baseline",
            "oos",
            "robustness",
            "optimization",
            "portfolio",
            "holdout",
            "paper",
        ],
        "warnings": warnings,
    }


@project_app.command("agent-brief")
def agent_brief(
    project_id: str,
    evidence_limit: int = typer.Option(50, min=1, max=100),
    as_of: str | None = typer.Option(None, help="point-in-time UTC knowledge cutoff"),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Prepare a bounded, evidence-cited scope packet for Codex or another agent."""
    try:
        row = _agent_brief(
            _store(),
            project_id,
            evidence_limit=evidence_limit,
            as_of=as_of,
        )
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit(row, json_out=json_out, fallback=f"agent brief for {row['project_id']}")


@project_app.command("override-research-gate")
def override_research_gate(
    project_id: str,
    actor: str = typer.Option(..., help="owner identity recorded on the override event"),
    reason: str = typer.Option(..., help="why exploratory work may precede research completion"),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Record an append-only owner research-gate override (trusted-local authority).

    Overridden projects carry research_gate_state="overridden" and every run launched
    under them is watermarked EXPLORATORY / RESEARCH GATE NOT COMPLETED — the override
    makes premature strategy work visible, never validated.
    """
    try:
        row = _store().record_research_gate_override(project_id, actor=actor, reason=reason)
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit(
        row,
        json_out=json_out,
        fallback=(
            f"research gate override {row['sequence']} recorded for {row['project_id']} "
            "(runs stay watermarked EXPLORATORY / RESEARCH GATE NOT COMPLETED)"
        ),
    )


@project_app.command("research-gate-overrides")
def research_gate_overrides(
    limit: int = typer.Option(100, min=1, max=500),
    offset: int = typer.Option(0, min=0),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """List override events on projects whose research gate is currently overridden."""
    try:
        rows = _store().list_active_research_gate_overrides(limit=limit, offset=offset)
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    if json_out:
        _emit(rows, json_out=True, fallback="")
        return
    if not rows:
        typer.echo("no active research gate overrides")
        return
    for row in rows:
        typer.echo(
            f"{row['project_id']} #{row['sequence']} {row['actor']} "
            f"{row['recorded_at']} {row['project_name']}"
        )


@project_app.command("version")
def version(
    project_id: str,
    strategy: str = typer.Option(..., help="registered strategy or explicit development name"),
    source_fingerprint: str = typer.Option(..., help="git/source execution fingerprint"),
    definition_json: str = typer.Option("{}", help="normalized strategy definition JSON object"),
    parameter_space_json: str = typer.Option("{}", help="declared parameter-space JSON object"),
    research_contract_id: str | None = typer.Option(
        None,
        help="owner-advanced confirmation contract required for a research-enabled project",
    ),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Create or reuse an immutable, content-addressed strategy version."""
    try:
        row = _store().create_strategy_version(
            project_id,
            strategy_name=strategy,
            source_fingerprint=source_fingerprint,
            definition=_object(definition_json, "--definition-json"),
            parameter_space=_object(parameter_space_json, "--parameter-space-json"),
            research_contract_id=research_contract_id,
        )
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit(row, json_out=json_out, fallback=f"strategy version {row['version_id']}")


@project_app.command("experiment")
def experiment(
    project_id: str,
    version_id: str = typer.Option(..., help="content-addressed strategy version"),
    snapshot: str = typer.Option(..., help="immutable ALPHA snapshot id"),
    universe: str = typer.Option(..., help="comma-separated frozen symbols"),
    split_policy_json: str = typer.Option(..., help="OOS/holdout split JSON object"),
    costs_json: str = typer.Option(..., help="fee/slippage JSON object"),
    seeds_json: str = typer.Option(..., help="semantic seed JSON object"),
    stage_config_json: str = typer.Option("{}", help="stage configuration JSON object"),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Create or reuse an immutable, content-addressed experiment specification."""
    symbols = [item.strip() for item in universe.split(",") if item.strip()]
    try:
        row = _store().create_experiment_spec(
            project_id,
            strategy_version_id=version_id,
            snapshot_id=snapshot,
            universe=symbols,
            split_policy=_object(split_policy_json, "--split-policy-json"),
            costs=_object(costs_json, "--costs-json"),
            seeds=_object(seeds_json, "--seeds-json"),
            stage_config=_object(stage_config_json, "--stage-config-json"),
        )
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit(row, json_out=json_out, fallback=f"experiment {row['experiment_id']}")


@project_app.command("link-run")
def link_run(
    project_id: str,
    experiment_id: str,
    run_id: str,
    stage: str = typer.Option(..., help="development lifecycle stage"),
    state: str = typer.Option(..., help="pass|warning|fail|queued|running|stale"),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Link one completed canonical run to a development stage."""
    try:
        row = _store().link_stage_run(
            project_id,
            experiment_id,
            stage=stage,
            state=cast(StageState, state),
            run_id=run_id,
        )
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit(row, json_out=json_out, fallback=f"linked {run_id} to {stage}: {state}")


@project_app.command("attempt")
def attempt(
    project_id: str,
    experiment_id: str,
    stage: str = typer.Option(...),
    status: str = typer.Option(...),
    config_fingerprint: str = typer.Option(...),
    run_id: str | None = typer.Option(None),
    error: str | None = typer.Option(None),
    details_json: str = typer.Option("{}"),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Append an immutable attempted, failed, pruned, or completed configuration."""
    try:
        row = _store().record_attempt(
            project_id,
            experiment_id,
            stage=stage,
            status=cast(AttemptStatus, status),
            config_fingerprint=config_fingerprint,
            run_id=run_id,
            error=error,
            details=_object(details_json, "--details-json"),
        )
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit(row, json_out=json_out, fallback=f"attempt {row['attempt_id']} {row['status']}")


@project_app.command("stage-state")
def stage_state(
    link_id: str,
    state: str,
    reason: str = typer.Option(...),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Append a legal state transition to a stage/run link."""
    try:
        row = _store().append_stage_state(
            link_id,
            cast(StageState, state),
            reason=reason,
        )
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit(row, json_out=json_out, fallback=f"stage link {link_id} {row['state']}")


@project_app.command("stage-transition")
def stage_transition(
    project_id: str,
    experiment_id: str,
    stage: str,
    state: str,
    reason: str = typer.Option(...),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Advance an experiment lifecycle stage before or without a completed run link."""
    try:
        row = _store().append_experiment_stage_state(
            project_id,
            experiment_id,
            stage,
            cast(StageState, state),
            reason=reason,
        )
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit(row, json_out=json_out, fallback=f"stage {stage} {row['state']}")


@project_app.command("seal-holdout")
def seal_holdout(
    project_id: str,
    experiment_id: str,
    actor: str = typer.Option(...),
    reason: str = typer.Option(...),
    start_date: str = typer.Option(..., help="inclusive sealed YYYY-MM-DD boundary"),
    end_date: str = typer.Option(..., help="inclusive sealed YYYY-MM-DD boundary"),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Seal an immutable experiment before its final holdout can be revealed."""
    try:
        row = _store().seal_holdout(
            project_id,
            experiment_id,
            actor=actor,
            reason=reason,
            start_date=start_date,
            end_date=end_date,
        )
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit(row, json_out=json_out, fallback=f"sealed holdout {experiment_id}")


@project_app.command("reveal-holdout")
def reveal_holdout(
    project_id: str,
    experiment_id: str,
    actor: str = typer.Option(...),
    reason: str = typer.Option(...),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Permanently audit a one-shot final-holdout reveal."""
    try:
        row = _store().reveal_holdout(
            project_id,
            experiment_id,
            actor=actor,
            reason=reason,
        )
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit(row, json_out=json_out, fallback=f"revealed holdout {experiment_id}")


@project_app.command("decide")
def decide(
    project_id: str,
    experiment_id: str,
    verdict: str = typer.Option(..., help="accept|reject|revise"),
    actor: str = typer.Option(..., help="owner freezing the decision"),
    reason: str = typer.Option(..., help="decision rationale"),
    acknowledge_negative_results: bool = typer.Option(
        False,
        "--acknowledge-negative-results",
        help="confirm failed, pruned, rejected, and cancelled attempts were reviewed",
    ),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Freeze one sandbox-only accept/reject/revise decision packet."""
    try:
        row = _store().freeze_decision_packet(
            project_id,
            experiment_id,
            verdict=cast(DecisionVerdict, verdict),
            actor=actor,
            reason=reason,
            negative_results_acknowledged=acknowledge_negative_results,
        )
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit(
        row,
        json_out=json_out,
        fallback=f"decision {row['packet_id']} {row['verdict']} (sandbox only)",
    )


@project_app.command("job-create")
def job_create(
    kind: str,
    request_json: str = typer.Option("{}"),
    project_id: str | None = typer.Option(None),
    experiment_id: str | None = typer.Option(None),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Create a durable queued development job."""
    try:
        row = _store().create_job(
            kind=kind,
            request=_object(request_json, "--request-json"),
            project_id=project_id,
            experiment_id=experiment_id,
        )
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit(row, json_out=json_out, fallback=f"queued job {row['job_id']}")


@project_app.command("job-status")
def job_status(
    job_id: str,
    status: str,
    result_run_id: str | None = typer.Option(None),
    terminal_error: str | None = typer.Option(None),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Advance a durable job lifecycle."""
    try:
        row = _store().set_job_status(
            job_id,
            cast(JobStatus, status),
            result_run_id=result_run_id,
            terminal_error=terminal_error,
        )
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit(row, json_out=json_out, fallback=f"job {job_id} {row['status']}")


@project_app.command("job-capacity")
def job_capacity(
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Show exact occupancy of the shared Qlib/Kronos heavyweight class."""
    row = _store().heavyweight_job_capacity()
    _emit(
        row,
        json_out=json_out,
        fallback=f"heavyweight jobs {row['active_count']}/{row['limit']}",
    )


@project_app.command("job-event")
def job_event(
    job_id: str,
    event_type: str,
    payload_json: str = typer.Option("{}"),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Append a heartbeat, progress, or log event to a live job."""
    try:
        row = _store().append_job_event(
            job_id,
            event_type=event_type,
            payload=_object(payload_json, "--payload-json"),
        )
        if event_type == "heartbeat":
            row = {
                **row,
                "cancel_requested": _store().job_cancellation_requested(job_id),
            }
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit(row, json_out=json_out, fallback=f"job {job_id} event {row['sequence']}")


@project_app.command("job-show")
def job_show(
    job_id: str,
    event_limit: int = typer.Option(200, min=1, max=500),
    event_offset: int = typer.Option(0, min=0),
    event_tail: bool = typer.Option(
        False,
        "--event-tail",
        help="page backward from the newest events while returning rows chronologically",
    ),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Show a durable job and a bounded window of its append-only event journal."""
    try:
        row = _store().get_job(
            job_id,
            event_limit=event_limit,
            event_offset=event_offset,
            event_tail=event_tail,
        )
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit(row, json_out=json_out, fallback=f"job {job_id} {row['status']}")


@project_app.command("job-cancel")
def job_cancel(
    job_id: str,
    actor: str = typer.Option(...),
    reason: str = typer.Option(...),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Persist an idempotent cancellation request for the owning durable worker to observe."""
    try:
        row = _store().request_job_cancellation(job_id, actor=actor, reason=reason)
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit(row, json_out=json_out, fallback=f"job {job_id} {row['status']}")


@project_app.command("job-cancel-requested")
def job_cancel_requested(
    job_id: str,
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Project whether the owning worker must honour an audited cancellation request."""
    try:
        requested = _store().job_cancellation_requested(job_id)
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    row = {"job_id": job_id, "cancel_requested": requested}
    _emit(
        row,
        json_out=json_out,
        fallback=f"job {job_id} cancel requested: {str(requested).lower()}",
    )


@project_app.command("job-list")
def job_list(
    limit: int = typer.Option(100, min=1, max=500),
    offset: int = typer.Option(0, min=0),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """List durable development jobs."""
    try:
        rows = _store().list_jobs(limit=limit, offset=offset)
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    if json_out:
        _emit(rows, json_out=True, fallback="")
        return
    if not rows:
        typer.echo("no development jobs")
        return
    for row in rows:
        typer.echo(f"{row['job_id']} {row['status']} {row['kind']}")


@project_app.command("job-reconcile")
def job_reconcile(
    reason: str = typer.Option("process restarted before terminal job status"),
    stale_after_seconds: int = typer.Option(60, min=30, max=86_400),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Mark only stale-heartbeat queued/running journals failed after confirmed interruption."""
    try:
        rows = _store().reconcile_interrupted_jobs(
            reason=reason,
            stale_after_seconds=stale_after_seconds,
        )
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit(rows, json_out=json_out, fallback=f"reconciled {len(rows)} interrupted jobs")


__all__ = ["project_app"]
