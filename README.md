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
uv run alpha data pull AAPL  --source yfinance --start 2010-01-01 --end 2024-12-31
uv run alpha data pull spy.us --source stooq   --start 2010-01-01 --end 2024-12-31   # equities/ETF/commodity/FX
uv run alpha data pull BTC/USD --source ccxt    --start 2018-01-01 --end 2024-12-31   # crypto

# 2. (optional) Freeze an immutable, content-hashed snapshot for reproducibility
uv run alpha data snapshot snap-2024 AAPL SPY BTC/USD
uv run alpha data verify   snap-2024

# 3. Backtest one fixed-parameter strategy (ts_momentum | ma_crossover | mean_reversion | breakout)
uv run alpha backtest run AAPL --strategy ma_crossover --param fast=20 --param slow=100

# 4. Run the full validation gauntlet → manifest + parquet + HTML tear sheet
uv run alpha validate AAPL --strategy ts_momentum            # --null-model bootstrap|student_t|garch

# 5. Search parameters with overfitting controls (Deflated Sharpe + PBO + SPA), not a bare best Sharpe
uv run alpha optim grid AAPL --grid lookback=126,252,504 --grid vol-window=21,63

# 6. Multi-asset: a diversified basket, or a cross-sectional long/short book
uv run alpha backtest portfolio SPY QQQ GLD BTC/USD --weighting inverse_vol
uv run alpha backtest cross-sectional SPY QQQ IWM GLD USO --top-quantile 0.3

# 7. Re-display any stored run (no engine re-run)
uv run alpha report <run_id>
```

Every command writes a byte-stable JSON manifest (and parquet/HTML where relevant) under
`data_dir/{runs,optim,portfolio,cross_sectional}/<run_id>/`. Re-running with the same inputs is
reproducible to the byte (`--seed` defaults to 7). Run any command with `--help` for all options.

## Caveats (read before trusting a result)

- **Live data needs outbound network.** `alpha data pull` hits Yahoo / Stooq / ccxt. In a sandbox
  with a restricted egress allowlist these hosts may be blocked (HTTP 403); run on a machine (or in
  an environment whose network policy permits them) with internet access. The pure parsers are
  unit-tested offline; the live `fetch` paths are `@pytest.mark.network` (run with `-m network`).
- **CASH accounts can't be levered or overspend.** With the default `--account-type CASH`, a
  vol-targeted notional that exceeds buying power (e.g. a low-volatility asset plus fees) has its
  orders rejected — the run **fails loud** with guidance rather than silently reporting flat equity.
  Use `--account-type MARGIN`, a lower `--target-vol`, or `--max-leverage` below 1.
- **Free data is survivorship-biased and (for Stooq) provider-adjusted.** Documented limitations of
  the $0 data tier; the bias-guard tests make the assumptions explicit.
- **Validation has been exercised on synthetic + offline-fixture data.** It has not yet been run
  against a live market pull end-to-end (blocked by the above network constraint).

## Not yet built (intentional)

- Paper trading (Phase 4, nautilus `SandboxExecutionClient`) — needs live feeds / crypto testnets.
- Full-engine cross-sectional with per-instrument t+1 fills (a returns-level panel version ships now).
- FRED macro / regime filters (needs a non-OHLCV store).
