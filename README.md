# Project ALPHA

A **$0, institutional-grade, Python** quantitative research platform — point-in-time data,
event-driven backtesting, and a heavy-tailed statistical **validation gauntlet** that tells you
whether a strategy's edge is real or just luck. Built and operated by AI agents.

> The point of ALPHA is **not** to hand you a money printer. It is machinery you can *trust*: a
> backtest is only believable once it survives walk-forward out-of-sample testing, a randomized-price
> null, bootstrap confidence intervals, the Deflated Sharpe Ratio, CPCV, and (for parameter sweeps)
> PBO + Reality-Check/SPA. On data with no edge, ALPHA correctly says *no edge*.

For the architecture, invariants, and module map see [`CLAUDE.md`](CLAUDE.md); the design rationale
lives in [`docs/superpowers/specs/`](docs/superpowers/specs/) and [`research/`](research/).

## Install

Requires Python 3.12 and [`uv`](https://docs.astral.sh/uv/).

```bash
uv sync
uv run alpha info        # smoke test: prints resolved settings + core version
```

## The full quality gate (run before every commit; mirrors CI)

```bash
uv run ruff check . && uv run ruff format --check . && uv run lint-imports \
  && uv run mypy packages apps tests && uv run pytest -q -m "not network"
```

## Workflow

```bash
# 1. Pull raw, unadjusted data into the point-in-time store (needs network — see Caveats)
uv run alpha data pull AAPL    --source yfinance --start 2010-01-01 --end 2024-12-31   # equities
uv run alpha data pull SPY     --source yfinance --start 2010-01-01 --end 2024-12-31   # ETF — yfinance is the reliable equity/ETF source
uv run alpha data pull BTC/USD --source ccxt     --start 2018-01-01 --end 2024-12-31   # crypto (Coinbase, paginated)
# Stooq adds $0 FX / commodities / indices (e.g. `--source stooq` for `spy.us`, `^spx`) but is
# best-effort: it now sits behind an anti-bot gate and then fails loud — see Caveats.

# 2. (optional) Freeze an immutable, content-hashed snapshot for reproducibility
uv run alpha data snapshot snap-2024 AAPL SPY BTC/USD
uv run alpha data verify   snap-2024

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

# 8. Paper-trading preflight: validate the sandbox exec venue + strategy parity (see Caveats)
uv run alpha paper preflight AAPL --strategy ma_crossover
```

Every command writes a byte-stable JSON manifest (and parquet/HTML where relevant) under
`data_dir/{runs,optim,portfolio,cross_sectional}/<run_id>/`. Re-running with the same inputs is
reproducible to the byte (`--seed` defaults to 7). Run any command with `--help` for all options.

## Caveats (read before trusting a result)

- **Live data needs outbound network.** `alpha data pull` hits Yahoo (yfinance) and Coinbase (ccxt)
  — both verified working end-to-end. **Stooq is best-effort:** it now gates its free CSV behind an
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

## Paper trading (Phase 4 — scaffolded)

The execution side is wired: `alpha paper preflight` builds a nautilus `SandboxExecutionClient`
venue (fills with the *same* close-decide / next-open convention as the backtest) and constructs the
**same strategy class** a backtest runs — verifying backtest↔paper parity offline. Going live needs
the one piece the spec defers post-v1: a **live market-data adapter + credentials + network** (e.g. a
nautilus Binance/Bybit testnet config). Supply it as `data_clients` to
`alpha_cli._paper.run_paper(...)` on a networked host.

## Conversational agent (MCP server)

`alpha_mcp` is a stdio [MCP](https://modelcontextprotocol.io) server that exposes the whole
research loop as 10 tools — `data_pull`, `backtest_run`, `validate`, `optim_grid`,
`propfirm_run`, `backtest_portfolio` / `cross_sectional`, plus `get_run` / `list_runs` /
`list_strategies`. It is purely additive: each action tool **subprocesses the `alpha` CLI** and
returns the byte-stable manifest the run wrote, so the agent and the CLI share one store and the
CLI stays the single source of truth.

The repo ships a `.mcp.json`, so **Claude Code auto-launches it** (`uv run alpha-mcp`). For Claude
Desktop, add to `claude_desktop_config.json`:

```json
{ "mcpServers": { "alpha": { "command": "uv", "args": ["run", "alpha-mcp"],
  "cwd": "/path/to/Project-ALPHA" } } }
```

Then drive ALPHA in plain language: *"pull AAPL, run the gauntlet on a momentum strategy, then
check it against a Topstep combine."* No API keys, $0.

## Web IDE

`uv run alpha-web` serves a local web IDE at **http://127.0.0.1:8800** (loopback only, no auth):

- **Run browser** (`/`) — every stored run with pass / A–F Verdict badges.
- **Run detail** (`/runs/{id}`) — the manifest, an inline equity chart, and the embedded HTML tear
  sheet.
- **New run** (`/new`) — pick a command + arguments and watch it run **live** (streamed output).
- **Console** (`/console`) — run any `alpha` command and stream it.

Server-rendered FastAPI + Jinja + native `EventSource` (no build step, no CDN). Like the MCP
server it's purely additive — it subprocesses the `alpha` CLI and reads the artifacts. For true
conversational control, pair it with the `alpha` MCP server (above) in a Claude client.

## Not yet built (intentional)

- Live paper-trading data feed (the user-supplied adapter described above).
- Full-engine cross-sectional with per-instrument t+1 fills (a returns-level panel version ships now).
- FRED macro / regime filters (needs a non-OHLCV store).
