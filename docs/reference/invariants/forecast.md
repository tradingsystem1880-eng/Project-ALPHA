---
owner: forecast facade
sources:
  - packages/alpha-forecast/src/**
  - tests/unit/test_forecast_*.py
  - tests/bias_guards/test_forecast_fake_causal.py
  - tests/bias_guards/test_kronos_cache_no_lookahead.py
verified: 1ac86fc02443
---

# Forecast invariants

What must hold in `alpha_forecast` (`packages/alpha-forecast/src/alpha_forecast/`): the typed facade over
the vendored Kronos model, forecast value types, the quantile signal rule and the offline fake.

## Package boundary

- Import only `alpha_core`, and only `alpha_cli` may import `alpha_forecast`: every other package's
  import-linter contract in `pyproject.toml` forbids it. [ADR-0008](../../adr/0008-vendored-kronos-and-alpha-forecast-layer.md),
  [engineering § Import layers](engineering.md#import-layers).
- Importing the package must never import torch: torch, pandas and the vendored model are imported inside
  methods of `kronos.py` only. Enforced by
  `tests/unit/test_forecast_kronos_facade.py::test_satisfies_protocol_and_import_stays_torch_free`.
- pandas is allowed only in `kronos.py`, at the upstream DataFrame API.
  [engineering § Polars by default](engineering.md#polars-by-default).

## Vendored model

- `_vendor/kronos/` is upstream Kronos pinned at `67b630e6` (`VENDORED_KRONOS_SHA`), MIT. Never edit it
  beyond the documented import rewrites; refresh only by re-fetching at a new pin. Only the facade imports it.
- It is excluded from ruff, mypy and coverage (`pyproject.toml`), so nothing there is lint- or type-checked.

## Sampling contract

- Upstream `predict(sample_count=S)` averages its draws into one path. The facade instead calls
  `predict_batch` with S copies at `sample_count=1`, so each row is an independent path.
- Batches are chunked at `_CHUNK = 32` with per-chunk torch seeds derived from the seed. Changing the chunk
  size or seed derivation changes the sampled paths: treat both as part of the contract.
- Only `device="cpu"` is bit-exact; mps and cuda are best-effort and `provenance()` records that.
  [research integrity § Deterministic seeds and identity](research-integrity.md#deterministic-seeds-and-identity).
- `provenance()` carries model and tokenizer ids and revisions, device, context, clip, torch version and
  vendor SHA. Never add `cache_dir` or `local_files_only`: they are machine-local. With local-only loading,
  missing weights raise `DataError` before any network call. [ADR-0010](../../adr/0010-local-kronos-weights-offline-policy.md).
- Context bars must be at least 2 and strictly ascending by `ts`.

## Forecast values

- `SampledPath` values are finite, equal-length, with close > 0. OHLC coherence is deliberately not
  enforced on model output: consumers use `close` and its quantiles, never a candle.
- `ForecastResult` needs horizon >= 1, at least one sample, and `step_ts` of length horizon, strictly
  increasing and after `origin_ts`.
- `future_session_ts`: any weekend bar among the trailing timestamps means calendar-day cadence (crypto),
  otherwise Monday to Friday. There is no holiday calendar; this is a documented approximation.
  Caller-supplied `step_ts` must be aware, strictly increasing and after the origin.
  `tests/unit/test_forecast_timestamps.py`.

## Signal rule

- `kronos_signal` compares the median end-of-horizon close with the origin close; `min_edge` is a dead band
  and `require_band_agreement` also needs the inner quartile on the same side. Non-finite inputs raise.
  `tests/unit/test_forecast_signal.py`.

## Fake forecaster

- `FakeForecaster` keys its RNG on the seed and a content hash of the input window, so it is a pure
  function of the window: identical windows give identical paths and bars outside the window change
  nothing. Enforced by `tests/bias_guards/test_forecast_fake_causal.py`. It is a test double, not a statistic.

## Settings and leakage

- `forecast_device` defaults to `cpu`; revisions default to `main` and are recorded verbatim, so pin commit
  hashes through the environment for byte-stable provenance (`alpha_core/config.py`).
- Kronos's pretraining cutoff is undisclosed; `forecast_pretrain_cutoff` (2025-08-02) is a conservative
  stand-in. Overlapping runs warn and are flagged in artifacts, never blocked.
  [ADR-0009](../../adr/0009-forecast-leakage-and-tier2-cost-policy.md).
- Engine use is cache-first: `alpha_cli` precomputes signals at exactly the engine's rebalance indices and
  `SignalReplay` replays them ([strategies § Replay and sandbox strategies](strategies.md#replay-and-sandbox-strategies)).
  Guarded by `tests/bias_guards/test_kronos_cache_no_lookahead.py`.

## Source identity

- `alpha_forecast` is one of the packages hashed into the v3 run `execution_fingerprint`
  (`apps/alpha-cli/src/alpha_cli/_identity.py`). [engineering § Hash-bound source bytes](engineering.md#hash-bound-source-bytes).
