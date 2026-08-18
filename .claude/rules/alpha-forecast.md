---
paths:
  - "packages/alpha-forecast/**"
---
# alpha_forecast rules

Verbatim relocation from the pre-v2 CLAUDE.md MODULE MAP (drift-tested against `tests/fixtures/claude_md_v1.md`). The core `CLAUDE.md` DAG paragraph and golden rules still apply here.
### `alpha_forecast` (`packages/alpha-forecast/src/alpha_forecast/`) — Kronos foundation-model forecasting. core only; only `alpha_cli` may import it. Importing the package never imports torch (facade imports are method-level).
| Module | Responsibility | Key public symbols |
|---|---|---|
| `types.py` | Frozen forecast values + protocol (numpy-free seam) | `SampledPath` (finite, close>0; OHLC coherence deliberately NOT enforced on model output), `ForecastResult(symbol, origin_ts, horizon, step_ts, samples)`, `Forecaster` protocol |
| `timestamps.py` | Future session timestamps | `future_session_ts(recent_ts, horizon)` — weekend bar in history ⇒ calendar cadence (crypto), else Mon–Fri; no holiday calendar (documented approximation) |
| `quantiles.py` | Per-step close quantiles across samples | `close_quantiles(result, qs=DEFAULT_QS)`, `DEFAULT_QS=(.05,.25,.5,.75,.95)` |
| `signals.py` | Pure quantile→signal rule | `kronos_signal(origin_close, q25_end, q50_end, q75_end, *, min_edge, require_band_agreement)` → {-1,0,1} |
| `fake.py` | Offline deterministic test double (rng keyed on seed + window content hash — window-pure by construction) | `FakeForecaster(vol_scale)` |
| `kronos.py` | **torch/pandas edge**; lazy-loads the vendored model | `KronosForecaster(model_id, model_revision, tokenizer_id, tokenizer_revision, device, max_context, clip, cache_dir, local_files_only)` (local cache + offline: missing weights raise `DataError` before any HTTP; both knobs excluded from provenance), `.provenance()`, `VENDORED_KRONOS_SHA`. Upstream `predict(sample_count=S)` AVERAGES paths → facade uses `predict_batch` with S copies @ `sample_count=1` (chunk 32, per-chunk torch seeds). cpu = bit-exact; mps/cuda best-effort |
| `_vendor/kronos/` | Pinned upstream model code (@ `67b630e6`, MIT; ruff/mypy-excluded) | `Kronos`, `KronosTokenizer`, `KronosPredictor` — facade-only import |

