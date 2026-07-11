"""KronosForecaster: a BarForecaster over the vendored Kronos model.

torch (and the vendored model code) is imported lazily on first real inference; importing
this module — and cache hits — never load it. This module is the project's sanctioned
pandas/torch edge (the vendored predictor speaks pandas).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

import numpy as np
import polars as pl

from alpha_core import Bar, DataError
from alpha_forecast import cache as _cache
from alpha_forecast.models import ModelSpec, future_timestamps, resolve_model

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path


@dataclass(frozen=True)
class ForecastResult:
    """A forecast path plus an optional per-bar close band (only when sample_count > 1)."""

    path: list[Bar]
    close_p10: list[float] | None
    close_p90: list[float] | None


_PRICE_FIELDS = ("open", "high", "low", "close")


class KronosForecaster:
    """Forecasts future bars with a pretrained Kronos checkpoint.

    Weights must already exist under `weights_dir` (see `alpha forecast pull`); a normal
    forecast NEVER downloads. All sampling randomness derives from `seed` + the window
    content, so results are call-order independent and cache keys double as determinism
    keys (deterministic per torch build on CPU; GPU determinism is not promised).
    """

    def __init__(
        self,
        *,
        model_name: str = "base",
        weights_dir: Path,
        cache_dir: Path | None = None,
        seed: int = 7,
        temperature: float = 1.0,
        top_p: float = 0.9,
        sample_count: int = 1,
        device: str | None = None,
    ) -> None:
        self._spec: ModelSpec = resolve_model(model_name)  # fail loud before any torch
        if temperature <= 0:
            raise DataError(f"temperature must be > 0, got {temperature}")
        if not 0 < top_p <= 1:
            raise DataError(f"top_p must be in (0, 1], got {top_p}")
        if sample_count < 1:
            raise DataError(f"sample_count must be >= 1, got {sample_count}")
        self._weights_dir = weights_dir
        self._cache_dir = cache_dir
        self._seed = seed
        self._temperature = temperature
        self._top_p = top_p
        self._sample_count = sample_count
        self._device = device
        self._predictor: Any = None

    @property
    def spec(self) -> ModelSpec:
        return self._spec

    # -- BarForecaster protocol ----------------------------------------------------------

    def forecast(self, bars: Sequence[Bar], horizon: int) -> list[Bar]:
        return self.forecast_full(bars, horizon).path

    # -- full API --------------------------------------------------------------------------

    def forecast_full(self, bars: Sequence[Bar], horizon: int) -> ForecastResult:
        if horizon < 1:
            raise DataError(f"horizon must be >= 1, got {horizon}")
        if len(bars) < 2:
            raise DataError(f"need >= 2 context bars, got {len(bars)}")
        if len(bars) > self._spec.max_context:
            raise DataError(
                f"context window of {len(bars)} bars exceeds Kronos-{self._spec.name}'s "
                f"max_context {self._spec.max_context}; pass a trailing slice instead "
                "(no silent truncation)"
            )
        symbols = {b.symbol for b in bars}
        if len(symbols) != 1:
            raise DataError(f"context window mixes symbols: {sorted(symbols)}")
        symbol = bars[-1].symbol

        key = _cache.cache_key(
            model=self._spec.name,
            revision=self._spec.revision,
            window=bars,
            horizon=horizon,
            temperature=self._temperature,
            top_p=self._top_p,
            sample_count=self._sample_count,
            seed=self._seed,
        )
        if self._cache_dir is not None:
            cached = _cache.load(self._cache_dir, key)
            if cached is not None:
                return _result_from_frame(cached, symbol)

        y_ts = future_timestamps(bars, horizon)
        samples = self._predict_samples(bars, y_ts, key)

        mean = samples.mean(axis=0)  # (horizon, 5) open/high/low/close/volume
        close_p10: list[float] | None = None
        close_p90: list[float] | None = None
        if samples.shape[0] > 1:
            closes = samples[:, :, 3]
            close_p10 = [float(v) for v in np.percentile(closes, 10, axis=0)]
            close_p90 = [float(v) for v in np.percentile(closes, 90, axis=0)]

        path = _sanitize_path(mean, y_ts, symbol, model_name=self._spec.name)
        result = ForecastResult(path=path, close_p10=close_p10, close_p90=close_p90)
        if self._cache_dir is not None:
            _cache.store(self._cache_dir, key, _frame_from_result(result))
        return result

    # -- internals ---------------------------------------------------------------------------

    def _load(self) -> Any:
        """Memoized torch-land load. local_files_only: a backtest must never download."""
        if self._predictor is not None:
            return self._predictor
        try:
            import torch  # noqa: F401  (needed by the vendored model)

            from alpha_forecast._vendor.kronos import Kronos, KronosPredictor, KronosTokenizer
        except ImportError as exc:
            raise DataError(
                "the Kronos torch stack is not installed; run `uv sync --group kronos` "
                f"first: {exc}"
            ) from exc
        try:
            tokenizer = KronosTokenizer.from_pretrained(
                self._spec.tokenizer_repo,
                cache_dir=str(self._weights_dir),
                local_files_only=True,
                revision=self._spec.revision,
            )
            model = Kronos.from_pretrained(
                self._spec.model_repo,
                cache_dir=str(self._weights_dir),
                local_files_only=True,
                revision=self._spec.revision,
            )
        except Exception as exc:  # noqa: BLE001 - re-raised typed with instructions
            raise DataError(
                f"Kronos-{self._spec.name} weights not found under {self._weights_dir}; "
                f"run `alpha forecast pull --model {self._spec.name}` (requires network) "
                f"first: {exc}"
            ) from exc
        model.eval()
        tokenizer.eval()
        self._predictor = KronosPredictor(  # type: ignore[no-untyped-call]  # vendored, untyped
            model,
            tokenizer,
            device=self._device,
            max_context=self._spec.max_context,
        )
        return self._predictor

    def _seed_torch(self, value: int) -> None:
        import torch

        torch.manual_seed(value)

    def _predict_samples(
        self, bars: Sequence[Bar], y_ts: list[datetime], key: str
    ) -> np.ndarray[Any, np.dtype[np.float64]]:
        """Run sample_count independent predict calls -> array (k, horizon, 5)."""
        import pandas as pd  # sanctioned pandas edge: the vendored predictor speaks pandas

        predictor = self._load()
        x_df = pd.DataFrame(
            {
                "open": [b.open for b in bars],
                "high": [b.high for b in bars],
                "low": [b.low for b in bars],
                "close": [b.close for b in bars],
                "volume": [b.volume for b in bars],
            }
        )
        x_ts = pd.Series(pd.DatetimeIndex([b.ts for b in bars]).tz_convert("UTC").tz_localize(None))
        y_ts_naive = pd.Series(pd.DatetimeIndex(y_ts).tz_convert("UTC").tz_localize(None))

        # Content-derived seeding: master seed + window hash -> call-order independence.
        key_int = int(key[:16], 16)
        children = np.random.SeedSequence([self._seed, key_int]).spawn(self._sample_count)
        out: list[np.ndarray[Any, np.dtype[np.float64]]] = []
        for child in children:
            self._seed_torch(int(child.generate_state(1, dtype=np.uint64)[0]))
            pred = predictor.predict(
                df=x_df,
                x_timestamp=x_ts,
                y_timestamp=y_ts_naive,
                pred_len=len(y_ts),
                T=self._temperature,
                top_k=0,
                top_p=self._top_p,
                sample_count=1,
                verbose=False,
            )
            out.append(pred[["open", "high", "low", "close", "volume"]].to_numpy(dtype=np.float64))
        return np.stack(out, axis=0)


def _sanitize_path(
    mean: np.ndarray[Any, np.dtype[np.float64]],
    y_ts: list[datetime],
    symbol: str,
    *,
    model_name: str,
) -> list[Bar]:
    """Structural-only fixes, then Bar's validator is the final gate. Broken -> DataError."""
    path: list[Bar] = []
    for i, ts in enumerate(y_ts):
        o, h, low, c, v = (float(x) for x in mean[i])
        for name, value in zip(_PRICE_FIELDS, (o, h, low, c), strict=True):
            if not math.isfinite(value) or value <= 0:
                raise DataError(
                    f"Kronos-{model_name} produced a non-tradable {name}={value!r} at "
                    f"step {i} ({ts.isoformat()}); refusing to clamp a broken forecast"
                )
        if not math.isfinite(v):
            raise DataError(
                f"Kronos-{model_name} produced non-finite volume at step {i} ({ts.isoformat()})"
            )
        # Kronos predicts channels independently; enforce OHLC ordering structurally.
        high = max(o, h, low, c)
        low_ = min(o, h, low, c)
        path.append(
            Bar(
                symbol=symbol,
                ts=ts,
                open=o,
                high=high,
                low=low_,
                close=c,
                volume=max(v, 0.0),
            )
        )
    return path


def _frame_from_result(result: ForecastResult) -> pl.DataFrame:
    data: dict[str, list[str] | list[float]] = {
        "ts": [b.ts.isoformat() for b in result.path],
        "open": [b.open for b in result.path],
        "high": [b.high for b in result.path],
        "low": [b.low for b in result.path],
        "close": [b.close for b in result.path],
        "volume": [b.volume for b in result.path],
    }
    if result.close_p10 is not None and result.close_p90 is not None:
        data["close_p10"] = result.close_p10
        data["close_p90"] = result.close_p90
    return pl.DataFrame(data)


def _result_from_frame(frame: pl.DataFrame, symbol: str) -> ForecastResult:
    path = [
        Bar(
            symbol=symbol,
            ts=datetime.fromisoformat(row["ts"]),
            open=row["open"],
            high=row["high"],
            low=row["low"],
            close=row["close"],
            volume=row["volume"],
        )
        for row in frame.iter_rows(named=True)
    ]
    has_band = "close_p10" in frame.columns and "close_p90" in frame.columns
    return ForecastResult(
        path=path,
        close_p10=list(frame["close_p10"]) if has_band else None,
        close_p90=list(frame["close_p90"]) if has_band else None,
    )
