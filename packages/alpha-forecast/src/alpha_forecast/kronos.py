"""Typed facade over the vendored Kronos model — the torch/pandas edge of the package.

Heavy imports (torch, pandas, the vendored model) happen inside methods only, so importing
this module — and the package — stays cheap and torch-free. pandas appears here because the
upstream API speaks DataFrames; this file is the sanctioned pandas boundary (spec ADR-0008).

Sampling contract: upstream ``predict(sample_count=S)`` AVERAGES its S draws into one path,
so this facade instead calls ``predict_batch`` with S copies of the series at
``sample_count=1`` — each batch row draws independently, giving S distinct paths in one
batched autoregressive pass. Batches are chunked at a fixed ``_CHUNK`` with a per-chunk
derived torch seed: reproducible for a fixed (seed, sample_count, torch version, device).
Only cpu is bit-exact; mps/cuda are best-effort (recorded via ``provenance()``).
"""

from __future__ import annotations

from collections.abc import Sequence
from importlib.metadata import version as _dist_version
from pathlib import Path
from typing import Any

from alpha_core import Bar, DataError
from alpha_forecast.timestamps import future_session_ts
from alpha_forecast.types import ForecastResult, SampledPath

VENDORED_KRONOS_SHA = "67b630e67f6a18c9e9be918d9b4337c960db1e9a"

_CHUNK = 32  # fixed batch chunk; changing it changes sampled paths (part of the contract)
_RECENT_TS_WINDOW = 10  # trailing bars inspected for the weekday-vs-calendar cadence rule


class KronosForecaster:
    """Forecaster-protocol implementation backed by pretrained Kronos weights.

    ``model_id``/``tokenizer_id`` accept HuggingFace ids or local checkpoint paths (a
    fine-tuned model drops in with no code change). ``cache_dir`` points hub resolution at
    a local weight cache and ``local_files_only`` forbids any network fetch (missing local
    weights raise ``DataError``); both are machine-local execution details and deliberately
    absent from ``provenance()`` — weight identity is (id, revision). The predictor is
    loaded lazily on the first ``forecast()`` and cached for the lifetime of the instance.
    """

    def __init__(
        self,
        *,
        model_id: str,
        model_revision: str,
        tokenizer_id: str,
        tokenizer_revision: str,
        device: str,
        max_context: int = 512,
        clip: int = 5,
        cache_dir: Path | None = None,
        local_files_only: bool = False,
    ) -> None:
        self.model_id = model_id
        self.model_revision = model_revision
        self.tokenizer_id = tokenizer_id
        self.tokenizer_revision = tokenizer_revision
        self.device = device
        self.max_context = max_context
        self.clip = clip
        self.cache_dir = cache_dir
        self.local_files_only = local_files_only
        self._predictor_cache: Any = None

    def provenance(self) -> dict[str, Any]:
        """Everything a manifest needs to reproduce (or distrust) this forecaster."""
        return {
            "model_id": self.model_id,
            "model_revision": self.model_revision,
            "tokenizer_id": self.tokenizer_id,
            "tokenizer_revision": self.tokenizer_revision,
            "device": self.device,
            "max_context": self.max_context,
            "clip": self.clip,
            "torch_version": _dist_version("torch"),
            "vendor_sha": VENDORED_KRONOS_SHA,
            "determinism": "exact" if self.device == "cpu" else "best-effort",
        }

    def _load_predictor(self) -> Any:
        if self._predictor_cache is None:
            from huggingface_hub.errors import LocalEntryNotFoundError

            from alpha_forecast._vendor.kronos import Kronos, KronosPredictor, KronosTokenizer

            try:
                tokenizer = KronosTokenizer.from_pretrained(
                    self.tokenizer_id,
                    revision=self.tokenizer_revision,
                    cache_dir=self.cache_dir,
                    local_files_only=self.local_files_only,
                )
                model = Kronos.from_pretrained(
                    self.model_id,
                    revision=self.model_revision,
                    cache_dir=self.cache_dir,
                    local_files_only=self.local_files_only,
                )
            except LocalEntryNotFoundError as err:
                raise DataError(
                    f"weights not in local cache {self.cache_dir}: "
                    f"{self.tokenizer_id}@{self.tokenizer_revision} / "
                    f"{self.model_id}@{self.model_revision} — download them with "
                    f"'HF_HUB_CACHE={self.cache_dir} hf download <id>' or unset "
                    "ALPHA_FORECAST_LOCAL_ONLY to allow hub fetches"
                ) from err
            self._predictor_cache = KronosPredictor(
                model, tokenizer, device=self.device, max_context=self.max_context, clip=self.clip
            )
        return self._predictor_cache

    def forecast(
        self,
        bars: Sequence[Bar],
        *,
        horizon: int,
        sample_count: int,
        temperature: float = 1.0,
        top_p: float = 0.9,
        top_k: int = 0,
        seed: int = 0,
    ) -> ForecastResult:
        if len(bars) < 2:
            raise DataError(f"KronosForecaster needs >= 2 context bars, got {len(bars)}")
        if horizon < 1:
            raise DataError(f"horizon must be >= 1, got {horizon}")
        if sample_count < 1:
            raise DataError(f"sample_count must be >= 1, got {sample_count}")
        ts = [b.ts for b in bars]
        if any(b <= a for a, b in zip(ts, ts[1:], strict=False)):
            raise DataError("bars must be sorted strictly ascending by ts")

        predictor = self._load_predictor()

        import numpy as np
        import pandas as pd
        import torch

        df = pd.DataFrame(
            {
                "open": [b.open for b in bars],
                "high": [b.high for b in bars],
                "low": [b.low for b in bars],
                "close": [b.close for b in bars],
                "volume": [b.volume for b in bars],
            }
        )
        x_ts = pd.Series(pd.to_datetime(ts))
        step_ts = future_session_ts(ts[-_RECENT_TS_WINDOW:], horizon)
        y_ts = pd.Series(pd.to_datetime(step_ts))

        seed_seq = np.random.SeedSequence([seed & 0xFFFFFFFF, 0x4B524F53])  # "KROS"
        chunk_seeds = seed_seq.generate_state((sample_count + _CHUNK - 1) // _CHUNK)

        pred_frames: list[pd.DataFrame] = []
        for chunk_index, start in enumerate(range(0, sample_count, _CHUNK)):
            n = min(_CHUNK, sample_count - start)
            torch.manual_seed(int(chunk_seeds[chunk_index]))
            pred_frames.extend(
                predictor.predict_batch(
                    [df] * n,
                    [x_ts] * n,
                    [y_ts] * n,
                    pred_len=horizon,
                    T=temperature,
                    top_k=top_k,
                    top_p=top_p,
                    sample_count=1,
                    verbose=False,
                )
            )

        samples = tuple(
            SampledPath(
                open=tuple(float(v) for v in frame["open"]),
                high=tuple(float(v) for v in frame["high"]),
                low=tuple(float(v) for v in frame["low"]),
                close=tuple(float(v) for v in frame["close"]),
                volume=tuple(float(v) for v in frame["volume"]),
            )
            for frame in pred_frames
        )
        return ForecastResult(
            symbol=bars[-1].symbol,
            origin_ts=bars[-1].ts,
            horizon=horizon,
            step_ts=tuple(step_ts),
            samples=samples,
        )
