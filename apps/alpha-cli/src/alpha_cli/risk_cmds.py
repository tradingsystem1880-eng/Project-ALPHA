"""``alpha risk`` — stress / what-if scenarios over a stored run's realized return stream.

Composes the run store (read a run's equity curve) with ``alpha_validation.scenario_metrics``; a
``--json`` projection the Workstation's Risk panel renders. No engine re-run, no new artifacts.
"""

from __future__ import annotations

import dataclasses
import json

import typer

from alpha_core import DataError
from alpha_core.config import AlphaSettings

risk_app = typer.Typer(help="Risk & scenario analysis over stored runs.")


@risk_app.command()
def scenario(
    from_run: str = typer.Option(..., "--from-run", help="run id with an equity curve"),
    confidence: float = typer.Option(0.95, help="VaR / CVaR confidence"),
    periods_per_year: int = typer.Option(252, help="annualization factor"),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Re-evaluate risk under vol-scaling and tail-shock scenarios for a stored run."""
    from alpha_cli._artifacts import find_run_dir, read_equity, read_manifest
    from alpha_cli.artifact_contract import sha256_file
    from alpha_validation import scenario_metrics
    from alpha_validation.metrics import to_returns

    data_dir = AlphaSettings().data_dir
    rdir = find_run_dir(data_dir, from_run)
    if rdir is None:
        raise typer.BadParameter(f"no run {from_run!r} found")
    try:
        manifest = read_manifest(rdir)
        equity_rows = read_equity(rdir)
        equity = [value for _, value in equity_rows]
        summaries = scenario_metrics(
            to_returns(equity), periods_per_year=periods_per_year, confidence=confidence
        )
    except DataError as exc:  # no equity curve (optim/portfolio/…) or a degenerate series
        raise typer.BadParameter(str(exc)) from exc

    payload = {
        "run_id": from_run,
        "confidence": confidence,
        "scenarios": [dataclasses.asdict(s) for s in summaries],
        "provenance": {
            "source_run_id": from_run,
            "source_command": manifest.get("command"),
            "source_artifact": "equity_curve.parquet",
            "source_artifact_sha256": sha256_file(rdir / "equity_curve.parquet"),
            "snapshot_id": manifest.get("snapshot_id"),
            "snapshot_hash": manifest.get("snapshot_hash"),
            "research_cutoff": manifest.get("research_cutoff"),
            "as_of": equity_rows[-1][0].isoformat() if equity_rows else None,
            "timezone": "UTC",
            "derived_projection": True,
            "metric_namespace": "alpha_validation.scenario",
            "periods_per_year": periods_per_year,
            "confidence": confidence,
        },
    }
    if json_out:
        typer.echo(json.dumps(payload))
        return
    for s in summaries:
        typer.echo(
            f"{s.name:>10}: vol={s.annual_vol:.3f} maxdd={s.max_drawdown:.3f} "
            f"var={s.value_at_risk:.4f} cvar={s.expected_shortfall:.4f}"
        )
