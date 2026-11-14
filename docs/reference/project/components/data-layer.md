---
owner: project layer
sources:
  - packages/alpha-data/CONTEXT.md
verified: ccf5b56ad3eb
---

# Data layer

The data layer downloads market data (stocks, ETFs and crypto), stores it exactly as received,
and lets every later step read only what was known at a given moment. It also freezes the exact
data a test used into a snapshot that can be checked later.

## Why it exists

A backtest is only as honest as its data. If a test can see a price, a split or a list of index
members before they were public, the result is worthless, and with live capital at stake that is
not acceptable ([owner decisions](../owner-decisions.md#2026-11-14-precision-and-live-capital)).
The data layer is where that honesty is enforced.

## Its job in the research loop

Step 2 of the [research loop](../overview.md#the-research-loop): every experiment reads frozen,
point-in-time data from here. The triage sheet calls getting real history the platform's main
bottleneck.

## Intended design

- Each download keeps a receipt of where it came from and when it became available.
- Reads take an "as of" time and refuse anything not known at that time.
- Snapshots are immutable and identified by a hash of their content.
- Crypto data has its own governed store ([ADR-0032](../../../adr/0032-governed-crypto-data-house.md));
  daily stock data has one authoritative source ([ADR-0017](../../../adr/0017-authoritative-daily-data-and-broker-paper-boundary.md)).
- Development on the Dell uses synthetic data plus free, keyless real data (below); keyed
  providers and confirmation of real data wait for the Mac
  ([owner decisions](../owner-decisions.md#2026-11-14-dell-now-mac-later),
  [free real data](../owner-decisions-2.md#2026-11-14-free-real-data-on-the-dell-now)).

## What is real today

See the capabilities below on [STATUS.md](../../../../STATUS.md).

### Real data on the Dell

Everything here is **not yet confirmed**: free sources, not the authoritative stock source of
ADR-0017, not checked against an independent source, and usable for personal research and backtests
only. Each capability's real-data line on [STATUS.md](../../../../STATUS.md) starts with
"not yet confirmed"; on the data itself the existing labels say the same (crypto archives:
`state: qualified`, which means only that the mechanical checks passed; the CCXT copy in the
stock store: `quality_status: legacy_unqualified`).

- **Where:** `/home/hunta/alpha-clean-base/data`, outside any git tree, set up with
  `bash scripts/setup.sh --data-dir /home/hunta/alpha-clean-base/data --storage-reserve-gb 10`.
  Every command needs `export ALPHA_DATA_DIR=/home/hunta/alpha-clean-base/data` first.
- **Crypto, 2026-11-14:** Binance spot daily bars, quote USDT, for BTC, ETH, BNB, LTC, ADA, XRP,
  TRX, XLM, LINK, ATOM, DOGE, BCH, SOL, DOT and AVAX, from each pair's first full month on
  Binance to October 2026, from Binance's free monthly archives through
  `alpha crypto-data backfill`; plus one Binance spot market list (`market_membership`). BTC and
  ETH daily bars also went through `alpha data pull --source ccxt --exchange binance` into the
  stock store, so the stock backtest commands can read them. Totals and the exact commands:
  [verification record](../../../work/archive/2026-11/2026-11-14-free-real-data-dell/04-verify.md).
- **Binance's terms** (Binance Vision Dataset Terms, version 1.0, last updated 26 August 2026):
  free under CC BY-NC-SA 4.0 for, among other uses, "algorithmic historical backtesting for
  purely personal non-production research"; live trading on the data is not allowed. Raw files
  must never be published or shared.
- **Stocks: none yet.** Yahoo's terms forbid collecting data "using any automated means" without
  Yahoo's prior permission, and its data host's `robots.txt` disallows every path; Stooq answers
  automated requests with a "verify your browser" check, and its `robots.txt` disallows all but
  two search engines. ALPHA's `yfinance` and `stooq` adapters exist but were not used. Free stock
  history needs an owner decision (see the verification record).

### Limits

- **Stooq:** since 2026-11-14 the `stooq` downloader no longer answers Stooq's "verify your
  browser" check itself (it used to solve the check and pose as a desktop browser; getting past a
  bot check is not acceptable here). It now sends one request under a generic client name and, when
  challenged, refuses with a clear message. Stooq data already stored stays readable.
- **Yahoo (`yfinance`):** Yahoo's terms forbid collecting data from its services "using any
  automated means" without Yahoo's express prior permission. The `yfinance` downloader must not be
  used unless Yahoo has given that permission. It is kept, not deleted, because the owner has not
  decided its future (see the [verification record](../../../work/archive/2026-11/2026-11-14-free-real-data-dell/05-handoff.md)).
- **Binance monthly archives:** a month's file exists only after the month ends, and Binance
  publishes it 1 to 7 days later (once 12; measured 2026-11-14), so a backfill lists the current
  month, and a just-ended month whose file is still missing for up to 14 days, as "not published
  yet" rather than failing; the current month comes from
  the bounded live-service tail. A governed crypto snapshot may hold many months of many coins;
  the daily price reader used by the daily rule lane still reads one month per snapshot.

## Where it lives

- **Workspaces:** `packages/alpha-data`
- **Capabilities:** `stock-data`, `crypto-data`, `crypto-backfill`, `download-bookkeeping`,
  `funding-download`, `retained-coverage`, `crypto-snapshots`, `providers-and-jobs`
- Code: `packages/alpha-data/src/alpha_data/`; the `alpha data` and `alpha crypto-data` commands in
  `apps/alpha-cli/`.
- Tests: `tests/smoke/test_data_smoke.py`, `tests/smoke/test_crypto_data_smoke.py` (crypto downloads through an
  offline recorded provider, `tests/smoke/_recorded_provider.py`), and the data tests under `tests/unit/` and `tests/bias_guards/`.
- How to change it: [packages/alpha-data/CONTEXT.md](../../../../packages/alpha-data/CONTEXT.md).
- Plans: the `plans` of each capability above in `docs/roadmap/capabilities.toml`.
- Backlog: [offline price import](../../../roadmap/backlog/offline-data-import.md),
  [durable acquisition journal](../../../roadmap/backlog/controlstore-durable-acquisition.md).
- Decision records: [ADR-0004](../../../adr/0004-two-clock-corporate-actions.md),
  [ADR-0005](../../../adr/0005-point-in-time-firewall.md), [ADR-0017](../../../adr/0017-authoritative-daily-data-and-broker-paper-boundary.md),
  [ADR-0032](../../../adr/0032-governed-crypto-data-house.md),
  [ADR-0046](../../../adr/0046-crypto-snapshot-members-are-content-addressed.md).

## Decisions and open questions

- The owner no longer uses QuantPad ([log](../owner-decisions.md#2026-11-14-quantpad-no-longer-used)).
Decided: the unused QuantPad code is removed and old records stay readable
  ([log](../owner-decisions.md#2026-11-14-agents-merge-and-decide-routine-matters)).
- Triage, 2026-11-14 under the owner's delegation
  ([triage sheet](../../../roadmap/triage-2026-11.md)): cards 1, 3 and 4 KEEP; cards 2 (download bookkeeping) and B
  (funding modules) SHELVE, kept for a future download-budget policy and funding research.

## Never

- Never let a read see data that was not knowable at its "as of" time.
- Never change a snapshot or receipt after it is written.
- The rules: [data invariants](../../invariants/data.md) and
  [point-in-time reads](../../invariants/research-integrity.md#point-in-time-reads).
