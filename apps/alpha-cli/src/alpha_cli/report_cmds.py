"""``alpha report <run_id>``: re-display any stored run from its manifest (no engine re-run).

Searches every run-type directory (``runs/`` gauntlet + backtest runs, ``portfolio/``,
``cross_sectional/``, ``optim/``) for ``<run_id>/manifest.json`` and prints a summary appropriate to
whatever the manifest contains. The manifest is self-sufficient, so this never loads data or touches
the backtest engine.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import typer

from alpha_core.config import AlphaSettings

_RUN_DIRS = ("runs", "portfolio", "cross_sectional", "optim", "propfirm", "forecast")
_RUN_ID_RE = re.compile(r"^[0-9a-f]{16}$")  # ids are 16 hex chars; reject before path-joining


def _fmt(x: Any) -> str:
    # bool is an int subclass; never render True/False as "1.0000"
    return f"{x:.4f}" if isinstance(x, int | float) and not isinstance(x, bool) else "n/a"


def _find_manifest(data_dir: Path, run_id: str) -> dict[str, Any] | None:
    if _RUN_ID_RE.fullmatch(run_id) is None:
        return None  # not a run id -> the standard not-found error, no filesystem probe
    for sub in _RUN_DIRS:
        path = data_dir / sub / run_id / "manifest.json"
        if path.exists():
            result: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
            result["__dir"] = str(path.parent)
            return result
    return None


def report(run_id: str) -> None:
    """Print the stored result for RUN_ID (any run type: gauntlet, backtest, portfolio, etc.)."""
    settings = AlphaSettings()
    manifest = _find_manifest(settings.data_dir, run_id)
    if manifest is None:
        raise typer.BadParameter(
            f"no run {run_id!r} under {settings.data_dir} ({'/'.join(_RUN_DIRS)})"
        )

    metadata = manifest.get("metadata", {})
    symbol = metadata.get("symbol") or manifest.get("symbol")
    symbols = manifest.get("symbols")
    label = symbol or (", ".join(symbols) if symbols else "?")
    typer.echo(
        f"run {run_id}  {manifest.get('command', 'gauntlet')}  "
        f"[{label}]  schema_version={manifest.get('schema_version')}"
    )

    if manifest.get("command") in ("forecast_run", "forecast_eval"):  # Kronos forecasting
        model = manifest.get("model") or {}
        params = manifest.get("params") or {}
        typer.echo(
            f"model: {model.get('model_id')}@{model.get('model_revision')} "
            f"device={model.get('device')} determinism={model.get('determinism')}"
        )
        typer.echo(
            f"params: context={params.get('context')} horizon={params.get('horizon')} "
            f"samples={params.get('samples')} seed={params.get('seed')}"
        )
        summary = manifest.get("summary")
        if isinstance(summary, dict):
            typer.echo(
                "summary: " + ", ".join(f"{k}={_fmt(v)}" for k, v in sorted(summary.items()))
            )
        for key, split_label in (
            ("summary_pre_cutoff", "pre-cutoff"),
            ("summary_post_cutoff", "post-cutoff"),
        ):
            split = manifest.get(key)
            if isinstance(split, dict):
                typer.echo(
                    f"{split_label}: "
                    + ", ".join(f"{k}={_fmt(v)}" for k, v in sorted(split.items()))
                )
        pretrain = manifest.get("pretrain") or {}
        if pretrain.get("overlap"):
            typer.secho(
                f"PRETRAIN OVERLAP: window {pretrain.get('overlap_start')}"
                f"..{pretrain.get('overlap_end')} <= assumed cutoff {pretrain.get('cutoff')} "
                f"— results may be memorized (ADR-0009)",
                fg=typer.colors.YELLOW,
            )
    forecast_block = manifest.get("forecast")
    if isinstance(forecast_block, dict):  # kronos strategy runs (backtest/validate)
        fmodel = forecast_block.get("model") or {}
        typer.echo(
            f"forecast model: {fmodel.get('model_id')}@{fmodel.get('model_revision')} "
            f"cache={forecast_block.get('cache_key')} "
            f"tier2={forecast_block.get('tier2_policy', 'n/a')}"
        )
        fp = forecast_block.get("pretrain") or {}
        if fp.get("overlap"):
            typer.secho(
                f"PRETRAIN OVERLAP: forecasts consumed bars <= assumed cutoff "
                f"{fp.get('cutoff')} — results may be memorized (ADR-0009)",
                fg=typer.colors.YELLOW,
            )
    if manifest.get("command") == "propfirm":  # prop-firm Monte Carlo run
        rules = manifest.get("rules", {})
        typer.echo(f"prop-firm: {manifest.get('firm')} (source {manifest.get('source')})")
        typer.echo(
            f"rules: account ${_fmt(rules.get('account_size'))}, "
            f"target ${_fmt(rules.get('profit_target'))}, "
            f"max-dd ${_fmt(rules.get('max_drawdown'))}"
        )
    if "passed" in manifest:
        typer.echo(f"verdict: {'PASS' if manifest['passed'] else 'FAIL'}")
    verdict = manifest.get("verdict")
    if isinstance(verdict, dict):  # the A-F grade (gauntlet runs)
        typer.echo(
            f"grade: {verdict.get('overall')} "
            f"(edge {verdict.get('edge')}/robustness {verdict.get('robustness')}/"
            f"risk {verdict.get('risk')}/sample {verdict.get('sample')})"
        )
    if "oos_metrics" in manifest:
        metrics = ", ".join(f"{k}={_fmt(v)}" for k, v in sorted(manifest["oos_metrics"].items()))
        typer.echo(f"OOS metrics: {metrics}")
    if "metrics" in manifest:  # portfolio / cross-sectional
        metrics = ", ".join(f"{k}={_fmt(v)}" for k, v in sorted(manifest["metrics"].items()))
        typer.echo(f"metrics: {metrics}")
    for key in ("psr", "dsr", "best_sharpe"):
        val = manifest.get(key)
        # Only scalar values here; a dict-valued `dsr` (gauntlet/optim) is rendered by the block
        # loop below — printing it here would emit a spurious, contradictory `dsr: n/a` line.
        if isinstance(val, int | float) and not isinstance(val, bool):
            typer.echo(f"{key}: {_fmt(val)}")
    if manifest.get("folds"):
        typer.echo(f"walk-forward: {len(manifest['folds'])} OOS folds")
    for n in manifest.get("nulls", []):
        v = "PASS" if n["passed"] else "FAIL"
        typer.echo(
            f"null[{n['tier']}]: percentile={_fmt(n['percentile'])} p={_fmt(n['p_value'])} -> {v}"
        )
    for key in ("sharpe_ci", "cagr_ci"):  # portfolio / cross-sectional intervals
        ci = manifest.get(key)
        if isinstance(ci, dict):
            typer.echo(f"{key}: [{_fmt(ci.get('lower'))}, {_fmt(ci.get('upper'))}]")
    for c in manifest.get("cis", []):  # gauntlet intervals
        typer.echo(
            f"CI[{c['metric']}]: {_fmt(c['point'])} [{_fmt(c['lower'])}, {_fmt(c['upper'])}] "
            f"@ {_fmt(c['confidence'])}"
        )
    for key in ("dsr", "pbo", "spa", "reality_check"):  # optim verdict blocks (nested dicts)
        block = manifest.get(key)
        if isinstance(block, dict):
            inner = ", ".join(
                f"{k}={_fmt(v) if isinstance(v, float) else v}" for k, v in block.items()
            )
            typer.echo(f"{key}: {inner}")
    if manifest.get("best_config"):
        best = ", ".join(f"{name}={val:g}" for name, val in manifest["best_config"])
        typer.echo(f"best config: {best}")
    for leg in manifest.get("legs", []):
        sharpe = _fmt(leg.get("oos_sharpe"))
        typer.echo(f"leg[{leg['symbol']}]: weight={_fmt(leg['weight'])} oos_sharpe={sharpe}")
    for o in manifest.get("outcomes", []):
        typer.echo(f"gate[{o['name']}]: {'PASS' if o['passed'] else 'FAIL'}")
    if "orders" in manifest:  # plain backtest run
        typer.echo(
            f"orders={manifest['orders']} fills={manifest.get('fills')} "
            f"rejected={manifest.get('rejected', 0)} "
            f"final_equity={_fmt(manifest.get('final_equity'))}"
        )
    tearsheet = Path(manifest["__dir"]) / "tearsheet.html"
    if tearsheet.exists():
        typer.echo(f"tear sheet: {tearsheet}")
