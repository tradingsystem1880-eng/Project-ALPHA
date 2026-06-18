# Project ALPHA — Agent Operating Manual

$0/free, institutional-grade Python quant research platform. **Written and operated entirely by AI agents.** This file is authoritative and OVERRIDES default behavior. Be terse, fail loud, never violate the architecture DAG.

- Spec: `docs/superpowers/specs/2026-06-14-project-alpha-v1-design.md`
- Research: `research/00-SYNTHESIS.md` (+ `research/01..07-*.md`)
- Phase plans: `docs/superpowers/plans/2026-*.md`
- Python 3.12, `uv` virtual workspace (root is not a package). Members: `packages/*`, `apps/*`.

## Architecture DAG (import-linter enforced — NEVER violate)
`alpha_core` ← `alpha_data`, `alpha_execution` ← `alpha_backtest`; `alpha_strategies`, `alpha_validation` ← `alpha_core`; `alpha_paper` composes core+data+execution+strategies; `alpha_cli` ← everything.
- `alpha_core` imports nothing internal.
- `alpha_data` → core only. `alpha_strategies` → core only. `alpha_validation` → core only. `alpha_execution` → core only. `alpha_backtest` → core + data + execution only.
- `alpha_paper` (paper-trading subsystem) may compose strategies + data + execution but must NOT import `alpha_backtest` (the backtest engine) or `alpha_cli`.
- `alpha_cli` is the ONLY layer allowed to compose the backtest engine with the validation gauntlet.
- Contracts live in root `pyproject.toml` `[tool.importlinter]` (7 forbidden contracts). Run `uv run lint-imports` after any cross-package import change.

## Golden rules (invariants)
- **TDD.** Failing test → minimal code → green → commit. Small, atomic, conventional commits (`feat(scope):`, `fix(...)`, `test(...)`, `build(...)`, `chore(...)`, `docs:`).
- **No look-ahead, ever.** Strategies/backtests read data ONLY via the point-in-time accessor `as_of`. Every data/strategy unit gets a `@pytest.mark.bias_guard` future-poison test (see `tests/bias_guards/`).
- **Execution convention:** decide on close of bar `t`, fill at open of `t+1`. Mechanism: `feed.to_execution_feed` emits an open-priced `QuoteTick` (at `bar.ts`) + a close-stamped (+23h) decision `Bar`; venue runs `bar_execution=False` so only quotes fill.
- **No empty `except`.** Raise/propagate typed `AlphaError`/`DataError`/`LookAheadError` with context, or re-raise. Fail loud on data gaps / NaN / inf / disorder / degenerate stats.
- **Polars** is the default dataframe. pandas + `quantstats_lumi` ONLY at the tear-sheet rendering edge (`alpha_validation.tearsheet`). `numpy`/`scipy.stats.norm` only in the `alpha_validation` numeric layer.
- **Strong typing.** `mypy --strict` is a CI gate. Overrides (do not "fix"): `nautilus_trader.*`, `scipy.*`, `quantstats_lumi.*` are `ignore_missing_imports` (no loadable stubs); nautilus Cython base classes get `# type: ignore[misc]`.
- **Determinism (spec §11.4).** All seeds derive from `AlphaSettings.random_seed` (default 7); the gauntlet spawns independent child seeds via `np.random.SeedSequence(master).spawn(n)` so gate order can't change results. `run_id` = sha256 of canonical sorted-key JSON of the params (no wall-clock). Manifests are byte-stable (sorted keys, `allow_nan=False` → non-finite must already be `null`).
- **Corporate actions: two clocks.** Knowledge time (`announce_date` else `ex_date`) gates visibility; `ex_date` gates price application. Splits adjust the price series; dividends are decoupled cash events credited at `pay_date` (never folded into prices). See spec §6.1.

## Commands
- Install: `uv sync`
- Full gate (run before every commit; mirrors CI `.github/workflows/ci.yml`):
  `uv run ruff check . && uv run ruff format --check . && uv run lint-imports && uv run mypy packages apps tests && uv run pytest -q -m "not network" --cov --cov-report=term-missing`
  (CI gates coverage at `fail_under=90`; config in `[tool.coverage]`.)
- Bias guards only: `uv run pytest -m bias_guard -q`
- Live-network tests (off by default, hit real APIs): `uv run pytest -m network -q`
- CLI smoke: `uv run alpha info`
- Ruff: line-length 100, target py312, rules `E,F,I,B,UP,SIM`. Markers (`--strict-markers` on): `bias_guard` (look-ahead/survivorship guards, gated in CI), `network` (skipped in CI/offline).

## CLI surface (`apps/alpha-cli/src/alpha_cli/`)
Entry point `alpha = alpha_cli.main:main`. `data`/`backtest`/`paper` are Typer sub-apps; `validate`/`report` are root commands.
- `alpha info` — print resolved `AlphaSettings` + core version.
- `alpha data pull SYMBOL --source {yfinance,ccxt} --start --end` — fetch + store raw bars/actions.
- `alpha data snapshot SNAPSHOT_ID SYMBOLS... [--source]` — freeze store → immutable hashed snapshot.
- `alpha data verify SNAPSHOT_ID` — re-hash snapshot vs manifest.
- `alpha backtest run SYMBOL [...params, fee_bps=1.0, slippage_bps=2.0, account_type=CASH, snapshot]` — one fixed-param TS-momentum run → artifacts.
- `alpha validate SYMBOL [...params, train_size=504, test_size=63, embargo=5, tier1_paths=1000, tier2_paths=64, n_resamples=2000, mean_block=5.0, threshold=0.95, seed, max_workers, snapshot]` — full gauntlet → manifest + parquet + HTML tear sheet. NOTE: `train_size` must clear the warmup floor `max(lookback+skip+1, vol_window+1)` or it fails loud.
- `alpha report RUN_ID` — re-display a stored run from `data_dir/runs/<run_id>/manifest.json` (no engine re-run).
- `alpha paper run SYMBOL [--asset-class equity|crypto, ...params, --exchange, --max-notional, --feed-interval, --snapshot]` — replay SYMBOL's stored history through the live sandbox `TradingNode` (a paper dry-run; a real-time feed is a later increment) → session artifacts.
- `alpha paper status` — list paper sessions under `data_dir/paper/`.
- `alpha paper report SESSION_ID` — print a stored session's headline metrics (computed from its equity curve).
Artifacts: `data_dir/runs/<run_id>/{manifest.json, equity_curve.parquet, trades.parquet, tearsheet.html}` (only the manifest+parquet are byte-pinned; HTML carries volatile fields). Paper: `data_dir/paper/<session_id>/{session.json, audit.log.jsonl, equity_curve.parquet}` (wall-clock provenance + audit, NOT byte-pinned; no secrets).

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
| `adapters/yfinance_adapter.py` | Equities (splits+divs) | `YFinanceAdapter`, `parse_yfinance_history` (pure) |
| `adapters/ccxt_adapter.py` | Crypto daily OHLCV (UTC; default exchange `coinbase`) | `CCXTAdapter`, `parse_ccxt_ohlcv` (pure) |

### `alpha_strategies` (`packages/alpha-strategies/src/alpha_strategies/`) — nautilus Strategy + pure decision fns. core only.
| Module | Responsibility | Key public symbols |
|---|---|---|
| `signals.py` | Pure momentum signal | `ts_momentum_signal(closes, lookback, skip) -> {-1,0,1}` |
| `sizing.py` | Pure vol-target sizing | `realized_volatility(closes, *, periods_per_year)`, `vol_target_size(signal, price, vol, *, target_vol, capital, max_leverage)` |
| `ts_momentum.py` | nautilus wiring + position state | `TimeSeriesMomentum(Strategy)` (decide on `on_bar`/close-t, order on `on_quote_tick`/open-t+1; rounds qty to the instrument's `size_precision` — integer equity lots / fractional crypto) |

### `alpha_execution` (`packages/alpha-execution/src/alpha_execution/`) — shared execution primitives (instruments, fee model, run-result schema). core only (+ nautilus). Used by both `alpha_backtest` and `alpha_paper`.
| Module | Responsibility | Key public symbols |
|---|---|---|
| `instruments.py` | Per-asset instruments | `equity_instrument(symbol, venue="SIM")`, `crypto_instrument(symbol)` (fractional `CurrencyPair`; fails loud on unknown symbol) |
| `frictions.py` | Per-notional fee model | `BpsFeeModel(fee_bps)` (slippage modeled separately in `feed`) |
| `results.py` | Engine-neutral result schema | `RunResult(orders, fills, trades, equity_curve, order_log)` (`BacktestResult` alias; `starting_equity`/`final_equity`), `Trade` |
| `orders.py` | Engine-neutral order identity | `order_signature(order) -> (side, qty)` (the sequence paper must match the backtest on) |

### `alpha_backtest` (`packages/alpha-backtest/src/alpha_backtest/`) — nautilus run harness. core + data + execution only.
| Module | Responsibility | Key public symbols |
|---|---|---|
| `feed.py` | Bar → nautilus feed (t+1-fill encoding) | `to_execution_feed(bars, bar_type, *, price_precision=2, size_precision=0, slippage_bps=...)`, `daily_bar_type(symbol, venue="SIM")` |
| `engine.py` | `BacktestEngine` harness (`bar_execution=False`) | `run_backtest(instrument, data, strategy, *, starting_cash, currency, account_type, leverage, fee_bps)` → `RunResult` (with `order_log`) |

### `alpha_validation` (`packages/alpha-validation/src/alpha_validation/`) — engine-agnostic stats primitives + tear sheet. core only (+ numpy/scipy; pandas/quantstats at the tearsheet edge).
| Module | Responsibility | Key public symbols |
|---|---|---|
| `metrics.py` | Pure numpy return/risk metrics | `to_returns`, `sharpe_ratio`, `annualized_volatility`, `cagr`, `max_drawdown`, `FloatArray`/`FloatSeq` |
| `walkforward.py` | Causal purged/embargoed splitter | `walk_forward_splits(n, *, train_size, test_size, embargo, anchored) -> list[Split]` |
| `bootstrap.py` | Stationary-bootstrap BCa CIs | `stationary_bootstrap_indices`, `block_bootstrap_ci`, `ConfidenceInterval`, `Statistic` |
| `montecarlo.py` | Randomized-price null (Tier 1, returns-level) | `randomized_price_null`, `NullResult`, `StrategyFn` |
| `tearsheet.py` | Report schema + render (pandas/quantstats edge) | `GauntletReport`, `RunMetadata`, `FoldSummary`, `NullSummary`, `CISummary`, `build_outcomes`, `report_to_manifest`, `render_tearsheet_html` |

### `alpha_cli` (`apps/alpha-cli/src/alpha_cli/`) — orchestration ONLY (allowed to compose engine + gauntlet). Engine imports are lazy.
| Module | Responsibility | Key public symbols |
|---|---|---|
| `main.py` | Typer app wiring | `app`, `info`, `main` |
| `data_cmds.py` | `alpha data ...` | `data_app`; `_ADAPTERS` registry (monkeypatched in tests) |
| `backtest_cmds.py` | `alpha backtest run` | `backtest_app`; `_load_bars` seam |
| `validate_cmds.py` | `alpha validate` | `validate` |
| `report_cmds.py` | `alpha report` | `report` |
| `paper_cmds.py` | `alpha paper run/status/report` | `paper_app`; `_load_bars` seam; builds the feed + strategy, runs a session, reports metrics via `alpha_validation.metrics` (the CLI-only validation edge) |
| `_runner.py` | Engine↔gauntlet glue, OOS stitch, run id | `RunSpec`, `load_bars`, `run_full_backtest`, `walk_forward_oos`/`_for_spec`, `OOSResult`, `run_id_for` |
| `_gauntlet.py` | Full gauntlet assembly | `run_gauntlet`, `GauntletParams`, `GauntletOutput` |
| `_surrogate.py` | Tier-1 cheap engine-free TS-momentum analogue | `make_ts_momentum_surrogate` (reuses the pure signal/sizing fns; matches the engine's vol window + warmup) |
| `_synth.py` | Tier-2 synthetic OHLCV paths + full-engine null | `synthetic_bar_paths`, `full_engine_null` (spawn pool, order-preserving, deterministic) |
| `_artifacts.py` | Run-dir layout + manifest/parquet IO | `run_dir`, `write_run`, `read_manifest` |

### `alpha_paper` (`packages/alpha-paper/src/alpha_paper/`) — paper trading via nautilus `SandboxExecutionClient`. Composes core+execution+strategies; NOT backtest/cli. Parity by construction (same strategy + `bar_execution=False`).
| Module | Responsibility | Key public symbols |
|---|---|---|
| `config.py` | Paper session spec | `PaperSpec` (mirrors `RunSpec` params + symbol/exchange/venue/`max_notional_per_order`), `paper_spec_from_settings` |
| `node.py` | Sandbox `TradingNode` assembly + lifecycle | `build_paper_node` (sandbox exec on the instrument's venue, `bar_execution=False`, RiskEngine cap, `graceful_shutdown_on_exception=True`), `run_node_for`, `halt_trading`/`resume_trading` (kill-switch) |
| `replay.py` | Replay a recorded feed into the node | `ReplayDataClient(Factory/Config)`, `register_replay_events` |
| `session.py` | Run a session + write artifacts | `run_paper_session` (+ `_EquityRecorder`), `PaperSessionResult` |
| `artifacts.py` | Session-dir layout (append-only, NOT byte-pinned) | `new_session_id`, `session_dir`, `write_session`/`read_session` (refuses credential keys), `AuditLog`, `write_equity_curve` |
| `reconcile.py` | Realized vs modeled slippage | `realized_slippage_bps`, `reconcile`, `Reconciliation` |
| `funding.py` | §13 short borrow/funding estimate (unmodeled by sandbox) | `estimate_short_funding_cost` |
| `errors.py` | Typed error | `PaperError(AlphaError)` |

Paper notes: a live `TradingNode` initializes the global nautilus logger once per process — tests hold one `LogGuard` for the session (`tests/conftest.py`) so multiple live nodes coexist. The sandbox hard-codes `MakerTakerFeeModel` (commission parity is out of scope; slippage reconciles). Live-node tests need a fresh event loop (`paper_loop` fixture).

## Validation gauntlet gates (spec §8) — produced by `build_outcomes` → `ValidationOutcome`s
- `walk_forward_oos` (gate 2): passes on a finite OOS Sharpe. OOS = concatenated contiguous test windows of ONE full-series run (fixed params → no refit; train windows are warmup only).
- `randomized_price_null` (gate 3, headline): two tiers — Tier 1 `returns_level` (surrogate on block-resampled returns) + Tier 2 `full_engine` (real engine on synthetic OHLCV paths). Passes only if observed beats the `threshold` percentile in **every** tier (conservative). Headline OOS Sharpe is the engine value; Tier-1 `observed` is the surrogate's own statistic (internal faithfulness diagnostic).
- `bootstrap_ci` (gate 4): passes when the Sharpe BCa lower bound > 0.
Overall `passed` = all gates pass.

## Where do I add X?
- **New strategy** → `alpha_strategies`: pure decision fn(s) in a new module + a `nautilus Strategy` subclass; bias-guard test required. Wire defaults via `_runner.RunSpec` / CLI flags.
- **New data source** → `alpha_data/adapters/<name>_adapter.py`: a pure parser fn + a `DataAdapter` class (`name`/`version`/`parser_version`); register in `alpha_cli/data_cmds.py::_ADAPTERS`. Live-net code under `@pytest.mark.network`.
- **New validation gate / statistic** → `alpha_validation`: engine-agnostic primitive (numpy/scipy, fail-loud), then wire into `alpha_cli/_gauntlet.py` and extend `tearsheet.build_outcomes`/the report schema.
- **Anything composing engine + gauntlet / multi-package orchestration** → `alpha_cli` ONLY (the DAG forbids it elsewhere). Keep engine imports lazy.
- **New domain type / error / protocol / setting** → `alpha_core` (export via `__init__.py`).
- **Shared instrument / fee / result primitive (used by backtest AND paper)** → `alpha_execution`.
- **Paper-trading (live/sandbox) logic** → `alpha_paper` (compose strategy + execution + a live data client; never import `alpha_backtest`). New crypto pairs: add to `alpha_execution.instruments._CRYPTO`.

## Build status
Phase 0 (rails) ✅ · Phase 1 (data spine) ✅ · Phase 2 (backtest core + strategy) ✅ · Phase 3 (validation gauntlet) ✅ · Phase 5 (tear sheet + CLI) ✅ · Phase 4 (paper trading via nautilus `SandboxExecutionClient`, crypto-first) ✅ 4a–4i: `alpha_execution` extraction, `alpha_paper` (config/artifacts, sandbox node, fixture/replay feed), backtest↔sandbox **order parity** (equity + crypto), slippage reconciliation, fractional sizing, risk controls (cap + kill-switch) + §13 funding caveat, `alpha paper` CLI, coverage gate. NEXT increment: a real-time `ccxt.pro` live data client (live paper proper, beyond replay dry-runs).
