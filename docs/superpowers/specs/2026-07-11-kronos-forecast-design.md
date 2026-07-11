# Design — alpha-forecast: Kronos foundation-model forecasting (Phase 7)

## Context

Project ALPHA's four strategies are classical signals. This phase integrates
[Kronos](https://github.com/shiyu-coder/Kronos) (MIT, AAAI 2026) — a decoder-only foundation
model over OHLCV "K-line language" with open weights on Hugging Face (`NeoQuasar/Kronos-mini`
4.1M / `-small` 24.7M / `-base` 102.3M) — as (a) a registry strategy judged by the existing
gauntlet and (b) an `alpha forecast` command with a chart in alpha-web and an alpha-mcp tool.

## Decisions (user-approved)

- Source: vendored from the upstream repo (MIT); weights never committed — they download from
  Hugging Face via `alpha forecast pull` (the only network path).
- Default model: **Kronos-base** (`--param model=2` in the strategy; `--model base` in the CLI).
  On CPU use mini (`model=0`) for anything gauntlet-shaped — see the cost table.
- Scope: full (strategy + forecast CLI/artifacts/report + web chart + MCP tool).
- torch stack is OPT-IN: `uv sync --group kronos`. The default install, CI, and every
  non-network test run without torch (stub forecasters); torch-requiring tests skip visibly.

## Architecture

```
alpha_core.protocols.BarForecaster        # forecast(bars, horizon) -> list[Bar]
        ^ implements                              ^ injected into
packages/alpha-forecast (core only)       alpha_strategies.kronos_forecast.KronosForecast
  models.py     ModelSpec registry, future_timestamps, KRONOS_TRAINING_CUTOFF,
                training_overlap_warning
  cache.py      content-addressed forecast cache (sha256 of model+revision+window+
                sampling+seed; excludes signal params -> optim sweeps reuse forecasts)
  forecaster.py KronosForecaster: lazy torch, from_pretrained(local_files_only=True),
                per-window torch seeding from AlphaSettings.random_seed (call-order
                independent), sample_count>1 -> mean path + close p10/p90 band,
                fail-loud sanitation (never clamps a broken forecast)
  download.py   pull_model (snapshot_download + offline verification load)
  _vendor/kronos/  upstream model/module.py + model/kronos.py (one import patch; see
                   _vendor/README.md for provenance)
alpha_cli composes: _strategies.py kronos entry (+ _KRONOS_FACTORY test seam),
  forecast_cmds.py (pull/run + artifacts), report_cmds; alpha_web + alpha_mcp read the
  forecast run type.
```

- Import DAG: `alpha_forecast <- core` only (new import-linter contract; 8 total).
  `alpha_strategies` stays core-only because the forecaster is constructor-injected by the CLI.
- `alpha_forecast` is the second sanctioned pandas edge (the vendored predictor speaks pandas).
- `AlphaSettings.weights_dir` (env `ALPHA_WEIGHTS_DIR`; default `data_dir/models`) locates
  weights. Named `weights_dir`, not `model_dir` (pydantic `model_` protected namespace).

### Strategy semantics

`KronosForecast(VolTargetStrategy)`: on each rebalance bar, the trailing `context` bars go to
the forecaster; `signals.forecast_signal(last_close, forecast_closes, deadband_bps)` maps the
horizon-end expected log-return to {-1,0,1} (strictly-greater deadband, flat inside); the base
class sizes vol-targeted, decide close t / fill open t+1. Strategy params (float-encoded in
`--param`): `model=0|1|2` (mini/small/base; default 2), `context=400`, `horizon=30`,
`deadband=25`, `temperature=1.0`, `top_p=0.9`, `sample_count=1`.

### Gauntlet: Tier-1 skipped-with-reason

A foundation model cannot run inside the 1000-path returns-level null on CPU, and a proxy
surrogate would Tier-1-test a different strategy. `StrategyDef.surrogate` is now Optional;
`NullSummary` gained `skipped`/`reason`; the null gate passes iff every tier that RAN passed
and at least one ran. The skip is visible in the manifest, the tear sheet (`SKIPPED` row),
`alpha report`, and the validate echo (`null pct SKIPPED/<tier2>`). Recommended kronos
validation knobs: `--param model=0 --tier2-paths 8`. Stub-forecaster gauntlet tests run serial
(the monkeypatched factory does not survive spawn workers).

## Weight-level look-ahead (the load-bearing caveat)

Kronos weights were trained on market data up to ~**2025-08** (`KRONOS_TRAINING_CUTOFF`).
Accessor-level PIT guards (bias guards verify the forecaster sees only trailing bars) CANNOT
catch what the weights already memorized. Every backtest/validate/optim/forecast whose window
starts before the cutoff:

- echoes a yellow warning ending "treat every gauntlet verdict on this window as an UPPER
  BOUND, not evidence of edge", and
- records it as `leakage_warning` in the manifest (rendered on the web run page too).

Genuinely out-of-sample evaluation exists only on post-2025-08 data. This is disclosable, not
fixable.

## Artifacts (`data_dir/forecast/<run_id>/`)

- `manifest.json` — byte-stable (sorted keys, `allow_nan=False`): model block (repos,
  max_context, revision, torch_version — provenance only, excluded from the run id), params,
  window block (n_bars, first/last ts, `window_sha`, last_close), forecast block (end_close,
  expected_log_return, direction), `leakage_warning`.
- `forecast.parquet` (`ts,o,h,l,c,v[,close_p10,close_p90]`) + `history.parquet` (the context
  window) — run pages render self-contained.
- `run_id = run_id_for({command, symbol, snapshot, model, horizon, context, T, top_p,
  sample_count, seed, window_sha})`.

## Runtime cost (CPU, order-of-magnitude — replace with measured numbers from
`tests/integration/test_kronos_live.py` timing output)

| Scenario | mini | small | base (default) |
|---|---|---|---|
| One forecast (ctx 400, h 30) | ~2–10 s | ~15–60 s | ~1–5 min |
| 10y daily backtest (~100 rebalance forecasts), cold cache | ~5–15 min | ~30–90 min | ~2–8 h |
| Same, warm cache | seconds | seconds | seconds |
| `alpha validate --tier2-paths 8` (synthetic paths defeat the cache) | ~20–60 min | hours | not recommended |

## Determinism

All sampling randomness derives from `AlphaSettings.random_seed` + the sha256 of the exact
context window (`np.random.SeedSequence([seed, window_hash]) -> torch.manual_seed`), so
results are call-order independent and the cache key doubles as the determinism key.
Deterministic per torch build on CPU; GPU/cross-version determinism is NOT promised —
manifests record `torch_version`.

## Open items / risks

1. `ModelSpec.revision` is None (HF unreachable from the build sandbox): pin the
   `NeoQuasar/*` snapshot revisions after the first `alpha forecast pull` and commit them.
2. `_vendor/README.md` records that the vendored files were retrieved via a text pipeline and
   functionally verified (tiny-random-weights end-to-end test) but not git-diffed against a
   specific upstream commit — re-verify + record the sha when github.com is reachable.
3. Upstream pins (`einops==0.8.1`, `huggingface_hub==0.33.1`) were relaxed to `>=` floors so
   the workspace resolver stays free.
4. Cache has no eviction (KB-scale entries; `rm -rf data/forecast_cache` to reset).
