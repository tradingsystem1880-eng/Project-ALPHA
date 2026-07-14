"""``alpha forecast``: pull Kronos weights (network) and forecast a symbol's next N bars.

``pull`` is the ONLY network path; ``run`` loads bars from the local store, forecasts with
the (offline, cached) Kronos forecaster, and writes ``data_dir/forecast/<run_id>/``:
``manifest.json`` (byte-stable), ``forecast.parquet`` + ``history.parquet`` (the context
window, so run pages render self-contained).
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING, Any

import polars as pl
import typer

from alpha_cli import _artifacts, _runner
from alpha_core import Bar, DataError
from alpha_core.config import AlphaSettings
from alpha_forecast import resolve_model, training_overlap_warning

if TYPE_CHECKING:
    from collections.abc import Sequence

    from alpha_forecast import ForecastResult

forecast_app = typer.Typer(help="Kronos foundation-model forecasting (pull weights, run).")

# monkeypatchable bar-load seam (mirrors backtest_cmds); tests point it at a fixture store
_load_bars = _runner.load_bars


def _default_forecaster_factory(
    *,
    model: str,
    temperature: float,
    top_p: float,
    sample_count: int,
    seed: int,
    settings: AlphaSettings,
) -> Any:
    from alpha_forecast import KronosForecaster

    return KronosForecaster(
        model_name=model,
        weights_dir=settings.resolved_weights_dir,
        cache_dir=settings.data_dir / "forecast_cache",
        seed=seed,
        temperature=temperature,
        top_p=top_p,
        sample_count=sample_count,
    )


# test seam (mirrors data_cmds._ADAPTERS): monkeypatch with a stub factory
_FORECASTER_FACTORY = _default_forecaster_factory


@forecast_app.command()
def pull(model: str = "base", force: bool = False) -> None:
    """Download the Kronos MODEL weights + tokenizer (network) into the weights dir."""
    settings = AlphaSettings()
    from alpha_forecast import pull_model

    try:
        spec = resolve_model(model)
        paths = pull_model(model, settings.resolved_weights_dir, force=force)
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(
        f"pulled Kronos-{spec.name} ({spec.params_m}M params, max_context {spec.max_context}) "
        f"into {settings.resolved_weights_dir}"
    )
    for repo, path in paths.items():
        typer.echo(f"  {repo} -> {path}")


@forecast_app.command()
def run(
    symbol: str,
    model: str = "base",
    horizon: int = 30,
    context: int = 400,
    temperature: float = 1.0,
    top_p: float = 0.9,
    sample_count: int = 1,
    seed: int | None = None,
    snapshot: str | None = None,
    start: str | None = None,
    end: str | None = None,
) -> None:
    """Forecast SYMBOL's next HORIZON bars from the trailing CONTEXT bars.

    ``--start/--end`` (YYYY-MM-DD) slice the history first for an as-of historical forecast.
    NOTE: Kronos weights saw market data up to ~2025-08 — a pre-cutoff window may be
    memorized, not forecast (a loud warning is echoed and recorded). CPU cost scales with
    model size but stays interactive: measured ~5-8 s per base forecast on an Apple-silicon
    CPU (mini is faster); sample_count multiplies it.
    """
    settings = AlphaSettings()
    resolved_seed = seed if seed is not None else settings.random_seed
    try:
        model_spec = resolve_model(model)
        bars, snapshot_id = _load_bars(symbol, data_dir=settings.data_dir, snapshot_id=snapshot)
        bars = _slice(bars, start, end)
        if len(bars) < 2:
            raise DataError(f"only {len(bars)} bars in the selected window; need >= 2")
        window = bars[-context:]
        forecaster = _FORECASTER_FACTORY(
            model=model,
            temperature=temperature,
            top_p=top_p,
            sample_count=sample_count,
            seed=resolved_seed,
            settings=settings,
        )
        warning = training_overlap_warning(window[0].ts, window[-1].ts)
        if warning is not None:
            typer.secho(warning, err=True, fg="yellow")
        result: ForecastResult = forecaster.forecast_full(window, horizon)
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc

    window_sha = _window_sha(window)
    run_id = _runner.run_id_for(
        {
            "command": "forecast_run",
            "symbol": symbol,
            "snapshot_id": snapshot_id,
            "model": model,
            "horizon": horizon,
            "context": len(window),
            "temperature": temperature,
            "top_p": top_p,
            "sample_count": sample_count,
            "seed": resolved_seed,
            "window_sha": window_sha,
        }
    )
    end_close = result.path[-1].close
    last_close = window[-1].close
    expected_log_return = math.log(end_close / last_close)
    direction = 1 if expected_log_return > 0 else (-1 if expected_log_return < 0 else 0)
    manifest = {
        "schema_version": 1,
        "run_id": run_id,
        "command": "forecast_run",
        "symbol": symbol,
        "snapshot_id": snapshot_id,
        "model": {
            "name": model_spec.name,
            "model_repo": model_spec.model_repo,
            "tokenizer_repo": model_spec.tokenizer_repo,
            "max_context": model_spec.max_context,
            "revision": model_spec.revision,
            "tokenizer_revision": model_spec.tokenizer_revision,
            "torch_version": _torch_version(),  # provenance only; excluded from the run id
        },
        "params": {
            "horizon": horizon,
            "context": len(window),
            "temperature": temperature,
            "top_p": top_p,
            "sample_count": sample_count,
            "seed": resolved_seed,
        },
        "window": {
            "n_bars": len(window),
            "first_ts": window[0].ts.isoformat(),
            "last_ts": window[-1].ts.isoformat(),
            "window_sha": window_sha,
            "last_close": last_close,
        },
        "forecast": {
            "first_ts": result.path[0].ts.isoformat(),
            "last_ts": result.path[-1].ts.isoformat(),
            "end_close": end_close,
            "expected_log_return": expected_log_return,
            "direction": direction,
        },
        "leakage_warning": warning,
    }
    rdir = _artifacts.run_dir(settings.data_dir, run_id, "forecast")
    _artifacts.write_manifest(rdir, manifest)
    _bars_frame(result.path, p10=result.close_p10, p90=result.close_p90).write_parquet(
        rdir / "forecast.parquet"
    )
    _bars_frame(window).write_parquet(rdir / "history.parquet")

    label = {1: "LONG", -1: "SHORT", 0: "FLAT"}[direction]
    typer.echo(
        f"forecast {symbol} -> run {run_id}: {model_spec.name}, {horizon} bars, "
        f"end close {end_close:.2f} ({expected_log_return * 100:+.2f}%), direction {label}"
    )


def _slice(bars: list[Bar], start: str | None, end: str | None) -> list[Bar]:
    lo = _parse_date(start, "start")
    hi = _parse_date(end, "end")
    out = [
        b for b in bars if (lo is None or b.ts >= lo) and (hi is None or b.ts.date() <= hi.date())
    ]
    if not out:
        raise DataError(f"no bars in the window start={start} end={end}")
    return out


def _parse_date(value: str | None, label: str) -> datetime | None:
    if value is None:
        return None
    try:
        d = date.fromisoformat(value)
    except ValueError as exc:
        raise DataError(f"--{label} must be YYYY-MM-DD, got {value!r}") from exc
    return datetime(d.year, d.month, d.day, tzinfo=UTC)


def _window_sha(window: Sequence[Bar]) -> str:
    rows = [[b.ts.isoformat(), b.open, b.high, b.low, b.close, b.volume] for b in window]
    canonical = json.dumps(rows, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _torch_version() -> str | None:
    try:
        from importlib.metadata import version

        return version("torch")
    except Exception:  # noqa: BLE001 - provenance-only; absence of torch is not an error
        return None


def _bars_frame(
    bars: Sequence[Bar], *, p10: list[float] | None = None, p90: list[float] | None = None
) -> pl.DataFrame:
    data: dict[str, Any] = {
        "ts": [b.ts for b in bars],
        "open": [b.open for b in bars],
        "high": [b.high for b in bars],
        "low": [b.low for b in bars],
        "close": [b.close for b in bars],
        "volume": [b.volume for b in bars],
    }
    if p10 is not None and p90 is not None:
        data["close_p10"] = p10
        data["close_p90"] = p90
    return pl.DataFrame(data)
