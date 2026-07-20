# Project ALPHA

A **$0, institutional-grade, Python** quantitative research platform — point-in-time data,
event-driven backtesting, and a heavy-tailed statistical **validation gauntlet** that tells you
whether a strategy's edge is real or just luck. Built and operated by AI agents.

> The point of ALPHA is **not** to hand you a money printer. It is machinery you can *trust*: a
> backtest is only believable once it survives walk-forward out-of-sample testing, a randomized-price
> null, bootstrap confidence intervals, the Deflated Sharpe Ratio, CPCV, and (for parameter sweeps)
> PBO + Reality-Check/SPA. On data with no edge, ALPHA correctly says *no edge*.

For the current-state architecture — the enforced dependency DAG, data flow, and the decision
records behind the load-bearing choices — see [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) (+ the
[ADRs](docs/adr/)). For the agent operating manual, invariants, and module map see
[`CLAUDE.md`](CLAUDE.md); the original design rationale lives in
[`docs/superpowers/specs/`](docs/superpowers/specs/) and [`research/`](research/).

The approved post-v2 extension is bounded by the
[architecture audit](docs/audit/2026-07-19-post-v2-architecture-audit.md),
[provider/paper implementation spec](docs/superpowers/specs/2026-07-19-provider-control-plane-crypto-paper-design.md),
[dependency/license matrix](docs/governance/2026-07-19-dependency-license-matrix.md), and
[risk register](docs/governance/2026-07-19-post-v2-risk-register.md).
The professional Workstation v3 program is implemented and passed its offline release gate. Root
licensing (R-22) still blocks distribution; R-14's Binance network smoke and R-24's UTC-rollover
sandbox soak remain pending. The program is governed by four specifications covering
[causal chart artifacts](docs/superpowers/specs/2026-07-19-workstation-v3-chart-artifacts-design.md),
[strategy development](docs/superpowers/specs/2026-07-19-workstation-v3-development-control-plane-design.md),
[cited evidence/agents](docs/superpowers/specs/2026-07-19-workstation-v3-evidence-agent-design.md),
and the [isolated Qlib worker](docs/superpowers/specs/2026-07-19-workstation-v3-qlib-worker-design.md).

## Install

Requires Python 3.12 and [`uv`](https://docs.astral.sh/uv/).

```bash
uv sync
uv run alpha info        # smoke test: prints resolved settings + core version
```

## The full quality gate (run before every commit; mirrors CI)

```bash
uv lock --check && uv sync --locked \
  && uv run ruff check . && uv run ruff format --check . && uv run lint-imports \
  && uv run mypy packages apps tests \
  && uv run pytest -q -m "not network" --cov --cov-report=term-missing \
  && uv run python scripts/generate_web_openapi.py --check \
  && uv build --all-packages
# Then reinstall dist/*.whl with --no-deps and import-smoke all 11 packages (the exact CI assertion
# is in .github/workflows/ci.yml).

cd apps/alpha-web/frontend
npm ci
npm run lint -- --deny-warnings
npm run test:coverage
npm run generate:api
npx playwright install chromium
npm run test:e2e

cd ../../../workers/qlib
uv lock --check && uv sync --locked
uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest -q
```

## Workflow

```bash
# 1. Pull raw, unadjusted data into the point-in-time store (needs network — see Caveats)
uv run alpha data pull AAPL    --source yfinance --start 2010-01-01 --end 2024-12-31   # equities
uv run alpha data pull SPY     --source yfinance --start 2010-01-01 --end 2024-12-31   # ETF — yfinance is the reliable equity/ETF source
uv run alpha data pull BTC/USD --source ccxt --exchange coinbase --start 2018-01-01 --end 2024-12-31
# Stooq adds $0 FX / commodities / indices (e.g. `--source stooq` for `spy.us`, `^spx`) but is
# best-effort: it now sits behind an anti-bot gate and then fails loud — see Caveats.

# 2. (optional) Freeze an immutable, content-hashed snapshot for reproducibility
uv run alpha data snapshot equities-2024 AAPL SPY --source yfinance
uv run alpha data snapshot btc-coinbase-2024 BTC/USD --source ccxt --exchange coinbase
uv run alpha data verify equities-2024

# 3. Backtest one fixed-parameter strategy (ts_momentum | ma_crossover | mean_reversion | breakout)
uv run alpha backtest run AAPL --strategy ma_crossover --param fast=20 --param slow=100

# 4. Run the full validation gauntlet → manifest + parquet + HTML tear sheet
uv run alpha validate AAPL --strategy ts_momentum            # --null-model bootstrap|student_t|garch

# 5. Search parameters with overfitting controls (Deflated Sharpe + PBO + SPA), not a bare best Sharpe
uv run alpha optim grid AAPL --grid lookback=126,252,504 --grid vol_window=21,63

# 6. Multi-asset: a diversified basket, or a cross-sectional long/short book
uv run alpha backtest portfolio SPY QQQ GLD BTC/USD --weighting inverse_vol
uv run alpha backtest cross-sectional SPY QQQ IWM GLD USO --top-quantile 0.3

# 7. Re-display any stored run (no engine re-run)
uv run alpha report <run_id>

# 8. Inspect the provider/system control plane and paper wiring offline
uv run alpha info providers --json
uv run alpha info system --json
uv run alpha paper preflight BTC/USDT --strategy ma_crossover

# 9. Opt-in crypto paper: public Binance data, LOCAL SANDBOX orders only (see Caveats)
PAPER_END=2026-07-19  # replace with the current UTC date; warmup must be fresh
uv run alpha data pull BTC/USDT --source ccxt --exchange binance --start 2024-01-01 --end "$PAPER_END"
uv run alpha data snapshot binance-warmup BTC/USDT --source ccxt --exchange binance
ALPHA_PAPER_ENABLED=true uv run alpha paper run BTC/USDT \
  --provider binance --snapshot binance-warmup --strategy ma_crossover
uv run alpha paper sessions --json

# 10. Analytics for the Workstation panels (all offline except screener, which needs a finnhub key)
uv run alpha options greeks 100 100 --vol 0.2              # Black-Scholes price + greeks
uv run alpha risk scenario --from-run <run_id>            # vol-scaling + tail-shock stress
uv run alpha research compare AAPL                        # rank every strategy on a symbol
uv run alpha screener quote AAPL                          # finnhub (set ALPHA_FINNHUB_API_KEY)

# 11. Start a governed strategy-development project and resolve a one-click suite
uv run alpha project create "AAPL mean reversion" \
  --hypothesis "Short-horizon dislocations revert after costs" \
  --falsification "Reject if locked holdout Sharpe is non-positive"
uv run alpha suite actions --json

# 12. Search exact cited evidence / export a bounded Codex brief
uv run alpha evidence list --asset AAPL --json
uv run alpha project agent-brief <project_id> --json

# 13. Inspect the isolated ML boundary (Qlib is never imported into this root environment)
uv run alpha ml --help
uv run --directory workers/qlib alpha-qlib-worker --help
```

New research commands write immutable v3 manifests plus hash-pinned typed Parquet and deterministic
HTML audit artifacts under
`data_dir/{runs,optim,portfolio,cross_sectional,propfirm,forecast}/<run_id>/`. Re-running with the
same identity verifies the existing bytes; a mismatch fails loudly (`--seed` defaults to 7).
V1/v2 runs remain readable and missing causal traces are labeled `trace_unavailable`. Mutable
project/job/evidence state lives in the CLI-owned `data_dir/control/workstation.sqlite3`, outside
the run store. Paper sessions are intentionally
nondeterministic operational records under `data_dir/paper/<uuid>/`, never research runs or
validation evidence. Run any command with `--help` for all options.

## Caveats (read before trusting a result)

- **This repository has no declared root project license.** No dependency or vendored-code license
  licenses ALPHA's original code. Distribution, publication, or hosted use is gated on an explicit
  owner license decision and release-time dependency/notice review; see the
  [license matrix](docs/governance/2026-07-19-dependency-license-matrix.md).
- **Live data needs outbound network.** `alpha data pull` hits Yahoo or a selected CCXT exchange;
  yfinance and Coinbase are verified working end-to-end. The Binance paper adapter is fully
  assembled and offline-tested, but its real connection/quote smoke and UTC-rollover soak remain
  explicit opt-in acceptance steps. **Stooq is best-effort:** it gates its free CSV behind an
  anti-bot challenge + a per-IP download quota, so `--source stooq` often **fails loud** with a
  `DataError` (it does *not* silently 404) — prefer `--source yfinance` for equities/ETFs. In a
  sandbox with a restricted egress allowlist any host may be blocked; run where the network policy
  permits them. The pure parsers are unit-tested offline; the live `fetch` paths are
  `@pytest.mark.network` (run with `-m network`).
- **CASH accounts can't be levered or overspend.** With the default `--account-type CASH`, a
  vol-targeted notional that exceeds buying power (e.g. a low-volatility asset plus fees) has its
  orders rejected — the run **fails loud** with guidance rather than silently reporting flat equity.
  Use `--account-type MARGIN`, a lower `--target-vol`, or `--max-leverage` below 1.
- **Free data is survivorship-biased and (for Stooq) provider-adjusted.** Documented limitations of
  the $0 data tier; the bias-guard tests make the assumptions explicit.
- **Validation has been run end-to-end against real market data.** yfinance (AAPL, incl. the 2020
  4:1 split) and Coinbase (BTC/USD, 2018–2024) feed the full gauntlet. On real AAPL it correctly
  **rejects** single-name `ts_momentum` (OOS Sharpe 0.65, but the returns-level null and a
  zero-straddling bootstrap CI fail it); a diversified `inverse_vol` basket clears it (OOS Sharpe
  ~1.18, PSR ~1.0). The parsers and gauntlet primitives are also covered offline.

## Paper trading (Phase 4 — sandbox-only)

The deterministic offline implementation is complete. `alpha paper run BASE/USDT` primes one of
the four rule strategies from a fresh, hash-verified, same-symbol `ccxt:binance` snapshot whose
hashed pull sidecar proves the stored bars were not relabelled from another exchange, then uses
public Binance `LIVE` market data through NautilusTrader and routes every order exclusively to a
**local Nautilus sandbox execution client** at venue `BINANCE`. `ALPHA_PAPER_ENABLED` defaults to
false. There is no Binance execution client, testnet/live-order mode, or real-order credential
surface. Kronos is rejected until a separately designed causal live cache exists.

History priming warms the same strategy class without emitting orders. Paper-only quantities honor
the live instrument's size increment while existing SIM results remain unchanged. SIGINT/SIGTERM
request a clean node stop, and node disposal is unconditional.

Operational state lives outside deterministic `RUN_DIRS` at
`data_dir/paper/<uuid>/{session.json,events/<sequence>.json}`. It persists bounded lifecycle,
order, fill, rejection, position, and reconciliation-warning events—never bars/ticks. Use
`alpha paper sessions` / `alpha paper show`, or the Workstation Paper Monitor, to inspect status,
heartbeat/staleness, position events, and the order blotter. Stale state never authorizes a raw PID
kill; cancellation is limited to a Workstation-known child job.

This proves assembly, safety gates, journaling, and deterministic compatibility offline. It does
**not** prove Binance availability, simulated fill realism, latency, queue position, fees, or
profitability. Before calling Phase 4 operationally accepted, run the separately marked network
smoke and one owner-initiated sandbox soak across UTC midnight.

## Conversational agent (MCP server)

`alpha_mcp` is a stdio [MCP](https://modelcontextprotocol.io) server with 42 bounded tools: the
original 12 data/run/validation/discovery tools remain during deprecation and 30 typed v3 tools add
project, version, experiment, stage, durable suite/job cancellation and reconciliation, evidence,
chart/comparison, AgentBrief, and ML planning/launch resources. It cannot reveal a final holdout,
place an order, run arbitrary Python, accept raw SQL, or expose filesystem paths. Agent-authored
evidence is forced to `draft` with agent provenance. Retained action `options` use a closed,
bounded per-tool deprecated compatibility vocabulary rather than arbitrary CLI flags; managed
model/tokenizer values reject filesystem-like paths. Each action tool **subprocesses the `alpha`
CLI** and returns either a capped, verified manifest written by a run-producing command or a strict
bounded CLI control projection, so the agent and CLI share one store and the CLI stays the single
source of truth.

The repo ships a `.mcp.json`, so **Claude Code auto-launches it** (`uv run alpha-mcp`). For Claude
Desktop, add to `claude_desktop_config.json`:

```json
{ "mcpServers": { "alpha": { "command": "uv", "args": ["run", "alpha-mcp"],
  "cwd": "/path/to/Project-ALPHA" } } }
```

Then drive ALPHA in plain language: *"pull AAPL, run the gauntlet on a momentum strategy, then
check it against a Topstep combine."* No API keys, $0.

## ALPHA Workstation (web terminal)

`uv run alpha-web` serves the **ALPHA Workstation** at **http://127.0.0.1:8800** (loopback only, no
auth): a dark, dockable, single-user research terminal that unifies every capability behind one
interface — Bloomberg/OpenBB-class, but $0.

- **Run browser** — every stored run (filter/paginate; pass / A–F Verdict badges), newest first.
- **Six curated desks** — Market, Development, Kronos, ML Research, Portfolio & Risk, and Operations,
  with linked A/B/C/D instrument contexts, preserved free-form layouts, and an atomic v2→v3
  migrator that keeps the legacy source and rejects unknown panels without partial persistence.
- **Professional market evidence** — a large native candle/volume chart with decisions, next-open
  fills, exits, holding intervals, vector pattern anchors, and linked tables sourced only from causal
  v3 artifacts. Legacy runs are never reconstructed from hindsight.
- **Native quant tear sheets** — equity/drawdown, calendar returns, distribution/Q-Q, rolling stats,
  benchmark/exposure/turnover, and trade analysis authored by Python; QuantStats-Lumi HTML remains a
  deterministic audit/export view. Dense series are deterministically endpoint-preserving and
  bounded, with original/returned/truncated metadata.
- **Development Center** — immutable setup, 14 exposed stage IDs (12 core lifecycle stages plus
  separate Kronos and ML tracks), resolved one-click suites,
  holdout/attempt governance, durable jobs, decision packets, Asset Memory, and AgentBrief export.
- **Kronos + ML studios** — complete sampled K-lines, uncertainty/terminal distributions,
  calibration/provenance/warnings, plus the isolated Alpha158-style LightGBM/Qlib workflow and
  close-stamped predictions replayed synchronously across the frozen universe through ALPHA's
  canonical engine. Replay metrics are authoritative for that execution, but the result remains
  labeled because counterfactual paths do not retrain the model.
- **Strategy lab** — a form built from the CLI's own catalogs; launch a run and watch it stream live.
- **Price chart / data explorer** — point-in-time candles + the symbol store, linked to a global
  symbol/date context. **Options**, **Screener/News**, **Risk scenarios**, and an **AI research
  desk** panel round out the four net-new modules.
- **Providers · System** — registry-driven provider readiness, limitations, redacted credential
  presence, data-directory capacity, dependency/cache status, and paper opt-in state; no network
  probe.
- **Paper Monitor** — permanent SANDBOX identity, durable sessions/heartbeats, latest position event,
  order/fill/rejection blotter, incremental event log, and known-job cancellation.
- **Command palette + savable workspaces** (dockable/floating/popout panels).

Built as a Vite/React/TypeScript SPA (Dockview + Lightweight Charts + uPlot + TanStack Table/Virtual +
cmdk) over a thin FastAPI **JSON + SSE** backend. Stable, bounded JSON responses are strict Pydantic
models with an explicit REST contract version; committed OpenAPI generates the frontend API
definitions. Like the MCP server it's purely additive —
provider/system data subprocesses the matching `alpha info … --json` projections, research data is a
manifest/artifact read, and paper monitoring uses the public operational journal seam; nothing
imports an engine. The SPA
source lives in [`apps/alpha-web/frontend`](apps/alpha-web/frontend); its **built assets are
committed** under `src/alpha_web/static/app`, so an installed Python wheel never needs Node. To change
the UI:

```bash
cd apps/alpha-web/frontend
npm ci
npm run lint -- --deny-warnings
npm run test:coverage
npm run generate:api
npx playwright install chromium
npm run test:e2e       # builds, then checks six desks at 1280/1440/1920 and runs axe
```

CI fails on frontend lint warnings, coverage regressions, stale generated API types,
TypeScript/build errors, serious/critical axe findings, desk/keyboard/responsive regressions, or
stale committed assets.
For conversational control, pair the Workstation's AI Console with the `alpha` MCP server (above).

## Not yet built (intentional)

- Real or exchange-testnet order execution, additional paper venues/providers, and automated orphan
  recovery (the shipped path is Binance public data + local sandbox execution only).
- Kronos live-paper cache semantics (the four rule strategies are supported).
- Full-engine cross-sectional with per-instrument t+1 fills (a returns-level panel version ships now).
- FRED macro / regime filters (needs a non-OHLCV store).
- Model fine-tuning (Kronos remains zero-shot, with overlap provenance and offline weight policy).
- Full counterfactual Qlib retraining/gauntlet authority and single-asset ML equivalence. The shipped
  synchronized cross-sectional replay is authoritative execution evidence, not a claim that the
  model was recomputed under randomized paths.

## Quality gate

The v3 offline release gate passed on 2026-07-19. It covers 12 import contracts, strict mypy,
warnings as errors, a true 93.00% minimum owned-source Python line coverage threshold,
OpenAPI/generated TypeScript freshness, frontend V8 coverage, Playwright/axe at 1280×720,
1440×900, and 1920×1080, deterministic artifact publication, isolated builds/imports for all 11
root wheels, and the separately locked Qlib worker. Historical hardening evidence is recorded in
[`docs/audit/2026-07-18-professional-hardening-readiness.md`](docs/audit/2026-07-18-professional-hardening-readiness.md);
exact current v3 release evidence is recorded in the
[post-v2 audit](docs/audit/2026-07-19-post-v2-architecture-audit.md). The root-license
decision (R-22), Binance network smoke (R-14), and UTC-rollover sandbox soak (R-24) remain pending.
