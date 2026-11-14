"""Bounded Strategy Development suite planning and durable execution.

The public plan contains only immutable project inputs and allowlisted command previews.  Actual
execution stays in ``alpha_cli`` and launches existing ``alpha`` commands; web/MCP surfaces never
construct engine flags or accept a filesystem path.
"""

from __future__ import annotations

import hashlib
import json
import math as math
import os
import re
import selectors
import signal
import subprocess
import time
from collections.abc import Callable, Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass, replace
from datetime import date, timedelta
from pathlib import Path
from typing import Final, cast

from alpha_cli._schemas import specs_for
from alpha_cli._suite_actions import _baseline_steps as _baseline_steps
from alpha_cli._suite_actions import _candidate_holdout_steps as _candidate_holdout_steps
from alpha_cli._suite_actions import _candidate_monte_carlo_steps as _candidate_monte_carlo_steps
from alpha_cli._suite_actions import _candidate_paper_steps as _candidate_paper_steps
from alpha_cli._suite_actions import _candidate_simple_steps as _candidate_simple_steps
from alpha_cli._suite_actions import _candidate_step as _candidate_step
from alpha_cli._suite_actions import _fixed_stress_steps as _fixed_stress_steps
from alpha_cli._suite_actions import _grid_steps as _grid_steps
from alpha_cli._suite_actions import _holdout_steps as _holdout_steps
from alpha_cli._suite_actions import _inner_oos_steps as _inner_oos_steps
from alpha_cli._suite_actions import _kronos_steps as _kronos_steps
from alpha_cli._suite_actions import _monte_carlo_steps as _monte_carlo_steps
from alpha_cli._suite_actions import _null_family_steps as _null_family_steps
from alpha_cli._suite_actions import _optimize_grid_steps as _optimize_grid_steps
from alpha_cli._suite_actions import _paper_preflight_steps as _paper_preflight_steps
from alpha_cli._suite_actions import _portfolio_cross_asset_steps as _portfolio_cross_asset_steps
from alpha_cli._suite_actions import _qlib_steps as _qlib_steps
from alpha_cli._suite_actions import _three_null_families_steps as _three_null_families_steps
from alpha_cli._suite_actions import _unsupported_candidate_steps as _unsupported_candidate_steps
from alpha_cli._suite_types import _CANDIDATE_SIMPLE_ACTIONS as _CANDIDATE_SIMPLE_ACTIONS
from alpha_cli._suite_types import _CANDIDATE_SIMPLE_GOVERNANCE as _CANDIDATE_SIMPLE_GOVERNANCE
from alpha_cli._suite_types import _SAFE_ID as _SAFE_ID
from alpha_cli._suite_types import _SAFE_MODEL as _SAFE_MODEL
from alpha_cli._suite_types import _SAFE_REVISION as _SAFE_REVISION
from alpha_cli._suite_types import _STANDARD_DEFINITION_OPTIONS as _STANDARD_DEFINITION_OPTIONS
from alpha_cli._suite_types import SuitePlan as SuitePlan
from alpha_cli._suite_types import SuiteStep as SuiteStep
from alpha_cli._suite_types import _common as _common
from alpha_cli._suite_types import _cutoff_preview as _cutoff_preview
from alpha_cli._suite_types import _definition_options as _definition_options
from alpha_cli._suite_types import _float_text as _float_text
from alpha_cli._suite_types import _integer as _integer
from alpha_cli._suite_types import _latest_run as _latest_run
from alpha_cli._suite_types import _latest_run_for_command as _latest_run_for_command
from alpha_cli._suite_types import _managed_qlib_id as _managed_qlib_id
from alpha_cli._suite_types import _number as _number
from alpha_cli._suite_types import _object as _object
from alpha_cli._suite_types import _PlanContext
from alpha_cli._suite_types import _ResearchWindow as _ResearchWindow
from alpha_cli._suite_types import _safe_id as _safe_id
from alpha_cli._suite_types import _seed as _seed
from alpha_cli._suite_types import _selected as _selected
from alpha_cli._suite_types import _split_options as _split_options
from alpha_cli._suite_types import _stage_float as _stage_float
from alpha_cli._suite_types import _stage_int as _stage_int
from alpha_cli._suite_types import _stage_states as _stage_states
from alpha_cli._suite_types import _strategy_options as _strategy_options
from alpha_cli._suite_types import _workload as _workload
from alpha_cli.control_store import AttemptStatus, ControlStore, StageState
from alpha_cli.run_store import RESEARCH_GATE_OVERRIDE_WATERMARK
from alpha_cli.strategy_candidate import (
    registered_hedged_basis_candidate,
    validate_hedged_basis_definition,
)
from alpha_cli.suite_catalog import SUITE_ACTIONS
from alpha_cli.suite_catalog import SuiteActionValue as SuiteAction
from alpha_core import DataError

_ACTION_STAGE: Final[dict[str, str]] = {
    "baseline": "baseline",
    "inner_oos": "oos",
    "three_null_families": "robustness",
    "monte_carlo": "monte_carlo",
    "optimize_grid": "optimization",
    "fixed_stress": "robustness",
    "portfolio_cross_asset": "portfolio",
    "qlib": "ml",
    "kronos": "kronos",
    "holdout_reveal": "holdout",
    "paper_preflight": "paper",
}


_RUN_BACKED_STAGE_ACTIONS: Final = frozenset(
    {
        "baseline",
        "inner_oos",
        "three_null_families",
        "monte_carlo",
        "optimize_grid",
        "portfolio_cross_asset",
        "qlib",
        "kronos",
        "holdout_reveal",
    }
)


_GOVERNED_STAGE_ACTIONS: Final = _RUN_BACKED_STAGE_ACTIONS | {"paper_preflight"}


_PRE_REVEAL_RESEARCH_ACTIONS: Final = frozenset(
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
    }
)


_PREREQUISITES: Final[dict[str, tuple[str, ...]]] = {
    "baseline": (),
    "inner_oos": ("baseline",),
    "three_null_families": ("oos",),
    "monte_carlo": ("robustness",),
    "optimize_grid": ("oos", "robustness", "monte_carlo"),
    "fixed_stress": ("baseline",),
    "portfolio_cross_asset": ("robustness", "optimization"),
    "qlib": ("data", "strategy"),
    "kronos": ("data",),
    "holdout_reveal": (
        "baseline",
        "oos",
        "robustness",
        "monte_carlo",
        "optimization",
        "portfolio",
        "candidate",
    ),
    "paper_preflight": ("holdout",),
}


_RUN_RE = re.compile(r"->\s+run\s+([0-9a-f]{16})\b")


_JSON_RUN_RE = re.compile(r'"run_id"\s*:\s*"([0-9a-f]{16})"')


_PROCESS_TERM_GRACE_SECONDS: Final = 2.0


_PROCESS_REAP_TIMEOUT_SECONDS: Final = 2.0


_PROCESS_GROUP_POLL_SECONDS: Final = 0.05


_SUITE_HEARTBEAT_INTERVAL_SECONDS: Final = 5.0


@dataclass(frozen=True)
class StepExecution:
    returncode: int
    run_ids: tuple[str, ...]


class SuiteProcessCleanupError(DataError):
    """An isolated suite process group could not be verified stopped."""


type StepRunner = Callable[[SuiteStep, str, ControlStore, Callable[[], bool]], StepExecution]


def _resolve_experiment(
    store: ControlStore,
    project_id: str,
    experiment_id: str,
    action: SuiteAction,
    *,
    data_dir: Path,
    resume_job_id: str | None,
) -> _PlanContext:
    if action not in SUITE_ACTIONS:
        raise DataError(f"unsupported suite action {action!r}; known: {sorted(SUITE_ACTIONS)}")
    project = store.get_project(project_id)
    experiment = _selected(
        project.get("experiments"),
        id_field="experiment_id",
        item_id=experiment_id,
        label="experiment",
    )
    version_id = str(experiment["strategy_version_id"])
    version = _selected(
        project.get("versions"),
        id_field="version_id",
        item_id=version_id,
        label="strategy version",
    )
    stage = _ACTION_STAGE[action]
    states = _stage_states(project, experiment_id)
    current_state = states.get(stage, "not_started")
    resume_reveal = bool(
        action == "holdout_reveal"
        and resume_job_id is not None
        and store.holdout_reveal_resume_authorized(
            project_id,
            experiment_id,
            resume_job_id,
            require_terminal=True,
        )
    )
    blockers: list[str] = []
    if project.get("current_experiment_id") != experiment_id:
        blockers.append("experiment is not the project's current immutable specification")
    if current_state in {"queued", "running", "fail", "stale"} and not resume_reveal:
        blockers.append(f"{stage} stage is {current_state}")
    for prerequisite in _PREREQUISITES[action]:
        prerequisite_state = states.get(prerequisite)
        if action == "monte_carlo" and prerequisite == "robustness":
            if prerequisite_state not in {"pass", "warning", "fail"}:
                blockers.append("robustness stage must be completed")
            continue
        if prerequisite == "monte_carlo" and prerequisite_state == "warning":
            if not store.monte_carlo_review_allows_progression(project_id, experiment_id):
                blockers.append("Monte Carlo warning requires an owner continue decision")
            continue
        if prerequisite_state not in {"pass", "warning"}:
            blockers.append(f"{prerequisite} stage must be pass or warning")

    return _PlanContext(
        store=store,
        project_id=project_id,
        experiment_id=experiment_id,
        action=action,
        data_dir=data_dir,
        project=project,
        experiment=experiment,
        version=version,
        stage=stage,
        states=states,
        current_state=current_state,
        resume_reveal=resume_reveal,
        blockers=blockers,
    )


def _resolve_immutable_inputs(ctx: _PlanContext) -> _PlanContext:
    universe_raw = ctx.experiment.get("universe")
    if not isinstance(universe_raw, list) or not universe_raw:
        raise DataError("invalid immutable experiment universe")
    universe = sorted(str(symbol) for symbol in universe_raw)
    primary = universe[0]
    snapshot = _safe_id(ctx.experiment.get("snapshot_id"), "snapshot_id")
    strategy = str(ctx.version.get("strategy_name"))
    definition = _object(ctx.version.get("definition"), "strategy definition")
    hedged_basis = strategy == registered_hedged_basis_candidate().strategy_name
    if hedged_basis:
        validate_hedged_basis_definition(definition)
        research_contract_id = ctx.version.get("research_contract_id")
        if not isinstance(research_contract_id, str):
            ctx.blockers.append("hedged basis candidate requires its promoted research contract")
            research_contract_id = "<promoted-research-contract-required>"
    else:
        specs_for(strategy)  # fail closed before building any argv
        research_contract_id = None
    parameter_space = _object(ctx.version.get("parameter_space"), "parameter space")
    split = _object(ctx.experiment.get("split_policy"), "split policy")
    costs = _object(ctx.experiment.get("costs"), "costs")
    seeds = _object(ctx.experiment.get("seeds"), "seeds")
    config = _object(ctx.experiment.get("stage_config"), "stage configuration")

    holdouts = ctx.project.get("holdouts")
    holdout = (
        next(
            (
                _object(row, "holdout state")
                for row in holdouts
                if isinstance(holdouts, list)
                and isinstance(row, dict)
                and row.get("experiment_id") == ctx.experiment_id
            ),
            None,
        )
        if isinstance(holdouts, list)
        else None
    )
    sealed_spec = ctx.store.get_holdout_spec(ctx.project_id, ctx.experiment_id)

    return replace(
        ctx,
        universe=universe,
        primary=primary,
        snapshot=snapshot,
        strategy=strategy,
        definition=definition,
        hedged_basis=hedged_basis,
        research_contract_id=research_contract_id,
        parameter_space=parameter_space,
        split=split,
        costs=costs,
        seeds=seeds,
        config=config,
        holdout=holdout,
        sealed_spec=sealed_spec,
    )


def _resolve_research_window(ctx: _PlanContext) -> _PlanContext:
    research_cutoff: str | None = None
    cutoff_marker: str | None = None
    if ctx.action in _PRE_REVEAL_RESEARCH_ACTIONS:
        if ctx.sealed_spec is None or ctx.holdout is None:
            ctx.blockers.append("dated final holdout must be sealed before research begins")
        elif ctx.holdout.get("revealed_at") is not None:
            ctx.blockers.append("research cannot resume after the final holdout is revealed")
        elif ctx.holdout.get("contaminated_at") is not None:
            ctx.blockers.append("final holdout is contaminated for this lineage")
        else:
            holdout_start = date.fromisoformat(str(ctx.sealed_spec["start_date"]))
            research_cutoff = (holdout_start - timedelta(days=1)).isoformat()
            cutoff_marker = f"<sealed-pre-holdout:{ctx.sealed_spec['spec_hash']}>"

    # spec §15 / ADR-0026: an owner override is the only unlinked path through a governed gate;
    # every strategy run launched under it carries the permanent EXPLORATORY watermark.
    gate_overridden = ctx.project.get("research_gate_state") == "overridden"
    common = (
        []
        if ctx.hedged_basis
        else _common(
            symbol=ctx.primary,
            strategy=ctx.strategy,
            snapshot=ctx.snapshot,
            costs=ctx.costs,
            definition=ctx.definition,
            gate_overridden=gate_overridden,
        )
    )
    cutoff_value = research_cutoff or "<sealed-research-cutoff-required>"
    public_cutoff = cutoff_marker or "<sealed-research-cutoff-required>"
    window = _ResearchWindow(cutoff_value, public_cutoff)
    research_common = [*common]
    if ctx.action in _PRE_REVEAL_RESEARCH_ACTIONS:
        research_common.extend(["--as-of", cutoff_value])
    governance: dict[str, object] = {
        "paper_only": True,
        "holdout_visible_to_optimization": False,
        "command_construction": "allowlisted",
    }
    if gate_overridden:
        governance["research_gate"] = {
            "state": "overridden",
            "watermark": RESEARCH_GATE_OVERRIDE_WATERMARK,
        }
    if ctx.action in _PRE_REVEAL_RESEARCH_ACTIONS:
        governance.update(
            {
                "sealed_holdout_required_before_research": True,
                "research_window": public_cutoff,
                "sealed_dates_visible": False,
            }
        )

    return replace(
        ctx,
        gate_overridden=gate_overridden,
        common=common,
        research_common=research_common,
        window=window,
        governance=governance,
    )


def _build_action_steps(ctx: _PlanContext) -> tuple[list[SuiteStep], dict[str, object]]:
    if ctx.hedged_basis and ctx.action in _CANDIDATE_SIMPLE_ACTIONS:
        return _candidate_simple_steps(ctx)
    if ctx.hedged_basis and ctx.action == "monte_carlo":
        return _candidate_monte_carlo_steps(ctx)
    if ctx.hedged_basis and ctx.action == "holdout_reveal":
        return _candidate_holdout_steps(ctx)
    if ctx.hedged_basis and ctx.action == "paper_preflight":
        return _candidate_paper_steps(ctx)
    if ctx.hedged_basis:
        return _unsupported_candidate_steps(ctx)
    if ctx.action == "baseline":
        return _baseline_steps(ctx)
    if ctx.action == "inner_oos":
        return _inner_oos_steps(ctx)
    if ctx.action == "three_null_families":
        return _three_null_families_steps(ctx)
    if ctx.action == "monte_carlo":
        return _monte_carlo_steps(ctx)
    if ctx.action == "optimize_grid":
        return _optimize_grid_steps(ctx)
    if ctx.action == "fixed_stress":
        return _fixed_stress_steps(ctx)
    if ctx.action == "portfolio_cross_asset":
        return _portfolio_cross_asset_steps(ctx)
    if ctx.action == "qlib":
        return _qlib_steps(ctx)
    if ctx.action == "kronos":
        return _kronos_steps(ctx)
    if ctx.action == "holdout_reveal":
        return _holdout_steps(ctx)
    return _paper_preflight_steps(ctx)


def build_suite_plan(
    store: ControlStore,
    project_id: str,
    experiment_id: str,
    action: SuiteAction,
    *,
    data_dir: Path,
    resume_job_id: str | None = None,
) -> SuitePlan:
    """Resolve one action solely from immutable, linked control-plane records."""
    ctx = _resolve_experiment(
        store,
        project_id,
        experiment_id,
        action,
        data_dir=data_dir,
        resume_job_id=resume_job_id,
    )
    ctx = _resolve_immutable_inputs(ctx)
    ctx = _resolve_research_window(ctx)
    steps, workload = _build_action_steps(ctx)
    return SuitePlan(
        schema_version=1,
        project_id=ctx.project_id,
        experiment_id=ctx.experiment_id,
        action=ctx.action,
        stage=ctx.stage,
        ready=not ctx.blockers,
        blockers=tuple(ctx.blockers),
        resolved_experiment=ctx.experiment,
        resolved_strategy_version=ctx.version,
        current_stage_state=ctx.current_state,
        estimated_workload=workload,
        steps=tuple(steps),
        governance=ctx.governance,
    )


def _fingerprint(plan: SuitePlan, step: SuiteStep, index: int) -> str:
    payload = {
        "schema_version": plan.schema_version,
        "experiment_id": plan.experiment_id,
        "action": plan.action,
        "step": index,
        "command": list(step.preview),
        "evidence_role": step.evidence_role,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return "suite:" + hashlib.sha256(canonical.encode()).hexdigest()


def _redact(line: str, step: SuiteStep) -> str:
    result = line
    for source, replacement in step.redactions:
        result = result.replace(source, replacement)
    return result[:8000]


def _process_group_exists(process_group_id: int) -> bool:
    try:
        os.killpg(process_group_id, 0)
    except ProcessLookupError:
        return False
    except PermissionError:  # pragma: no cover - the suite owns its child group.
        return True
    return True


def _terminate_process_group(process: subprocess.Popen[str]) -> None:
    """Terminate the isolated step session, then force-kill and reap after a fixed grace."""
    process_group_id = process.pid
    with suppress(ProcessLookupError):
        os.killpg(process_group_id, signal.SIGTERM)
    deadline = time.monotonic() + _PROCESS_TERM_GRACE_SECONDS
    while _process_group_exists(process_group_id):
        process.poll()  # Reap a cooperative group leader while descendants wind down.
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(_PROCESS_GROUP_POLL_SECONDS, remaining))
    if _process_group_exists(process_group_id):
        with suppress(ProcessLookupError):
            os.killpg(process_group_id, signal.SIGKILL)
        kill_deadline = time.monotonic() + _PROCESS_REAP_TIMEOUT_SECONDS
        while _process_group_exists(process_group_id):
            process.poll()
            remaining = kill_deadline - time.monotonic()
            if remaining <= 0:
                raise SuiteProcessCleanupError("suite process group still exists after SIGKILL")
            time.sleep(min(_PROCESS_GROUP_POLL_SECONDS, remaining))
    try:
        process.wait(timeout=_PROCESS_REAP_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired as exc:  # pragma: no cover - SIGKILL should be final.
        raise SuiteProcessCleanupError(
            "suite subprocess could not be reaped after SIGKILL"
        ) from exc


def _verified_process_group_exists(process: subprocess.Popen[str]) -> bool:
    """Reap an exited leader and fail closed if group liveness cannot be established."""
    try:
        process.poll()
        return _process_group_exists(process.pid)
    except Exception as exc:
        raise SuiteProcessCleanupError(
            f"suite process-group liveness could not be verified: {exc}"
        ) from exc


def _cleanup_process_group(process: subprocess.Popen[str]) -> None:
    """Verify post-spawn cleanup and normalize every ordinary cleanup failure."""
    try:
        if _verified_process_group_exists(process):
            _terminate_process_group(process)
    except SuiteProcessCleanupError:
        raise
    except Exception as exc:
        raise SuiteProcessCleanupError(
            f"suite process-group cleanup could not be verified: {exc}"
        ) from exc


def _default_step_runner(
    step: SuiteStep,
    job_id: str,
    store: ControlStore,
    cancelled: Callable[[], bool],
) -> StepExecution:
    process = subprocess.Popen(
        ["alpha", *step.argv],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        start_new_session=True,
    )
    stdout = process.stdout
    selector: selectors.BaseSelector | None = None
    run_ids: list[str] = []
    last_heartbeat = time.monotonic()
    termination_requested = False

    def record(raw: str) -> None:
        line = _redact(raw.rstrip("\n"), step)
        store.append_job_event(job_id, event_type="log", payload={"line": line})
        for pattern in (_RUN_RE, _JSON_RUN_RE):
            match = pattern.search(line)
            if match is not None and match.group(1) not in run_ids:
                run_ids.append(match.group(1))

    try:
        if stdout is None:  # pragma: no cover - PIPE guarantees stdout.
            raise DataError("suite subprocess did not expose stdout")
        selector = selectors.DefaultSelector()
        selector.register(stdout, selectors.EVENT_READ)
        stdout_open = True
        group_alive = _verified_process_group_exists(process)
        while stdout_open or group_alive:
            if cancelled() and group_alive and not termination_requested:
                _terminate_process_group(process)
                termination_requested = True
            if stdout_open:
                events = selector.select(timeout=0.5)
            else:
                time.sleep(0.5)
                events = []
            for _key, _ in events:
                raw = stdout.readline()
                if not raw:
                    selector.unregister(stdout)
                    stdout_open = False
                    break
                record(raw)
            group_alive = _verified_process_group_exists(process)
            if (
                group_alive
                and time.monotonic() - last_heartbeat >= _SUITE_HEARTBEAT_INTERVAL_SECONDS
            ):
                store.append_job_event(job_id, event_type="heartbeat", payload={"step": step.label})
                last_heartbeat = time.monotonic()
    finally:
        cleanup_error: SuiteProcessCleanupError | None = None
        close_error: Exception | None = None
        try:
            _cleanup_process_group(process)
        except SuiteProcessCleanupError as exc:
            cleanup_error = exc
        finally:
            if selector is not None:
                try:
                    selector.close()
                except Exception as exc:
                    close_error = exc
            if stdout is not None:
                try:
                    stdout.close()
                except Exception as exc:
                    if close_error is None:
                        close_error = exc
        if cleanup_error is not None:
            if close_error is not None:
                cleanup_error.add_note(f"resource close also failed: {close_error}")
            raise cleanup_error
        if close_error is not None:
            raise close_error
    return StepExecution(returncode=int(process.wait()), run_ids=tuple(run_ids))


def _prepare_stage(store: ControlStore, plan: SuitePlan) -> None:
    state = plan.current_stage_state
    if state == "not_started":
        store.append_experiment_stage_state(
            plan.project_id,
            plan.experiment_id,
            plan.stage,
            "ready",
            reason=f"suite plan {plan.action} resolved",
        )
        state = "ready"
    if state == "ready":
        store.append_experiment_stage_state(
            plan.project_id,
            plan.experiment_id,
            plan.stage,
            "queued",
            reason=f"suite action {plan.action} queued",
        )
        store.append_experiment_stage_state(
            plan.project_id,
            plan.experiment_id,
            plan.stage,
            "running",
            reason=f"suite action {plan.action} started",
        )


def _finish_stage(
    store: ControlStore,
    plan: SuitePlan,
    state: StageState,
    reason: str,
    *,
    job_id: str,
) -> None:
    detail = store.get_project(plan.project_id)
    current = _stage_states(detail, plan.experiment_id).get(plan.stage)
    if current == "running":
        if plan.action == "paper_preflight":
            store.complete_suite_journal_stage(
                plan.project_id,
                plan.experiment_id,
                suite_action=plan.action,
                stage=plan.stage,
                state=state,
                job_id=job_id,
                reason=reason,
            )
            return
        store.complete_suite_stage(
            plan.project_id,
            plan.experiment_id,
            suite_action=plan.action,
            stage=plan.stage,
            state=state,
            reason=reason,
        )


def _headline_state(data_dir: Path, plan: SuitePlan, run_ids: Sequence[str]) -> StageState:
    if (
        plan.action == "paper_preflight"
        and plan.governance.get("preflight_outcome") == "UNSUPPORTED_MULTI_VENUE_PAPER"
    ):
        return "fail"
    if not run_ids:
        return "pass"
    if plan.action not in {
        "three_null_families",
        "optimize_grid",
        "holdout_reveal",
    }:
        return "pass"
    from alpha_cli._artifacts import read_manifest
    from alpha_cli.run_store import find_run_dir

    run_dir = find_run_dir(data_dir, run_ids[0])
    if run_dir is None:
        raise DataError(f"suite result run {run_ids[0]!r} was not published")
    manifest = read_manifest(run_dir)
    if plan.action == "three_null_families" and manifest.get("command") == (
        "candidate_null_bootstrap"
    ):
        return "pass" if manifest.get("passed") is True else "fail"
    if plan.action in {"optimize_grid", "holdout_reveal"}:
        return "pass" if manifest.get("passed") is True else "fail"
    outcomes = manifest.get("outcomes")
    if isinstance(outcomes, list):
        headline = next(
            (
                row
                for row in outcomes
                if isinstance(row, dict) and row.get("name") == "randomized_price_null"
            ),
            None,
        )
        if isinstance(headline, dict):
            return "pass" if headline.get("passed") is True else "fail"
    return "fail"


def _monte_carlo_results(data_dir: Path, run_ids: Sequence[str]) -> list[tuple[str, StageState]]:
    """Read each family manifest once and map its declared status to a stage-link state."""
    from alpha_cli._artifacts import read_manifest
    from alpha_cli.run_store import find_run_dir

    status_states: dict[str, StageState] = {
        "clear": "pass",
        "warning": "warning",
        "fail": "fail",
    }
    results: list[tuple[str, StageState]] = []
    for run_id in run_ids:
        result_dir = find_run_dir(data_dir, run_id)
        if result_dir is None:
            raise DataError(f"suite result run {run_id!r} was not published")
        status = str(read_manifest(result_dir).get("status"))
        results.append((run_id, status_states.get(status, "fail")))
    return results


def _monte_carlo_stage_state(results: Sequence[tuple[str, StageState]]) -> StageState:
    states = {state for _, state in results}
    if "fail" in states:
        return "fail"
    if "warning" in states:
        return "warning"
    return "pass" if results and states == {"pass"} else "fail"


def _record_optimization_trial_attempts(
    store: ControlStore,
    plan: SuitePlan,
    *,
    data_dir: Path,
    job_id: str,
    run_ids: Sequence[str],
) -> None:
    """Project every declared grid row into the append-only project attempt ledger."""
    if plan.action != "optimize_grid":
        return
    if len(run_ids) != 1:
        raise DataError(
            "deterministic grid suite must publish exactly one canonical optimization run"
        )

    from alpha_cli import _optim
    from alpha_cli._artifacts import read_manifest
    from alpha_cli.artifact_contract import verify_manifest_artifacts
    from alpha_cli.run_store import find_run_dir

    run_id = run_ids[0]
    run_dir = find_run_dir(data_dir, run_id)
    if run_dir is None:
        raise DataError(f"optimization run {run_id!r} was not published")
    manifest = read_manifest(run_dir)
    verify_manifest_artifacts(run_dir, manifest)
    if manifest.get("command") == "candidate_optim":
        metadata = manifest.get("metadata")
        trials = metadata.get("trials") if isinstance(metadata, Mapping) else None
        if not isinstance(trials, list) or len(trials) != 3:
            raise DataError("candidate optimization requires its fixed three-cost ledger")
        for trial in trials:
            if not isinstance(trial, Mapping):
                raise DataError("candidate optimization trial is invalid")
            canonical = json.dumps(dict(trial), sort_keys=True, separators=(",", ":"))
            store.record_attempt(
                plan.project_id,
                plan.experiment_id,
                stage=plan.stage,
                status="completed",
                config_fingerprint=hashlib.sha256(canonical.encode()).hexdigest(),
                run_id=run_id,
                details={
                    "action": plan.action,
                    "job_id": job_id,
                    "trial": trial.get("trial"),
                    "total_round_trip_cost_bps": trial.get("total_round_trip_cost_bps"),
                    "mean_net_return": trial.get("mean_net_return"),
                    "selected": trial.get("selected"),
                    "selection_authority": "registered_40_bps_cost_remains_immutable",
                },
            )
        return
    if manifest.get("command") != "optim_grid":
        raise DataError(f"suite optimization evidence {run_id!r} is not an optim_grid run")

    for outcome in _optim.read_trial_ledger(run_dir):
        details: dict[str, object] = {
            "action": plan.action,
            "job_id": job_id,
            "trial": outcome.trial_index,
            "config": [[name, value] for name, value in outcome.config],
            "source_artifact": "trial_ledger.parquet",
            "row_selector": {"trial": outcome.trial_index},
            "n_oos": len(outcome.oos_returns),
            "annualized_sharpe": outcome.annualized_sharpe,
        }
        if outcome.status in {"pruned", "rejected"}:
            details["reason"] = outcome.error
        store.record_attempt(
            plan.project_id,
            plan.experiment_id,
            stage=plan.stage,
            status=cast(AttemptStatus, outcome.status),
            config_fingerprint=outcome.config_fingerprint,
            run_id=run_id,
            error=outcome.error if outcome.status == "failed" else None,
            details=details,
        )


def reserve_suite_job(
    store: ControlStore,
    plan: SuitePlan,
    *,
    job_id: str | None = None,
) -> dict[str, object]:
    """Persist/reuse the exact queued suite journal before a detached worker is launched."""
    if not plan.ready:
        raise DataError("suite plan is not ready: " + "; ".join(plan.blockers))
    return store.create_suite_job(
        kind=f"suite:{plan.action}",
        request=plan.as_dict(),
        project_id=plan.project_id,
        experiment_id=plan.experiment_id,
        job_id=job_id,
    )


def _start_suite_step(
    store: ControlStore,
    plan: SuitePlan,
    step: SuiteStep,
    index: int,
    job_id: str,
) -> str:
    """Journal the queued attempt and initial events before checking cancellation."""
    fingerprint = _fingerprint(plan, step, index)
    store.record_attempt(
        plan.project_id,
        plan.experiment_id,
        stage=plan.stage,
        status="queued",
        config_fingerprint=fingerprint,
        details={
            "action": plan.action,
            "job_id": job_id,
            "step": index,
            "label": step.label,
            "evidence_role": step.evidence_role,
        },
    )
    store.append_job_event(
        job_id,
        event_type="progress",
        payload={"step": index, "total": len(plan.steps), "label": step.label},
    )
    store.append_job_event(
        job_id,
        event_type="heartbeat",
        payload={"step": index, "label": step.label},
    )
    return fingerprint


def _complete_suite_execution(
    store: ControlStore,
    plan: SuitePlan,
    *,
    data_dir: Path,
    job_id: str,
    run_ids: list[str],
    request: dict[str, object],
) -> dict[str, object]:
    """Publish run links, final stage state and the successful job result in order."""
    _record_optimization_trial_attempts(
        store,
        plan,
        data_dir=data_dir,
        job_id=job_id,
        run_ids=run_ids,
    )
    if plan.action == "monte_carlo":
        linked_results = _monte_carlo_results(data_dir, run_ids)
        stage_state = _monte_carlo_stage_state(linked_results)
    else:
        stage_state = _headline_state(data_dir, plan, run_ids)
        linked_results = [(run_id, stage_state) for run_id in run_ids]
        if plan.action == "three_null_families" and run_ids:
            linked_results = [
                *((run_id, "warning") for run_id in run_ids[1:]),
                (run_ids[0], stage_state),
            ]
    for run_id, link_state in linked_results:
        store.link_suite_stage_run(
            plan.project_id,
            plan.experiment_id,
            suite_action=plan.action,
            stage=plan.stage,
            state=link_state,
            run_id=run_id,
        )
    if plan.action in _GOVERNED_STAGE_ACTIONS:
        _finish_stage(
            store,
            plan,
            stage_state,
            "suite completed; headline evidence governs stage state",
            job_id=job_id,
        )
    reported_stage_state = (
        stage_state if plan.action in _GOVERNED_STAGE_ACTIONS else plan.current_stage_state
    )
    result = {
        "action": plan.action,
        "stage": plan.stage,
        "stage_state": reported_stage_state,
        "run_ids": run_ids,
        "headline_run_id": run_ids[0] if run_ids else None,
    }
    store.append_job_result(job_id, result)
    completed = store.set_job_status(
        job_id,
        "succeeded",
        result_run_id=run_ids[0] if run_ids else None,
    )
    return {**completed, "plan": request, "result": result}


def _record_suite_cleanup_failure(
    store: ControlStore,
    plan: SuitePlan,
    job_id: str,
    index: int,
    exc: SuiteProcessCleanupError,
) -> None:
    """Keep capacity reserved when process cleanup cannot be verified."""
    if index:
        step = plan.steps[index - 1]
        store.record_attempt(
            plan.project_id,
            plan.experiment_id,
            stage=plan.stage,
            status="failed",
            config_fingerprint=_fingerprint(plan, step, index),
            error=str(exc)[:8000],
            details={
                "action": plan.action,
                "job_id": job_id,
                "step": index,
                "cleanup_unverified": True,
            },
        )
    store.append_job_event(
        job_id,
        event_type="log",
        payload={
            "line": (
                f"suite process-group cleanup failed: {exc}; heavyweight capacity remains reserved"
            )
        },
    )
    # A terminal journal would release the shared heavyweight slot even though a descendant
    # may still be executing. Leave both the stage and job running until stale-lease
    # reconciliation can surface the abandoned execution for an owner.


def execute_suite(
    store: ControlStore,
    plan: SuitePlan,
    *,
    data_dir: Path,
    job_id: str | None = None,
    owner_actor: str | None = None,
    owner_reason: str | None = None,
    cancelled: Callable[[], bool] = lambda: False,
    step_runner: StepRunner = _default_step_runner,
) -> dict[str, object]:
    """Execute a ready plan and journal every state, attempt, log, and result."""
    if not plan.ready:
        raise DataError("suite plan is not ready: " + "; ".join(plan.blockers))
    resume_reveal = plan.governance.get("resume_same_job_after_interruption") is True
    if (
        plan.action == "holdout_reveal"
        and not resume_reveal
        and (not owner_actor or not owner_reason)
    ):
        raise DataError("holdout reveal requires an explicit owner actor and reason")
    request = plan.as_dict()
    job = reserve_suite_job(store, plan, job_id=job_id)
    jid = str(job["job_id"])
    audited_reveal_for_job = bool(
        plan.action == "holdout_reveal"
        and store.holdout_reveal_resume_authorized(plan.project_id, plan.experiment_id, jid)
    )

    def cancellation_requested() -> bool:
        return cancelled() or store.job_cancellation_requested(jid)

    if plan.action in _GOVERNED_STAGE_ACTIONS:
        _prepare_stage(store, plan)
    store.set_job_status(jid, "running")
    run_ids: list[str] = []
    current_index = 0
    try:
        for current_index, step in enumerate(plan.steps, start=1):
            fingerprint = _start_suite_step(store, plan, step, current_index, jid)
            if cancellation_requested():
                raise InterruptedError("suite action cancelled")
            if step.argv == ("__holdout__",):
                if not audited_reveal_for_job:
                    store.reveal_holdout(
                        plan.project_id,
                        plan.experiment_id,
                        actor=cast(str, owner_actor),
                        reason=cast(str, owner_reason),
                    )
                execution = StepExecution(returncode=0, run_ids=())
            else:
                execution = step_runner(step, jid, store, cancellation_requested)
            if cancellation_requested():
                raise InterruptedError("suite action cancelled")
            if execution.returncode != 0:
                raise DataError(
                    f"suite step {current_index} {step.label!r} failed with exit "
                    f"{execution.returncode}"
                )
            for run_id in execution.run_ids:
                if run_id not in run_ids:
                    run_ids.append(run_id)
            store.record_attempt(
                plan.project_id,
                plan.experiment_id,
                stage=plan.stage,
                status="passed",
                config_fingerprint=fingerprint,
                run_id=execution.run_ids[0] if execution.run_ids else None,
                details={
                    "action": plan.action,
                    "job_id": jid,
                    "step": current_index,
                    "label": step.label,
                    "evidence_role": step.evidence_role,
                    "run_ids": list(execution.run_ids),
                },
            )
        return _complete_suite_execution(
            store,
            plan,
            data_dir=data_dir,
            job_id=jid,
            run_ids=run_ids,
            request=request,
        )
    except InterruptedError:
        if current_index:
            step = plan.steps[current_index - 1]
            store.record_attempt(
                plan.project_id,
                plan.experiment_id,
                stage=plan.stage,
                status="cancelled",
                config_fingerprint=_fingerprint(plan, step, current_index),
                details={"action": plan.action, "job_id": jid, "step": current_index},
            )
        resumable_holdout = bool(
            plan.action == "holdout_reveal"
            and store.holdout_reveal_resume_authorized(plan.project_id, plan.experiment_id, jid)
        )
        if plan.action in _GOVERNED_STAGE_ACTIONS and not resumable_holdout:
            _finish_stage(store, plan, "fail", "suite action cancelled", job_id=jid)
        store.set_job_status(jid, "cancelled")
        raise
    except SuiteProcessCleanupError as exc:
        _record_suite_cleanup_failure(store, plan, jid, current_index, exc)
        raise
    except Exception as exc:
        if current_index:
            step = plan.steps[current_index - 1]
            store.record_attempt(
                plan.project_id,
                plan.experiment_id,
                stage=plan.stage,
                status="failed",
                config_fingerprint=_fingerprint(plan, step, current_index),
                error=str(exc)[:8000],
                details={"action": plan.action, "job_id": jid, "step": current_index},
            )
        resumable_holdout = bool(
            plan.action == "holdout_reveal"
            and store.holdout_reveal_resume_authorized(plan.project_id, plan.experiment_id, jid)
        )
        if plan.action in _GOVERNED_STAGE_ACTIONS and not resumable_holdout:
            _finish_stage(store, plan, "fail", "suite action failed", job_id=jid)
        store.set_job_status(jid, "failed", terminal_error=str(exc)[:8000])
        raise


__all__ = [
    "SUITE_ACTIONS",
    "SuiteProcessCleanupError",
    "StepExecution",
    "SuiteAction",
    "SuitePlan",
    "SuiteStep",
    "build_suite_plan",
    "execute_suite",
    "reserve_suite_job",
]
