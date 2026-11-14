---
owner: command line models and forecasts
sources:
  - apps/alpha-cli/src/alpha_cli/ml_*.py
  - apps/alpha-cli/src/alpha_cli/_ml_*.py
  - apps/alpha-cli/src/alpha_cli/_forecast*.py
  - apps/alpha-cli/src/alpha_cli/forecast_cmds.py
  - tests/unit/test_ml_*.py
  - tests/unit/test_qlib_isolation.py
  - tests/unit/test_forecast_*.py
  - tests/integration/test_ml_cli.py
  - tests/integration/test_forecast_*.py
verified: 1724a5befe5d
---

# Command line model invariants

What must not break when changing the isolated Qlib exchange (`alpha ml ...`, `ml_*` and `_ml_*` modules) and the
Kronos forecast composition (`alpha forecast ...`, `_forecast*` modules). Project-wide rule:
[research integrity § Models and isolated workers](research-integrity.md#models-and-isolated-workers).

## Qlib worker boundary

- The root runtime never imports Qlib, LightGBM or the worker package, and never deserialises a model object.
  `workers/qlib` has its own project and lock and is absent from the root lock. Enforced by
  `tests/unit/test_qlib_isolation.py`. [ADR-0016](../../adr/0016-isolated-qlib-worker.md)
- The worker runs through `uv run --locked` with a credential-free environment (`ml_cmds._worker_environment`):
  an allow-listed set of variables, a fixed `PYTHONHASHSEED`, and single-threaded numeric libraries.
- The request's `worker_lock_hash` must equal the selected worker's `uv.lock` bytes, or training refuses to start.
- The worker gets only immutable snapshot, fold and config inputs; only validated JSON and Parquet come back
  (`validate_result_bundle`). A worker that rewrites its inputs, or a result whose claims do not match the control
  record, fails validation. Enforced by `tests/unit/test_ml_boundary_guards.py`.
- Workstation-managed exchanges live below `data_dir/control/ml/`.

## Exchange contract

- Daily panel rows and predictions are available at the canonical close, `session_ts + 23h`
  (`ml_contract.DECISION_CLOSE_OFFSET`); any other `available_at` fails. Never stamp at session midnight.
- Fold test windows may not overlap, and a zero buffer still needs the label-horizon gap. Enforced by
  `tests/unit/test_ml_contract.py`.
- Every supported request version rejects a new `point_in_time` membership claim, because none carries a membership
  schedule. `current_membership` must carry its permanent survivorship warning.
- Frozen legacy point-in-time results stay readable as `declared_unverified`; training and replay-signal generation
  refuse them.
- Request bytes are canonical; unsafe paths, hash drift and non-canonical JSON fail loud.
- The `alpha158` feature recipe is version 1, 2 or 3 (3 is opt-in; 1 stays the default). Version 3 takes all 158 columns and the fold
  processors from upstream Qlib and needs the worker's ten-file source inventory (`ml_refit.py`). Frozen inventories of 7 and 9 files
  are never reinterpreted, and a partly present tier fails. [ADR-0042](../../adr/0042-qlib-worker-delegates-data-layer-to-upstream.md)
- `native_qlib_pipeline.py` is a demo on fabricated data, not this exchange: research ML goes only through `alpha ml ...`.

## Replay is authoritative

- ALPHA re-executes validated predictions in one synchronized, costed, long-only multi-asset replay through
  `alpha_backtest.portfolio_replay` (`_ml_replay.py`). Its engine metrics and causal artifacts are the evidence; Qlib
  diagnostics are advisory.
- The replay is labelled `not_run_model_not_recomputed_under_counterfactual` for null validation: randomized paths do
  not retrain the model, so it is not a full counterfactual gauntlet. Never drop that label.
- `ml_compare.py` compares lineage-bound predictions only; it runs no economic simulation.
- `_ml_observation_store.py` is a bounded diagnostic journal, never Qlib admission or accounting.

## Kronos forecasts

- Model, tokenizer, revisions and device come from `ALPHA_FORECAST_*` settings, never from strategy parameters.
- The Kronos signal cache key (`_forecast_cache.cache_key`) hashes bars, model identity from settings, Kronos parameters,
  cadence and seed. The cache directory `data_dir/forecasts/<key>` is reused across runs and is not a run directory.
- The local weights path and offline switch never enter run ids or manifests; missing offline weights fail before any
  network access. [ADR-0010](../../adr/0010-local-kronos-weights-offline-policy.md)
- Every forecast records `pretrain` overlap against the assumed training cutoff (`_forecast.pretrain_overlap`), warns
  loudly when windows overlap, and evaluation splits metrics pre and post cutoff.
  [ADR-0009](../../adr/0009-forecast-leakage-and-tier2-cost-policy.md)
- Rolling-origin evaluation seeds each origin independently of stride (`_forecast_eval.py`).
- `--model fake` is the offline test double; never use it as evidence.
- For `alpha validate` on `kronos`, Tier 1 and default Tier 2 replay the observed signal cache (an association test,
  recorded as `tier2_policy`); `--tier2-mode model` re-forecasts each synthetic path.
- Kronos has no live-paper support (`supports_live_paper=False`).
- Kronos and Qlib jobs share the single heavyweight capacity slot; see
  [command line control plane § Jobs, leases and capacity](cli-control-store.md#jobs-leases-and-capacity).
