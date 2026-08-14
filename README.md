# Project ALPHA

A **private, local, Python** quantitative research platform — point-in-time data,
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
[daily-data/IBKR Paper hardening](docs/superpowers/specs/2026-08-03-daily-data-ibkr-paper-hardening.md),
[QuantPad external research boundary](docs/adr/0018-quantpad-external-research-data-boundary.md),
[family-scoped crypto data authority](docs/adr/0032-governed-crypto-data-house.md),
[dependency/license matrix](docs/governance/2026-07-19-dependency-license-matrix.md), and
[risk register](docs/governance/2026-07-19-post-v2-risk-register.md).
The professional Workstation program is implemented for private, single-owner, local use;
distribution is outside the approved scope while dependency notices and provider/data terms remain
mandatory. Provider state is explicit and receipted rather than inferred from packages or
environment variables. The program is governed by four specifications covering
[causal chart artifacts](docs/superpowers/specs/2026-07-19-workstation-v3-chart-artifacts-design.md),
[strategy development](docs/superpowers/specs/2026-07-19-workstation-v3-development-control-plane-design.md),
[cited evidence/agents](docs/superpowers/specs/2026-07-19-workstation-v3-evidence-agent-design.md),
and the [isolated Qlib worker](docs/superpowers/specs/2026-07-19-workstation-v3-qlib-worker-design.md).

The [Research Scientist program](docs/superpowers/specs/2026-08-06-research-scientist-program-design.md)
now provides the bounded D0/D1/one-shot-D2 lifecycle, compact exact-membership boundaries, explicit
owner-clicked literature discovery and extraction, anchored claim screening, cited non-authoritative
recommendations, and per-action Touch ID for the closed research-lifecycle authority set. It never
turns literature, model output, standalone experiments, provider configuration, or a broker what-if
preview into strategy, paper, or order authority.

Crypto data is governed per dataset family rather than collapsed into one universal price:
Binance owns native CEX spot/futures history, Bybit owns advanced derivatives/options, CoinGecko
owns identity/reference, GeckoTerminal owns DEX pool data, Coin Metrics Community owns its frozen
catalog and only the reviewed on-chain metrics proven available by it, and Coinbase/CCXT is
comparison. Venue, market type, units, clocks, and USD,
USDT, and USDC denominations remain distinct; automatic provider fallback is prohibited. Existing
CCXT snapshots and the Binance sandbox-paper warmup contract remain unchanged.
Provider-native observations are admitted to research only through exact mechanical qualification
and frozen `CryptoSnapshotV1` membership. Coinbase/Bybit price comparisons are diagnostics, never
fallbacks; derived funding, basis, OI, volatility, liquidity, and on-chain features retain exact
input hashes and conservative availability times. CoinGecko metadata/reference observations are
supplemental and cannot satisfy a venue-price validation requirement.

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
# Then reinstall dist/*.whl with --no-deps and import-smoke all 13 packages (the exact CI assertion
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

cd ../literature
uv lock --check && uv sync --locked
uv run ruff check . && uv run ruff format --check . && uv run mypy
uv run pytest -q -m "not network"
```

## Workflow

```bash
# 1. Pull raw, unadjusted data into the point-in-time store (needs network — see Caveats)
# with ALPHA_TIINGO_API_KEY already injected from the OS keychain
uv run alpha data pull AAPL --source tiingo --venue XNAS --calendar XNAS --start 2010-01-01 --end 2024-12-31
uv run alpha data pull SPY --source tiingo --asset-class etf --venue ARCX --calendar XNYS --start 2010-01-01 --end 2024-12-31
uv run alpha data pull BTC/USD --source ccxt --exchange coinbase --start 2018-01-01 --end 2024-12-31
# Yahoo/Stooq remain explicit comparison feeds; neither may silently replace canonical Tiingo.

# Public bulk crypto storage is separately configured. The UUID is mandatory for a removable
# volume; CI and tests use the isolated `data/bulk` default without acquiring network data.
# ALPHA_BULK_DATA_DIR=/Volumes/Expansion/Project-ALPHA/crypto-data
# ALPHA_BULK_VOLUME_UUID=<mounted-volume-uuid>
uv run alpha crypto-data storage-inventory --json
uv run alpha crypto-data storage-verify --json
# Freeze the current provider catalogs into an inspectable plan, then run only an explicitly
# confirmed cadence page (maximum 25 tasks, checkpointed after each task).
uv run alpha crypto-data profile-create --json
uv run alpha crypto-data profiles --json
uv run alpha crypto-data profile-show <PROFILE_ID> --cadence daily --limit 25 --json
uv run alpha crypto-data profile-run <PROFILE_ID> --cadence daily --limit 25 --confirm --json
# Derived features remain non-authoritative and require exact named qualified inputs.
uv run alpha crypto-data features --json
# Cache cleanup is deliberately separate and confirmed; it never removes raw, normalized,
# staged, snapshot, manifest, or control artifacts.
uv run alpha crypto-data cache-clean --confirm --json

# 2. (optional) Freeze an immutable, content-hashed snapshot for reproducibility
uv run alpha data snapshot equities-2024 AAPL SPY --source tiingo
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

# 10. Daily stock/ETF decision path (see docs/operations/README.md before enabling IBKR Paper)
uv run alpha paper scheduler-status --config /absolute/private/daily-paper.json
uv run alpha paper scheduler-tick --config /absolute/private/daily-paper.json
uv run alpha paper ibkr-preflight SPY.ARCA --asset-class etf
uv run alpha paper readiness --json

# 11. Analytics for the Workstation panels (all offline except screener, which needs a finnhub key)
uv run alpha options greeks 100 100 --vol 0.2              # Black-Scholes price + greeks
uv run alpha risk scenario --from-run <run_id>            # vol-scaling + tail-shock stress
uv run alpha research compare AAPL                        # rank every strategy on a symbol
uv run alpha screener quote AAPL                          # finnhub (set ALPHA_FINNHUB_API_KEY)

# 12. Capture a raw idea before strategy development
uv run alpha research capture \
  "SPY may bounce after a causally confirmed double bottom in a four-trading-hour window" --json
uv run alpha research status <project_id> --json

# The complete trusted-local CLI inventory is visible here. Gate 1 can run only the registered
# double-bottom `run pilot` on D0;
# `run deep` and `run confirm` fail closed until the empirical evidence firewall ships.
uv run alpha research --help

# `project create` is an alternative entry point and automatically captures the required
# Research Case in triage. It no longer creates a strategy-ready project.
uv run alpha project create "AAPL mean reversion" \
  --hypothesis "Short-horizon dislocations revert after costs" \
  --falsification "Reject if locked holdout Sharpe is non-positive"

# 13. Search exact cited evidence / export a bounded Codex brief for an eligible project
uv run alpha evidence list --asset AAPL --json
uv run alpha project agent-brief <project_id> --json

# 14. Inspect the isolated ML boundary (Qlib is never imported into this root environment)
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

Research Case mutable state shares that SQLite authority. Deterministic Markdown dossiers default
to `data_dir/research/projects/<project_id>/`; manual edits fail verification and are never parsed
back as control input. Fresh projects are research-required and cannot create a strategy version
without an approved confirmation contract plus the owner `advance_to_strategy` disposition.
Pre-launch projects already present when schema v2 migrates are explicitly grandfathered for
compatibility; existing post-launch records become research-required. Only the verified migration
transaction can emit that grandfathered state, and its v1 backup must logically match the source.

The Gate 1 CLI inventory is `capture`, `sources add|screen|freeze`, `draft`, `approve`, `reject`,
`run pilot|deep|confirm`, `status`, `report`, `export`, `verify`, `pause`, `resume`, `cancel`, and
`decide|revise`. Only the canonical `double_bottom` + `second_trough_confirmable` contract can run
the Gate 1 D0 pilot; other ideas and neckline variants remain draftable but execution fails closed.
`deep` and `confirm` are explicit fail-closed placeholders. An
owner can use `decide` after D0 to close an early case only as `INCONCLUSIVE` or `INVALID` with
`revise`, `park`, or `reject`; D0 cannot support either `CONTRADICTED` or advancement. A
`CONTRADICTED` result requires lineage-bound typed non-synthetic evidence. `revise` reopens one
immutable child only while D2 has never been authorized or viewed.

The executable Gate 1 contract is an exact synthetic acceptance fixture
(`alpha_synthetic_fixture` / `SYNTHETIC_SPY` / UTC / equal 60-minute bars / 240-minute pattern
window). Literal SPY/ES or alternate endpoint drafts are marked unavailable and cannot be approved;
they require the later qualified-data/operator gate. Completion requires a canonical hashed
raw-measurement acceptance artifact; the control plane reruns the exact detector, null,
four-observation topology-embargo, and power criteria and never trusts a manifest pass flag. A
completed D0 run moves directly to the
owner disposition because empirical D1 is not present.

## Caveats (read before trusting a result)

- **This repository has no declared root project license.** No dependency or vendored-code license
  licenses ALPHA's original code. Distribution, publication, or hosted use is gated on an explicit
  owner license decision and release-time dependency/notice review; see the
  [license matrix](docs/governance/2026-07-19-dependency-license-matrix.md).
- **Live data needs outbound network.** `alpha data pull` may hit Tiingo, Yahoo, Stooq, or a selected
  CCXT exchange. Tiingo is the authoritative stock/ETF EOD path but requires an owner key and
  current-universe qualification before operational authority is claimed. Yahoo/Stooq are
  comparison-only once Tiingo is canonical. A short AAPL Tiingo pull passed the complete live
  receipt→promotion→snapshot→candle path on 2026-08-04; this is not current-universe qualification.
  The Binance public quote smoke also passed, while durable readiness evidence and the UTC-rollover
  soak remain explicit opt-in acceptance steps. **Stooq is best-effort:** it gates its free CSV behind an
  anti-bot challenge + a per-IP download quota, so `--source stooq` often **fails loud** with a
  `DataError` (it does *not* silently 404). In a
  sandbox with a restricted egress allowlist any host may be blocked; run where the network policy
  permits them. The pure parsers are unit-tested offline; the live `fetch` paths are
  `@pytest.mark.network` (run with `-m network`).
- **Research owner-only CLI operations are a trusted-local authority boundary, not authentication.**
  Approval, rejection, and disposition are absent from MCP, REST, and the Cockpit, but the local
  CLI actor string is an audit record rather than cryptographic proof of physical owner presence.
- **CASH accounts can't be levered or overspend.** With the default `--account-type CASH`, a
  vol-targeted notional that exceeds buying power (e.g. a low-volatility asset plus fees) has its
  orders rejected — the run **fails loud** with guidance rather than silently reporting flat equity.
  Use `--account-type MARGIN`, a lower `--target-vol`, or `--max-leverage` below 1.
- **Daily vendor data retains survivorship, revision, calendar, and licensing limits.** Tiingo raw
  fields are canonical only after qualification; adjusted fields are a check. Comparison feeds and
  bias guards make disagreements/assumptions explicit rather than providing silent fallback.
- **Validation has been run end-to-end against real market data.** yfinance (AAPL, incl. the 2020
  4:1 split) and Coinbase (BTC/USD, 2018–2024) feed the full gauntlet. On real AAPL it correctly
  **rejects** single-name `ts_momentum` (OOS Sharpe 0.65, but the returns-level null and a
  zero-straddling bootstrap CI fail it); a diversified `inverse_vol` basket clears it (OOS Sharpe
  ~1.18, PSR ~1.0). The parsers and gauntlet primitives are also covered offline.

## Paper trading (Phase 4 — local Sandbox + IBKR Paper, never live capital)

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

For stocks/ETFs, the wake-safe five-minute scheduler uses exchange calendars and UTC to perform
Tiingo receipt → candidate gate/quarantine → canonical promotion → immutable snapshot → Nautilus
simulation → immutable next-session `OrderIntent`. Native Nautilus IB clients can release only that
exact intent to IBKR Paper after dual flags, loopback paper port 4002, a DU account, digest-pinned
gateway, instrument/client-ID allowlists, exact journal/broker reconciliation, fresh quote, and
cutoff checks. Long-only equity limits are 5% NAV/order, 10%/position, 50% gross, 1% daily-loss halt,
and five open orders. The intent hash is atomically claimed once across process restarts, journaled
before submission, and used as the client-order ID; an ambiguous attempt is reconciled, never
resubmitted. Safe stop cancels ALPHA-owned DAY orders and never flattens positions. Full account
identifiers and secrets stay outside API/browser state.

Journal schema v2 distinguishes `local_sandbox` and `ibkr_paper` while reading v1 Binance sessions.
`alpha paper readiness --json` passes only from every required machine event and no blockers; it is
currently pending until the external Binance, Tiingo, and real IBKR scenarios are performed. IBKR
Paper fills do not prove live execution quality. Explicit dated micro futures are connectivity
probes only; futures research and live-capital routing are absent. See the
[operations runbook](docs/operations/README.md) and [ADR-0017](docs/adr/0017-authoritative-daily-data-and-broker-paper-boundary.md).

## Conversational agent (MCP server)

`alpha_mcp` is a stdio [MCP](https://modelcontextprotocol.io) server whose current generated count
and authority are recorded in the [capability matrix](docs/governance/capability-authority-matrix.md).
It provides bounded data/run/validation, development-control, evidence, chart/comparison,
AgentBrief, ML, and Research Case resources. Research tools cannot approve or decide a case,
consume D2 confirmation, create strategy, holdout, paper, or order authority. The wider MCP
surface cannot reveal a final holdout, place an
order, run arbitrary Python, accept raw SQL, or expose filesystem paths. Agent-authored
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
check it against a Topstep combine."* No embedded LLM API key; provider credentials remain scoped.

### QuantPad external market-data MCP

The project-scoped `.codex/config.toml` also registers QuantPad's OAuth MCP endpoint. After starting
a new Codex session, run `/mcp` and sign in with the paid QuantPad account. Use its MCP tools for
symbol resolution, coverage/schema discovery, usage checks, and small OHLCV previews. Use the
official `quantpad-data` SDK/REST API for bulk bars, ticks, L1, or `mbp-10` L2; never assemble a
dataset by looping MCP previews or scraping the website. QuantPad output is research scratch data,
not canonical ALPHA data or paper evidence, until the ADR-0018 adapter/qualification gate exists.
The keychain and routing procedure is in the [operations runbook](docs/operations/README.md).

## ALPHA Workstation (web terminal)

`uv run alpha-web` serves the **ALPHA Workstation** at **http://localhost:8801** (loopback only, no
auth): a dark, dockable, single-user research terminal that unifies every capability behind one
interface — a focused owner workstation over the same governed CLI contracts.

- **Run browser** — every stored run (filter/paginate; pass / A–F Verdict badges), newest first.
- **Six curated desks** — Market, Development, Kronos, ML Research, Portfolio & Risk, and Operations,
  with linked A/B/C/D instrument contexts, preserved free-form layouts, and an atomic v2→v3
  migrator that keeps the legacy source and rejects unknown panels without partial persistence.
  Each desk accepts only compatible run families, while inactive tabs suspend background requests.
- **Professional market evidence** — a large native candle/volume chart with decisions, next-open
  fills, exits, holding intervals, vector pattern anchors, and linked tables sourced only from causal
  v3 artifacts. Execution/decision/all layers keep dense overlays readable through a deterministic
  visual cap while the complete returned evidence remains inspectable. Legacy runs are never
  reconstructed from hindsight.
- **Native quant tear sheets** — equity/drawdown, calendar returns, distribution/Q-Q, rolling stats,
  benchmark/exposure/turnover, and trade analysis authored by Python; QuantStats-Lumi HTML remains a
  deterministic audit/export view. Dense series are deterministically endpoint-preserving and
  bounded, with original/returned/truncated metadata. Explicitly unavailable analytics remain
  distinct from artifacts that were not emitted.
- **Development Center** — immutable setup, 15 exposed stage IDs (13 core lifecycle stages plus
  separate Kronos and ML tracks), resolved one-click suites, required four-family Monte Carlo
  evidence and owner warning review, holdout/attempt governance, durable jobs, decision packets,
  Asset Memory, and AgentBrief export.
- **Research Cockpit** — exact-idea capture, explicit thesis/mechanism/prediction and competing
  explanations, owner-visible gates, native-unit budgets, synthetic D0 plus governed empirical
  D1 and one-shot D2 lanes, immutable D2/D3 firewalls, and a teaching-oriented terminal packet.
  Empirical packet sections remain `NOT_TESTED` without typed D1/D2 evidence. Touch ID protects
  the closed research-lifecycle actions; the UI cannot bypass their server gates.
- **Kronos + ML studios** — complete sampled K-lines, uncertainty/terminal distributions,
  calibration/provenance/warnings, plus the isolated Alpha158-style LightGBM/Qlib workflow and
  close-stamped predictions replayed synchronously across the frozen universe through ALPHA's
  canonical engine. Replay metrics are authoritative for that execution, but the result remains
  labeled because counterfactual paths do not retrain the model.
- **Strategy lab** — a form built from the CLI's own catalogs; launch a run and watch it stream live.
- **Price chart / data explorer** — point-in-time candles + the symbol store, linked to a global
  symbol/date context. **Options**, **Screener/News**, **Risk scenarios**, and the bounded **Codex
  Research** context panel round out the specialist tools.
- **Providers · System** — separate local configuration, last explicit verification receipt, and
  granted capabilities, plus limitations, capacity, dependency/cache status, and paper opt-ins.
  Refresh never probes; each supported provider check requires an explicit click.
- **Paper Monitor** — permanent PAPER/NO-LIVE-CAPITAL identity, separate local Sandbox and IBKR Paper
  modes, reconciliation/risk/readiness state, latest position, bounded event log, and order/fill/
  cancellation/expiration markers on the existing price chart.
- **Live Job Monitor** — running work stays above terminal history with exact elapsed time, current
  operation, output activity, accessible progress, live logs, and cancellation. ETA remains visibly
  indeterminate until a comparable successful command provides a same-session median; UI-launched
  Kronos/Qlib children use reduced scheduling priority to keep the desk responsive.
- **Command palette + savable workspaces** over the fixed six-screen information architecture.

Built as a Vite/React/TypeScript SPA (Lightweight Charts + TanStack Table/Virtual + cmdk) over a
thin FastAPI **JSON + SSE** backend. Stable, bounded JSON responses are strict Pydantic
models with an explicit REST contract version; committed OpenAPI generates the frontend API
definitions. Bounded Research Case routes mirror the supported MCP read/draft boundary while
owner actions remain confined to the Touch ID service. Like the MCP server it's purely additive —
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
npm run test:e2e       # builds, then checks six desks at 1280×720 / 1440×900 / 1920×1080 and runs axe
```

CI fails on frontend lint warnings, coverage regressions, stale generated API types,
TypeScript/build errors, serious/critical axe findings, desk/keyboard/responsive regressions, or
stale committed assets.
For conversational control, pair the Workstation's AI Console with the `alpha` MCP server (above).

## Not yet built (intentional)

- Research source-network/download worker and lawful document-retention plane.
- Qualified real intraday research adapter or any production empirical D1/D2 runner. The default
  future split is 60/20/20 over indivisible chronological eligible date/session/dependency groups;
  an alternative must be event-blind, owner-approved before D1, and retain D3 at 20% or more.
- Verified owner-presence authentication, autonomous research continuation, and research ML/
  self-improvement. Local owner CLI fields are not cryptographic identity.
- Live or exchange-testnet order execution, paper venues beyond IBKR/local Sandbox, strategy futures,
  automatic rolls, and automated orphan recovery.
- Kronos live-paper cache semantics (the four rule strategies are supported).
- Full-engine cross-sectional with per-instrument t+1 fills (a returns-level panel version ships now).
- FRED macro / regime filters (needs a non-OHLCV store).
- Model fine-tuning (Kronos remains zero-shot, with overlap provenance and offline weight policy).
- Full counterfactual Qlib retraining/gauntlet authority and single-asset ML equivalence. The shipped
  synchronized cross-sectional replay is authoritative execution evidence, not a claim that the
  model was recomputed under randomized paths.

## Quality gate

The v3 offline release gate passed on 2026-07-19. The current gate covers 14 import contracts,
strict mypy, warnings as errors, a true 93.00% minimum owned-source Python line coverage threshold,
OpenAPI/generated TypeScript freshness, frontend V8 coverage, Playwright/axe at 1280×720,
1440×900, and 1920×1080, deterministic artifact publication, isolated builds/imports for all 13
root wheels, and the separately locked Qlib worker. Historical hardening evidence is recorded in
[`docs/audit/2026-07-18-professional-hardening-readiness.md`](docs/audit/2026-07-18-professional-hardening-readiness.md);
exact 2026-07-19 v3 release evidence is recorded in the
[post-v2 audit](docs/audit/2026-07-19-post-v2-architecture-audit.md). The root-license
decision (R-22), durable Binance readiness evidence, UTC-rollover sandbox soak (R-24),
current-universe Tiingo qualification, and every real IBKR Paper acceptance scenario remain
pending. The standalone R-14 public-quote network smoke passed locally on 2026-08-04.
