"""``alpha report <run_id>``: re-display a stored run from its manifest (no engine re-run).

Reads ``data_dir/runs/<run_id>/manifest.json`` and prints the gate table, CIs, and verdict. The
manifest is self-sufficient, so this never loads data or touches the backtest engine.
"""

from __future__ import annotations

from typing import Any

import typer

from alpha_cli import _artifacts
from alpha_core.config import AlphaSettings


def _fmt(x: Any) -> str:
    # bool is an int subclass; never render True/False as "1.0000"
    return f"{x:.4f}" if isinstance(x, int | float) and not isinstance(x, bool) else "n/a"


def report(run_id: str) -> None:
    """Print the stored gauntlet result for RUN_ID (gates, CIs, verdict) from its manifest."""
    settings = AlphaSettings()
    rdir = _artifacts.run_dir(settings.data_dir, run_id)
    if not (rdir / "manifest.json").exists():
        raise typer.BadParameter(f"no run {run_id!r} under {settings.data_dir / 'runs'}")
    manifest = _artifacts.read_manifest(rdir)

    metadata = manifest.get("metadata", {})
    symbol = metadata.get("symbol", manifest.get("symbol", "?"))
    typer.echo(f"run {run_id}  symbol={symbol}  schema_version={manifest.get('schema_version')}")

    if "passed" in manifest:
        typer.echo(f"verdict: {'PASS' if manifest['passed'] else 'FAIL'}")
    if "oos_metrics" in manifest:
        metrics = ", ".join(f"{k}={_fmt(v)}" for k, v in sorted(manifest["oos_metrics"].items()))
        typer.echo(f"OOS metrics: {metrics}")
    if manifest.get("folds"):
        typer.echo(f"walk-forward: {len(manifest['folds'])} OOS folds")
    for n in manifest.get("nulls", []):
        verdict = "PASS" if n["passed"] else "FAIL"
        typer.echo(
            f"null[{n['tier']}]: percentile={_fmt(n['percentile'])} "
            f"p={_fmt(n['p_value'])} -> {verdict}"
        )
    for c in manifest.get("cis", []):
        typer.echo(
            f"CI[{c['metric']}]: {_fmt(c['point'])} [{_fmt(c['lower'])}, {_fmt(c['upper'])}] "
            f"@ {_fmt(c['confidence'])}"
        )
    for o in manifest.get("outcomes", []):
        typer.echo(f"gate[{o['name']}]: {'PASS' if o['passed'] else 'FAIL'}")
    if (rdir / "tearsheet.html").exists():
        typer.echo(f"tear sheet: {rdir / 'tearsheet.html'}")
