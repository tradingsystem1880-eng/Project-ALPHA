# Project ALPHA — Agent Operating Manual

$0/free, institutional-grade Python quant research platform. **Written and operated entirely by AI agents.** This file is authoritative and OVERRIDES default behavior. Be terse, fail loud, never violate the architecture DAG.

- Spec: `docs/superpowers/specs/2026-06-14-project-alpha-v1-design.md`
- Research: `research/00-SYNTHESIS.md` (+ `research/01..07-*.md`)
- Phase plans: `docs/superpowers/plans/2026-*.md`
- Python 3.12, `uv` virtual workspace (root is not a package). Members: `packages/*`, `apps/*`.

## Architecture DAG (import-linter enforced — NEVER violate)
`alpha_core` ← `alpha_data` ← `alpha_backtest`; `alpha_strategies`, `alpha_validation`, `alpha_forecast` ← `alpha_core`; `alpha_cli` ← everything; `alpha_mcp`, `alpha_web` ← `alpha_cli` (top of DAG).
- `alpha_core` imports nothing internal.
- `alpha_data` → core only. `alpha_strategies` → core only. `alpha_validation` → core only. `alpha_forecast` → core only (only `alpha_cli` may import it). `alpha_backtest` → core + data only.
- `alpha_cli` is the ONLY layer allowed to compose the backtest engine with the validation gauntlet.
- `alpha_mcp` and `alpha_web` sit atop the DAG and compose nothing — they subprocess the `alpha` CLI; nothing imports them.
- Contracts live in root `pyproject.toml` `[tool.importlinter]` (8 forbidden contracts). Run `uv run lint-imports` after any cross-package import change.

## Golden rules (invariants)
- **TDD.** Failing test → minimal code → green → commit. Small, atomic, conventional commits (`feat(scope):`, `fix(...)`, `test(...)`, `build(...)`, `chore(...)`, `docs:`).
- **No look-ahead, ever.** Strategies/backtests read data ONLY via the point-in-time accessor `as_of`. Every data/strategy unit gets a `@pytest.mark.bias_guard` future-poison test (see `tests/bias_guards/`).
- **Execution convention:** decide on close of bar `t`, fill at open of `t+1`. Mechanism: `feed.to_execution_feed` emits an open-priced `QuoteTick` (at `bar.ts`) + a close-stamped (+23h) decision `Bar`; venue runs `bar_execution=False` so only quotes fill.
- **No empty `except`.** Raise/propagate typed `AlphaError`/`DataError`/`LookAheadError` with context, or re-raise. Fail loud on data gaps / NaN / inf / disorder / degenerate stats.
- **Polars** is the default dataframe. pandas ONLY at two sanctioned edges: the tear-sheet renderer (`alpha_validation.tearsheet`, with `quantstats_lumi`) and the Kronos model facade (`alpha_forecast.kronos` — upstream API speaks DataFrames). `numpy`/`scipy.stats.norm` in the `alpha_validation` numeric layer; numpy/torch also live inside `alpha_forecast` internals (never at its public seam, which is plain floats/tuples).
- **Strong typing.** `mypy --strict` is a CI gate. Overrides (do not "fix"): `nautilus_trader.*`, `scipy.*`, `quantstats_lumi.*` are `ignore_missing_imports` (no loadable stubs); nautilus Cython base classes get `# type: ignore[misc]`.
- **Determinism (spec §11.4).** All seeds derive from `AlphaSettings.random_seed` (default 7); the gauntlet spawns independent child seeds via `np.random.SeedSequence(master).spawn(n)` so gate order can't change results. `run_id` = sha256 of canonical sorted-key JSON of the params (no wall-clock). Manifests are byte-stable (sorted keys, `allow_nan=False` → non-finite must already be `null`).
- **Corporate actions: two clocks.** Knowledge time (`announce_date` else `ex_date`) gates visibility; `ex_date` gates price application (a known-but-future split does NOT rescale prices yet). Splits adjust the price series; dividends are decoupled cash events **credited by the engine at `pay_date`** against the pre-ex holding (shorts debited; never folded into prices; threaded through every run path incl. Tier-2 nulls — Tier-1 stays price-only by design). Yahoo serves split-adjusted OHLCV, so the yfinance parser reconstructs RAW prices from in-window split events (fails loud if the vendor convention drifts). See spec §6.1.

## Commands
- Install: `uv sync`
- Full gate (run before every commit; mirrors CI `.github/workflows/ci.yml`):
  `uv run ruff check . && uv run ruff format --check . && uv run lint-imports && uv run mypy packages apps tests && uv run pytest -q -m "not network"`
- Bias guards only: `uv run pytest -m bias_guard -q`
- Live-network tests (off by default, hit real APIs): `uv run pytest -m network -q`
- CLI smoke: `uv run alpha info`
- Ruff: line-length 100, target py312, rules `E,F,I,B,UP,SIM`. Markers (`--strict-markers` on): `bias_guard` (look-ahead/survivorship guards, gated in CI), `network` (skipped in CI/offline).

## CLI surface (`apps/alpha-cli/src/alpha_cli/`)
Entry point `alpha = alpha_cli.main:main`. `data`/`backtest`/`optim`/`paper` are Typer sub-apps; `validate`/`report` are root commands.
- `alpha info` — print resolved `AlphaSettings` + core version.
- `alpha data pull SYMBOL --source {yfinance,ccxt,stooq} --start --end` — fetch + store raw bars/actions.
- `alpha data snapshot SNAPSHOT_ID SYMBOLS... [--source]` — freeze store → immutable hashed snapshot.
- `alpha data verify SNAPSHOT_ID` — re-hash snapshot vs manifest.
- `alpha backtest run SYMBOL [--strategy ts_momentum|ma_crossover|mean_reversion|breakout|kronos, --param name=value, --periods-per-year, --size-on-equity, --halt-drawdown F, ...params, snapshot]` — one fixed-param run → artifacts. Slash symbols (`BTC/USD`) dispatch to a 5-decimal crypto instrument and require `--account-type MARGIN`. `--size-on-equity` re-bases vol sizing on current net-liq; `--halt-drawdown F` is a flatten-for-good kill-switch at `peak×(1−F)` (both opt-in; REJECTED by `validate`/`optim` — Tier-1 can't model equity-path-dependent sizing). `kronos` params (floats): `context/horizon/samples/temperature/top_p/top_k/min_edge/band`; model selection via `ALPHA_FORECAST_*` env (never params); the CLI auto-precomputes the signal cache (`data_dir/forecasts/<key>`) before entering the engine.
- `alpha forecast run SYMBOL [--horizon 21 --samples 100 --context --model --device --as-of --seed]` — probabilistic outcome cone (sampled OHLCV paths + close quantiles) → `data_dir/forecast/<run_id>/{manifest.json, paths.parquet, quantiles.parquet, history.parquet}`. `--model fake` = offline test double. Pre-cutoff windows warn loud + set `pretrain.overlap` (ADR-0009).
- `alpha forecast eval SYMBOL [--horizon --stride --samples ...]` — rolling-origin forecast skill: CRPS/pinball/coverage/hit-rate vs RW-drift + stationary-bootstrap baselines, split pre/post `forecast_pretrain_cutoff`.
- `alpha backtest portfolio SYMBOLS... [--strategy, --weighting equal|inverse_vol, --seed, ...params]` — diversified basket (canonical sorted symbol order): per-symbol OOS streams combined (inverse-vol weights are CAUSAL — per-date trailing vol, never full-sample) → portfolio metrics + PSR + BCa CIs + manifest (`data_dir/portfolio/<run_id>`).
- `alpha backtest cross-sectional SYMBOLS... [--top-quantile, --no-long-short, --fee-bps, --slippage-bps, --seed, ...params]` — relative-strength book: rank the universe (canonical sorted order), long winners / short losers, vol-targeted, fee+slippage charged on rebalance turnover → OOS metrics + PSR + CIs + manifest (`data_dir/cross_sectional/<run_id>`).
- `alpha validate SYMBOL [--strategy, --param, ...params, train_size=504, test_size=63, embargo=5, tier1_paths=1000, tier2_paths=64, n_resamples=2000, mean_block=5.0, threshold=0.95, --null-model bootstrap|student_t|garch, tier1_divergence_tol=0.25, --tier2-mode replay|model (kronos only), periods_per_year=252, seed, max_workers, snapshot]` — full gauntlet → manifest + parquet + HTML tear sheet. NOTE: `train_size` must clear the strategy's warmup floor or it fails loud. `--allow-short` defaults by account: MARGIN→short-ok, CASH→long-flat; an explicit `--allow-short` on CASH fails loud (the venue denies short sells wholesale). `--snapshot` verifies + reads the frozen snapshot (not the live store). `run_id` excludes `max_workers` (execution-only). For `kronos`: Tier-1 + default Tier-2 REPLAY the observed signal cache (association test, flagged in `manifest["forecast"].tier2_policy`); `--tier2-mode model` re-forecasts every synthetic path (parent-process caches; ~tier2_paths × model cost).
- `alpha optim grid SYMBOL --grid name=v1,v2,... [--strategy, ...params, pbo_blocks, n_resamples, dsr_threshold, alpha, seed, max_workers]` — parameter sweep judged for overfitting (Deflated Sharpe + PBO + Reality-Check/SPA) → manifest (`data_dir/optim/<run_id>`).
- `alpha paper preflight SYMBOL [--strategy, --venue, --account-type, --starting-cash, --currency, --param]` — validate the Phase-4 paper wiring offline: build the sandbox exec + node configs + the parity strategy; reports the remaining live-data-adapter step.
- `alpha propfirm run [SYMBOL] [--firm topstep|apex|takeprofit, --from-run RUN_ID, --account-size, --profit-target, --max-drawdown, --daily-loss, --profit-split, --min-trading-days, --n-paths, --mean-block, --horizon, seed, ...backtest params]` — prop-firm Monte Carlo: resample a strategy's daily return stream (fresh backtest of SYMBOL, or `--from-run`'s stored equity curve) and walk it through a firm's eval→funded→payout rules (return-scaled, EOD granularity) → pass/bust/payout probabilities + expected payout → manifest (`data_dir/propfirm/<run_id>`). Exactly one of SYMBOL / `--from-run`. Presets are illustrative, not authoritative firm terms.
- `alpha report RUN_ID` — re-display any stored run (runs/optim/portfolio/cross_sectional/propfirm/forecast) from its manifest (no engine re-run).
Artifacts: `data_dir/runs/<run_id>/{manifest.json, equity_curve.parquet, trades.parquet, tearsheet.html}` (only the manifest+parquet are byte-pinned; HTML carries volatile fields). Forecast runs: `data_dir/forecast/<run_id>/` (+ `paths/quantiles/history` or `origins` parquet). Kronos signal caches (NOT runs): `data_dir/forecasts/<key>/{signals.parquet, meta.json}`.

## MODULE MAP

### `alpha_core` (`packages/alpha-core/src/alpha_core/`) — domain types, protocols, errors, config. Imports nothing internal.
| Module | Responsibility | Key public symbols |
|---|---|---|
| `types.py` | Frozen domain values | `Bar` (OHLCV; validates finite/positive/OHLC-consistent), `ValidationOutcome(name, passed, detail)` |
| `errors.py` | Typed error hierarchy | `AlphaError` ← `DataError`, `LookAheadError` |
| `protocols.py` | Structural interfaces | `DataSource` (`available_symbols`, `as_of`), `Validator` |
| `config.py` | Typed settings (env `ALPHA_*`/`.env`) | `AlphaSettings(data_dir=Path("data"), random_seed=7)` |
| `corporate.py` | Corporate-action types (two-clock) | `ActionType` (SPLIT/DIVIDEND/REDENOMINATION/SYMBOL_MIGRATION), `CorporateAction` (`knowledge_time`, `knowledge_is_estimated`) |

### `alpha_data` (`packages/alpha-data/src/alpha_data/`) — ingestion, PIT storage, snapshots.
| Module | Responsibility | Key public symbols |
|---|---|---|
| `store.py` | Raw unadjusted Parquet store (wholesale replace) | `ParquetStore(root)`: `write_bars/read_bars/list_symbols/write_actions/read_actions` |
| `pit.py` | **Look-ahead firewall** (frame-level) | `PointInTimeReader.as_of` (split-adjusted, future-excluded), `.dividends_as_of` |
| `source.py` | Typed PIT `DataSource` seam | `PointInTimeSource.as_of` → `list[Bar]`, `.dividends_as_of` |
| `corporate.py` | Two-clock split/div math | `known_actions`, `cash_dividends`, `split_factor` |
| `snapshot.py` | Immutable hashed snapshots + manifest | `create_snapshot`, `verify_snapshot` |
| `ingest.py` | Persist a `FetchResult` | `store_fetch_result` |
| `adapters/base.py` | Adapter seam | `FetchResult(symbol, bars, actions)`, `DataAdapter` protocol |
| `adapters/yfinance_adapter.py` | Equities (splits+divs); reconstructs RAW prices from Yahoo's split-adjusted series, fail-loud discontinuity check | `YFinanceAdapter`, `parse_yfinance_history` (pure) |
| `adapters/ccxt_adapter.py` | Crypto daily OHLCV (UTC; default exchange `coinbase`; **paginated** past coinbase's 300-candle/call cap via `_paginate_ohlcv`) | `CCXTAdapter`, `parse_ccxt_ohlcv` (pure) |
| `adapters/stooq_adapter.py` | Free EOD OHLCV (FX/commodity/index/ETF; provider-adjusted, no actions). **Anti-bot gated:** browser-UA + SHA-256 PoW solve, then **fails loud** (`_csv_or_raise`) on Stooq's per-IP "Access denied" — yfinance is the reliable equity/ETF source | `StooqAdapter`, `parse_stooq_csv` (pure) |

### `alpha_strategies` (`packages/alpha-strategies/src/alpha_strategies/`) — nautilus Strategy + pure decision fns. core only.
| Module | Responsibility | Key public symbols |
|---|---|---|
| `signals.py` | Pure signals (all `{-1,0,1}`, trailing-window only) | `ts_momentum_signal`, `ma_crossover_signal(closes, fast, slow)`, `zscore_reversion_signal(closes, window, entry_z)`, `breakout_signal(highs, lows, closes, window)` |
| `sizing.py` | Pure vol-target sizing | `realized_volatility(closes, *, periods_per_year)`, `vol_target_size(signal, price, vol, *, target_vol, capital, max_leverage)` |
| `base.py` | Shared nautilus lifecycle for vol-targeted signals (+ opt-in `size_on_equity`, `halt_drawdown` kill-switch) | `VolTargetStrategy` (decide close-t / fill open-t+1; subclasses implement `_signal()`) |
| `ts_momentum.py` | TS-momentum (a `VolTargetStrategy` subclass since the 2026-07 audit) | `TimeSeriesMomentum` |
| `signal_replay.py` | Replay a precomputed per-bar signal sequence (the kronos engine strategy; fail-loud on uncovered indices) | `SignalReplay(VolTargetStrategy)` |
| `ma_crossover.py` · `mean_reversion.py` · `breakout.py` | `VolTargetStrategy` subclasses | `MovingAverageCrossover`, `MeanReversion`, `DonchianBreakout` |

### `alpha_backtest` (`packages/alpha-backtest/src/alpha_backtest/`) — nautilus run harness. core + data only.
| Module | Responsibility | Key public symbols |
|---|---|---|
| `feed.py` | Bar → nautilus feed (t+1-fill encoding) | `to_execution_feed(bars, bar_type, *, slippage_bps=...)`, `daily_bar_type(symbol, venue="SIM")` |
| `engine.py` | `BacktestEngine` harness (`bar_execution=False`; credits dividend cash at pay_date) | `run_backtest(instrument, data, strategy, *, starting_cash, account_type, leverage, fee_bps, dividends)` → `BacktestResult` |
| `instruments.py` | Per-asset instruments (slash pairs → 5-decimal crypto) | `instrument_for(symbol)`, `equity_instrument`, `crypto_instrument` |
| `frictions.py` | Per-notional fee model | `BpsFeeModel(fee_bps)` (slippage modeled separately in `feed`) |
| `results.py` | Result schema | `BacktestResult(orders, fills, trades, equity_curve)` (`starting_equity`/`final_equity`), `Trade` |

### `alpha_validation` (`packages/alpha-validation/src/alpha_validation/`) — engine-agnostic stats primitives + tear sheet. core only (+ numpy/scipy; pandas/quantstats at the tearsheet edge).
| Module | Responsibility | Key public symbols |
|---|---|---|
| `metrics.py` | Pure numpy return/risk metrics | `to_returns`, `sharpe_ratio`, `annualized_volatility`, `cagr`, `max_drawdown`, `FloatArray`/`FloatSeq` |
| `walkforward.py` | Causal purged/embargoed splitter | `walk_forward_splits(n, *, train_size, test_size, embargo, anchored) -> list[Split]` |
| `cpcv.py` | Combinatorial purged cross-validation | `combinatorial_purged_splits(n, *, n_groups, n_test_groups, embargo)`, `CPCVSplit`, `n_cpcv_splits` |
| `bootstrap.py` | Stationary-bootstrap BCa CIs | `stationary_bootstrap_indices`, `block_bootstrap_ci`, `ConfidenceInterval`, `Statistic` |
| `montecarlo.py` | Randomized-price null + fat-tailed generators | `randomized_price_null`, `parametric_price_null`, `student_t_paths`, `garch_paths`, `NullResult`, `StrategyFn` |
| `dsr.py` | Probabilistic + Deflated Sharpe (Bailey–LdP) | `probabilistic_sharpe_ratio`, `deflated_sharpe`, `expected_max_sharpe`, `DeflatedSharpeResult` |
| `overfitting.py` | PBO via CSCV (Bailey et al.) | `probability_of_backtest_overfitting`, `PBOResult` |
| `propfirm.py` | Prop-firm Monte Carlo (return-scaled, multi-phase eval→funded→payout; reuses `stationary_bootstrap_indices`) | `PropFirmRules`, `PropFirmResult`, `simulate_propfirm`, `FIRM_PRESETS` |
| `verdict.py` | A–F grade over the computed gates (pure, threshold-banded) | `VerdictSummary`, `grade_verdict` |
| `reality_check.py` | White's Reality Check + Hansen's SPA | `reality_check`, `spa_test`, `DataSnoopingResult` |
| `tearsheet.py` | Report schema + render (pandas/quantstats edge) | `GauntletReport`, `RunMetadata`, `FoldSummary`, `NullSummary`, `CISummary`, `DSRSummary`, `CPCVSummary`, `build_outcomes`, `report_to_manifest`, `render_tearsheet_html` |

### `alpha_forecast` (`packages/alpha-forecast/src/alpha_forecast/`) — Kronos foundation-model forecasting. core only; only `alpha_cli` may import it. Importing the package never imports torch (facade imports are method-level).
| Module | Responsibility | Key public symbols |
|---|---|---|
| `types.py` | Frozen forecast values + protocol (numpy-free seam) | `SampledPath` (finite, close>0; OHLC coherence deliberately NOT enforced on model output), `ForecastResult(symbol, origin_ts, horizon, step_ts, samples)`, `Forecaster` protocol |
| `timestamps.py` | Future session timestamps | `future_session_ts(recent_ts, horizon)` — weekend bar in history ⇒ calendar cadence (crypto), else Mon–Fri; no holiday calendar (documented approximation) |
| `quantiles.py` | Per-step close quantiles across samples | `close_quantiles(result, qs=DEFAULT_QS)`, `DEFAULT_QS=(.05,.25,.5,.75,.95)` |
| `signals.py` | Pure quantile→signal rule | `kronos_signal(origin_close, q25_end, q50_end, q75_end, *, min_edge, require_band_agreement)` → {-1,0,1} |
| `fake.py` | Offline deterministic test double (rng keyed on seed + window content hash — window-pure by construction) | `FakeForecaster(vol_scale)` |
| `kronos.py` | **torch/pandas edge**; lazy-loads the vendored model | `KronosForecaster(model_id, model_revision, tokenizer_id, tokenizer_revision, device, max_context, clip)`, `.provenance()`, `VENDORED_KRONOS_SHA`. Upstream `predict(sample_count=S)` AVERAGES paths → facade uses `predict_batch` with S copies @ `sample_count=1` (chunk 32, per-chunk torch seeds). cpu = bit-exact; mps/cuda best-effort |
| `_vendor/kronos/` | Pinned upstream model code (@ `67b630e6`, MIT; ruff/mypy-excluded) | `Kronos`, `KronosTokenizer`, `KronosPredictor` — facade-only import |

### `alpha_cli` (`apps/alpha-cli/src/alpha_cli/`) — orchestration ONLY (allowed to compose engine + gauntlet). Engine imports are lazy.
| Module | Responsibility | Key public symbols |
|---|---|---|
| `main.py` | Typer app wiring | `app`, `info`, `main` |
| `data_cmds.py` | `alpha data ...` | `data_app`; `_ADAPTERS` registry (monkeypatched in tests) |
| `backtest_cmds.py` | `alpha backtest run` / `portfolio` | `backtest_app`; `_load_bars` seam |
| `validate_cmds.py` | `alpha validate` | `validate` |
| `optim_cmds.py` | `alpha optim grid` | `optim_app` |
| `paper_cmds.py` | `alpha paper preflight` | `paper_app` |
| `propfirm_cmds.py` | `alpha propfirm run` | `propfirm_app` |
| `report_cmds.py` | `alpha report` (all run types) | `report` |
| `_strategies.py` | Strategy registry (dispatch by `strategy_name`) | `STRATEGIES` (incl. `kronos` = cache replay), `build_strategy`, `warmup_for`, `surrogate_for`, `known_strategies` |
| `forecast_cmds.py` | `alpha forecast run` / `eval` | `forecast_app`; `--model fake` sentinel |
| `_forecast.py` | Forecast-run glue (PIT slice, pretrain overlap, artifacts) + forecaster factory/provenance | `run_forecast`, `write_forecast_run`, `pretrain_overlap`, `forecast_seed`, `FORECAST_SEED_NS` |
| `_forecast_eval.py` | Rolling-origin skill eval (stride-independent per-origin seeds, cutoff split) | `run_forecast_eval`, `origin_indices`, `ForecastEvalOutput` |
| `_forecast_cache.py` | Content-addressed kronos signal caches (`data_dir/forecasts/<key>`; schedule-exact, idempotent; model identity from settings) | `ensure_forecast_cache`, `prepare_spec_for_engine`, `signal_indices`, `cache_key`, `read_signals` |
| `_runner.py` | Engine↔gauntlet glue, OOS stitch, run id | `RunSpec` (`strategy_name`, `strategy_params`, `param()`), `load_bars`, `load_dividends`, `parse_strategy_params`, `resolve_allow_short`, `run_full_backtest`, `walk_forward_oos`/`_for_spec`, `OOSResult`, `run_id_for` |
| `_gauntlet.py` | Full gauntlet assembly (+ DSR, CPCV, null-model) | `run_gauntlet`, `GauntletParams`, `GauntletOutput` |
| `_optim.py` | Parameter sweep + overfitting verdict | `run_optimization`, `expand_grid`, `OptimResult` |
| `_portfolio.py` | Diversified-basket backtest | `run_portfolio`, `PortfolioResult`, `LegSummary` |
| `_cross_sectional.py` | Cross-sectional momentum (returns-level panel) | `run_cross_sectional`, `CrossSectionalResult` |
| `_paper.py` | Phase-4 paper scaffold (sandbox exec + parity) | `build_sandbox_exec_config`, `build_paper_node_config`, `run_paper` (live run network-gated) |
| `_propfirm.py` | Prop-firm run glue (resolve returns from fresh backtest / `--from-run`; resolve preset + overrides) | `run_propfirm`, `resolve_rules`, `PropFirmRunResult` |
| `_surrogate.py` | Tier-1 engine-free surrogates (weights exposed for the convention-divergence guard) | `Surrogate`, `make_surrogate` (generic), `make_ts_momentum_surrogate` |
| `_synth.py` | Tier-2 synthetic OHLCV paths + full-engine null | `synthetic_bar_paths`, `full_engine_null` (spawn pool, order-preserving, deterministic) |
| `_artifacts.py` | Run-dir layout + manifest/parquet IO | `run_dir`, `write_run`, `read_manifest`, `read_equity` |

### `alpha_mcp` (`apps/alpha-mcp/src/alpha_mcp/`) — MCP server (top of DAG; subprocesses the `alpha` CLI, composes nothing). Launch: `uv run alpha-mcp` (repo `.mcp.json` auto-launches it in Claude Code).
| Module | Responsibility | Key public symbols |
|---|---|---|
| `server.py` | FastMCP instance + ~10 tools + `main()` (stdio) | `mcp`, `main`; action tools `data_pull`/`backtest_run`/`backtest_portfolio`/`backtest_cross_sectional`/`validate`/`optim_grid`/`propfirm_run`; read tools `get_run`/`list_runs`/`list_strategies` |
| `_invoke.py` | Subprocess core: run `alpha`, parse `-> run <id>`, read manifest (fail-loud on non-zero exit) | `run_alpha(args, *, data_dir, run_type)` |
| `_runs.py` | Filesystem reads over the run store | `get_run`, `list_runs` |

Tools take typed common knobs + an `options` dict mapping any CLI flag (`{"lookback":"5"}` → `--lookback 5`) and a `params` dict for strategy `--param name=value`. Adding/removing a CLI command? Update `server.py`'s tool surface to match.

### `alpha_web` (`apps/alpha-web/src/alpha_web/`) — local web IDE (top of DAG; subprocesses the `alpha` CLI). Launch: `uv run alpha-web` → http://127.0.0.1:8800 (loopback only).
| Module | Responsibility | Key public symbols |
|---|---|---|
| `app.py` | FastAPI factory + routes + `main()` (uvicorn) | `create_app`, `main`; routes `/healthz`, `/` (run browser), `/runs/{id}` (+ `/tearsheet`), `/new`, `/console`, `POST /runs` + `/console/run`, `GET /jobs/{id}/stream` (SSE) |
| `_invoke.py` | Background job runner: spawn `alpha`, tail stdout, parse run id, SSE `event_stream` | `Job`, `launch`, `event_stream`, `JOBS`, `RUN_TYPE` |
| `_runs.py` | Filesystem reads | `list_runs`, `get_run`, `equity_values`, `tearsheet_file` |
| `_charts.py` | Server-side inline equity SVG (no JS charting lib) | `equity_svg` |
| `templates/` · `static/` | Jinja pages + dark CSS + `console.js` (native `EventSource`, no build step) | — |

Server-rendered (Jinja + native EventSource, no HTMX/CDN). Action endpoints subprocess `alpha` and stream output live; reads come from the manifests. The real conversational path is `alpha_mcp`, not an in-app LLM (the console panel links to it).

## Validation gauntlet gates (spec §8) — produced by `build_outcomes` → `ValidationOutcome`s
- `walk_forward_oos` (gate 2): passes on a finite OOS Sharpe. OOS = concatenated contiguous test windows of ONE full-series run (fixed params → no refit; train windows are warmup only).
- `randomized_price_null` (gate 3, headline): two tiers — Tier 1 `returns_level` (surrogate on resampled returns, scored on the walk-forward OOS window; `--null-model` selects bootstrap/student_t/garch) + Tier 2 `full_engine` (real engine on level-continuous synthetic OHLCV paths). Passes only if observed beats the `threshold` percentile in **every** tier (conservative) — except that a Tier-1 FAIL is demoted to advisory (`flagged_low_fidelity`, reported but not vetoing) when Tier-2 passed AND the measured close-fill vs t+1-open-fill `convention_divergence` of the same surrogate weights exceeds `tier1_divergence_tol` (the documented Tier-1 crediting bias for high-turnover strategies; see `docs/investigations/2026-06-23-tier1-surrogate-crediting-bias.md`). A Tier-2 fail is never rescued.
- `bootstrap_ci` (gate 4): passes when the Sharpe BCa lower bound > 0.
- `deflated_sharpe`: PSR/DSR of the OOS stream (single run → n_trials=1, DSR=PSR); passes when DSR ≥ `dsr_threshold`.
- `cpcv_oos`: distribution of OOS Sharpe across combinatorial purged CV folds of the OOS stream; passes when the mean fold Sharpe > 0.
A degenerate (flat/zero-variance) OOS short-circuits to a clean FAIL (degenerate gates), never an undefined-Sharpe crash. Overall `passed` = all gates pass.
- **Multi-trial gates (`alpha optim`):** Deflated Sharpe (deflated by the trial-Sharpe variance), PBO via CSCV, and White/Hansen Reality-Check/SPA judge a parameter sweep for selection bias — they only become meaningful with many configs, so they live in `_optim`, not the single-run gauntlet.

## Where do I add X?
- **New strategy** → `alpha_strategies`: pure decision fn(s) in a new module + a `nautilus Strategy` subclass; bias-guard test required. Wire defaults via `_runner.RunSpec` / CLI flags.
- **New data source** → `alpha_data/adapters/<name>_adapter.py`: a pure parser fn + a `DataAdapter` class (`name`/`version`/`parser_version`); register in `alpha_cli/data_cmds.py::_ADAPTERS`. Live-net code under `@pytest.mark.network`.
- **New validation gate / statistic** → `alpha_validation`: engine-agnostic primitive (numpy/scipy, fail-loud), then wire into `alpha_cli/_gauntlet.py` and extend `tearsheet.build_outcomes`/the report schema.
- **Anything composing engine + gauntlet / multi-package orchestration** → `alpha_cli` ONLY (the DAG forbids it elsewhere). Keep engine imports lazy.
- **New domain type / error / protocol / setting** → `alpha_core` (export via `__init__.py`).

## Build status
Phase 0 (rails) ✅ · Phase 1 (data spine) ✅ · Phase 2 (backtest core + strategy) ✅ · Phase 3 (validation gauntlet) ✅ · Phase 5 (tear sheet + CLI) ✅.
**Live data spine verified against real markets** ✅ (yfinance + ccxt/coinbase end-to-end; gauntlet correctly rejects single-name `ts_momentum` on AAPL and accepts a diversified basket. Stooq is anti-bot-gated → fails loud).
Phase 6 (broaden) — in progress: strategy registry + 3 more strategies (MA-crossover, mean-reversion, breakout) ✅ · institutional gauntlet (DSR/PSR, CPCV, PBO, Reality-Check/SPA, fat-tailed nulls) ✅ · parameter optimization with overfitting controls (`alpha optim`) ✅ · multi-asset basket portfolio (`alpha backtest portfolio`) ✅ · cross-sectional momentum (returns-level panel, `alpha backtest cross-sectional`) ✅ · Stooq data source ✅ · prop-firm Monte Carlo (`alpha propfirm`, QuantPad-style pass/payout probabilities) ✅. Remaining: full-engine cross-sectional (per-instrument t+1 fills; needs a multi-instrument engine), more data sources (FRED macro needs a non-OHLCV store).
Kronos foundation-model track (spec `docs/superpowers/specs/2026-07-04-kronos-forecast-integration-design.md`, ADRs 0008/0009) — COMPLETE in the stacked PR chain #14–#19: `alpha_forecast` package (vendored pinned model @ `67b630e6`, typed facade, FakeForecaster, torch-cpu CI index) ✅ · `alpha forecast run` (outcome cones, leakage warn, MCP) ✅ · web fan chart ✅ · `alpha forecast eval` (CRPS/coverage vs RW+bootstrap baselines, pre/post-cutoff split) ✅ · `kronos` strategy via content-addressed signal caches through backtest/validate/optim (+ `--tier2-mode replay|model`) ✅. Deferred: kronos through portfolio/propfirm-fresh paths (build fails loud with guidance), tearsheet caveat note, fine-tuning (zero-shot only per spec).
Phase 4 (paper trading) — scaffolded: nautilus `SandboxExecutionClient` venue (backtest-parity fills) + node-config assembly + a `alpha paper preflight` parity check, all offline-verified. Remaining (post-v1, network-bound): wiring a live market-data adapter + credentials to `_paper.run_paper`.
QuantPad-parity track (separate from the internal phase numbers above): A–F Verdict + tail-risk ✅ · prop-firm Monte Carlo ✅ · conversational agent = MCP server (`alpha_mcp`, subprocesses the CLI; `uv run alpha-mcp` / repo `.mcp.json`) ✅ · local web IDE (`alpha_web`, FastAPI + Jinja + SSE; `uv run alpha-web`) ✅. All four QuantPad-parity surfaces shipped.
