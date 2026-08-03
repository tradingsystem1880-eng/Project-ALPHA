"""``alpha suite`` — allowlisted, durable Strategy Development execution."""

from __future__ import annotations

import json
import signal
from typing import cast

import typer

from alpha_cli._suite import (
    SUITE_ACTIONS,
    SuiteAction,
    build_suite_plan,
    execute_suite,
    reserve_suite_job,
)
from alpha_cli.control_store import ControlStore
from alpha_core import DataError
from alpha_core.config import AlphaSettings

suite_app = typer.Typer(
    help="Preview and run immutable, allowlisted Strategy Development workflows."
)


def _context() -> tuple[ControlStore, AlphaSettings]:
    settings = AlphaSettings()
    return ControlStore(settings.data_dir), settings


def _emit(value: object, *, json_out: bool, fallback: str) -> None:
    if json_out:
        typer.echo(json.dumps(value, sort_keys=True, allow_nan=False))
    else:
        typer.echo(fallback)


@suite_app.command("actions")
def actions(json_out: bool = typer.Option(False, "--json")) -> None:
    """List the fixed public action identifiers."""
    rows = [{"action": action} for action in sorted(SUITE_ACTIONS)]
    _emit(rows, json_out=json_out, fallback="\n".join(row["action"] for row in rows))


@suite_app.command("plan")
def plan(
    project_id: str,
    experiment_id: str,
    action: str,
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Resolve immutable inputs, readiness, governance, commands, and workload without running."""
    store, settings = _context()
    try:
        resolved = build_suite_plan(
            store,
            project_id,
            experiment_id,
            cast(SuiteAction, action),
            data_dir=settings.data_dir,
        )
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    status = "READY" if resolved.ready else "BLOCKED: " + "; ".join(resolved.blockers)
    _emit(resolved.as_dict(), json_out=json_out, fallback=f"{action}: {status}")


@suite_app.command("run")
def run(
    project_id: str,
    experiment_id: str,
    action: str,
    job_id: str | None = typer.Option(None, help="preallocated canonical UUID for detached launch"),
    owner_actor: str | None = typer.Option(None, help="required only for final holdout reveal"),
    owner_reason: str | None = typer.Option(None, help="required only for final holdout reveal"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Execute exactly one ready allowlisted plan and persist its complete durable journal."""
    store, settings = _context()
    cancelled = False

    def request_cancel(_signum: int, _frame: object) -> None:
        nonlocal cancelled
        cancelled = True

    previous = signal.getsignal(signal.SIGTERM)
    signal.signal(signal.SIGTERM, request_cancel)
    try:
        resolved = build_suite_plan(
            store,
            project_id,
            experiment_id,
            cast(SuiteAction, action),
            data_dir=settings.data_dir,
            resume_job_id=job_id,
        )
        result = execute_suite(
            store,
            resolved,
            data_dir=settings.data_dir,
            job_id=job_id,
            owner_actor=owner_actor,
            owner_reason=owner_reason,
            cancelled=lambda: cancelled,
        )
    except InterruptedError as exc:
        raise typer.BadParameter("suite action was cancelled") from exc
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    finally:
        signal.signal(signal.SIGTERM, previous)
    _emit(
        result,
        json_out=json_out,
        fallback=f"suite {action} -> job {result['job_id']} {result['status']}",
    )


@suite_app.command("reserve")
def reserve(
    project_id: str,
    experiment_id: str,
    action: str,
    job_id: str = typer.Option(..., help="preallocated canonical UUID for detached launch"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Persist the exact queued journal before a detached suite worker is spawned."""
    store, settings = _context()
    try:
        resolved = build_suite_plan(
            store,
            project_id,
            experiment_id,
            cast(SuiteAction, action),
            data_dir=settings.data_dir,
        )
        job = reserve_suite_job(store, resolved, job_id=job_id)
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    result = {"job_id": job["job_id"], "status": job["status"], "plan": resolved.as_dict()}
    _emit(result, json_out=json_out, fallback=f"reserved suite {action} -> job {job_id}")


@suite_app.command("status")
def status(
    job_id: str,
    event_limit: int = typer.Option(200, min=1, max=500),
    event_offset: int = typer.Option(0, min=0),
    event_tail: bool = typer.Option(False, "--event-tail"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Read one durable job and its bounded journal."""
    store, _ = _context()
    try:
        row = store.get_job(
            job_id,
            event_limit=event_limit,
            event_offset=event_offset,
            event_tail=event_tail,
        )
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit(row, json_out=json_out, fallback=f"job {job_id} {row['status']}")


__all__ = ["suite_app"]
