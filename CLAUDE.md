# Project ALPHA — Agent Operating Manual

$0/free, institutional-grade Python quant research platform. **Written and operated entirely by AI agents.** This file is authoritative and OVERRIDES default behavior. Be terse, fail loud, never violate the architecture DAG.

- Spec: `docs/superpowers/specs/2026-06-14-project-alpha-v1-design.md`
- Research: `research/00-SYNTHESIS.md` (+ `research/01..07-*.md`)
- Phase plans: `docs/superpowers/plans/2026-*.md`
- Python 3.12, `uv` virtual workspace (root is not a package). Members: `packages/*`, `apps/*`.

## Architecture DAG (import-linter enforced — NEVER violate)
`alpha_core` ← `alpha_data` ← `alpha_backtest`; `alpha_strategies`, `alpha_validation`, `alpha_forecast`, `alpha_options`, `alpha_screener` ← `alpha_core`; `alpha_cli` ← everything; `alpha_mcp`, `alpha_web` ← `alpha_cli` (top of DAG).
- `alpha_core` imports nothing internal.
- `alpha_data` → core only. `alpha_strategies` → core only. `alpha_validation` → core only. `alpha_forecast` → core only. `alpha_options` → core only. `alpha_screener` → core only. `alpha_backtest` → core + data only.
- `alpha_cli` is the ONLY layer allowed to compose the backtest engine with the validation gauntlet (and to inject `alpha_forecast` forecasters into strategies via the core `BarForecaster` protocol).
- `alpha_mcp` and `alpha_web` sit atop the DAG and compose nothing — they subprocess the `alpha` CLI; nothing imports them.
- Contracts live in root `pyproject.toml` `[tool.importlinter]` (10 forbidden contracts). Run `uv run lint-imports` after any cross-package import change.

## Golden rules (invariants)
- **TDD.** Failing test → minimal code → green → commit. Small, atomic, conventional commits (`feat(scope):`, `fix(...)`, `test(...)`, `build(...)`, `chore(...)`, `refactor(...)`, `ci:`, `docs:`).
- **No look-ahead, ever.** Strategies/backtests read data ONLY via the point-in-time accessor `as_of`. Every data/strategy unit gets a `@pytest.mark.bias_guard` future-poison test (see `tests/bias_guards/`).
- **Execution convention:** decide on close of bar `t`, fill at open of `t+1`. Mechanism: `feed.to_execution_feed` emits an open-priced `QuoteTick` (at `bar.ts`) + a close-stamped (+23h) decision `Bar`; venue runs `bar_execution=False` so only quotes fill.
- **No empty `except`.** Raise/propagate typed `AlphaError`/`DataError`/`LookAheadError` with context, or re-raise. Fail loud on data gaps / NaN / inf / disorder / degenerate stats.
- **Polars** is the default dataframe. pandas + `quantstats_lumi` ONLY at the tear-sheet rendering edge (`alpha_validation.tearsheet`); pandas + torch ONLY at the vendored-Kronos edge (`alpha_forecast`, the second sanctioned pandas edge). `numpy`/`scipy.stats.norm` only in the `alpha_validation` numeric layer.
- **Kronos weight-level look-ahead.** Kronos pretrained weights saw market data up to ~2025-08; accessor-level PIT guards cannot catch that. Any `kronos_forecast` run whose window starts earlier echoes a loud warning + records `leakage_warning` in the manifest — treat such verdicts as UPPER BOUNDS, never edge evidence.
- **Strong typing.** `mypy --strict` is a CI gate. Overrides (do not "fix"): `nautilus_trader.*`, `scipy.*`, `quantstats_lumi.*` are `ignore_missing_imports` (no loadable stubs); nautilus Cython base classes get `# type: ignore[misc]`.
- **Determinism (spec §11.4).** All seeds derive from `AlphaSettings.random_seed` (default 7); the gauntlet spawns independent child seeds via `np.random.SeedSequence(master).spawn(n)` so gate order can't change results. `run_id` = sha256 of canonical sorted-key JSON of the params (no wall-clock). Manifests are byte-stable (sorted keys, `allow_nan=False` → non-finite must already be `null`).
- **Corporate actions: two clocks.** Knowledge time (`announce_date` else `ex_date`) gates visibility; `ex_date` gates price application. Splits adjust the price series; dividends are decoupled cash events credited at `pay_date` (never folded into prices). See spec §6.1.

## Commands
- Install: `uv sync` (torch-free). Kronos torch stack (opt-in; heavy CUDA wheels on Linux, small on macOS): `uv sync --group kronos` — without it, torch-requiring tests skip visibly and real Kronos inference fails loud with instructions.
- Full gate (run before every commit; mirrors CI `.github/workflows/ci.yml`):
  `uv run ruff check . && uv run ruff format --check . && uv run lint-imports && uv run mypy packages apps tests && uv run pytest -q -m "not network" && uv run pytest -q -m bias_guard`
- Bias guards only: `uv run pytest -m bias_guard -q` (also a dedicated CI step, so the guard suite can never silently select zero tests)
- Live-network tests (off by default, hit real APIs): `uv run pytest -m network -q`
- CLI smoke: `uv run alpha info`
- Ruff: line-length 100, target py312, rules `E,F,I,B,UP,SIM`. Markers (`--strict-markers` on): `bias_guard` (look-ahead/survivorship guards, gated in CI), `network` (skipped in CI/offline).

## CLI surface (`apps/alpha-cli/src/alpha_cli/`)
Entry point `alpha = alpha_cli.main:main`. `data`/`backtest`/`optim`/`paper` are Typer sub-apps; `validate`/`report` are root commands.
- `alpha info` — print resolved `AlphaSettings` + core version. Subcommands `alpha info strategies [--json]` / `alpha info commands [--json]` emit machine-readable catalogs (strategy `--param` axes; the Typer command tree with defaults) that the Workstation forms consume.
- `alpha data pull SYMBOL --source {yfinance,ccxt,stooq} --start --end` — fetch + store raw bars/actions.
- `alpha data snapshot SNAPSHOT_ID SYMBOLS... [--source]` — freeze store → immutable hashed snapshot.
- `alpha data verify SNAPSHOT_ID` — re-hash snapshot vs manifest.
- `alpha data candles SYMBOL [--start --end --snapshot] [--json]` — point-in-time-adjusted OHLCV via `load_bars` (`--end` is an as-of cutoff; bias-guarded). Powers the Workstation price chart.
- `alpha data symbols [--json]` — list symbols with stored bars.
- `alpha backtest run SYMBOL [--strategy ts_momentum|ma_crossover|mean_reversion|breakout|kronos_forecast, --param name=value, ...params, snapshot]` — one fixed-param run → artifacts.
- `alpha backtest portfolio SYMBOLS... [--strategy, --weighting equal|inverse_vol, ...params]` — diversified basket: per-symbol OOS streams combined → portfolio metrics + PSR + BCa CIs + manifest (`data_dir/portfolio/<run_id>`).
- `alpha backtest cross-sectional SYMBOLS... [--top-quantile, --no-long-short, ...params]` — relative-strength book: rank the universe, long winners / short losers, vol-targeted → OOS metrics + PSR + CIs + manifest (`data_dir/cross_sectional/<run_id>`).
- `alpha validate SYMBOL [--strategy, --param, ...params, train_size=504, test_size=63, embargo=5, tier1_paths=1000, tier2_paths=64, n_resamples=2000, mean_block=5.0, threshold=0.95, --null-model bootstrap|student_t|garch, seed, max_workers, snapshot]` — full gauntlet → manifest + parquet + HTML tear sheet. NOTE: `train_size` must clear the strategy's warmup floor or it fails loud.
- `alpha optim grid SYMBOL --grid name=v1,v2,... [--strategy, ...params, pbo_blocks, n_resamples, dsr_threshold, alpha, seed, max_workers]` — parameter sweep judged for overfitting (Deflated Sharpe + PBO + Reality-Check/SPA) → manifest (`data_dir/optim/<run_id>`).
- `alpha paper preflight SYMBOL [--strategy, --venue, --account-type, --starting-cash, --currency, --param]` — validate the Phase-4 paper wiring offline: build the sandbox exec + node configs + the parity strategy; reports the remaining live-data-adapter step.
- `alpha forecast pull [--model base|small|mini]` — download Kronos weights+tokenizer from Hugging Face into `weights_dir` (`ALPHA_WEIGHTS_DIR`, default `data_dir/models`); the ONLY network path of alpha_forecast.
- `alpha forecast run SYMBOL [--model base|small|mini, --horizon 30, --context 400, --temperature, --top-p, --sample-count, --seed, --snapshot, --start/--end]` — Kronos next-N-bars OHLCV forecast from the trailing context window → `data_dir/forecast/<run_id>/{manifest.json, forecast.parquet, history.parquet}` + web chart (solid history, dashed forecast, p10/p90 band). Loud `leakage_warning` on pre-2025-08 windows.
- `alpha propfirm run [SYMBOL] [--firm topstep|apex|takeprofit, --from-run RUN_ID, --account-size, --profit-target, --max-drawdown, --daily-loss, --profit-split, --min-trading-days, --n-paths, --mean-block, --horizon, seed, ...backtest params]` — prop-firm Monte Carlo: resample a strategy's daily return stream (fresh backtest of SYMBOL, or `--from-run`'s stored equity curve) and walk it through a firm's eval→funded→payout rules (return-scaled, EOD granularity) → pass/bust/payout probabilities + expected payout → manifest (`data_dir/propfirm/<run_id>`). Exactly one of SYMBOL / `--from-run`. Presets are illustrative, not authoritative firm terms.
- `alpha options greeks SPOT STRIKE --vol --days --rate --kind {call,put} [--json]` / `alpha options iv SPOT STRIKE --price ... [--json]` / `alpha options curve STRIKE --vol ... [--width --points] [--json]` — Black-Scholes price + greeks / implied volatility / greeks-vs-spot curve (pure calculators; no store, no run artifacts). Powers the Workstation Options panel.
- `alpha risk scenario --from-run RUN_ID [--confidence --periods-per-year] [--json]` — re-evaluate a stored run's risk (Sharpe/vol/drawdown/VaR/CVaR) under mean-preserving vol-scaling + tail-shock scenarios (reads the run's equity curve; no engine re-run). Powers the Workstation Risk panel.
- `alpha screener quote SYMBOL [--json]` / `alpha screener news SYMBOL [--days --limit] [--json]` — finnhub quotes & company news. **Opt-in, key-gated:** set `ALPHA_FINNHUB_API_KEY` (free at finnhub.io); without it, fails loud with instructions (the minimal key handling a keyed provider requires). Powers the Workstation Screener panel.
- `alpha report RUN_ID` — re-display any stored run (runs/optim/portfolio/cross_sectional/propfirm/forecast) from its manifest (no engine re-run).
Artifacts: `data_dir/runs/<run_id>/{manifest.json, equity_curve.parquet, trades.parquet, tearsheet.html}` (only the manifest+parquet are byte-pinned; HTML carries volatile fields).

## MODULE MAP

### `alpha_core` (`packages/alpha-core/src/alpha_core/`) — domain types, protocols, errors, config. Imports nothing internal.
| Module | Responsibility | Key public symbols |
|---|---|---|
| `types.py` | Frozen domain values | `Bar` (OHLCV; validates finite/positive/OHLC-consistent), `ValidationOutcome(name, passed, detail)` |
| `errors.py` | Typed error hierarchy | `AlphaError` ← `DataError`, `LookAheadError` |
| `protocols.py` | Structural interfaces | `DataSource` (`available_symbols`, `as_of`), `Validator`, `BarForecaster` (`forecast(bars, horizon) -> list[Bar]`) |
| `config.py` | Typed settings (env `ALPHA_*`/`.env`) | `AlphaSettings(data_dir=Path("data"), random_seed=7, weights_dir=None)` (`resolved_weights_dir` → `data_dir/models`) |
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
| `adapters/yfinance_adapter.py` | Equities (splits+divs) | `YFinanceAdapter`, `parse_yfinance_history` (pure) |
| `adapters/ccxt_adapter.py` | Crypto daily OHLCV (UTC; default exchange `coinbase`; **paginated** past coinbase's 300-candle/call cap via `_paginate_ohlcv`) | `CCXTAdapter`, `parse_ccxt_ohlcv` (pure) |
| `adapters/stooq_adapter.py` | Free EOD OHLCV (FX/commodity/index/ETF; provider-adjusted, no actions). **Anti-bot gated:** browser-UA + SHA-256 PoW solve, then **fails loud** (`_csv_or_raise`) on Stooq's per-IP "Access denied" — yfinance is the reliable equity/ETF source | `StooqAdapter`, `parse_stooq_csv` (pure) |

### `alpha_strategies` (`packages/alpha-strategies/src/alpha_strategies/`) — nautilus Strategy + pure decision fns. core only.
| Module | Responsibility | Key public symbols |
|---|---|---|
| `signals.py` | Pure signals (all `{-1,0,1}`, trailing-window only) | `ts_momentum_signal`, `ma_crossover_signal(closes, fast, slow)`, `zscore_reversion_signal(closes, window, entry_z)`, `breakout_signal(highs, lows, closes, window)` |
| `sizing.py` | Pure vol-target sizing | `realized_volatility(closes, *, periods_per_year)`, `vol_target_size(signal, price, vol, *, target_vol, capital, max_leverage)` |
| `base.py` | Shared nautilus lifecycle for vol-targeted signals | `VolTargetStrategy` (decide close-t / fill open-t+1; subclasses implement `_signal()`) |
| `ts_momentum.py` | TS-momentum (standalone reference impl) | `TimeSeriesMomentum(Strategy)` |
| `ma_crossover.py` · `mean_reversion.py` · `breakout.py` | `VolTargetStrategy` subclasses | `MovingAverageCrossover`, `MeanReversion`, `DonchianBreakout` |
| `kronos_forecast.py` | Forecaster-driven strategy (torch-free: the `BarForecaster` is constructor-injected by the CLI) | `KronosForecast(VolTargetStrategy)`; pure mapping `signals.forecast_signal(last_close, forecast_closes, deadband_bps)` |

### `alpha_backtest` (`packages/alpha-backtest/src/alpha_backtest/`) — nautilus run harness. core + data only.
| Module | Responsibility | Key public symbols |
|---|---|---|
| `feed.py` | Bar → nautilus feed (t+1-fill encoding) | `to_execution_feed(bars, bar_type, *, slippage_bps=...)`, `daily_bar_type(symbol, venue="SIM")` |
| `engine.py` | `BacktestEngine` harness (`bar_execution=False`) | `run_backtest(instrument, data, strategy, *, starting_cash, account_type, leverage, fee_bps)` → `BacktestResult` |
| `instruments.py` | Per-asset instruments | `equity_instrument(symbol, venue="SIM")` |
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
| `reality_check.py` | White's Reality Check + Hansen's SPA | `reality_check`, `spa_test`, `DataSnoopingResult` |
| `scenario.py` | Stress/what-if over a return stream (mean-preserving vol scaling + tail shocks; reuses the metric primitives) | `scenario_metrics`, `ScenarioSummary` |
| `tearsheet.py` | Report schema + render (pandas/quantstats edge) | `GauntletReport`, `RunMetadata`, `FoldSummary`, `NullSummary`, `CISummary`, `DSRSummary`, `CPCVSummary`, `build_outcomes`, `report_to_manifest`, `render_tearsheet_html` |

### `alpha_forecast` (`packages/alpha-forecast/src/alpha_forecast/`) — Kronos foundation-model forecasting. core only; torch/pandas lazy (opt-in `uv sync --group kronos`); second sanctioned pandas edge.
| Module | Responsibility | Key public symbols |
|---|---|---|
| `models.py` | Model registry + pure helpers (no torch) | `ModelSpec`, `MODEL_SPECS` (mini 4.1M/ctx 2048, small 24.7M/512, base 102.3M/512), `resolve_model`, `future_timestamps` (weekday-aware), `KRONOS_TRAINING_CUTOFF` (2025-08-01), `training_overlap_warning` |
| `forecaster.py` | `BarForecaster` impl: lazy torch, `from_pretrained(local_files_only=True)`, per-window seeding from `random_seed` + window sha (call-order independent; CPU-deterministic per torch build), `sample_count>1` → mean path + close p10/p90 band, fail-loud sanitation (never clamps a broken forecast) | `KronosForecaster`, `ForecastResult(path, close_p10, close_p90)` |
| `cache.py` | Content-addressed forecast cache (`data_dir/forecast_cache/<sha256>.parquet`; key excludes signal params so optim sweeps reuse forecasts; no eviction — delete the dir to reset) | `cache_key`, `load` (corrupt → `DataError`), `store` |
| `download.py` | The ONLY network module: HF snapshot + offline verification load | `pull_model` |
| `_vendor/kronos/` | Vendored upstream model code (MIT; one relative-import patch; excluded from ruff/mypy; see `_vendor/README.md` for provenance) | `Kronos`, `KronosTokenizer`, `KronosPredictor` |

### `alpha_options` (`packages/alpha-options/src/alpha_options/`) — options & derivatives analytics (Black-Scholes). core only (+ numpy/scipy); pure, fail-loud.
| Module | Responsibility | Key public symbols |
|---|---|---|
| `black_scholes.py` | BSM European pricing / greeks / implied vol (vega per 1 vol point, theta per day, rho per 1%); fail-loud on non-finite/non-positive inputs or below-intrinsic price | `bs_price`, `bs_greeks`, `implied_vol`, `Greeks` |

### `alpha_screener` (`packages/alpha-screener/src/alpha_screener/`) — screener & news via finnhub (opt-in, API-key-gated). core only.
| Module | Responsibility | Key public symbols |
|---|---|---|
| `models.py` · `parse.py` | Typed `Quote`/`NewsItem` + pure finnhub-dict parsers (offline-testable, fail-loud) | `Quote`, `NewsItem`, `parse_quote`, `parse_news` |
| `finnhub.py` | The one network edge: lazy finnhub client gated on `ALPHA_FINNHUB_API_KEY` (fail-loud with setup instructions when absent) | `fetch_quote`, `fetch_news` |

### `alpha_cli` (`apps/alpha-cli/src/alpha_cli/`) — orchestration ONLY (allowed to compose engine + gauntlet). Engine imports are lazy.
| Module | Responsibility | Key public symbols |
|---|---|---|
| `main.py` | Typer app wiring | `app`, `main` |
| `data_cmds.py` | `alpha data ...` (pull/snapshot/verify/**candles**/**symbols**) | `data_app`; `_ADAPTERS` registry (monkeypatched in tests) |
| `info_cmds.py` | `alpha info` (settings) + `info strategies`/`info commands` `--json` catalogs (Typer→Click introspection) for the workstation forms | `info_app` |
| `options_cmds.py` | `alpha options greeks/iv/curve` — Black-Scholes `--json` projections (composes `alpha_options`) | `options_app` |
| `risk_cmds.py` | `alpha risk scenario --from-run` — stress a stored run's returns (composes `read_equity` + `alpha_validation.scenario_metrics`) | `risk_app` |
| `screener_cmds.py` | `alpha screener quote/news` — finnhub quotes & news (composes `alpha_screener`; fail-loud without a key) | `screener_app` |
| `_schemas.py` | Declarative strategy `--param` axes (names/defaults/ranges) mirrored from `_strategies` | `STRATEGY_PARAM_SCHEMA`, `ParamSpec` |
| `backtest_cmds.py` | `alpha backtest run` / `portfolio` | `backtest_app`; `_load_bars` seam |
| `validate_cmds.py` | `alpha validate` | `validate` |
| `optim_cmds.py` | `alpha optim grid` | `optim_app` |
| `paper_cmds.py` | `alpha paper preflight` | `paper_app` |
| `propfirm_cmds.py` | `alpha propfirm run` | `propfirm_app` |
| `forecast_cmds.py` | `alpha forecast pull/run` (+ `_FORECASTER_FACTORY` test seam) | `forecast_app` |
| `report_cmds.py` | `alpha report` (all run types) | `report` |
| `_strategies.py` | Strategy registry (dispatch by `strategy_name`; `kronos_forecast` params ride `--param model=0|1|2` (mini/small/base, default 2=base), `context`, `horizon`, `deadband`, `temperature`, `top_p`, `sample_count`; `_KRONOS_FACTORY` test seam) | `STRATEGIES`, `build_strategy`, `warmup_for`, `surrogate_for` (`None` surrogate → Tier-1 skipped-with-reason), `has_tier1_surrogate`, `pre_run_warnings`, `known_strategies` |
| `_runner.py` | Engine↔gauntlet glue, OOS stitch, run id | `RunSpec` (`strategy_name`, `strategy_params`, `param()`), `load_bars`, `parse_strategy_params`, `run_full_backtest`, `walk_forward_oos`/`_for_spec`, `OOSResult`, `run_id_for` |
| `_gauntlet.py` | Full gauntlet assembly (+ DSR, CPCV, null-model) | `run_gauntlet`, `GauntletParams`, `GauntletOutput` |
| `_optim.py` | Parameter sweep + overfitting verdict | `run_optimization`, `expand_grid`, `OptimResult` |
| `_portfolio.py` | Diversified-basket backtest | `run_portfolio`, `PortfolioResult`, `LegSummary` |
| `_cross_sectional.py` | Cross-sectional momentum (returns-level panel) | `run_cross_sectional`, `CrossSectionalResult` |
| `_paper.py` | Phase-4 paper scaffold (sandbox exec + parity) | `build_sandbox_exec_config`, `build_paper_node_config`, `run_paper` (live run network-gated) |
| `_propfirm.py` | Prop-firm run glue (resolve returns from fresh backtest / `--from-run`; resolve preset + overrides) | `run_propfirm`, `resolve_rules`, `PropFirmRunResult` |
| `_surrogate.py` | Tier-1 engine-free surrogates | `make_surrogate` (generic), `make_ts_momentum_surrogate` |
| `_synth.py` | Tier-2 synthetic OHLCV paths + full-engine null | `synthetic_bar_paths`, `full_engine_null` (spawn pool, order-preserving, deterministic) |
| `_artifacts.py` | Run-dir layout + manifest/parquet IO: `run_dir(..., kind=...)` validates against the `alpha_cli.RUN_DIRS` registry (registry lives at the package root, polars-free, so web/mcp import it cheaply); `write_manifest` is the single byte-stable manifest writer | `run_dir`, `write_manifest`, `write_run`, `read_manifest`, `read_equity` (+ root `RUN_DIRS`) |

### `alpha_mcp` (`apps/alpha-mcp/src/alpha_mcp/`) — MCP server (top of DAG; subprocesses the `alpha` CLI, composes nothing). Launch: `uv run alpha-mcp` (repo `.mcp.json` auto-launches it in Claude Code).
| Module | Responsibility | Key public symbols |
|---|---|---|
| `server.py` | FastMCP instance + 11 tools + `main()` (stdio) | `mcp`, `main`; action tools `data_pull`/`backtest_run`/`backtest_portfolio`/`backtest_cross_sectional`/`validate`/`optim_grid`/`propfirm_run`/`forecast_run`; read tools `get_run`/`list_runs`/`list_strategies` |
| `_invoke.py` | Subprocess core: run `alpha`, parse `-> run <id>`, read manifest (fail-loud on non-zero exit) | `run_alpha(args, *, data_dir, run_type)` |
| `_runs.py` | Filesystem reads over the run store | `get_run`, `list_runs` |

Tools take typed common knobs + an `options` dict mapping any CLI flag (`{"lookback":"5"}` → `--lookback 5`) and a `params` dict for strategy `--param name=value`. Adding/removing a CLI command? Update `server.py`'s tool surface to match.

### `alpha_web` (`apps/alpha-web/`) — the **Workstation**: a dockable research terminal (top of DAG; subprocesses the `alpha` CLI). Launch: `uv run alpha-web` → http://127.0.0.1:8800 (loopback only). A thin FastAPI JSON+SSE backend serves a built **Vite/React/Dockview SPA** (`frontend/` → committed assets in `static/app`); the engine never runs in-process.
| Module | Responsibility | Key public symbols |
|---|---|---|
| `app.py` | FastAPI factory: mount `/api` routers + serve the SPA at `/` and `/app` (assets via `/static`) + `main()` (uvicorn) | `create_app`, `main` |
| `api/runs.py` | Run store as JSON | `/api/runs` (filter/paginate, mtime-desc), `/api/runs/{id}` (+ `/equity` `/trades` `/forecast` `/tearsheet`) |
| `api/jobs.py` | Job lifecycle | `POST /api/jobs` · `GET /api/jobs[/{id}]` · `GET /api/jobs/{id}/stream` (SSE, `Last-Event-ID` replay) · `DELETE /api/jobs/{id}` (cancel) |
| `api/catalog.py` · `api/candles.py` · `api/manifest.py` · `api/workspaces.py` · `api/options.py` · `api/risk.py` · `api/screener.py` | JSON projections | `/api/{strategies,commands,symbols}` · `/api/candles/{symbol}` · `/api/apps` (panel manifest) · `/api/workspaces` · `/api/options/{greeks,iv,curve}` · `/api/risk/scenario` · `/api/screener/{quote,news}` |
| `_invoke.py` | Background job runner: spawn `alpha` (own process group), tail stdout, parse run id, SSE `event_stream` w/ replay + `cancel` | `Job`, `launch`, `event_stream`, `list_jobs`, `cancel_job`, `JOBS`, `RUN_TYPE` |
| `_runs.py` | Filesystem reads | `query_runs`, `run_detail`, `equity_series`, `trades`, `forecast_series`, `tearsheet_file` |
| `_catalog.py` · `_candles.py` · `_workspaces.py` · `_options.py` · `_risk.py` · `_screener.py` | subprocess the CLI's `--json` projections · catalogs · PIT candles (cached) · layout store · Black-Scholes · run stress scenarios · finnhub quotes/news | `strategies`/`commands`/`symbols` · `candles` · `…_workspace` · `greeks`/`iv`/`curve` · `scenario` · `quote`/`news` |
| `frontend/` | SPA source (Vite/React/TS): Dockview shell, cmdk palette, linked symbol/date/run context, panels (Run Browser, Run Detail, Strategy Lab, Price, Data Explorer, Options, Risk, Screener, AI Console, Workspaces), charts (Lightweight Charts + uPlot) | built to `static/app` (committed) |

The SPA composes nothing — every action is `POST /api/jobs` (subprocess `alpha`) streamed over SSE; reads come from the manifests. The **frontend** is excluded from the Python gate (ruff/mypy/pytest) and its built assets are committed, so CI needs no Node (see README). The real conversational path is `alpha_mcp` (the AI Console links to it), not an in-app LLM.

## Validation gauntlet gates (spec §8) — produced by `build_outcomes` → `ValidationOutcome`s
- `walk_forward_oos` (gate 2): passes on a finite OOS Sharpe. OOS = concatenated contiguous test windows of ONE full-series run (fixed params → no refit; train windows are warmup only).
- `randomized_price_null` (gate 3, headline): two tiers — Tier 1 `returns_level` (surrogate on resampled returns; `--null-model` selects bootstrap/student_t/garch) + Tier 2 `full_engine` (real engine on synthetic OHLCV paths). Passes only if observed beats the `threshold` percentile in **every tier that ran** and ≥1 tier ran (conservative). A strategy with no engine-free surrogate (`kronos_forecast`) records Tier-1 as SKIPPED-with-reason (visible in manifest/tear sheet/echo) and is gated on Tier-2 alone — use `--param model=0 --tier2-paths 8` for tractable kronos validation.
- `bootstrap_ci` (gate 4): passes when the Sharpe BCa lower bound > 0.
- `deflated_sharpe`: PSR/DSR of the OOS stream (single run → n_trials=1, DSR=PSR); passes when DSR ≥ `dsr_threshold`.
- `cpcv_oos`: distribution of OOS Sharpe across combinatorial purged CV folds of the OOS stream; passes when the mean fold Sharpe > 0.
A degenerate (flat/zero-variance) OOS short-circuits to a clean FAIL (degenerate gates), never an undefined-Sharpe crash. Overall `passed` = all gates pass.
- **Multi-trial gates (`alpha optim`):** Deflated Sharpe (deflated by the trial-Sharpe variance), PBO via CSCV, and White/Hansen Reality-Check/SPA judge a parameter sweep for selection bias — they only become meaningful with many configs, so they live in `_optim`, not the single-run gauntlet.

## Where do I add X?
- **New strategy** → `alpha_strategies`: pure decision fn(s) in a new module + a `nautilus Strategy` subclass; bias-guard test required. Wire defaults via `_runner.RunSpec` / CLI flags.
- **New data source** → `alpha_data/adapters/<name>_adapter.py`: a pure parser fn + a `DataAdapter` class (`name`/`version`/`parser_version`); register in `alpha_cli/data_cmds.py::_ADAPTERS`. Live-net code under `@pytest.mark.network`.
- **New forecaster** → `alpha_forecast` (or a sibling package): implement the core `BarForecaster` protocol; inject it into a strategy via the CLI registry (`_strategies.py`), NEVER import torch-land from `alpha_strategies`.
- **New validation gate / statistic** → `alpha_validation`: engine-agnostic primitive (numpy/scipy, fail-loud), then wire into `alpha_cli/_gauntlet.py` and extend `tearsheet.build_outcomes`/the report schema.
- **Anything composing engine + gauntlet / multi-package orchestration** → `alpha_cli` ONLY (the DAG forbids it elsewhere). Keep engine imports lazy.
- **New domain type / error / protocol / setting** → `alpha_core` (export via `__init__.py`).

## Build status
Phase 0 (rails) ✅ · Phase 1 (data spine) ✅ · Phase 2 (backtest core + strategy) ✅ · Phase 3 (validation gauntlet) ✅ · Phase 5 (tear sheet + CLI) ✅.
**Live data spine verified against real markets** ✅ (yfinance + ccxt/coinbase end-to-end; gauntlet correctly rejects single-name `ts_momentum` on AAPL and accepts a diversified basket. Stooq is anti-bot-gated → fails loud).
Phase 6 (broaden) — in progress: strategy registry + 3 more strategies (MA-crossover, mean-reversion, breakout) ✅ · institutional gauntlet (DSR/PSR, CPCV, PBO, Reality-Check/SPA, fat-tailed nulls) ✅ · parameter optimization with overfitting controls (`alpha optim`) ✅ · multi-asset basket portfolio (`alpha backtest portfolio`) ✅ · cross-sectional momentum (returns-level panel, `alpha backtest cross-sectional`) ✅ · Stooq data source ✅ · prop-firm Monte Carlo (`alpha propfirm`, QuantPad-style pass/payout probabilities) ✅. Remaining: full-engine cross-sectional (per-instrument t+1 fills; needs a multi-instrument engine), more data sources (FRED macro needs a non-OHLCV store).
Phase 7 (Kronos foundation model) ✅ — `alpha_forecast` package (vendored MIT Kronos, lazy torch via `uv sync --group kronos`), `kronos_forecast` registry strategy (bias-guarded; Tier-1 skipped-with-reason), `alpha forecast pull|run` + forecast artifacts + web chart + MCP `forecast_run`, loud weight-leakage warnings. HF revisions pinned (repo-specific `revision` + `tokenizer_revision`, verified by real pulls of base+mini 2026-07-11) and real CPU timings measured (spec 2026-07-11: base forecast ~5-8 s on Apple-silicon CPU, not minutes). Vendored files git-verified against upstream `67b630e6` (2026-07-14; identical modulo the documented import patch + whitespace normalization — see `_vendor/README.md`). No open items.
Phase 4 (paper trading) — scaffolded: nautilus `SandboxExecutionClient` venue (backtest-parity fills) + node-config assembly + a `alpha paper preflight` parity check, all offline-verified. Remaining (post-v1, network-bound): wiring a live market-data adapter + credentials to `_paper.run_paper`.
QuantPad-parity track (separate from the internal phase numbers above): A–F Verdict + tail-risk ✅ · prop-firm Monte Carlo ✅ · conversational agent = MCP server (`alpha_mcp`, subprocesses the CLI; `uv run alpha-mcp` / repo `.mcp.json`) ✅ · local web IDE (`alpha_web`; `uv run alpha-web`) ✅. All four QuantPad-parity surfaces shipped.

**Workstation** (institutional research & trading terminal) ✅ — `alpha_web` evolved into a dockable, multi-workspace SPA (Vite/React/**Dockview** + **Lightweight Charts**/uPlot + cmdk, dark "instrument-panel" theme) over a thin FastAPI **JSON+SSE** backend: `/api/{runs,jobs,strategies,commands,symbols,candles,apps,workspaces}` (subprocess `alpha`, read manifests). Panels: Run Browser · Run Detail (A–F verdict, gauntlet gates/folds, equity+drawdown, per-command optim/propfirm/portfolio blocks, embedded tear sheet) · Strategy Lab (catalog-driven launch + live console) · Price (PIT candles, linked symbol/date context) · Data Explorer · AI Console (→ MCP) · Workspaces (save/load layouts). New CLI: `data candles/symbols`, `info strategies/commands` (`--json`). Frontend excluded from the Python gate; built assets committed so CI needs no Node. Roadmap: **Options & Derivatives ✅** (`alpha_options` Black-Scholes; `alpha options`; Options panel) · **Risk & scenario ✅** (`alpha_validation.scenario`; `alpha risk scenario`; Risk panel) · **Screener & News ✅** (`alpha_screener` finnhub, opt-in `ALPHA_FINNHUB_API_KEY`; `alpha screener quote/news`; Screener panel) · next: AI Research desk (MCP-path, $0). Each module = a new package/module + CLI command + manifest-described panel, no shell redesign.
