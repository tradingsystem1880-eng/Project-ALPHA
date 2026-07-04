# ADR-0008: Vendored Kronos model behind a layer-1 `alpha_forecast` facade

**Status:** Accepted
**Date:** 2026-07-04
**Deciders:** AI build agents (per `CLAUDE.md`)

## Context

Project ALPHA integrates [Kronos](https://github.com/shiyu-coder/Kronos) (MIT, AAAI 2026) — a decoder-only foundation model for financial K-lines — for probabilistic OHLCV forecasting and a forecast-driven strategy. Three integration questions had real alternatives: **how to obtain the model code** (the upstream repo is clone-only with no `pyproject.toml`; a thin `kronos-model-arch` 0.1.0 PyPI wheel exists with weak provenance), **where the capability sits in the DAG**, and **how its pandas/torch API coexists with the house rules** (Polars-default, numpy confined to `alpha_validation`, mypy `--strict`).

Two upstream facts shaped the facade: `predict(sample_count=S)` **averages** its S draws into one path (useless for outcome cones), and sampling reads the **global torch RNG** (no seed parameter).

## Decision

**Vendor the two upstream model files** (`model/kronos.py`, `model/module.py`) into `alpha_forecast/_vendor/kronos/`, pinned to commit `67b630e67f6a18c9e9be918d9b4337c960db1e9a`, verbatim except a documented sys.path/star-import rewrite; retain the MIT LICENSE and a provenance header. ruff and mypy exclude the vendor tree (`extend-exclude` + `exclude` + a `follow_imports = "skip"` override), mirroring the nautilus-Cython pattern.

**New layer-1 package `alpha_forecast`** (core-only imports; the 8th import-linter contract forbids everything except `alpha_cli` from importing it). The public seam is numpy-free (`ForecastResult`/`SampledPath` as frozen tuples-of-floats; `Forecaster` protocol); numpy/torch/pandas live strictly inside. Importing the package never imports torch (facade imports are method-level; subprocess-guarded by a test).

**Sampling contract:** the facade calls `predict_batch` with S copies of the series at `sample_count=1` — each batch row draws independently, giving S *distinct* paths in one batched autoregressive pass (fixed chunk size 32, per-chunk `SeedSequence`-derived `torch.manual_seed`). Default device is `cpu` (bit-reproducible; verified live); `mps`/`cuda` are opt-in and flagged `determinism: "best-effort"` in every manifest via `provenance()`.

**pandas edge:** `alpha_forecast.kronos` is the second sanctioned pandas boundary (after `alpha_validation.tearsheet`) because the upstream API speaks DataFrames.

**Code anchors:**
- `packages/alpha-forecast/src/alpha_forecast/kronos.py:KronosForecaster.forecast` — batch-of-copies sampling, chunked seeding, explicit device.
- `packages/alpha-forecast/src/alpha_forecast/_vendor/kronos/kronos.py` — provenance header + pin.
- root `pyproject.toml` — contract `alpha_forecast depends only on core`; `[[tool.uv.index]] pytorch-cpu` gated to linux so CI never resolves CUDA wheels (`uv.lock` carries zero `nvidia-*` packages).
- `tests/unit/test_forecast_kronos_facade.py` — torch-free-import subprocess guard; `tests/integration/test_kronos_live.py` (`network`) — live pin + determinism + distinct-paths proof.

## Options Considered

### Option A: vendor pinned upstream files behind a typed facade (chosen)

| Dimension | Assessment |
|---|---|
| Complexity | Low — two files + one import rewrite, excluded from lint/type gates |
| Cost | Manual refresh procedure (re-fetch at a new pin, reapply the rewrite) |
| Correctness-risk | Low — exact pin, no supply chain between us and the reviewed source |
| Fit | Excellent — deterministic provenance matches the platform's pinning discipline |

### Option B: `kronos-model-arch` PyPI wheel

| Dimension | Assessment |
|---|---|
| Complexity | Lowest — `uv add` |
| Cost | None up front |
| Correctness-risk | High — single 0.1.0 release, weak provenance, may drift from the repo |
| Fit | Poor — an unauditable wheel under a strict-reproducibility platform |

### Option C: git dependency on the upstream repo

| Dimension | Assessment |
|---|---|
| Complexity | Medium — upstream has no `pyproject.toml`, so it is not installable as-is |
| Cost | Blocked on upstream packaging |
| Correctness-risk | Medium |
| Fit | Poor today — not installable without forking anyway |

## Trade-off Analysis

Vendoring trades a small refresh burden for exact, auditable provenance — the same trade the platform already makes for pinned snapshots and content-addressed run ids. Layer-1 placement keeps the model a *feature library* like `alpha_strategies`/`alpha_validation`: only `alpha_cli` may compose it with data and the engine, so torch can never leak into the backtest or validation layers.

## Consequences

- **Easier:** byte-pinned model provenance in every manifest; offline test suite (FakeForecaster double); CPU-only CI.
- **Harder:** upstream fixes require a deliberate re-vendor (documented in the file headers); a fine-tuned checkpoint must be loadable via `from_pretrained` local paths (supported).
- **Revisit when:** upstream ships a real package with tagged releases, or Kronos-large lands and the 512-token context stops being the binding constraint.
