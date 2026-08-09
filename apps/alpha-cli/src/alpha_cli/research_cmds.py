"""``alpha research`` — governed Research Case workflow and legacy exploratory comparison."""

from __future__ import annotations

import hashlib
import json
import platform
import sys
from collections.abc import Mapping
from dataclasses import asdict
from importlib.metadata import version
from pathlib import Path
from typing import Any, cast

import typer

from alpha_cli.control_store import (
    ControlStore,
    ResearchContractScope,
    ResearchDisposition,
    ResearchOutcome,
    ResearchPhase,
    ResearchResponsibility,
)
from alpha_cli.research_dossier import (
    DossierReceipt,
    export_research_dossier,
    verify_research_dossier,
)
from alpha_cli.research_gate_packet import (
    research_backlog_row,
    research_evidence_hub_projection,
    research_hypothesis_card,
    research_report_projection,
    research_scorecard_projection,
)
from alpha_cli.research_intake import draft_exploration_contract
from alpha_cli.research_protocols import (
    load_research_protocols,
    read_research_protocol,
)
from alpha_cli.research_runtime import (
    d0_execution_fingerprint,
    registered_d0_operator,
    run_synthetic_pilot,
    validate_d0_pilot_contract,
)
from alpha_core import DataError
from alpha_core.config import AlphaSettings
from alpha_research import ResearchChartFingerprintV1, ResearchD2BoundaryV1

research_app = typer.Typer(help="Governed research cases, contracts, sources, and bounded runs.")
sources_app = typer.Typer(help="Immutable research-source records and frozen source packs.")
context_app = typer.Typer(help="Content-addressed Codex context packets; recording is visibility.")
note_app = typer.Typer(help="Append-only Codex/owner commentary notes — never evidence.")
protocols_app = typer.Typer(help="The Git-owned Codex research protocol library.")
data_app = typer.Typer(help="Fail-closed research dataset registration and descriptive audits.")
claim_app = typer.Typer(help="Claim-level literature evidence; only owner screening elevates.")
sources_app.add_typer(claim_app, name="claim")
research_app.add_typer(sources_app, name="sources")
research_app.add_typer(context_app, name="context")
research_app.add_typer(note_app, name="note")
research_app.add_typer(protocols_app, name="protocols")
research_app.add_typer(data_app, name="data")


def _store() -> ControlStore:
    return ControlStore(AlphaSettings().data_dir)


def _emit(value: object, *, json_out: bool, fallback: str) -> None:
    if json_out:
        typer.echo(json.dumps(value, sort_keys=True, allow_nan=False))
    else:
        typer.echo(fallback)


def _object(raw: str, label: str) -> dict[str, object]:
    try:
        value: object = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(f"{label} must be a valid JSON object") from exc
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise typer.BadParameter(f"{label} must be a valid JSON object")
    return cast(dict[str, object], value)


def _answers(values: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw in values:
        key, separator, value = raw.partition("=")
        if not separator or not key or not value:
            raise typer.BadParameter("--answer must use material_question=value")
        if key in result:
            raise typer.BadParameter(f"duplicate research answer {key!r}")
        result[key] = value
    return result


def _sha_json(value: object) -> str:
    try:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode(
            "utf-8"
        )
    except (TypeError, ValueError) as exc:
        raise DataError("research fingerprint input must contain finite JSON values") from exc
    return hashlib.sha256(encoded).hexdigest()


def _manifest_artifact_sha256(manifest: Mapping[str, object], artifact: str) -> str:
    artifacts = manifest.get("artifacts")
    metadata = None if not isinstance(artifacts, Mapping) else artifacts.get(artifact)
    digest = None if not isinstance(metadata, Mapping) else metadata.get("sha256")
    if (
        not isinstance(digest, str)
        or len(digest) != 64
        or any(character not in "0123456789abcdef" for character in digest)
    ):
        raise DataError(f"research run has no valid {artifact!r} artifact digest")
    return digest


def _file_sha(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise DataError(f"cannot fingerprint research implementation at {path}") from exc


def _python_tree_sha(path: Path) -> str:
    files = sorted(candidate for candidate in path.rglob("*.py") if candidate.is_file())
    if not files:
        raise DataError(f"cannot fingerprint empty research implementation tree at {path}")
    return _sha_json(
        {candidate.relative_to(path).as_posix(): _file_sha(candidate) for candidate in files}
    )


def _dependency_lock_sha() -> str:
    repository_lock = Path(__file__).resolve().parents[4] / "uv.lock"
    if repository_lock.is_file():
        return _file_sha(repository_lock)
    return _sha_json(
        {
            distribution: version(distribution)
            for distribution in (
                "alpha-research",
                "matplotlib",
                "numpy",
                "scipy",
            )
        }
    )


def _implementation_hashes() -> dict[str, str | None]:
    import alpha_research
    from alpha_cli import research_intake, research_runtime

    intake_path = Path(research_intake.__file__)
    runtime_path = Path(research_runtime.__file__)
    research_root = Path(alpha_research.__file__).parent
    dependency_lock = _dependency_lock_sha()
    code = _sha_json(
        {
            "alpha_research": _python_tree_sha(research_root),
            "research_intake": _file_sha(intake_path),
            "research_runtime": _file_sha(runtime_path),
        }
    )
    environment = _sha_json(
        {
            "alpha_research": version("alpha-research"),
            "dependency_lock": dependency_lock,
            "matplotlib": version("matplotlib"),
            "numpy": version("numpy"),
            "platform_machine": platform.machine(),
            "platform_system": platform.system(),
            "python": list(sys.version_info[:3]),
            "scipy": version("scipy"),
        }
    )
    evaluator = _sha_json(
        {
            "detector": "point-in-time-double-bottom-v1",
            "pilot": "d0-synthetic-v1",
            "power": "known-sigma-prospective-v1",
            "rendering": "deterministic-matplotlib-line-chart-v1",
        }
    )
    return {
        "code": code,
        "dependency_lock": dependency_lock,
        "environment": environment,
        "evaluator": evaluator,
        "data": None,
    }


def _require_resolved_material(value: object, label: str) -> None:
    """Reject approval-ready material fields that still contain sentinel placeholders."""

    if isinstance(value, Mapping):
        for key, item in value.items():
            _require_resolved_material(item, f"{label}.{key}")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _require_resolved_material(item, f"{label}[{index}]")
        return
    if isinstance(value, str) and any(
        marker in value.casefold()
        for marker in ("unresolved", "placeholder", "selection_required", "provider_required")
    ):
        raise DataError(f"approval-ready {label} contains unresolved material semantics")


def _approval_payload(
    draft: Mapping[str, object],
    *,
    source_pack_id: str,
    d2_relation_to_prior: str | None = None,
) -> dict[str, object]:
    result = dict(draft)
    primary_claim = result.get("primary_claim")
    if not isinstance(primary_claim, dict) or not primary_claim:
        raise DataError("approval-ready research contract requires one resolved primary claim")
    thesis = result.get("thesis")
    if not isinstance(thesis, dict) or not thesis:
        raise DataError("approval-ready research contract requires a thesis")
    result["thesis"] = {**thesis, "primary_claims": [primary_claim]}
    result["source_pack_id"] = source_pack_id
    result["budget"] = {"wall_seconds": 8_400, "source_requests": 40, "variants": 64}
    result["hashes"] = _implementation_hashes()
    chart_value = result.get("chart_fingerprint")
    event_value = result.get("event_definition")
    if not isinstance(chart_value, dict) or not isinstance(event_value, dict):
        raise DataError("approval-ready research contract requires chart and event definitions")
    if result.get("approval_ready") is True:
        _require_resolved_material(chart_value, "chart_fingerprint")
        _require_resolved_material(event_value, "event_definition")
        _require_resolved_material(primary_claim, "primary_claim")
    duration_minutes = chart_value.get("bar_duration_minutes")
    if (
        isinstance(duration_minutes, bool)
        or not isinstance(duration_minutes, int)
        or duration_minutes < 1
    ):
        raise DataError("approval-ready chart requires a positive fixed bar duration")
    pattern_window = chart_value.get("pattern_window_trading_minutes")
    if pattern_window is not None:
        bar_construction = (
            f"fixed_{duration_minutes}_trading_minute_bars_with_"
            f"{pattern_window}_trading_minute_pattern_window"
        )
    elif duration_minutes == 1_440:
        bar_construction = "fixed_session_daily_bars"
    else:
        bar_construction = f"fixed_{duration_minutes}_elapsed_minute_bars"
    chart = ResearchChartFingerprintV1(
        instrument=str(chart_value.get("instrument", "")),
        provider=str(chart_value.get("provider", "")),
        venue=str(chart_value.get("venue", "")),
        timezone=str(chart_value.get("timezone", "")),
        session=str(chart_value.get("session", "")),
        bar_construction=bar_construction,
        bar_duration_seconds=duration_minutes * 60,
        anchor=str(chart_value.get("anchor", "")),
        adjustment_basis=str(chart_value.get("adjustment_basis", "")),
        timestamp_semantics=str(chart_value.get("timestamp_semantics", "")),
    )
    endpoint = primary_claim.get("estimand", primary_claim.get("endpoint"))
    horizon = primary_claim.get("horizon_trading_minutes", primary_claim.get("horizon"))
    if not isinstance(endpoint, str) or not endpoint or not isinstance(horizon, str | int):
        raise DataError("approval-ready primary claim requires an exact endpoint and horizon")
    event_formula = json.dumps(event_value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    eligible_groups = tuple(f"synthetic-acceptance-session-{index:03d}" for index in range(1, 11))
    synthetic_dataset = _sha_json(
        {
            "schema": "AlphaSyntheticResearchAcceptanceDatasetV1",
            "generator": "d0-synthetic-v1",
            "chart_fingerprint": chart.to_dict(),
            "eligible_groups": list(eligible_groups),
        }
    )
    boundary = ResearchD2BoundaryV1.from_eligible_groups(
        dataset_fingerprint=synthetic_dataset,
        eligible_groups=eligible_groups,
        chart_fingerprint=chart,
        event_formula=event_formula,
        event_availability_timestamp=str(event_value.get("availability", "")),
        primary_endpoint=endpoint,
        primary_horizon=str(horizon),
        outcome_overlap_embargo_groups=1,
    )
    d2_definition: dict[str, object] = {
        "purpose": "research_confirmation",
        "share": 0.20,
        "state": "sealed",
        "boundary_hash": boundary.boundary_sha256,
    }
    if d2_relation_to_prior is not None:
        d2_definition["relation_to_prior"] = d2_relation_to_prior
    result["protocol"] = {
        "chart_fingerprint": chart.to_dict(),
        "event_definition": result.get("event_definition"),
        "primary_claims": [primary_claim],
        "primary_claim_count": 1,
        "boundary_authority": {
            "kind": "synthetic_acceptance_fixture",
            "real_market_evidence": False,
            "empirical_confirmation_authorized": False,
        },
        "evidence_topology": {
            "boundary": boundary.to_dict(),
            "D0": {"purpose": "synthetic_validation", "share": 0.0},
            "D1": {"purpose": "discovery", "share": 0.60},
            "D2": d2_definition,
            "D3": {"purpose": "final_strategy_holdout", "share": 0.20, "state": "sealed"},
        },
        "statistical_policy": result.get("statistical_policy"),
        "required_falsifiers": result.get("required_falsifiers"),
        "confounders": result.get("confounders"),
        "complete_variant_family": {
            "primary_formulations": 1,
            "preregistered_sensitivity_contrasts": 8,
            "maximum_declared_grid_cells": 64,
        },
    }
    protocol = cast(dict[str, object], result["protocol"])
    resolved = result.get("resolved_material_choices")
    if (
        isinstance(resolved, Mapping)
        and result.get("approval_ready") is True
        and event_value.get("name") == "double_bottom"
        and event_value.get("availability") == "second_trough_confirmable"
        and resolved.get("chart_construction") == "spy_rth_60m_four_hour_window"
        and resolved.get("primary_outcome") == "four_trading_hour_return_25bp"
    ):
        protocol["d0_operator"] = registered_d0_operator(result)
    return result


def _case_name(raw_idea: str) -> str:
    collapsed = " ".join(raw_idea.split())
    return collapsed if len(collapsed) <= 120 else f"{collapsed[:117]}..."


def _case_payload(
    store: ControlStore, project_id: str
) -> tuple[dict[str, object], dict[str, object]]:
    summary = store.research_case_summary(project_id)
    active = summary.get("active_contract")
    if not isinstance(active, dict):
        raise DataError("research case has no active contract projection")
    payload = active.get("payload")
    if not isinstance(payload, dict):
        raise DataError("research case has no active contract payload")
    return cast(dict[str, object], payload), summary


@research_app.command("capture")
def capture(
    idea: str,
    name: str | None = typer.Option(None, help="owner-facing case name; defaults from the idea"),
    created_by: str = typer.Option("codex", help="capturing actor"),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Capture exact owner wording and immediately perform bounded deterministic triage."""
    store = _store()
    draft = draft_exploration_contract(idea)
    questions = cast(list[object], draft["blocking_questions"])
    count = len(questions)
    if count:
        next_action = f"Owner answers the {count} material definition questions in one batch."
        responsibility: ResearchResponsibility = "owner"
        blocker = "The primary chart, event timestamp, or outcome is materially ambiguous."
        recovery = "Answer the single bounded question batch; Codex handles technical defaults."
    else:
        next_action = "Codex checks source and data feasibility."
        responsibility = "codex"
        blocker = None
        recovery = None
    try:
        captured = store.capture_research_case(
            name=_case_name(idea) if name is None else name,
            hypothesis=idea,
            falsification_criterion=(
                "Reject, invalidate, or mark inconclusive when required negative controls, "
                "power, point-in-time validity, or the minimum economic effect fail."
            ),
            draft_payload=draft,
            created_by=created_by,
            next_action=next_action,
            responsibility=responsibility,
            blocker=blocker,
            recovery=recovery,
        )
        project = cast(dict[str, object], captured["project"])
        contract = cast(dict[str, object], captured["contract"])
        case = cast(dict[str, object], captured["case"])
        project_id = str(project["project_id"])
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit(
        {"project": project, "contract": contract, "case": case},
        json_out=json_out,
        fallback=f"captured research case {project_id}; {next_action}",
    )


@sources_app.command("add")
def sources_add(
    project_id: str,
    title: str = typer.Option(...),
    locator: str = typer.Option(..., help="DOI, stable URL, or owner-provided locator"),
    provider: str = typer.Option(...),
    access_mode: str = typer.Option(..., help="metadata_only|open_access|owner_provided"),
    metadata_json: str = typer.Option("{}"),
    content_hash: str | None = typer.Option(None),
    doi: str | None = typer.Option(None, "--doi", help="typed DOI (normalized lowercase)"),
    year: int | None = typer.Option(None, "--year", help="publication year"),
    author: list[str] = typer.Option(  # noqa: B008
        [], "--author", help="repeatable typed author entries"
    ),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Record permitted metadata or lawfully retained bytes by immutable receipt."""
    try:
        row = _store().create_research_source(
            project_id,
            title=title,
            locator=locator,
            provider=provider,
            access_mode=access_mode,
            metadata=_object(metadata_json, "--metadata-json"),
            content_hash=content_hash,
            doi=doi,
            year=year,
            authors=author or None,
        )
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit(row, json_out=json_out, fallback=f"research source {row['source_id']}")


@sources_app.command("search")
def sources_search(
    query: str,
    limit: int = typer.Option(50, min=1, max=200, help="bounded page size"),
    offset: int = typer.Option(0, min=0, help="page offset"),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Search local source records by title/locator/DOI terms; never the network."""
    try:
        rows = _store().search_research_sources(query, limit=limit, offset=offset)
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit(
        {"items": rows, "limit": limit, "offset": offset},
        json_out=json_out,
        fallback="\n".join(f"{row['source_id']} {row['title']}" for row in rows)
        or "no matching sources",
    )


@claim_app.command("add")
def claim_add(
    project_id: str,
    source_id: str = typer.Option(..., "--source-id", help="the source this claim reads"),
    contract_id: str = typer.Option(
        ..., "--contract-id", help="the hypothesis version this claim bears on"
    ),
    text: str = typer.Option(..., "--text", help="the claim statement"),
    direction: str = typer.Option(
        ..., "--direction", help="supports|contradicts|contextualizes|method"
    ),
    strength: str = typer.Option(..., "--strength", help="weak|moderate|strong"),
    method: str = typer.Option(..., "--method", help="how the source tested it"),
    sample: str = typer.Option(..., "--sample", help="the source's sample/period"),
    market: list[str] = typer.Option(  # noqa: B008
        [], "--market", help="repeatable market labels"
    ),
    limitations: str = typer.Option(..., "--limitations", help="known limitations"),
    author: str = typer.Option("codex", "--author", help="drafting actor"),
    author_kind: str = typer.Option("agent", "--author-kind", help="owner or agent"),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Draft one claim-level literature statement; a paper is never auto-trusted."""
    try:
        claim = _store().draft_source_claim(
            project_id,
            source_id=source_id,
            contract_id=contract_id,
            claim_text=text,
            direction=direction,
            strength=strength,
            method_summary=method,
            sample_summary=sample,
            markets=market,
            limitations=limitations,
            author=author,
            author_kind=author_kind,
        )
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit(claim, json_out=json_out, fallback=f"drafted claim {claim['claim_id']}")


@claim_app.command("screen")
def claim_screen(
    project_id: str,
    claim_id: str,
    actor: str = typer.Option(..., "--actor", help="owner actor performing screening"),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Owner screening appends the screened revision (trusted-local authority)."""
    try:
        claim = _store().screen_source_claim(project_id, claim_id=claim_id, actor=actor)
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit(claim, json_out=json_out, fallback=f"screened claim {claim['claim_id']}")


@claim_app.command("list")
def claim_list(
    project_id: str,
    include_history: bool = typer.Option(False, "--history", help="include all revisions"),
    limit: int = typer.Option(200, min=1, max=200, help="bounded page size"),
    offset: int = typer.Option(0, min=0, help="page offset"),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """List claims (latest revision per claim unless --history)."""
    try:
        rows = _store().list_source_claims(
            project_id, include_history=include_history, limit=limit, offset=offset
        )
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit(
        {"items": rows, "limit": limit, "offset": offset},
        json_out=json_out,
        fallback="\n".join(
            f"{row['claim_id']} {row['direction']}/{row['strength']} {row['status']}"
            for row in rows
        )
        or "no claims recorded",
    )


@sources_app.command("fetch")
def sources_fetch(
    url: str,
    objects_dir: Path | None = typer.Option(  # noqa: B008
        None, "--objects-dir", help="content-addressed object store (default under data_dir)"
    ),
    allow_host: list[str] = typer.Option(  # noqa: B008
        [], "--allow-host", help="explicit host allowlist entries (repeatable)"
    ),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Owner-invoked driver for the isolated literature worker (the ONE network surface).

    Every URL, redirect, and response is validated inside the worker via the fail-closed
    acquisition primitives; the stored object is content-addressed and labelled
    UNTRUSTED_SOURCE. The worker never sees credentials or shell context.
    """
    import subprocess

    worker_dir = Path(__file__).resolve().parents[4] / "workers" / "literature"
    if not (worker_dir / "pyproject.toml").is_file():
        raise typer.BadParameter(
            f"literature worker missing at {worker_dir}; it is repository content and is "
            "unavailable outside a checked-out working tree"
        )
    target_dir = (
        AlphaSettings().data_dir / "research" / "objects" if objects_dir is None else objects_dir
    )
    argv = [
        "uv",
        "run",
        "--project",
        str(worker_dir),
        "literature-worker",
        "fetch",
        "--url",
        url,
        "--objects-dir",
        str(target_dir),
    ]
    for host in allow_host:
        argv += ["--allow-host", host]
    completed = subprocess.run(  # noqa: S603 - closed argv, no shell
        argv, capture_output=True, text=True, timeout=180, check=False
    )
    if completed.returncode != 0:
        raise typer.BadParameter(
            completed.stderr.strip() or completed.stdout.strip() or "literature worker failed"
        )
    result = _object(completed.stdout, "literature worker output")
    _emit(
        result,
        json_out=json_out,
        fallback=f"stored {result.get('sha256')} ({result.get('trust_label')})",
    )


@sources_app.command("screen")
def sources_screen(
    source_id: str,
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Show one immutable source for manual screening; Gate 1 records no screening mutation."""
    try:
        row = _store().get_research_source(source_id)
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit(row, json_out=json_out, fallback=f"research source {row['source_id']}")


@sources_app.command("freeze")
def sources_freeze(
    project_id: str,
    source_ids: list[str] = typer.Option(  # noqa: B008
        ..., "--source-id", help="included source id; repeatable"
    ),
    definition_json: str = typer.Option("{}"),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Freeze an order-independent, content-addressed source pack."""
    try:
        row = _store().create_research_source_pack(
            project_id,
            source_ids=source_ids,
            definition=_object(definition_json, "--definition-json"),
        )
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit(row, json_out=json_out, fallback=f"research source pack {row['pack_id']}")


@research_app.command("draft")
def draft(
    project_id: str,
    source_pack_id: str = typer.Option(..., help="frozen project source pack"),
    answers: list[str] = typer.Option(  # noqa: B008
        [], "--answer", help="material_question=value; repeatable"
    ),
    created_by: str = typer.Option("codex"),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Create a complete exploration contract from owner answers and automatic fingerprints."""
    store = _store()
    try:
        project = store.get_project(project_id)
        source_pack = store.get_research_source_pack(source_pack_id)
        if source_pack.get("project_id") != project_id:
            raise DataError("research source pack must belong to the drafted project")
        preview = draft_exploration_contract(
            str(project["hypothesis"]), resolutions=_answers(answers)
        )
        if preview["blocking_questions"]:
            raise DataError("all material research questions must be resolved in the one batch")
        payload = _approval_payload(preview, source_pack_id=source_pack_id)
        contract = store.create_research_contract(
            project_id,
            scope="exploration",
            payload=payload,
            created_by=created_by,
            author_kind="agent",
        )
        selected = store.research_case_summary(project_id)
        if selected["phase"] == "captured":
            store.transition_research_phase(
                project_id,
                to_phase="triage",
                contract_id=str(contract["contract_id"]),
                actor=created_by,
                reason="attached the complete draft to the legally migrated research case",
                next_action="Codex verifies the frozen source pack and material resolutions.",
                responsibility="codex",
            )
            selected = store.research_case_summary(project_id)
        if selected["phase"] == "triage":
            approval_ready = payload.get("approval_ready") is True
            store.transition_research_phase(
                project_id,
                to_phase="exploration_review",
                contract_id=str(contract["contract_id"]),
                actor=created_by,
                reason="complete exploration contract and immutable source pack are ready",
                next_action=(
                    "Owner approves or rejects the exact exploration contract."
                    if approval_ready
                    else (
                        "Owner rejects and closes the Gate-1-unavailable proposal or waits for "
                        "its registered operator to be implemented."
                    )
                ),
                responsibility="owner",
                blocker=(
                    None
                    if approval_ready
                    else "Gate 1 has no registered operator for this exact contract."
                ),
                recovery=(
                    None
                    if approval_ready
                    else (
                        "Reject and close the proposal, or wait for the operator to be added "
                        "through normal repository implementation and review."
                    )
                ),
            )
        elif selected["phase"] != "exploration_review":
            raise DataError(
                "research draft can attach only to captured, triage, or exploration review"
            )
        case = store.research_case_summary(project_id)
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit(
        {"contract": contract, "case": case},
        json_out=json_out,
        fallback=f"exploration contract {contract['contract_id']} awaits owner review",
    )


@research_app.command("approve")
def approve(
    scope: str,
    project_id: str,
    contract_id: str,
    actor: str = typer.Option(..., help="human owner identity"),
    reason: str = typer.Option(...),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Owner-approve one exact exploration or confirmation contract."""
    store = _store()
    try:
        if scope not in {"exploration", "confirmation"}:
            raise DataError("research approval scope must be exploration or confirmation")
        typed_scope = cast(ResearchContractScope, scope)
        review = store.review_research_contract(
            project_id,
            contract_id,
            scope=typed_scope,
            decision="approve",
            actor=actor,
            actor_kind="human",
            reason=reason,
        )
        if scope == "exploration":
            phase: ResearchPhase = "pilot"
            next_action = "Codex runs the deterministic D0 synthetic pilot."
        else:
            phase = "sealed_confirmation"
            next_action = "Codex may launch the exact one-shot D2 confirmation job."
        store.transition_research_phase(
            project_id,
            to_phase=phase,
            contract_id=contract_id,
            actor=actor,
            reason=f"owner approved the exact {scope} contract",
            next_action=next_action,
            responsibility="codex",
        )
        case = store.research_case_summary(project_id)
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit(
        {"review": review, "case": case},
        json_out=json_out,
        fallback=f"approved {scope} contract {contract_id}",
    )


@research_app.command("revise")
def revise(
    project_id: str,
    source_pack_id: str = typer.Option(..., help="frozen project source pack for the child"),
    answers: list[str] = typer.Option(  # noqa: B008
        [], "--answer", help="material_question=value; repeatable"
    ),
    actor: str = typer.Option(..., help="human owner requesting the bounded revision"),
    reason: str = typer.Option(...),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Create and reopen one pre-D2 revision child after an owner revise disposition."""

    store = _store()
    try:
        case = store.research_case_summary(project_id)
        project = store.get_project(project_id)
        source_pack = store.get_research_source_pack(source_pack_id)
        if source_pack.get("project_id") != project_id:
            raise DataError("research source pack must belong to the revised project")
        preview = draft_exploration_contract(
            str(project["hypothesis"]), resolutions=_answers(answers)
        )
        if preview["blocking_questions"]:
            raise DataError("all material research questions must be resolved in the one batch")
        payload = _approval_payload(
            preview,
            source_pack_id=source_pack_id,
            d2_relation_to_prior="unopened_sealed_reuse",
        )
        active = case.get("active_contract")
        if (
            case.get("phase") == "exploration_review"
            and isinstance(active, dict)
            and active.get("parent_contract_id") is not None
            and active.get("payload") == payload
        ):
            contract = active
            row = case
            _emit(
                {"contract": contract, "case": row},
                json_out=json_out,
                fallback=f"reopened revised exploration contract {contract['contract_id']}",
            )
            return
        decision = case.get("research_decision")
        if case.get("phase") != "closed" or not isinstance(decision, dict):
            raise DataError("research revision requires a closed owner decision")
        if decision.get("disposition") != "revise":
            raise DataError("research revision requires owner disposition 'revise'")
        if case.get("d2_state") != "sealed":
            raise DataError(
                "Gate-4 data required: an authorized, consumed, or contaminated D2 boundary "
                "cannot be reused"
            )
        parent_id = str(case["exploration_contract_id"])
        contract = store.create_research_contract(
            project_id,
            scope="exploration",
            parent_contract_id=parent_id,
            payload=payload,
            created_by="codex",
            author_kind="agent",
        )
        revision_id = str(contract["contract_id"])
        selected = store.research_case_summary(project_id)
        if not (
            selected.get("phase") == "exploration_review"
            and selected.get("active_contract_id") == revision_id
        ):
            store.reopen_research_revision(
                project_id,
                revision_id,
                actor=actor,
                reason=reason,
                next_action="Owner approves or rejects the exact revised exploration contract.",
            )
        row = store.research_case_summary(project_id)
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit(
        {"contract": contract, "case": row},
        json_out=json_out,
        fallback=f"reopened revised exploration contract {contract['contract_id']}",
    )


@research_app.command("reject")
def reject(
    scope: str,
    project_id: str,
    contract_id: str,
    actor: str = typer.Option(..., help="human owner identity"),
    reason: str = typer.Option(...),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Owner-reject one exact contract without granting any research authority."""

    store = _store()
    try:
        if scope not in {"exploration", "confirmation"}:
            raise DataError("research rejection scope must be exploration or confirmation")
        review = store.review_research_contract(
            project_id,
            contract_id,
            scope=cast(ResearchContractScope, scope),
            decision="reject",
            actor=actor,
            actor_kind="human",
            reason=reason,
        )
        case = store.research_case_summary(project_id)
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit(
        {"review": review, "case": case},
        json_out=json_out,
        fallback=f"rejected {scope} contract {contract_id}",
    )


@research_app.command("run")
def run_research(
    stage: str,
    project_id: str,
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Run an allowed research stage; Gate 1 exposes only the deterministic D0 pilot."""
    if stage in {"deep", "confirm"}:
        raise typer.BadParameter(f"Gate-1 unavailable: {stage} research engine is not shipped")
    if stage != "pilot":
        raise typer.BadParameter("research run stage must be pilot, deep, or confirm")
    store = _store()
    try:
        payload, case = _case_payload(store, project_id)
        if case["phase"] != "pilot":
            raise DataError("synthetic pilot requires the owner-approved pilot phase")
        contract_id = str(case["active_contract_id"])
        validate_d0_pilot_contract(payload)
        execution_state = str(case["execution_state"])
        latest_attempt_id = case.get("latest_attempt_id")
        if (
            execution_state in {"idle", "queued"}
            and isinstance(latest_attempt_id, str)
            and isinstance(case.get("latest_run_id"), str)
        ):
            recovered = store.verified_research_attempt(project_id, latest_attempt_id)
            recovered_attempt = cast(dict[str, object], recovered["attempt"])
            recovered_manifest = cast(dict[str, object], recovered["manifest"])
            if (
                recovered_attempt.get("status") == "completed"
                and recovered_attempt.get("kind") == "d0-synthetic-pilot"
                and recovered_attempt.get("phase") == "pilot"
                and recovered_attempt.get("contract_id") == contract_id
                and recovered_manifest.get("evidence_zone") == "D0"
            ):
                if execution_state == "queued":
                    store.transition_research_execution(
                        project_id,
                        to_state="idle",
                        contract_id=contract_id,
                        actor="system",
                        reason="recovered the completed immutable D0 run after interruption",
                        next_action=(
                            "Owner records INCONCLUSIVE with revise, park, or reject; empirical "
                            "D1 is unavailable in Gate 1."
                        ),
                        responsibility="owner",
                        checkpoint="d0:complete",
                    )
                store.transition_research_phase(
                    project_id,
                    to_phase="research_decision",
                    contract_id=contract_id,
                    actor="system",
                    reason="recovered the verified completed D0 attempt after interruption",
                    next_action=(
                        "Owner records INCONCLUSIVE with revise, park, or reject; empirical D1 "
                        "is unavailable in Gate 1."
                    ),
                    responsibility="owner",
                )
                recovered_case = store.research_case_summary(project_id)
                _emit(
                    {
                        "manifest": recovered_manifest,
                        "attempt": recovered_attempt,
                        "case": recovered_case,
                    },
                    json_out=json_out,
                    fallback=(
                        f"recovered D0 pilot {recovered_manifest['run_id']}; "
                        "owner disposition required"
                    ),
                )
                return
        if cast(int, case["attempt_count"]) >= 3:
            raise DataError(
                "synthetic pilot stopped after the initial attempt and two safe retries; owner "
                "revision or disposition is required"
            )
        approved_hashes = payload.get("hashes")
        current_hashes = _implementation_hashes()
        if not isinstance(approved_hashes, Mapping) or _sha_json(approved_hashes) != _sha_json(
            current_hashes
        ):
            raise DataError(
                "approved research implementation fingerprints no longer match the executable "
                "code, dependency lock, evaluator, or environment; create and approve a revised "
                "contract before another pilot"
            )
        execution_fingerprint = d0_execution_fingerprint(payload)
        if execution_state == "idle":
            store.transition_research_execution(
                project_id,
                to_state="queued",
                contract_id=contract_id,
                actor="codex",
                reason="the bounded synthetic pilot is queued",
                next_action="Run the D0 point-in-time acceptance fixture.",
                responsibility="codex",
                checkpoint="d0:queued",
            )
        elif execution_state != "queued":
            raise DataError("synthetic pilot must be idle or explicitly queued for resume")
        reservation = store.reserve_d0_research_launch(
            project_id,
            contract_id,
            config_fingerprint=execution_fingerprint,
        )
        raw_launch_number = reservation.get("launch_number")
        if isinstance(raw_launch_number, bool) or not isinstance(raw_launch_number, int):
            raise DataError("research launch reservation has no valid launch number")
        attempt_number = raw_launch_number
        reservation_id = str(reservation["reservation_id"])
        try:
            manifest = run_synthetic_pilot(
                AlphaSettings().data_dir,
                project_id=project_id,
                contract_id=contract_id,
                contract=payload,
            )
        except Exception as run_error:
            retries_exhausted = attempt_number >= 3
            error_text = str(run_error).strip() or type(run_error).__name__
            error_text = error_text[:8192]
            checkpoint_errors: list[str] = []
            try:
                store.record_research_attempt(
                    project_id,
                    contract_id,
                    kind="d0-synthetic-pilot",
                    status="failed",
                    config_fingerprint=execution_fingerprint,
                    budget_used={},
                    details={
                        "attempt_number": attempt_number,
                        "evidence_zone": "D0",
                        "real_market_evidence": False,
                        "finding": "The D0 pilot failed; no empirical conclusion was produced.",
                    },
                    error=error_text,
                    launch_reservation_id=reservation_id,
                )
            except Exception as terminal_error:
                checkpoint_errors.append(f"terminal attempt: {terminal_error}")
            try:
                store.transition_research_execution(
                    project_id,
                    to_state="blocked" if retries_exhausted else "failed",
                    contract_id=contract_id,
                    actor="system",
                    reason="the D0 pilot failed and stopped at a durable checkpoint",
                    next_action=(
                        "Owner revises, parks, or rejects the case; the safe retry limit is "
                        "exhausted."
                        if retries_exhausted
                        else (
                            "Codex may inspect the failure and resume safely; no more than two "
                            "retries."
                        )
                    ),
                    responsibility="owner" if retries_exhausted else "codex",
                    checkpoint=f"d0:failed:{attempt_number}",
                    blocker=error_text,
                    recovery=(
                        "Change the approved contract only through owner-directed revision."
                        if retries_exhausted
                        else "Inspect the error, correct only implementation defects, then resume."
                    ),
                )
            except Exception as execution_error:
                checkpoint_errors.append(f"execution checkpoint: {execution_error}")
            if retries_exhausted:
                try:
                    store.transition_research_phase(
                        project_id,
                        to_phase="research_decision",
                        contract_id=contract_id,
                        actor="system",
                        reason="the D0 pilot exhausted the initial attempt and two safe retries",
                        next_action=(
                            "Owner records INVALID with revise, park, or reject; D2 remains sealed."
                        ),
                        responsibility="owner",
                        blocker="The synthetic evaluator could not complete reliably.",
                        recovery=(
                            "Revise the implementation under a new reviewed lineage or close it."
                        ),
                    )
                except Exception as phase_error:
                    checkpoint_errors.append(f"phase checkpoint: {phase_error}")
            checkpoint_suffix = (
                ""
                if not checkpoint_errors
                else "; checkpoint errors: " + "; ".join(checkpoint_errors)
            )
            raise DataError(
                f"synthetic pilot failed and was checkpointed: {error_text}{checkpoint_suffix}"
            ) from run_error
        # The pilot succeeded and its immutable run is published. From here on, a store
        # write failure must never be recorded as a pilot failure: fabricating a terminal
        # 'failed' attempt would falsify the append-only ledger and mis-checkpoint the case.
        try:
            attempt = store.record_research_attempt(
                project_id,
                contract_id,
                kind="d0-synthetic-pilot",
                status="completed",
                config_fingerprint=str(manifest["execution_fingerprint"]),
                budget_used={},
                details={
                    "attempt_number": attempt_number,
                    "evidence_zone": "D0",
                    "finding": (
                        "D0 detector, point-in-time timing, null, and power fixtures passed; this "
                        "is not real-market evidence."
                    ),
                    "d0_acceptance_ref": {
                        "artifact": "d0_acceptance.json",
                        "content_sha256": _manifest_artifact_sha256(manifest, "d0_acceptance.json"),
                    },
                },
                run_id=str(manifest["run_id"]),
                launch_reservation_id=reservation_id,
            )
        except Exception as record_error:
            raise DataError(
                f"the D0 pilot completed and published immutable run {manifest['run_id']}, but "
                "recording its completed attempt failed; no failed attempt was fabricated. "
                "Inspect the control store, then `alpha research resume` and re-run the pilot: "
                "the identical run republishes idempotently and the attempt is recorded on "
                f"success: {record_error}"
            ) from record_error
        store.transition_research_execution(
            project_id,
            to_state="idle",
            contract_id=contract_id,
            actor="system",
            reason="the D0 pilot completed and its immutable run was recorded",
            next_action=(
                "Owner records INCONCLUSIVE with revise, park, or reject; empirical D1 is "
                "unavailable in Gate 1."
            ),
            responsibility="owner",
            checkpoint="d0:complete",
        )
        store.transition_research_phase(
            project_id,
            to_phase="research_decision",
            contract_id=contract_id,
            actor="codex",
            reason="D0 detector, null, topology, and power fixtures passed",
            next_action=(
                "Owner records INCONCLUSIVE with revise, park, or reject; empirical D1 is "
                "unavailable in Gate 1."
            ),
            responsibility="owner",
        )
        case = store.research_case_summary(project_id)
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit(
        {"manifest": manifest, "attempt": attempt, "case": case},
        json_out=json_out,
        fallback=f"D0 pilot {manifest['run_id']} completed; owner disposition required",
    )


@research_app.command("list")
def list_cases(
    limit: int = typer.Option(50, min=1, max=100, help="bounded page size"),
    offset: int = typer.Option(0, min=0, help="page offset"),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """List bounded research-case backlog rows, newest research activity first."""
    try:
        rows = _store().list_research_cases(limit=limit + 1, offset=offset)
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    items = [
        research_backlog_row(cast(Mapping[str, object], row["case"]), str(row["updated_at"]))
        for row in rows[:limit]
    ]
    _emit(
        {"items": items, "limit": limit, "offset": offset, "has_more": len(rows) > limit},
        json_out=json_out,
        fallback="\n".join(
            f"{item['case_id']} {item['phase']}/{item['execution_state']} {item['title']}"
            for item in items
        )
        or "no research cases",
    )


@research_app.command("evidence-hub")
def evidence_hub(
    project_id: str,
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Project the eleven-section Evidence Hub with honest NOT_TESTED empty states."""
    try:
        hub = research_evidence_hub_projection(_store(), project_id)
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    sections = hub["sections"]
    section_names = ", ".join(sections) if isinstance(sections, dict) else ""
    _emit(hub, json_out=json_out, fallback=f"evidence hub sections: {section_names}")


@context_app.command("build")
def context_build(
    project_id: str,
    kind: str = typer.Option(..., "--kind", help="packet kind"),
    symbol: str | None = typer.Option(None, "--symbol", help="required for asset packets"),
    protocol: str | None = typer.Option(
        None, "--protocol", help="pair a library protocol; its content hash is recorded"
    ),
    created_by: str = typer.Option("codex", "--created-by", help="recording actor"),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Assemble and record one bounded, content-addressed Codex context packet."""
    protocol_hash: str | None = None
    if protocol is not None:
        entry = read_research_protocol(protocol)
        protocol_hash = str(entry["sha256"])
    try:
        packet = _store().build_research_context_packet(
            project_id,
            kind=kind,
            created_by=created_by,
            symbol=symbol,
            protocol_id=protocol,
            protocol_content_hash=protocol_hash,
        )
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit(packet, json_out=json_out, fallback=f"recorded packet {packet['packet_id']}")


@context_app.command("show")
def context_show(
    packet_id: str,
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Return one recorded packet byte-identically."""
    try:
        packet = _store().get_research_context_packet(packet_id)
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit(
        packet,
        json_out=json_out,
        fallback=f"{packet['packet_id']} {packet['packet_kind']} {packet['created_at']}",
    )


@context_app.command("list")
def context_list(
    project_id: str,
    limit: int = typer.Option(50, min=1, max=200, help="bounded page size"),
    offset: int = typer.Option(0, min=0, help="page offset"),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """List this case's recorded packets, newest first."""
    try:
        rows = _store().list_research_context_packets(project_id, limit=limit, offset=offset)
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit(
        {"items": rows, "limit": limit, "offset": offset},
        json_out=json_out,
        fallback="\n".join(f"{row['packet_id']} {row['packet_kind']}" for row in rows)
        or "no packets recorded",
    )


@note_app.command("add")
def note_add(
    project_id: str,
    kind: str = typer.Option(..., "--kind", help="note kind"),
    body: str = typer.Option(..., "--body", help="note body"),
    author: str = typer.Option("codex", "--author", help="author name"),
    author_kind: str = typer.Option("agent", "--author-kind", help="owner or agent"),
    packet: str | None = typer.Option(None, "--packet", help="originating context packet"),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Append one commentary note — structurally outside the evidence model."""
    try:
        note = _store().add_research_note(
            project_id,
            note_kind=kind,
            body=body,
            author=author,
            author_kind=author_kind,
            context_packet_id=packet,
        )
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit(note, json_out=json_out, fallback=f"recorded note {note['note_id']}")


@note_app.command("list")
def note_list(
    project_id: str,
    limit: int = typer.Option(100, min=1, max=200, help="bounded page size"),
    offset: int = typer.Option(0, min=0, help="page offset"),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """List this case's commentary notes, newest first (never evidence)."""
    try:
        rows = _store().list_research_notes(project_id, limit=limit, offset=offset)
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit(
        {"items": rows, "limit": limit, "offset": offset},
        json_out=json_out,
        fallback="\n".join(f"{row['note_id']} {row['note_kind']}" for row in rows)
        or "no notes recorded",
    )


@protocols_app.command("list")
def protocols_list(
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """List the Git-owned protocol library; index↔file drift fails loud."""
    try:
        protocols = load_research_protocols()
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit(
        {"protocols": protocols},
        json_out=json_out,
        fallback="\n".join(f"{entry['id']}: {entry['purpose']}" for entry in protocols),
    )


@protocols_app.command("show")
def protocols_show(
    protocol_id: str,
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Show one protocol entry plus its exact content."""
    try:
        protocol = read_research_protocol(protocol_id)
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit(protocol, json_out=json_out, fallback=str(protocol["content"]))


def _dataset_origin(
    *,
    kind: str,
    symbol: str,
    snapshot_id: str | None,
    receipt: Path | None,
) -> tuple[str, str, dict[str, object]]:
    """Resolve (store kind, provider, origin) fail-closed from on-disk bytes."""
    data_dir = AlphaSettings().data_dir
    if kind == "snapshot":
        if snapshot_id is None:
            raise DataError("snapshot registration requires --snapshot-id")
        manifest_path = data_dir / "snapshots" / snapshot_id / "manifest.json"
        if not manifest_path.is_file():
            raise DataError(f"unknown snapshot {snapshot_id!r}; nothing to register")
        raw = manifest_path.read_bytes()
        manifest = json.loads(raw)
        symbols = manifest.get("symbols") if isinstance(manifest, dict) else None
        if not isinstance(symbols, dict) or symbol not in symbols:
            raise DataError(f"snapshot {snapshot_id!r} does not contain {symbol!r}")
        provider = str(manifest.get("source", "unknown"))
        return (
            "snapshot",
            provider,
            {
                "snapshot_id": snapshot_id,
                "manifest_sha256": hashlib.sha256(raw).hexdigest(),
            },
        )
    if kind == "store-slice":
        from alpha_data.store import ParquetStore

        store = ParquetStore(data_dir / "store")
        provenance = store.read_provenance(symbol)
        path = store._provenance_path(symbol)  # noqa: SLF001 - CLI/store projection seam
        if provenance is None or not path.is_file():
            raise DataError(
                f"stored bars for {symbol!r} have no pull provenance; fail-closed — "
                "unreceipted data cannot be registered for research"
            )
        return (
            "store_slice",
            str(provenance.get("source", "unknown")),
            {"provenance_sha256": hashlib.sha256(path.read_bytes()).hexdigest()},
        )
    if kind == "quantpad":
        if receipt is None or not receipt.is_file():
            raise DataError("quantpad registration requires --receipt pointing at a receipt file")
        payload = json.loads(receipt.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise DataError("quantpad receipt must be a JSON object")
        receipt_id = payload.get("receipt_id")
        response_sha = payload.get("response_sha256")
        if not isinstance(receipt_id, str) or not isinstance(response_sha, str):
            raise DataError("quantpad receipt must carry receipt_id and response_sha256")
        return (
            "quantpad_receipt",
            "quantpad",
            {"receipt_id": receipt_id, "response_sha256": response_sha},
        )
    raise DataError(f"unsupported research dataset kind {kind!r}")


@data_app.command("register")
def data_register(
    symbol: str,
    kind: str = typer.Option(..., "--kind", help="snapshot | store-slice | quantpad"),
    start: str = typer.Option(..., "--start", help="range start (ISO date)"),
    end: str = typer.Option(..., "--end", help="range end (ISO date)"),
    snapshot_id: str | None = typer.Option(None, "--snapshot-id", help="snapshot to bind"),
    receipt: Path | None = typer.Option(  # noqa: B008
        None, "--receipt", help="quantpad receipt file"
    ),
    bar_minutes: int | None = typer.Option(None, "--bar-minutes", help="intraday bar minutes"),
    registered_by: str = typer.Option("owner", "--registered-by", help="registering actor"),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Register a research dataset against its exact receipt/provenance bytes."""
    try:
        dataset_kind, provider, origin = _dataset_origin(
            kind=kind, symbol=symbol.upper(), snapshot_id=snapshot_id, receipt=receipt
        )
        ref = _store().register_research_dataset(
            dataset_kind=dataset_kind,
            instrument=symbol,
            provider=provider,
            start_ts=start,
            end_ts=end,
            bar_duration_minutes=bar_minutes,
            origin=origin,
            registered_by=registered_by,
        )
    except (DataError, json.JSONDecodeError, OSError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit(ref, json_out=json_out, fallback=f"registered research dataset {ref['ref_id']}")


@data_app.command("list")
def data_list(
    symbol: str | None = typer.Option(None, "--symbol", help="filter by instrument"),
    limit: int = typer.Option(100, min=1, max=200, help="bounded page size"),
    offset: int = typer.Option(0, min=0, help="page offset"),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """List registered research datasets with their latest audit."""
    try:
        rows = _store().list_research_datasets(instrument=symbol, limit=limit, offset=offset)
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit(
        {"items": rows, "limit": limit, "offset": offset},
        json_out=json_out,
        fallback="\n".join(
            f"{row['ref_id']} {row['instrument']} {row['dataset_kind']}" for row in rows
        )
        or "no registered research datasets",
    )


@data_app.command("audit")
def data_audit(
    project_id: str,
    ref_id: str,
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Run a bounded descriptive audit and record it against the dataset and case."""
    from alpha_cli.research_data_audit import run_data_audit

    store = _store()
    try:
        ref = store.get_research_dataset(ref_id)
        # Bind the audit to a real research case before any computation happens.
        store.research_case_summary(project_id)
        result = run_data_audit(AlphaSettings().data_dir, project_id=project_id, ref=ref)
        manifest = result["manifest"]
        audit = store.record_research_dataset_audit(
            ref_id,
            project_id=project_id,
            run_id=str(manifest["run_id"]),
            summary=cast(Mapping[str, object], result["summary"]),
        )
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit(
        {"manifest": manifest, "audit": audit},
        json_out=json_out,
        fallback=(
            f"audit run {manifest['run_id']}: {audit['summary']['blocking_count']} blocking, "  # type: ignore[index]
            f"{audit['summary']['limiting_count']} limiting"  # type: ignore[index]
        ),
    )


@research_app.command("brief")
def brief(
    project_id: str,
    created_by: str = typer.Option("codex", "--created-by", help="recording actor"),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Build the "Resume with Codex" delta brief and record it as a packet."""
    try:
        row = _store().research_brief(project_id, created_by=created_by)
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit(
        row,
        json_out=json_out,
        fallback=f"brief recorded as {row['packet_id']}; next: {row['next_action']}",
    )


@research_app.command("status")
def status(
    project_id: str,
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Show the one current phase, execution state, next action, budget, and firewall state."""
    try:
        row = _store().research_case_summary(project_id)
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    active = row.get("active_contract")
    payload = active.get("payload") if isinstance(active, dict) else None
    card = research_hypothesis_card(payload if isinstance(payload, dict) else {})
    scorecard = research_scorecard_projection(_store(), project_id, summary=row)
    _emit(
        # Additive card/scorecard keys only: the summary itself stays byte-identical
        # because the dossier embeds and hashes it.
        {**row, "hypothesis_card": card, "scorecard": scorecard},
        json_out=json_out,
        fallback=f"{row['phase']} / {row['execution_state']}: {row['next_action']}",
    )


@research_app.command("report")
def report(
    project_id: str,
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Show the current progress report or deterministic terminal ResearchGatePacket."""
    store = _store()
    try:
        report_payload = research_report_projection(store, project_id)
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    if report_payload["report_schema"] == "ResearchGatePacketV1":
        fallback = (
            f"terminal research packet for {project_id}: "
            f"{report_payload['scientific_outcome']} / "
            f"{report_payload['recommended_disposition']}"
        )
    else:
        case = cast(dict[str, object], report_payload["case"])
        fallback = f"research report for {project_id}: {case['next_action']}"
    _emit(
        report_payload,
        json_out=json_out,
        fallback=fallback,
    )


def _receipt_payload(receipt: DossierReceipt) -> dict[str, object]:
    raw = asdict(receipt)
    raw["path"] = str(raw["path"])
    return cast(dict[str, object], raw)


@research_app.command("export")
def export(
    project_id: str,
    output_dir: Path | None = typer.Option(  # noqa: B008
        None, help="generated dossier directory"
    ),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Generate a deterministic Markdown dossier from authority projections."""
    store = _store()
    try:
        contract, summary = _case_payload(store, project_id)
        contract_id = str(summary["active_contract_id"])
        target = (
            AlphaSettings().data_dir / "research" / "projects" / project_id
            if output_dir is None
            else output_dir
        )
        receipt = export_research_dossier(
            target,
            project_id=project_id,
            contract_id=contract_id,
            contract=contract,
            summary=summary,
        )
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    payload = _receipt_payload(receipt)
    _emit(payload, json_out=json_out, fallback=f"exported {payload['path']}")


@research_app.command("verify")
def verify(
    project_id: str,
    path: Path = typer.Option(...),  # noqa: B008
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Regenerate and byte-verify a dossier without parsing Markdown as control state."""
    store = _store()
    try:
        contract, summary = _case_payload(store, project_id)
        receipt = verify_research_dossier(
            path,
            project_id=project_id,
            contract_id=str(summary["active_contract_id"]),
            contract=contract,
            summary=summary,
        )
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    payload = _receipt_payload(receipt)
    _emit(payload, json_out=json_out, fallback=f"verified {payload['path']}")


@research_app.command("pause")
def pause(
    project_id: str,
    reason: str = typer.Option(...),
    checkpoint: str | None = typer.Option(None),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Pause an active research worker at a durable checkpoint."""
    store = _store()
    try:
        case = store.research_case_summary(project_id)
        store.transition_research_execution(
            project_id,
            to_state="paused",
            contract_id=str(case["active_contract_id"]),
            actor="codex",
            reason=reason,
            next_action="Owner reviews the paused case or asks Codex to resume.",
            responsibility="owner",
            checkpoint=checkpoint,
        )
        row = store.research_case_summary(project_id)
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit(row, json_out=json_out, fallback=f"paused research case {project_id}")


@research_app.command("resume")
def resume(
    project_id: str,
    reason: str = typer.Option("owner requested bounded continuation"),
    acknowledge_orphaned_process: bool = typer.Option(
        False,
        "--acknowledge-orphaned-process",
        help="confirm that a stale running process is no longer alive before re-queueing",
    ),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Resume a paused or failed case without changing its contract or budget."""
    store = _store()
    try:
        case = store.research_case_summary(project_id)
        if case["phase"] in {"research_decision", "closed"}:
            raise DataError("terminal research decision state cannot resume execution")
        if case["phase"] == "pilot" and cast(int, case["attempt_count"]) >= 3:
            raise DataError(
                "synthetic pilot retry limit is exhausted; owner revision or disposition is "
                "required"
            )
        store.transition_research_execution(
            project_id,
            to_state="queued",
            contract_id=str(case["active_contract_id"]),
            actor="owner",
            reason=reason,
            next_action="Codex resumes from the last durable checkpoint.",
            responsibility="codex",
            checkpoint=cast(str | None, case["checkpoint"]),
            reconcile_running=(
                case["execution_state"] == "running" and acknowledge_orphaned_process
            ),
        )
        row = store.research_case_summary(project_id)
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit(row, json_out=json_out, fallback=f"queued research case {project_id}")


@research_app.command("cancel")
def cancel(
    project_id: str,
    reason: str = typer.Option(...),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Return active research execution to idle without changing its evidence phase."""
    store = _store()
    try:
        case = store.research_case_summary(project_id)
        store.transition_research_execution(
            project_id,
            to_state="idle",
            contract_id=str(case["active_contract_id"]),
            actor="owner",
            reason=reason,
            next_action="Owner chooses whether to revise, park, or resume the case.",
            responsibility="owner",
            checkpoint=cast(str | None, case["checkpoint"]),
        )
        row = store.research_case_summary(project_id)
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit(row, json_out=json_out, fallback=f"cancelled active work for {project_id}")


@research_app.command("decide")
def decide(
    project_id: str,
    outcome: str = typer.Option(..., help="SUPPORTED|CONTRADICTED|INCONCLUSIVE|INVALID"),
    disposition: str = typer.Option(..., help="advance_to_strategy|revise|park|reject"),
    actor: str = typer.Option(...),
    reason: str = typer.Option(...),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Record the owner-only research outcome/disposition and close the case."""
    store = _store()
    try:
        case = store.research_case_summary(project_id)
        if case["phase"] in {
            "exploration_review",
            "pilot",
            "deep_research",
            "confirmation_review",
        }:
            decision = store.close_early_research_case(
                project_id,
                outcome=cast(ResearchOutcome, outcome),
                disposition=cast(ResearchDisposition, disposition),
                actor=actor,
                reason=reason,
            )
            row = store.research_case_summary(project_id)
            _emit(
                {"decision": decision, "case": row},
                json_out=json_out,
                fallback=f"closed research case {project_id}: {outcome} / {disposition}",
            )
            return
        contract_id = str(case["active_contract_id"])
        decision = store.record_research_decision(
            project_id,
            contract_id,
            outcome=cast(ResearchOutcome, outcome),
            disposition=cast(ResearchDisposition, disposition),
            actor=actor,
            actor_kind="human",
            reason=reason,
        )
        if case["execution_state"] != "idle":
            store.transition_research_execution(
                project_id,
                to_state="idle",
                contract_id=contract_id,
                actor=actor,
                reason="the owner recorded the terminal research disposition",
                next_action="Close the governed research case.",
                responsibility="owner",
                checkpoint=cast(str | None, case["checkpoint"]),
            )
        store.transition_research_phase(
            project_id,
            to_phase="closed",
            contract_id=contract_id,
            actor=actor,
            reason="owner recorded the terminal research disposition",
            next_action="Research case is closed; any revision starts a new contract lineage.",
            responsibility="owner",
        )
        row = store.research_case_summary(project_id)
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit(
        {"decision": decision, "case": row},
        json_out=json_out,
        fallback=f"closed research case {project_id}: {outcome} / {disposition}",
    )


def _spec(name: str) -> Any:
    from alpha_cli import _runner

    return _runner.RunSpec(
        lookback=252,
        skip=21,
        vol_window=63,
        target_vol=0.15,
        rebalance_every=21,
        max_leverage=1.0,
        allow_short=True,
        periods_per_year=252,
        fee_bps=1.0,
        slippage_bps=2.0,
        starting_cash=1_000_000.0,
        account_type="MARGIN",  # avoid CASH order-rejection so the comparison reflects the signal
        train_size=504,
        test_size=63,
        embargo=5,
        anchored=False,
        strategy_name=name,
    )


@research_app.command()
def compare(
    symbol: str,
    strategies: str = typer.Option("", help="comma-separated; default = all engine strategies"),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Backtest each strategy on SYMBOL and rank them by total return."""
    from alpha_cli import _runner, _strategies

    names = [s.strip() for s in strategies.split(",") if s.strip()] or [
        # kronos needs a precomputed forecast cache (built by backtest/validate/optim, not this
        # lightweight comparison spec), so exclude it from the default all-strategies sweep.
        n
        for n in _strategies.known_strategies()
        if n != "kronos"
    ]
    settings = AlphaSettings()
    try:
        bars, _ = _runner.load_bars(symbol, data_dir=settings.data_dir)
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc

    rows: list[dict[str, Any]] = []
    for name in names:
        try:
            result = _runner.run_full_backtest(bars, _spec(name))
            total = result.final_equity / result.starting_equity - 1.0
            rows.append(
                {
                    "strategy": name,
                    "total_return": total,
                    "final_equity": result.final_equity,
                    "n_trades": len(result.trades),
                    "error": None,
                }
            )
        except DataError as exc:  # e.g. warmup exceeds the available bars — report, keep comparing
            rows.append({"strategy": name, "total_return": None, "error": str(exc)})

    rows.sort(
        key=lambda r: (r["total_return"] is not None, r.get("total_return") or 0.0), reverse=True
    )
    payload = {"symbol": symbol, "n_bars": len(bars), "ranked": rows}
    if json_out:
        typer.echo(json.dumps(payload))
        return
    for r in rows:
        if r["error"]:
            typer.echo(f"{r['strategy']:>16}: (skipped — {r['error']})")
        else:
            typer.echo(
                f"{r['strategy']:>16}: return={r['total_return']:+.4f} trades={r['n_trades']}"
            )
