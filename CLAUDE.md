# Project ALPHA — Agent Operating Manual

$0/free, institutional-grade Python quant research platform. **Written and operated entirely by AI agents.** This file is authoritative and OVERRIDES default behavior. Be terse, fail loud, never violate the architecture DAG.

- Baseline spec: `docs/superpowers/specs/2026-06-14-project-alpha-v1-design.md`
- Current post-v2 delta: `docs/superpowers/specs/2026-07-19-provider-control-plane-crypto-paper-design.md`
  + `docs/audit/2026-07-19-post-v2-architecture-audit.md`
- Governance: `docs/governance/2026-07-19-dependency-license-matrix.md`
  + `docs/governance/2026-07-19-post-v2-risk-register.md`
- Research: `research/00-SYNTHESIS.md` (+ `research/01..07-*.md`)
- Phase plans: `docs/superpowers/plans/2026-*.md`
- Python 3.12, `uv` virtual workspace (root is not a package). Members: `packages/*`, `apps/*`.

## Architecture DAG (import-linter enforced — NEVER violate)
`alpha_core` ← `alpha_data` ← `alpha_backtest`; `alpha_strategies`, `alpha_validation`, `alpha_forecast`, `alpha_options`, `alpha_screener` ← `alpha_core`; `alpha_cli` ← everything; `alpha_mcp`, `alpha_web` ← `alpha_core` + public `alpha_cli` seams (top of DAG).
- `alpha_core` imports nothing internal.
- `alpha_data` → core only. `alpha_strategies` → core only. `alpha_validation` → core only. `alpha_forecast` → core only (only `alpha_cli` may import it). `alpha_options` → core only. `alpha_screener` → core only. `alpha_backtest` → core + data only.
- `alpha_cli` is the ONLY layer allowed to compose the backtest engine with the validation gauntlet.
- `alpha_mcp` and `alpha_web` sit atop the DAG and compose nothing — actions plus provider/system and engine-backed projections subprocess the `alpha` CLI; lightweight reads use only public CLI-owned catalog/run-store/paper-store seams. Nothing imports either surface.
- Contracts live in root `pyproject.toml` `[tool.importlinter]` (12 forbidden contracts, including outbound surface limits). Run `uv run lint-imports` after any cross-package import change.

## Golden rules (invariants)
- **TDD.** Failing test → minimal code → green → commit. Small, atomic, conventional commits (`feat(scope):`, `fix(...)`, `test(...)`, `build(...)`, `chore(...)`, `docs:`).
- **No look-ahead, ever.** Strategies/backtests read data ONLY via the point-in-time accessor `as_of`. Every data/strategy unit gets a `@pytest.mark.bias_guard` future-poison test (see `tests/bias_guards/`).
- **Execution convention:** decide on close of bar `t`, fill at open of `t+1`. Mechanism: `feed.to_execution_feed` emits an open-priced `QuoteTick` (at `bar.ts`) + a close-stamped (+23h) decision `Bar`; venue runs `bar_execution=False` so only quotes fill.
- **No empty `except`.** Raise/propagate typed `AlphaError`/`DataError`/`LookAheadError` with context, or re-raise. Fail loud on data gaps / NaN / inf / disorder / degenerate stats.
- **Polars** is the default dataframe. pandas ONLY at three sanctioned vendor/library edges: the yfinance adapter/parser (`alpha_data.adapters.yfinance_adapter` — the vendor returns DataFrames), the tear-sheet renderer (`alpha_validation.tearsheet`, with `quantstats_lumi`), and the Kronos model facade (`alpha_forecast.kronos` — upstream API speaks DataFrames). `numpy`/`scipy.stats.norm` in the `alpha_validation` numeric layer; numpy/torch also live inside `alpha_forecast` internals (never at its public seam, which is plain floats/tuples).
- **Strong typing.** `mypy --strict` is a CI gate. Overrides (do not "fix"): `nautilus_trader.*`, `scipy.*`, `quantstats_lumi.*` are `ignore_missing_imports` (no loadable stubs); nautilus Cython base classes get `# type: ignore[misc]`.
- **Determinism (spec §11.4).** All seeds derive from `AlphaSettings.random_seed` (default 7); the gauntlet spawns independent child seeds via `np.random.SeedSequence(master).spawn(n)` so gate order can't change results. `run_id` = sha256 of canonical sorted-key JSON of the params (no wall-clock). Manifests are byte-stable (sorted keys, `allow_nan=False` → non-finite must already be `null`).
- **License posture.** ALPHA has no declared root project license. Do not infer or add one implicitly; distribution/publication remains gated on an explicit owner decision and exact dependency/notice review. See `docs/governance/2026-07-19-dependency-license-matrix.md`.
- **Corporate actions: two clocks.** Knowledge time (`announce_date` else `ex_date`) gates visibility; `ex_date` gates price application (a known-but-future split does NOT rescale prices yet). Splits adjust the price series; dividends are decoupled cash events **credited by the engine at `pay_date`** against the pre-ex holding (shorts debited; never folded into prices; threaded through every run path incl. Tier-2 nulls — Tier-1 stays price-only by design). Yahoo serves split-adjusted OHLCV, so the yfinance parser reconstructs RAW prices from in-window split events (fails loud if the vendor convention drifts). See spec §6.1.

## Commands
- Install: `uv sync`
- Full Python gate (run before every commit; mirrors CI `.github/workflows/ci.yml`):
  `uv lock --check && uv sync --locked && uv run ruff check . && uv run ruff format --check . && uv run lint-imports && uv run mypy packages apps tests && uv run pytest -q -m "not network" --cov --cov-report=term`
- Frontend gate: `cd apps/alpha-web/frontend && npm ci && npm run lint -- --deny-warnings && npm run test:coverage && npm run generate:api && npm run build` (generated contracts and `static/app` must stay clean after regeneration).
- Bias guards only: `uv run pytest -m bias_guard -q`
- Live-network tests (off by default, hit real APIs): `uv run pytest -m network -q`
- CLI smoke: `uv run alpha info`
- Ruff: line-length 100, target py312, rules `E,F,I,B,UP,SIM`. Markers (`--strict-markers` on): `bias_guard` (look-ahead/survivorship guards, gated in CI), `network` (skipped in CI/offline).

## CLI surface (`apps/alpha-cli/src/alpha_cli/`)
Entry point `alpha = alpha_cli.main:main`. `data`/`backtest`/`optim`/`paper`/`info`/`options`/`risk`/`screener`/`research` are Typer sub-apps; `validate`/`report` are root commands. Machine-readable projections (`--json`) back the Workstation SPA.
- `alpha info` — print resolved `AlphaSettings` + core version.
- `alpha info strategies [--json]` — registered strategies + tunable `--param` axes (from `_schemas.STRATEGY_PARAM_SCHEMA`) + `has_tier1_surrogate` + `supports_live_paper`.
- `alpha info commands [--json]` — the Typer→Click command tree (flags + defaults, introspected from the real signatures) for the SPA's dynamic new-run form.
- `alpha info providers [--json]` · `alpha info system [--json]` — redacted provider capabilities/configuration and local-only readiness (data-dir access/free space, counts, Nautilus pin, Kronos cache, paper opt-in); never probe the network.
- `alpha data pull SYMBOL --source {yfinance,ccxt,stooq} [--exchange coinbase|binance] --start --end` — fetch + store raw bars/actions; `--exchange` applies only to CCXT.
- `alpha data snapshot SNAPSHOT_ID SYMBOLS... [--source --exchange coinbase|binance]` — freeze store → immutable hashed snapshot; CCXT provenance is venue-qualified (`ccxt:coinbase|binance`).
- `alpha data verify SNAPSHOT_ID` — re-hash snapshot vs manifest.
- `alpha data candles SYMBOL [--start --end --snapshot --json]` — point-in-time OHLCV (split-adjusted; `--end` is an as-of cutoff, via `_runner.load_bars`'s `as_of`) for the SPA price chart; reads through the same look-ahead firewall a backtest uses (bias-guarded).
- `alpha data symbols [--json]` — every symbol with stored bars (the SPA symbol picker).
- `alpha options greeks SPOT STRIKE --vol [--days --rate --kind --json]` · `alpha options iv SPOT STRIKE --price [...]` · `alpha options curve STRIKE --vol [--width --points ...]` — Black-Scholes price/greeks/implied-vol (pure `alpha_options`; no store, no look-ahead surface).
- `alpha risk scenario --from-run RUN_ID [--confidence --periods-per-year --json]` — stress a stored run's realized return stream (vol-scaling + tail shocks) via `alpha_validation.scenario_metrics`; no engine re-run.
- `alpha screener quote SYMBOL [--json]` · `alpha screener news SYMBOL [--days --limit --json]` — finnhub quotes/news (opt-in; fails loud without `ALPHA_FINNHUB_API_KEY`).
- `alpha research compare SYMBOL [--strategies --json]` — backtest each registered strategy (kronos excluded — needs a cache) and rank by total return (the AI-desk "analyst lanes").
- `alpha backtest run SYMBOL [--strategy ts_momentum|ma_crossover|mean_reversion|breakout|kronos, --param name=value, --periods-per-year, --size-on-equity, --halt-drawdown F, ...params, snapshot]` — one fixed-param run → artifacts. Slash symbols (`BTC/USD`) dispatch to a 5-decimal crypto instrument and require `--account-type MARGIN`. `--size-on-equity` re-bases vol sizing on current net-liq; `--halt-drawdown F` is a flatten-for-good kill-switch at `peak×(1−F)` (both opt-in; REJECTED by `validate`/`optim` — Tier-1 can't model equity-path-dependent sizing). `kronos` params (floats): `context/horizon/samples/temperature/top_p/top_k/min_edge/band`; model selection via `ALPHA_FORECAST_*` env (never params); the CLI auto-precomputes the signal cache (`data_dir/forecasts/<key>`) before entering the engine.
- `alpha forecast run SYMBOL [--horizon 21 --samples 100 --context --model --device --as-of --seed]` — probabilistic outcome cone (sampled OHLCV paths + close quantiles) → `data_dir/forecast/<run_id>/{manifest.json, paths.parquet, quantiles.parquet, history.parquet}`. `--model fake` = offline test double. Pre-cutoff windows warn loud + set `pretrain.overlap` (ADR-0009).
- `alpha forecast eval SYMBOL [--horizon --stride --samples ...]` — rolling-origin forecast skill: CRPS/pinball/coverage/hit-rate vs RW-drift + stationary-bootstrap baselines, split pre/post `forecast_pretrain_cutoff`.
- `alpha backtest portfolio SYMBOLS... [--strategy, --weighting equal|inverse_vol, --seed, ...params]` — diversified basket (canonical sorted symbol order): per-symbol OOS streams combined (inverse-vol weights are CAUSAL — per-date trailing vol, never full-sample) → portfolio metrics + PSR + BCa CIs + manifest (`data_dir/portfolio/<run_id>`).
- `alpha backtest cross-sectional SYMBOLS... [--top-quantile, --no-long-short, --fee-bps, --slippage-bps, --seed, ...params]` — relative-strength book: rank the universe (canonical sorted order), long winners / short losers, vol-targeted, fee+slippage charged on rebalance turnover → OOS metrics + PSR + CIs + manifest (`data_dir/cross_sectional/<run_id>`).
- `alpha validate SYMBOL [--strategy, --param, ...params, train_size=504, test_size=63, embargo=5, tier1_paths=1000, tier2_paths=64, n_resamples=2000, mean_block=5.0, threshold=0.95, --null-model bootstrap|student_t|garch, tier1_divergence_tol=0.25, --tier2-mode replay|model (kronos only), periods_per_year=252, seed, max_workers, snapshot]` — full gauntlet → manifest + parquet + HTML tear sheet. NOTE: `train_size` must clear the strategy's warmup floor or it fails loud. `--allow-short` defaults by account: MARGIN→short-ok, CASH→long-flat; an explicit `--allow-short` on CASH fails loud (the venue denies short sells wholesale). `--snapshot` verifies + reads the frozen snapshot (not the live store). `run_id` excludes `max_workers` (execution-only). For `kronos`: Tier-1 + default Tier-2 REPLAY the observed signal cache (association test, flagged in `manifest["forecast"].tier2_policy`); `--tier2-mode model` re-forecasts every synthetic path (parent-process caches; ~tier2_paths × model cost).
- `alpha optim grid SYMBOL --grid name=v1,v2,... [--strategy, ...params, pbo_blocks, n_resamples, dsr_threshold, alpha, seed, max_workers]` — parameter sweep judged for overfitting (Deflated Sharpe + PBO + Reality-Check/SPA) → manifest (`data_dir/optim/<run_id>`).
- `alpha paper preflight BASE/USDT [--strategy --starting-cash --param]` — construct the public Binance-data + local Nautilus sandbox-execution configuration and the parity strategy offline, without connecting.
- `alpha paper run BASE/USDT --provider binance --snapshot SNAPSHOT_ID [--strategy --param ...]` — opt-in (`ALPHA_PAPER_ENABLED=true`) public Binance `LIVE` data + local sandbox orders only. Requires a fresh, verified, same-symbol `ccxt:binance` snapshot; rule strategies only (Kronos rejected). Never constructs Binance execution or accepts real-order credentials.
- `alpha paper sessions [--json]` · `alpha paper show SESSION_ID [--json]` — list/read durable operational sessions; reads never signal a recorded PID.
- `alpha propfirm run [SYMBOL] [--firm topstep|apex|takeprofit, --from-run RUN_ID, --account-size, --profit-target, --max-drawdown, --daily-loss, --profit-split, --min-trading-days, --n-paths, --mean-block, --horizon, seed, ...backtest params]` — prop-firm Monte Carlo: resample a strategy's daily return stream (fresh backtest of SYMBOL, or `--from-run`'s stored equity curve) and walk it through a firm's eval→funded→payout rules (return-scaled, EOD granularity) → pass/bust/payout probabilities + expected payout → manifest (`data_dir/propfirm/<run_id>`). Exactly one of SYMBOL / `--from-run`. Presets are illustrative, not authoritative firm terms.
- `alpha report RUN_ID` — re-display any stored run (runs/optim/portfolio/cross_sectional/propfirm/forecast) from its manifest (no engine re-run).
Artifacts: `data_dir/runs/<run_id>/{manifest.json, equity_curve.parquet, trades.parquet, nulls.parquet, tearsheet.html}` (only the manifest+parquet are byte-pinned; HTML carries volatile fields; `nulls.parquet` = per-tier null-path statistics). Optim runs add `trials.parquet` (trial×step OOS returns); propfirm runs add `propfirm_paths.parquet` (per-path passed/busted/days/payout); portfolio & cross-sectional runs add `equity_curve.parquet` (combined OOS stream, baseline 1.0). Every required sidecar is atomically published BEFORE the atomic manifest completion marker. Forecast runs: `data_dir/forecast/<run_id>/` (+ `paths/quantiles/history` or `origins` parquet). Kronos signal caches (NOT runs): `data_dir/forecasts/<key>/{meta.json, signals.parquet}` where `signals.parquet` is the completion gate. Operational paper sessions are deliberately outside `RUN_DIRS`: `data_dir/paper/<uuid>/session.json` + atomic low-volume `events/<sequence>.json` (ADR-0012).

## MODULE MAP

### `alpha_core` (`packages/alpha-core/src/alpha_core/`) — domain types, protocols, errors, config. Imports nothing internal.
| Module | Responsibility | Key public symbols |
|---|---|---|
| `types.py` | Frozen domain values | `Bar` (OHLCV; validates finite/positive/OHLC-consistent), `ValidationOutcome(name, passed, detail)` |
| `errors.py` | Typed error hierarchy | `AlphaError` ← `DataError`, `LookAheadError` |
| `protocols.py` | Structural interfaces | `DataSource` (`available_symbols`, `as_of`), `Validator`, `ExecutionEventSink` (flat low-volume operational events only) |
| `config.py` | Typed settings (env `ALPHA_*`/`.env`) | `AlphaSettings(data_dir=Path("data"), random_seed=7, paper_enabled=False)`; `forecast_hub_cache`/`forecast_local_only` = machine-local HF weight cache + no-network loading (never in run ids/manifests; ADR-0010) |
| `corporate.py` | Corporate-action types (two-clock) | `ActionType` (SPLIT/DIVIDEND/REDENOMINATION/SYMBOL_MIGRATION), `CorporateAction` (`knowledge_time`, `knowledge_is_estimated`) |

### `alpha_data` (`packages/alpha-data/src/alpha_data/`) — ingestion, PIT storage, snapshots.
| Module | Responsibility | Key public symbols |
|---|---|---|
| `store.py` | Raw unadjusted Parquet store (wholesale replace) + fail-closed per-symbol pull provenance | `ParquetStore(root)`: bars/actions methods + `write_provenance/read_provenance/clear_provenance` |
| `pit.py` | **Look-ahead firewall** (frame-level) | `PointInTimeReader.as_of` (split-adjusted, future-excluded), `.dividends_as_of` |
| `source.py` | Typed PIT `DataSource` seam | `PointInTimeSource.as_of` → `list[Bar]`, `.dividends_as_of` |
| `corporate.py` | Two-clock split/div math | `known_actions`, `cash_dividends`, `split_factor` |
| `snapshot.py` | Immutable hashed snapshots + manifest; copies/hashes pull-provenance sidecars and rejects source relabelling | `create_snapshot`, `verify_snapshot` |
| `ingest.py` | Persist a `FetchResult` | `store_fetch_result` |
| `adapters/base.py` | Adapter seam | `FetchResult(symbol, bars, actions)`, `DataAdapter` protocol |
| `adapters/yfinance_adapter.py` | Equities (splits+divs); reconstructs RAW prices from Yahoo's split-adjusted series, fail-loud discontinuity check | `YFinanceAdapter`, `parse_yfinance_history` (pure) |
| `adapters/ccxt_adapter.py` | Crypto daily OHLCV (UTC; validated `coinbase|binance`; **paginated** past per-call caps; venue-qualified provenance) | `SUPPORTED_CCXT_EXCHANGES`, `CCXTAdapter`, `parse_ccxt_ohlcv` (pure) |
| `adapters/stooq_adapter.py` | Free EOD OHLCV (FX/commodity/index/ETF; provider-adjusted, no actions). **Anti-bot gated:** browser-UA + SHA-256 PoW solve, then **fails loud** (`_csv_or_raise`) on Stooq's per-IP "Access denied" — yfinance is the reliable equity/ETF source | `StooqAdapter`, `parse_stooq_csv` (pure) |

### `alpha_strategies` (`packages/alpha-strategies/src/alpha_strategies/`) — nautilus Strategy + pure decision fns. core only.
| Module | Responsibility | Key public symbols |
|---|---|---|
| `signals.py` | Pure signals (all `{-1,0,1}`, trailing-window only) | `ts_momentum_signal`, `ma_crossover_signal(closes, fast, slow)`, `zscore_reversion_signal(closes, window, entry_z)`, `breakout_signal(highs, lows, closes, window)` |
| `sizing.py` | Pure vol-target sizing | `realized_volatility(closes, *, periods_per_year)`, `vol_target_size(signal, price, vol, *, target_vol, capital, max_leverage)` |
| `base.py` | Shared nautilus lifecycle for vol-targeted signals (+ opt-in `size_on_equity`, `halt_drawdown`; paper-only no-order priming + venue increment normalization) | `VolTargetStrategy` (`prime_history`; subclasses implement `_signal()`), `normalize_order_quantity` |
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
| `scenario.py` | Stress/what-if over a return stream (mean-preserving vol scaling + tail shocks; reuses `metrics`) | `scenario_metrics(returns, *, periods_per_year, confidence)`, `ScenarioSummary`, `scale_volatility`, `append_shock` |
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
| `kronos.py` | **torch/pandas edge**; lazy-loads the vendored model | `KronosForecaster(model_id, model_revision, tokenizer_id, tokenizer_revision, device, max_context, clip, cache_dir, local_files_only)` (local cache + offline: missing weights raise `DataError` before any HTTP; both knobs excluded from provenance), `.provenance()`, `VENDORED_KRONOS_SHA`. Upstream `predict(sample_count=S)` AVERAGES paths → facade uses `predict_batch` with S copies @ `sample_count=1` (chunk 32, per-chunk torch seeds). cpu = bit-exact; mps/cuda best-effort |
| `_vendor/kronos/` | Pinned upstream model code (@ `67b630e6`, MIT; ruff/mypy-excluded) | `Kronos`, `KronosTokenizer`, `KronosPredictor` — facade-only import |

### `alpha_options` (`packages/alpha-options/src/alpha_options/`) — options & derivatives analytics. core only (+ numpy/scipy).
| Module | Responsibility | Key public symbols |
|---|---|---|
| `black_scholes.py` | Pure European-option pricing/greeks/IV (no market data, no look-ahead surface) | `bs_price`, `bs_greeks` (vega/1pt, theta/day, rho/1%), `implied_vol`, `Greeks` |

### `alpha_screener` (`packages/alpha-screener/src/alpha_screener/`) — screener & news via finnhub (opt-in, API-key-gated). core only; the one network edge.
| Module | Responsibility | Key public symbols |
|---|---|---|
| `models.py` | Frozen response values | `Quote`, `NewsItem` |
| `parse.py` | Pure finnhub-response parsers (fail loud on malformed / unknown-symbol bodies) | `parse_quote`, `parse_news` |
| `finnhub.py` | The one network edge (lazy `import finnhub`; gated on `ALPHA_FINNHUB_API_KEY`) | `fetch_quote`, `fetch_news` |

### `alpha_cli` (`apps/alpha-cli/src/alpha_cli/`) — orchestration ONLY (allowed to compose engine + gauntlet). Engine imports are lazy. Package root exports `RUN_DIRS` (the run-type subdir tuple; polars-free so the MCP/web clients import it cheaply).
| Module | Responsibility | Key public symbols |
|---|---|---|
| `main.py` | Typer app wiring (mounts every sub-app) | `app`, `main` |
| `info_cmds.py` | `alpha info` (+ `strategies`/`commands`/`providers`/`system` JSON projections) | `info_app`; `_strategy_catalog`, `_command_catalog` (Typer→Click introspection) |
| `providers.py` · `system_status.py` | One redacted provider/capability/option registry + local-only readiness | `ProviderDefinition`, `provider_definitions`, `historical_adapter_factories`, `provider_catalog`; `system_status`, `PINNED_NAUTILUS_VERSION` |
| `data_cmds.py` | `alpha data ...` (incl. provider-derived adapters, CCXT exchange provenance, PIT candles + symbols) | `data_app`; `_ADAPTERS` registry (monkeypatched in tests) |
| `backtest_cmds.py` | `alpha backtest run` / `portfolio` | `backtest_app`; `_load_bars` seam |
| `validate_cmds.py` | `alpha validate` | `validate` |
| `optim_cmds.py` | `alpha optim grid` | `optim_app` |
| `paper_cmds.py` | `alpha paper preflight/run/sessions/show` (opt-in, Binance public data + sandbox orders only) | `paper_app` |
| `paper_store.py` | Public lightweight operational session/event journal, separate from deterministic runs | `PaperEventSink`, `create_session`, `append_event`, `heartbeat_session`, `finish_session`, `list_sessions`, `read_session`, `read_events` |
| `propfirm_cmds.py` | `alpha propfirm run` | `propfirm_app` |
| `options_cmds.py` | `alpha options greeks/iv/curve` (Black-Scholes `--json`) | `options_app` |
| `risk_cmds.py` | `alpha risk scenario --from-run` (stress a stored run) | `risk_app` |
| `screener_cmds.py` | `alpha screener quote/news` (finnhub, key-gated) | `screener_app` |
| `research_cmds.py` | `alpha research compare` (rank strategies; the AI desk's engine) | `research_app` |
| `report_cmds.py` | `alpha report` (all run types) | `report` |
| `_schemas.py` | Declarative strategy `--param` catalog (the one place naming knobs; mirrors `_strategies` defaults) for `info strategies --json` | `STRATEGY_PARAM_SCHEMA`, `ParamSpec` |
| `_strategies.py` | Strategy registry (dispatch + validation/live-paper metadata) | `STRATEGIES` (four rule strategies `supports_live_paper`; `kronos` cache replay rejected for paper), `build_strategy`, `warmup_for`, `surrogate_for`, `known_strategies` |
| `forecast_cmds.py` | `alpha forecast run` / `eval` | `forecast_app`; `--model fake` sentinel |
| `_forecast.py` | Forecast-run glue (PIT slice, pretrain overlap, artifacts) + forecaster factory/provenance | `run_forecast`, `write_forecast_run`, `pretrain_overlap`, `forecast_seed`, `FORECAST_SEED_NS` |
| `_forecast_eval.py` | Rolling-origin skill eval (stride-independent per-origin seeds, cutoff split) | `run_forecast_eval`, `origin_indices`, `ForecastEvalOutput` |
| `_forecast_cache.py` | Content-addressed kronos signal caches (`data_dir/forecasts/<key>`; schedule-exact, idempotent; model identity from settings) | `ensure_forecast_cache`, `prepare_spec_for_engine`, `signal_indices`, `cache_key`, `read_signals` |
| `_runner.py` | Engine↔gauntlet glue, OOS stitch, run id | `RunSpec` (`strategy_name`, `strategy_params`, `param()`), `load_bars` (opt `as_of` knowledge cutoff — `alpha data candles` passes `--end`), `load_dividends`, `parse_strategy_params`, `resolve_allow_short`, `run_full_backtest`, `walk_forward_oos`/`_for_spec`, `OOSResult`, `run_id_for` |
| `_gauntlet.py` | Full gauntlet assembly (+ DSR, CPCV, null-model) | `run_gauntlet`, `GauntletParams`, `GauntletOutput` |
| `_optim.py` | Parameter sweep + overfitting verdict | `run_optimization`, `expand_grid`, `OptimResult` |
| `_portfolio.py` | Diversified-basket backtest | `run_portfolio`, `PortfolioResult`, `LegSummary` |
| `_cross_sectional.py` | Cross-sectional momentum (returns-level panel) | `run_cross_sectional`, `CrossSectionalResult` |
| `_paper.py` | Phase-4 crypto paper composer: same-venue PIT warmup, public Binance data, local sandbox factory, graceful lifecycle | `binance_instrument_id`, `build_binance_data_config`, `load_paper_warmup`, `build_sandbox_exec_config`, `build_paper_node_config`, `run_paper` |
| `_propfirm.py` | Prop-firm run glue (resolve returns from fresh backtest / `--from-run`; resolve preset + overrides) | `run_propfirm`, `resolve_rules`, `PropFirmRunResult` |
| `_surrogate.py` | Tier-1 engine-free surrogates (weights exposed for the convention-divergence guard) | `Surrogate`, `make_surrogate` (generic), `make_ts_momentum_surrogate` |
| `_synth.py` | Tier-2 synthetic OHLCV paths + full-engine null | `synthetic_bar_paths`, `full_engine_null` (spawn pool, order-preserving, deterministic) |
| `_artifacts.py` | Run-dir layout + manifest/parquet IO | `run_dir`, `find_run_dir` (resolve a run by id across every `RUN_DIRS` subdir; 16-hex-guarded), `write_run`, `read_manifest`, `read_equity` |
| `catalog.py` · `run_store.py` | Lightweight supported seams for top-of-DAG surfaces (no numeric/engine imports) | strategy/command metadata; `RUN_DIRS`, run-ID validation, manifest discovery/read |

### `alpha_mcp` (`apps/alpha-mcp/src/alpha_mcp/`) — MCP server (top of DAG; subprocesses the `alpha` CLI, composes nothing). Launch: `uv run alpha-mcp` (repo `.mcp.json` auto-launches it in Claude Code).
| Module | Responsibility | Key public symbols |
|---|---|---|
| `server.py` | FastMCP instance + 12 tools + `main()` (stdio) | actions `data_pull`, backtest run/portfolio/cross-sectional, `validate`, `optim_grid`, forecast run/eval, `propfirm_run`; reads `get_run`, `list_runs`, `list_strategies` |
| `_invoke.py` | Subprocess core: run `alpha`, parse `-> run <id>`, read manifest (fail-loud on non-zero exit) | `run_alpha(args, *, data_dir, run_type)` |
| `_runs.py` | Filesystem reads over the run store | `get_run`, `list_runs` |

Tools take typed common knobs + an `options` dict mapping any CLI flag (`{"lookback":"5"}` → `--lookback 5`) and a `params` dict for strategy `--param name=value`. Adding/removing a CLI command? Update `server.py`'s tool surface to match.

### `alpha_web` (`apps/alpha-web/src/alpha_web/`) — the **ALPHA Workstation**: a thin JSON+SSE backend serving a built SPA (top of DAG; subprocesses CLI actions and status projections, composes nothing). Launch: `uv run alpha-web` → http://127.0.0.1:8800 (loopback only). Its only platform imports are `alpha_core.config` plus public lightweight CLI-owned catalog/run-store/paper-store seams; provider/system status comes from `alpha info … --json`, research reads come from manifests/artifacts, and paper monitoring reads the operational journal (never a direct `alpha_data`/engine import).
| Module | Responsibility | Key public symbols |
|---|---|---|
| `app.py` | FastAPI factory: mount `/api` routers, serve the SPA (catch-all), `/healthz`, `main()` (uvicorn) | `create_app`, `main` |
| `api/` | Thin JSON routers | `runs.py` (research artifacts), `jobs.py` (launch/list/detail/SSE/cancel + additive `session_id`), `activity.py`, `catalog.py` (strategies/commands/symbols), `control.py` (providers/system), `paper.py` (sessions/detail/events), `candles.py`, `options.py`, `risk.py`, `screener.py`, `research.py`, `workspaces.py` |
| `api/models.py` | Strict stable JSON response contracts; OpenAPI source | Pydantic models incl. `StrategyDefinition.supports_live_paper`, job `session_id`, `PaperSession`, `PaperEvent` |
| `_invoke.py` | Background job runner: spawn `alpha` (own process group), tail stdout, parse run/session ids, SSE `event_stream` w/ `Last-Event-ID` replay, killpg known child cancel | `Job`, `launch`, `event_stream`, `list_jobs`, `cancel_job`, `JOBS`, `RUN_TYPE` |
| `_activity.py` | **Live desk**: per-connection polling SSE diff of the run store + job registry (stat-only mtime scan; manifest read only on change) — runs launched ANYWHERE (UI/CLI/MCP) surface live | `activity_events`, `snapshot_runs`, `job_states`, `clamp_poll` |
| `_runs.py` | Filesystem reads over the run store (incl. `nulls.parquet`, `trials.parquet`, `propfirm_paths.parquet`, portfolio/xs `equity_curve.parquet`) | `query_runs`, `run_detail` (+ artifact flags), readable-completion checks, equity/trades/forecast/null/trial/propfirm/origin projections |
| `_catalog.py` · `_candles.py` | Subprocess `alpha … --json` (strategy/command/symbol/provider/system projections; PIT candles cached on parquet mtime) | `_run_json`; `strategies`, `commands`, `symbols`, `providers`, `system`; `candles` |
| `_options.py` · `_risk.py` · `_screener.py` · `_research.py` | Subprocess the matching `alpha` sub-command → `--json` for the SPA panels | `greeks`/`iv`/`curve`; `scenario`; `quote`/`news`; `compare` |
| `_workspaces.py` | Named Dockview-layout store (`data_dir/web/workspaces/<slug>.json`; traversal-guarded) | `save_workspace`, `load_workspace`, `list_workspaces` |
| `static/app/` | The **committed** built SPA assets (served offline; CI never runs Node) | — |
| `../frontend/` | SPA source (Vite + React + TS + Dockview + Lightweight Charts + uPlot + TanStack Table/Virtual + cmdk; self-hosted fontsource Inter/JetBrains Mono variable); excluded from ruff/mypy/pytest. Local ritual for frontend changes: `npm run lint -- --deny-warnings && npm run test:coverage && npm run generate:api && npm run build`; every step is a CI gate. | — |
| `../frontend/src/explain/` | The **explanation engine**: pure TS turning manifest numbers into dual-voice narratives (narrative/terse toggle) — gate stories, verdict band mirror (`bands.ts` ↔ `verdict.py`, drift-guarded by vitest fixtures of real manifests), rule-based next-step suggestions, metric glossary | `gateStories`, `verdictStories`, `suggestions`, `GLOSSARY`, `recomputeVerdict` |
| `../frontend/src/panels/ProviderSystem.tsx` · `PaperMonitor.tsx` | Provider/system readiness and durable sandbox monitoring (SANDBOX banner, stale heartbeat, position/event views, known-job cancel) | `ProviderSystem`, `PaperMonitor` |

Server = thin JSON+SSE orchestrator; all composition stays behind `alpha`. Actions plus provider/system and engine-backed projections subprocess `alpha`; research reads come from artifacts, and paper reads from the public operational journal. The real conversational path is `alpha_mcp`, not an in-app LLM (the AI Console panel points to it). OpenAPI, generated TypeScript, frontend coverage/lint/build, and committed `static/app` freshness are mandatory CI gates.

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
- **New data source** → `alpha_data/adapters/<name>_adapter.py`: a pure parser fn + a `DataAdapter` class (`name`/`version`/`parser_version`); add one evidence-gated `ProviderDefinition` so `data_cmds` derives it. Live-net code under `@pytest.mark.network`.
- **New validation gate / statistic** → `alpha_validation`: engine-agnostic primitive (numpy/scipy, fail-loud), then wire into `alpha_cli/_gauntlet.py` and extend `tearsheet.build_outcomes`/the report schema.
- **Anything composing engine + gauntlet / multi-package orchestration** → `alpha_cli` ONLY (the DAG forbids it elsewhere). Keep engine imports lazy.
- **New domain type / error / protocol / setting** → `alpha_core` (export via `__init__.py`).
- **New net-new analytics module** (e.g. options/screener) → a new core-only `packages/alpha-*` + its own import-linter "depends only on core" contract + an `alpha_cli/<x>_cmds.py` sub-app emitting `--json` (register in `main.py`).
- **New Workstation panel** → a manifest/artifact read and/or `alpha ... --json` projection + an `alpha_web/api/` router + a `frontend/src/panels/` component registered in `panels/registry.tsx`. Operational state needs a separately governed public seam (never `RUN_DIRS` by default). Then run the frontend gate and commit `static/app`.

## Build status
Phase 0 (rails) ✅ · Phase 1 (data spine) ✅ · Phase 2 (backtest core + strategy) ✅ · Phase 3 (validation gauntlet) ✅ · Phase 5 (tear sheet + CLI) ✅.
**Live data spine verified against real markets** ✅ (yfinance + ccxt/coinbase end-to-end; gauntlet correctly rejects single-name `ts_momentum` on AAPL and accepts a diversified basket. Stooq is anti-bot-gated → fails loud).
Phase 6 shipped scope — complete and professionally hardened: strategy registry + 3 more strategies ✅ · institutional gauntlet ✅ · overfitting-aware optimization ✅ · basket portfolio ✅ · returns-level cross-sectional momentum ✅ · Stooq adapter ✅ · prop-firm Monte Carlo ✅. Explicitly deferred product expansion: full-engine cross-sectional execution, FRED/non-OHLCV macro data, and model fine-tuning.
**2026-07 institutional audit** ✅ — 38 verified findings fixed on main (see `docs/audit/2026-07-05-institutional-audit.md`): yfinance raw-price reconstruction (PARSER_VERSION=2), allow-short-by-account fail-loud, honest two-tier nulls (+ convention-divergence guard), verified `--snapshot` reads, causal portfolio weights, dividend cash crediting at `pay_date`, opt-in `--size-on-equity`/`--halt-drawdown`, crypto instruments, web/MCP hardening, schema-v2 manifests.
Kronos foundation-model track (spec `docs/superpowers/specs/2026-07-04-kronos-forecast-integration-design.md`, ADRs 0008/0009/0010) — COMPLETE, landed on main via the 2026-07 cleanup: `alpha_forecast` package (vendored pinned model @ `67b630e6`, typed facade, FakeForecaster, torch-cpu CI index) ✅ · `alpha forecast run` (outcome cones, leakage warn, MCP) ✅ · web fan chart ✅ · `alpha forecast eval` (CRPS/coverage vs RW+bootstrap baselines, pre/post-cutoff split) ✅ · `kronos` strategy via content-addressed signal caches through backtest/validate/optim (+ `--tier2-mode replay|model`) ✅ · fully-local weights: Kronos-base (largest released; Kronos-large is closed) cached at `data/models`, hash-pinned + offline-loaded via `.env` (`ALPHA_FORECAST_HUB_CACHE`/`_LOCAL_ONLY`, ADR-0010) ✅. Deferred: kronos through portfolio/propfirm-fresh paths (build fails loud with guidance), tearsheet caveat note, fine-tuning (zero-shot only per spec).
Phase 4 (paper trading) — **offline deterministic implementation complete** (2026-07-19): provider/system control plane; CCXT Binance provenance; `ALPHA_PAPER_ENABLED=false` opt-in; verified fresh same-venue snapshot warmup with no-order `prime_history`; four rule strategies; public Binance `LIVE` data factory + local Nautilus sandbox execution factory only; graceful node disposal; venue-increment quantity normalization; durable atomic session/event journal outside `RUN_DIRS`; CLI/API monitoring and Workstation Provider/System + Paper Monitor panels. No Binance execution client or real-order credential surface exists. Pending operational acceptance: opt-in `network` connection/quote smoke and one reviewed UTC-rollover sandbox soak; real/testnet execution and Kronos live cache remain out of scope.
QuantPad-parity track (separate from the internal phase numbers above): A–F Verdict + tail-risk ✅ · prop-firm Monte Carlo ✅ · conversational agent = MCP server (`alpha_mcp`, subprocesses the CLI; `uv run alpha-mcp` / repo `.mcp.json`) ✅ · local web IDE (`alpha_web`; now the Workstation SPA) ✅. All four QuantPad-parity surfaces shipped.
**ALPHA Workstation** ✅ (spec `docs/superpowers/specs/2026-07-16-alpha-workstation-design.md`) — a Bloomberg/OpenBB-class single-user terminal unifying every capability behind one dark, dockable SPA. `alpha_web` evolved from the Jinja IDE into a thin FastAPI JSON+SSE backend serving a built Vite/React/Dockview app (run browser, run detail w/ verdict+equity+trades+forecast cone+tearsheet, strategy lab w/ live console, price chart, data explorer, command palette, savable workspaces). New CLI `--json` projections (`info strategies/commands`, `data candles/symbols`) + four net-new modules: **options** (`alpha_options` Black-Scholes), **screener/news** (`alpha_screener` finnhub, key-gated), **risk/scenario** (`alpha_validation.scenario`), **AI research desk** (`alpha research compare` over the MCP path). SPA source under `apps/alpha-web/frontend`; built assets are committed and CI verifies frontend lint, coverage, generated types, build, and asset freshness.
**Workstation v2 — the real trading terminal** ✅ (2026-07-18) — the 10x pass: **live desk** (`/api/activity/stream` SSE store/job diffs; Activity Feed + Job Monitor panels, toasts, live Run Browser — Claude-launched CLI/MCP runs surface without reload) · **explanation engine** (`frontend/src/explain/`: dual-voice gate/verdict narratives drift-guarded against `verdict.py`, next-step suggestions, 27-term glossary + Term tooltips + Glossary panel) · **run story** (tabbed kind-aware Run Detail: gates w/ null histograms + CI bar, fold-shaded synced equity/drawdown w/ trade markers, optim param heatmap + per-trial curves, propfirm funnel + outcome histograms, forecast 50/90% fan + spaghetti, forecast-eval CRPS-per-origin) · **shell v2** (working SYM/ASOF, palette v2 w/ symbol/run/action/workspace pages, density + narrative/terse toggles, first-run desk preset, `#run=` deep links, per-panel error boundaries, self-hosted fonts, full A–F verdict colors) · **Pipeline panel** (guided loop w/ prefilled next steps) · TanStack sortable/virtualized blotters · Phase-6 deterministic artifacts (nulls/trials/propfirm-paths/portfolio-equity parquet) + typed projections serving them. Frontend vitest (node-env, local-only) guards the band mirror.
