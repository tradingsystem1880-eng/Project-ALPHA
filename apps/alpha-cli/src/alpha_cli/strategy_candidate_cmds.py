"""Explicit sandbox-only development-candidate commands."""

from __future__ import annotations

import json

import typer

from alpha_cli import _runner
from alpha_cli.crypto_data_cmds import crypto_hedged_basis_observations
from alpha_cli.strategy_candidate import hedged_basis_paper_preflight
from alpha_cli.strategy_candidate_runtime import run_hedged_basis_candidate
from alpha_core import DataError
from alpha_core.config import AlphaSettings

strategy_candidate_app = typer.Typer(
    help="Sandbox-only multi-leg candidate evaluation; no paper or order authority."
)


@strategy_candidate_app.command("run")
def run(
    snapshot_id: str,
    research_contract_id: str = typer.Option(...),
    analysis: str = typer.Option("baseline", help="registered candidate analysis"),
    source_run_id: str | None = typer.Option(None, help="exact upstream validation run"),
    as_of: str | None = typer.Option(None, help="inclusive pre-holdout cutoff YYYY-MM-DD"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Evaluate a frozen candidate stream; never constructs either venue adapter."""
    settings = AlphaSettings()
    try:
        cutoff = _runner.parse_as_of(as_of)
        observations = crypto_hedged_basis_observations(snapshot_id)
        manifest = run_hedged_basis_candidate(
            settings.data_dir,
            snapshot_id=snapshot_id,
            snapshot_hash=str(_runner.verified_snapshot_hash(settings.data_dir, snapshot_id)),
            research_contract_id=research_contract_id,
            observations=observations,
            analysis=analysis,
            source_run_id=source_run_id,
            research_cutoff=as_of,
            as_of=cutoff,
        )
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    if json_out:
        typer.echo(json.dumps(manifest, sort_keys=True, allow_nan=False))
        return
    typer.echo(f"hedged basis {analysis} -> run {manifest['run_id']} (SANDBOX ONLY)")


@strategy_candidate_app.command("paper-preflight")
def paper_preflight(json_out: bool = typer.Option(False, "--json")) -> None:
    """Report the permanent unsupported multi-venue paper boundary without connecting."""
    result = hedged_basis_paper_preflight()
    if json_out:
        typer.echo(json.dumps(result, sort_keys=True, allow_nan=False))
        return
    typer.echo(
        f"{result['code']}: deterministic sandbox evaluation remains available; "
        "no broker connection or order was attempted."
    )


__all__ = ["strategy_candidate_app"]
