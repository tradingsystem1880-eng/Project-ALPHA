"""Content-addressed Kronos signal caches — how a slow foundation model enters a fast engine.

Strategies are rebuilt from a pickled ``RunSpec`` inside spawn workers, so a live torch
model can never ride into the engine. Instead the CLI precomputes the ``{-1,0,1}`` signal
(plus the end-close quantiles behind it) at exactly the rebalance-schedule bar indices the
engine will query, under ``data_dir/forecasts/<key>/``, keyed by a sha256 over everything
the signals depend on: bars content, model identity + revisions + device, forecast params,
cadence, and seed. Model selection for strategy runs comes from ``AlphaSettings``
(``ALPHA_FORECAST_MODEL=...``) — strategy params are float-valued and cannot carry ids.
The ``kronos`` strategy replays the cache by bar index (``SignalReplay``); a missing or
mismatched cache fails loud, never silently flat.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl

from alpha_cli import _forecast
from alpha_cli._artifacts import sanitize
from alpha_cli._atomic import publish, write_text
from alpha_cli._runner import RunSpec
from alpha_core import Bar, DataError
from alpha_core.config import AlphaSettings
from alpha_forecast import close_quantiles, kronos_signal


@dataclass(frozen=True)
class KronosParams:
    """The kronos strategy's per-strategy parameters (decoded from ``strategy_params``)."""

    context: int
    horizon: int
    samples: int
    temperature: float
    top_p: float
    top_k: int
    min_edge: float
    band: bool


def kronos_params(spec: RunSpec) -> KronosParams:
    from alpha_cli._schemas import default_for

    return KronosParams(
        context=int(spec.param("context", default_for("kronos", "context"))),
        horizon=int(spec.param("horizon", default_for("kronos", "horizon"))),
        samples=int(spec.param("samples", default_for("kronos", "samples"))),
        temperature=spec.param("temperature", default_for("kronos", "temperature")),
        top_p=spec.param("top_p", default_for("kronos", "top_p")),
        top_k=int(spec.param("top_k", default_for("kronos", "top_k"))),
        min_edge=spec.param("min_edge", default_for("kronos", "min_edge")),
        band=bool(spec.param("band", default_for("kronos", "band"))),
    )


def bars_sha256(bars: Sequence[Bar]) -> str:
    """Content hash of a bar series (any change in any bar changes every cache key)."""
    payload = "|".join(
        f"{b.ts.isoformat()},{b.open!r},{b.high!r},{b.low!r},{b.close!r},{b.volume!r}" for b in bars
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def signal_indices(
    n_bars: int, *, min_history: int, vol_window: int, rebalance_every: int
) -> list[int]:
    """The exact bar indices ``VolTargetStrategy`` will query ``_signal`` at.

    Mirrors the engine cadence: history clamps to ``max(min_history, vol_window + 1)``
    closes, first decision at that bar, then every ``rebalance_every`` bars.
    """
    if rebalance_every < 1:
        raise DataError(f"rebalance_every must be >= 1, got {rebalance_every}")
    first = max(min_history, vol_window + 1) - 1
    if first >= n_bars:
        raise DataError(
            f"not enough bars for a single kronos decision: {n_bars} bars < warmup {first + 1}"
        )
    return list(range(first, n_bars, rebalance_every))


def cache_key(bars: Sequence[Bar], spec: RunSpec, *, seed: int) -> str:
    """16-hex content address for the signal cache of (bars, model, params, cadence, seed)."""
    settings = AlphaSettings()
    kp = kronos_params(spec)
    payload = {
        "symbol": bars[0].symbol,
        "bars_sha256": bars_sha256(bars),
        "model": settings.forecast_model,
        "model_revision": settings.forecast_model_revision,
        "tokenizer": settings.forecast_tokenizer,
        "tokenizer_revision": settings.forecast_tokenizer_revision,
        "device": settings.forecast_device,
        "context": kp.context,
        "horizon": kp.horizon,
        "samples": kp.samples,
        "temperature": kp.temperature,
        "top_p": kp.top_p,
        "top_k": kp.top_k,
        "min_edge": kp.min_edge,
        "band": kp.band,
        "vol_window": spec.vol_window,
        "rebalance_every": spec.rebalance_every,
        "seed": seed,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def ensure_forecast_cache(
    bars: Sequence[Bar], spec: RunSpec, *, data_dir: Path, seed: int
) -> tuple[str, dict[str, Any]]:
    """Precompute (or reuse) the signal cache for ``bars`` + ``spec``; return (key, meta).

    Forecasts run ONLY at the rebalance-schedule indices; each origin gets a child seed
    keyed on its absolute bar index, so a shared prefix of two series yields identical
    early rows (the look-ahead guard relies on this). Idempotent: an existing cache is
    returned untouched — the key already encodes everything the contents depend on.
    """
    key = cache_key(bars, spec, seed=seed)
    cdir = data_dir / "forecasts" / key
    signals_path = cdir / "signals.parquet"
    meta_path = cdir / "meta.json"
    if signals_path.exists() and meta_path.exists():
        try:
            meta_raw = json.loads(meta_path.read_text(encoding="utf-8"))
            pl.read_parquet_schema(signals_path)
        except (json.JSONDecodeError, OSError, pl.exceptions.PolarsError) as exc:
            raise DataError(f"corrupt forecast cache {key!r} at {cdir}") from exc
        if not isinstance(meta_raw, dict) or meta_raw.get("cache_key") != key:
            raise DataError(f"invalid forecast cache metadata for {key!r} at {meta_path}")
        meta: dict[str, Any] = meta_raw
        return key, meta

    settings = AlphaSettings()
    kp = kronos_params(spec)
    indices = signal_indices(
        len(bars),
        min_history=kp.context,
        vol_window=spec.vol_window,
        rebalance_every=spec.rebalance_every,
    )
    forecaster = _forecast._forecaster_factory(
        model=settings.forecast_model,
        model_revision=settings.forecast_model_revision,
        tokenizer=settings.forecast_tokenizer,
        tokenizer_revision=settings.forecast_tokenizer_revision,
        device=settings.forecast_device,
        hub_cache=settings.forecast_hub_cache,
        local_files_only=settings.forecast_local_only,
    )
    master = seed & 0xFFFFFFFF
    rows: list[dict[str, Any]] = []
    for t in indices:
        window = list(bars[t - kp.context + 1 : t + 1])
        bar_seed = int(
            np.random.SeedSequence([master, _forecast.FORECAST_SEED_NS, t]).generate_state(1)[0]
        )
        result = forecaster.forecast(
            window,
            horizon=kp.horizon,
            sample_count=kp.samples,
            temperature=kp.temperature,
            top_p=kp.top_p,
            top_k=kp.top_k,
            seed=bar_seed,
        )
        quantiles = close_quantiles(result, qs=(0.25, 0.5, 0.75))
        origin_close = window[-1].close
        rows.append(
            {
                "bar_index": t,
                "ts": bars[t].ts,
                "close": origin_close,
                "signal": kronos_signal(
                    origin_close,
                    quantiles[0.25][-1],
                    quantiles[0.5][-1],
                    quantiles[0.75][-1],
                    min_edge=kp.min_edge,
                    require_band_agreement=kp.band,
                ),
                "q25_end": quantiles[0.25][-1],
                "q50_end": quantiles[0.5][-1],
                "q75_end": quantiles[0.75][-1],
            }
        )

    cdir.mkdir(parents=True, exist_ok=True)
    signals = pl.DataFrame(rows)
    meta = sanitize(
        {
            "cache_key": key,
            "symbol": bars[0].symbol,
            "n_bars": len(bars),
            "n_signals": len(rows),
            "bars_sha256": bars_sha256(bars),
            "first_ts": bars[0].ts.isoformat(),
            "last_ts": bars[-1].ts.isoformat(),
            "model": _forecast._provenance(forecaster, model=settings.forecast_model),
            "params": {
                "context": kp.context,
                "horizon": kp.horizon,
                "samples": kp.samples,
                "temperature": kp.temperature,
                "top_p": kp.top_p,
                "top_k": kp.top_k,
                "min_edge": kp.min_edge,
                "band": kp.band,
            },
            "vol_window": spec.vol_window,
            "rebalance_every": spec.rebalance_every,
            "seed": seed,
            "pretrain": _forecast.pretrain_overlap(bars, settings.forecast_pretrain_cutoff),
        }
    )
    # Metadata is a sidecar; signals.parquet is the atomic completion gate readers check first.
    write_text(meta_path, json.dumps(meta, indent=2, sort_keys=True, allow_nan=False))
    publish(signals_path, signals.write_parquet)
    return key, meta


def read_signals(data_dir: Path, key: str) -> list[int | None]:
    """The cache's dense per-bar signal list (None off-schedule). Fails loud when absent."""
    cdir = data_dir / "forecasts" / key
    signals_path = cdir / "signals.parquet"
    meta_path = cdir / "meta.json"
    if not signals_path.exists():
        raise DataError(
            f"no forecast signal cache {key!r} under {data_dir / 'forecasts'} — run kronos "
            "through `alpha backtest run` / `alpha validate` / `alpha optim grid` (they "
            "auto-precompute)"
        )
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        frame = pl.read_parquet(signals_path)
    except (json.JSONDecodeError, OSError, pl.exceptions.PolarsError) as exc:
        raise DataError(f"corrupt forecast signal cache {key!r} at {cdir}") from exc
    if not isinstance(meta, dict) or not isinstance(meta.get("n_bars"), int):
        raise DataError(f"invalid forecast signal cache metadata for {key!r} at {meta_path}")
    dense: list[int | None] = [None] * int(meta["n_bars"])
    for index, signal in zip(frame["bar_index"].to_list(), frame["signal"].to_list(), strict=True):
        dense[int(index)] = int(signal)
    return dense


def prepare_spec_for_engine(
    bars: Sequence[Bar], spec: RunSpec, *, data_dir: Path, seed: int
) -> tuple[RunSpec, dict[str, Any] | None]:
    """No-op for ordinary strategies; for kronos: ensure the cache + pin its key on the spec."""
    if spec.strategy_name != "kronos":
        return spec, None
    key, meta = ensure_forecast_cache(bars, spec, data_dir=data_dir, seed=seed)
    return replace(spec, forecast_cache=key), meta
