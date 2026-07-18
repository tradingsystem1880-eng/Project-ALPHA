# Kronos Foundation-Model Integration — Design (approved 2026-07-04)

> **Implemented-state pointer (2026-07-18):** The shipped integration uses local, hash-pinned
> Kronos-base weights with offline-only loading per ADR-0010. This remains the point-in-time design;
> current commands and policy live in [`CLAUDE.md`](../../../CLAUDE.md) and
> [`docs/ARCHITECTURE.md`](../../ARCHITECTURE.md).

Integrate [Kronos](https://github.com/shiyu-coder/Kronos) (open-source, MIT, AAAI 2026 — a
decoder-only foundation model for financial K-lines, pretrained on 12B+ candles across 45
exchanges) into Project ALPHA as a first-class research capability:

1. **Probabilistic forecasting** — `alpha forecast run SYMBOL`: sampled OHLCV paths +
   close-quantile outcome cones (BrighterData-style), rendered as a server-side SVG fan
   chart in `alpha_web`.
2. **Honest skill evaluation** — `alpha forecast eval SYMBOL`: rolling-origin CRPS /
   pinball / coverage / hit-rate vs random-walk-with-drift and stationary-bootstrap
   baselines, split pre/post the assumed pretraining cutoff.
3. **A `kronos` strategy** in the registry that flows through backtest/validate/optim like
   any other strategy, via precomputed content-addressed signal caches.

## Approved scope decisions

- **Full stack, staged stacked PRs** (package → run CLI → web → eval → strategy → ADRs).
- **Zero-shot only**: pretrained HF weights (`NeoQuasar/Kronos-small` default; mini/base
  selectable; local checkpoint paths accepted for future fine-tunes). No qlib pipeline.
- **Leakage policy: warn + manifest flag.** Kronos's training-data cutoff is undisclosed;
  `AlphaSettings.forecast_pretrain_cutoff` defaults to 2025-08-02 (paper submission,
  conservative). Overlapping runs get a loud CLI warning + `pretrain.overlap` manifest
  block; eval splits metrics pre/post cutoff; tear sheets carry the caveat.

## Load-bearing design facts

- Upstream `predict(sample_count=S)` **averages** its S draws (verified in source at the
  vendored pin). The facade therefore calls `predict_batch` with S copies of the series at
  `sample_count=1` — the batch dimension draws independently, giving S distinct paths in
  one batched autoregressive pass (fixed chunk size 32, per-chunk derived torch seeds).
- Upstream sampling uses the **global torch RNG** (no seed parameter): the facade seeds
  `torch.manual_seed` from `SeedSequence` children per chunk. cpu = bit-exact; mps/cuda =
  best-effort, recorded via `provenance()` in every manifest.
- Engine strategies are **rebuilt from pickled `RunSpec` inside spawn workers** and
  `strategy_params` is float-valued — a live torch model can never enter the engine. The
  `kronos` strategy is therefore a pure `SignalReplay` over a precomputed, content-addressed
  per-bar signal cache (`data_dir/forecasts/<key>/`), computed by `alpha_cli` at the
  rebalance-schedule indices only (~56 model calls per 5y daily backtest).
- Vendored code (`alpha_forecast/_vendor/kronos/`, pinned @ `67b630e6`, MIT) instead of the
  weak-provenance `kronos-model-arch` PyPI wheel; ruff/mypy exclude the vendor tree.
- `alpha_forecast` is a layer-1 package (core-only imports; only `alpha_cli` may import it —
  the 8th import-linter contract). pandas is sanctioned ONLY inside the Kronos facade (the
  second pandas edge, after the tear sheet). torch resolves from the PyTorch CPU index on
  linux so CI never pulls CUDA wheels.

Full phased plan (PR-by-PR files, tests, risks, verification):
`~/.claude/plans/i-wnat-to-inlcude-elegant-coral.md` (session artifact); ADRs 0008/0009
carry the durable rationale.
