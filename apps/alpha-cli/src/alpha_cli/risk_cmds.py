"""``alpha risk`` — stress / what-if scenarios over a stored run's realized return stream.

Composes the run store (read a run's equity curve) with ``alpha_validation.scenario_metrics``; a
``--json`` projection the Workstation's Risk panel renders. No engine re-run, no new artifacts.
"""

from __future__ import annotations

import dataclasses
import json
from datetime import datetime, timedelta
from itertools import pairwise
from typing import Annotated

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
    include_metric_basis: Annotated[
        bool,
        typer.Option(
            "--include-metric-basis",
            help="include version-1 metric/anchor disclosure; requires --json",
        ),
    ] = False,
) -> None:
    """Re-evaluate risk under vol-scaling and tail-shock scenarios for a stored run."""
    if include_metric_basis and not json_out:
        raise typer.BadParameter("--include-metric-basis requires --json")
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
        # The reader preserves file order; returns require the producer's
        # strictly increasing UTC path, not a silent sort or clock inference.
        timestamps = [timestamp for timestamp, _ in equity_rows]
        if any(
            not isinstance(timestamp, datetime) or timestamp.utcoffset() != timedelta(0)
            for timestamp in timestamps
        ):
            raise DataError("equity timestamps must be timezone-aware UTC datetimes")
        if any(current <= previous for previous, current in pairwise(timestamps)):
            raise DataError("equity timestamps must be strictly increasing")
        equity = [value for _, value in equity_rows]
        summaries = scenario_metrics(
            to_returns(equity), periods_per_year=periods_per_year, confidence=confidence
        )
    except OverflowError as exc:
        raise typer.BadParameter("risk inputs exceed supported numeric range") from exc
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
            **(
                {
                    "metric_basis": {
                        "schema_version": 1,
                        "anchor_kind": "first_recorded_equity",
                        "anchor_ts": equity_rows[0][0].isoformat(),
                        "anchor_value": equity[0],
                        "anchor_units": "recorded_equity_units",
                        "initial_capital_status": "unknown",
                        "external_cash_flow_status": "unknown",
                        "return_accumulation": "compounded_simple_returns",
                        "drawdown_convention": "non_positive_fraction_from_scenario_wealth_peaks",
                        "benchmark_adjustment": "none_by_projection",
                        "pre_anchor_losses": "not_measured",
                    }
                }
                if include_metric_basis
                else {}
            ),
        },
    }
    if json_out:
        try:
            encoded = json.dumps(payload, allow_nan=False)
        except ValueError as exc:
            raise typer.BadParameter("risk report contains non-finite values") from exc
        typer.echo(encoded)
        return
    typer.echo(
        "Metric source: alpha_validation.scenario (ALPHA recomputation). "
        f"Recorded-equity simple returns; total return compounds; {periods_per_year} periods/year. "
        "No benchmark adjustment."
    )
    typer.echo(
        f"Anchor: first recorded equity {equity[0]:.17g} at {equity_rows[0][0].isoformat()} "
        "(recorded equity units)."
    )
    typer.echo(
        "Initial-capital baseline and external cash-flow coverage are not verified by this "
        "projection; losses before the anchor are not measured."
    )
    for s in summaries:
        typer.echo(
            f"{s.name:>10}: vol={s.annual_vol:.3f} maxdd={s.max_drawdown:.3f} "
            f"var={s.value_at_risk:.4f} cvar={s.expected_shortfall:.4f}"
        )
