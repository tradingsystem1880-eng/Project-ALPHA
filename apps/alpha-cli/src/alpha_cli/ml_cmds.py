"""CLI projections for the isolated Qlib JSON/Parquet exchange contract."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Annotated, Any

import typer

from alpha_cli._ml_replay import run_ml_replay
from alpha_cli._runner import parse_as_of
from alpha_cli.ml_contract import (
    MLContractError,
    evaluate_result_bundle,
    prepare_exchange,
    publish_replay_signal_frame,
    sha256_file,
    validate_input_anchor,
    validate_request_bundle,
    validate_result_bundle,
)
from alpha_cli.ml_input import export_project_input
from alpha_core import DataError
from alpha_core.config import AlphaSettings

ml_app = typer.Typer(help="Prepare and validate isolated cross-sectional ML worker exchanges.")


def _default_worker_project() -> Path:
    return Path(__file__).resolve().parents[4] / "workers" / "qlib"


def _worker_project(path: Path | None) -> tuple[Path, Path]:
    project = _default_worker_project() if path is None else Path(path)
    if project.is_symlink() or not project.is_dir():
        raise MLContractError(f"Qlib worker project must be a regular directory: {project}")
    if not (project / "pyproject.toml").is_file():
        raise MLContractError(f"Qlib worker project is missing pyproject.toml: {project}")
    lock = project / "uv.lock"
    if lock.is_symlink() or not lock.is_file():
        raise MLContractError(f"Qlib worker project is missing a regular uv.lock: {project}")
    return project, lock


def _emit(value: dict[str, Any], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(value, sort_keys=True, allow_nan=False))
        return
    for key, item in value.items():
        typer.echo(f"{key}: {item}")


@ml_app.command("export-input")
def export_input(
    project_id: Annotated[str, typer.Argument(help="strategy project id")],
    experiment_id: Annotated[str, typer.Argument(help="immutable experiment id")],
    output: Annotated[Path, typer.Argument(help="new immutable input-bundle directory")],
    as_of: Annotated[
        str | None,
        typer.Option("--as-of", help="inclusive research cutoff YYYY-MM-DD"),
    ] = None,
    as_json: Annotated[bool, typer.Option("--json", help="emit machine-readable JSON")] = False,
) -> None:
    """Generate a validated Alpha158 starter bundle from one frozen ALPHA snapshot."""
    try:
        summary = export_project_input(
            data_dir=AlphaSettings().data_dir,
            project_id=project_id,
            experiment_id=experiment_id,
            output_dir=output,
            as_of=parse_as_of(as_of),
        )
    except (DataError, MLContractError, OSError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit(summary, as_json=as_json)


@ml_app.command()
def prepare(
    spec: Annotated[Path, typer.Argument(help="experiment spec JSON")],
    panel: Annotated[Path, typer.Argument(help="aligned OHLCV panel Parquet")],
    exchange: Annotated[Path, typer.Argument(help="new immutable exchange directory")],
    worker_lock: Annotated[
        Path | None,
        typer.Option(
            "--worker-lock",
            help="optional lockfile whose SHA-256 must match worker_lock_hash",
        ),
    ] = None,
    as_json: Annotated[bool, typer.Option("--json", help="emit machine-readable JSON")] = False,
) -> None:
    """Validate and atomically publish a worker request bundle."""
    try:
        request = prepare_exchange(spec, panel, exchange, worker_lock_path=worker_lock)
    except MLContractError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit(
        {
            "status": "prepared",
            "exchange": str(exchange),
            "config_hash": request["config_hash"],
            "snapshot_hash": request["snapshot_hash"],
            "worker_lock_hash": request["worker_lock_hash"],
        },
        as_json=as_json,
    )


@ml_app.command()
def train(
    exchange: Annotated[Path, typer.Argument(help="prepared worker exchange directory")],
    mode: Annotated[
        str,
        typer.Option("--mode", help="real Qlib/LightGBM or deterministic fake worker"),
    ] = "real",
    worker_project: Annotated[
        Path | None,
        typer.Option(
            "--worker-project",
            help="isolated worker project (default: repository workers/qlib)",
        ),
    ] = None,
    no_sync: Annotated[
        bool,
        typer.Option(
            "--no-sync",
            help="require an already-synced worker environment; never install dependencies",
        ),
    ] = False,
    timeout_seconds: Annotated[
        int,
        typer.Option(
            "--timeout-seconds",
            min=60,
            max=86_400,
            help="hard worker timeout",
        ),
    ] = 7_200,
    as_json: Annotated[bool, typer.Option("--json", help="emit machine-readable JSON")] = False,
) -> None:
    """Run the separately locked worker and validate its portable result."""
    if mode not in {"real", "fake"}:
        raise typer.BadParameter("--mode must be 'real' or 'fake'")
    try:
        request = validate_request_bundle(exchange)
        expected_input_anchor = validate_input_anchor(exchange)
        project, lock = _worker_project(worker_project)
        actual_lock_hash = sha256_file(lock)
        if request.request["worker_lock_hash"] != actual_lock_hash:
            raise MLContractError(
                "request worker_lock_hash does not match the selected isolated worker lock"
            )
        uv = shutil.which("uv")
        if uv is None:
            raise MLContractError("uv is required to launch the isolated Qlib worker")
        command = [uv, "run", "--project", str(project), "--locked"]
        if no_sync:
            command.append("--no-sync")
        command.extend(
            [
                "alpha-qlib-worker",
                mode,
                str(Path(exchange).resolve()),
                "--worker-lock",
                str(lock.resolve()),
            ]
        )
        environment = dict(os.environ)
        environment["PYTHONHASHSEED"] = str(request.request["seed"])
        completed = subprocess.run(
            command,
            cwd=project,
            env=environment,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        if completed.returncode != 0:
            detail = "\n".join(
                [*completed.stdout.splitlines(), *completed.stderr.splitlines()][-20:]
            )
            raise MLContractError(
                f"isolated {mode} worker failed with exit {completed.returncode}: {detail}"
            )
        validated = validate_result_bundle(exchange, expected_input_anchor=expected_input_anchor)
    except subprocess.TimeoutExpired as exc:
        raise typer.BadParameter(
            f"isolated {mode} worker exceeded {timeout_seconds} seconds"
        ) from exc
    except (MLContractError, OSError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit(
        {
            "status": "trained",
            "mode": mode,
            "exchange": str(exchange),
            "rows": validated.predictions.height,
            "worker": validated.result["worker"],
            "config_hash": validated.result["config_hash"],
            "worker_lock_hash": validated.result["worker_lock_hash"],
            "diagnostic_only": True,
            "counterfactual_refit": False,
        },
        as_json=as_json,
    )


@ml_app.command(name="import")
def import_result(
    exchange: Annotated[Path, typer.Argument(help="completed worker exchange directory")],
    as_json: Annotated[bool, typer.Option("--json", help="emit machine-readable JSON")] = False,
) -> None:
    """Validate a completed worker result without publishing an ALPHA run."""
    try:
        validated = validate_result_bundle(exchange)
    except MLContractError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit(
        {
            "status": "validated",
            "exchange": str(exchange),
            "rows": validated.predictions.height,
            "config_hash": validated.result["config_hash"],
            "worker_lock_hash": validated.result["worker_lock_hash"],
            "diagnostic_only": True,
            "next_required_step": (
                "canonical ALPHA replay: run `alpha ml replay EXCHANGE` for validation"
            ),
        },
        as_json=as_json,
    )


@ml_app.command()
def evaluate(
    exchange: Annotated[Path, typer.Argument(help="completed worker exchange directory")],
    as_json: Annotated[bool, typer.Option("--json", help="emit machine-readable JSON")] = False,
) -> None:
    """Compute portable score diagnostics; this is not an ALPHA verdict."""
    try:
        summary = evaluate_result_bundle(exchange)
    except MLContractError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit(summary, as_json=as_json)


@ml_app.command("prepare-replay")
def prepare_replay(
    exchange: Annotated[Path, typer.Argument(help="completed worker exchange directory")],
    output: Annotated[
        Path,
        typer.Argument(help="immutable replay_signals.parquet output path"),
    ],
    as_json: Annotated[bool, typer.Option("--json", help="emit machine-readable JSON")] = False,
) -> None:
    """Publish the causal top-quintile signal handoff for canonical ALPHA replay."""
    try:
        frame = publish_replay_signal_frame(exchange, output)
    except MLContractError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit(
        {
            "status": "replay_handoff_prepared",
            "output": str(output),
            "rows": frame.height,
            "selected_rows": frame.filter(frame["selected"]).height,
            "sha256": sha256_file(output),
            "authority": "signal_handoff_only",
            "next_required_step": "run `alpha ml replay EXCHANGE`",
        },
        as_json=as_json,
    )


@ml_app.command()
def replay(
    exchange: Annotated[Path, typer.Argument(help="completed worker exchange directory")],
    starting_cash: Annotated[
        float,
        typer.Option("--starting-cash", min=1.0, help="canonical replay starting net liquidation"),
    ] = 1_000_000.0,
    periods_per_year: Annotated[
        int,
        typer.Option("--periods-per-year", min=1, help="annualization periods for ALPHA metrics"),
    ] = 252,
    as_of: Annotated[
        str | None,
        typer.Option("--as-of", help="inclusive research cutoff YYYY-MM-DD"),
    ] = None,
    as_json: Annotated[bool, typer.Option("--json", help="emit machine-readable JSON")] = False,
) -> None:
    """Replay validated OOS predictions through ALPHA and publish an immutable v3 run."""
    try:
        result = run_ml_replay(
            exchange,
            data_dir=AlphaSettings().data_dir,
            starting_cash=starting_cash,
            periods_per_year=periods_per_year,
            research_cutoff=parse_as_of(as_of),
        )
    except (DataError, MLContractError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    manifest = result.manifest
    _emit(
        {
            "status": "replayed",
            "run_id": result.run_id,
            "authority": manifest["authority"],
            "label": manifest["label"],
            "n_oos_periods": manifest["n_oos_periods"],
            "metrics": manifest["metrics"],
            "validation": manifest["validation"],
        },
        as_json=as_json,
    )
