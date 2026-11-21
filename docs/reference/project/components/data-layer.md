---
owner: project layer
sources:
  - packages/alpha-data/CONTEXT.md
verified: d1c3a536e0695e17
---

# Data layer

The data layer downloads market data (stocks, ETFs and crypto), stores it exactly as received, and lets every later step
read only what was known at a given moment. It also freezes the exact data a test used into a snapshot that can be checked later.

## Why it exists

A backtest is only as honest as its data. If a test can see a price, a split or a list of index members before they were
public, the result is worthless, and with live capital at stake that is not acceptable
([owner decisions](../owner-decisions.md#2026-11-14-precision-and-live-capital)). The data layer is where that honesty is enforced.

## Its job in the research loop

Step 2 of the [research loop](../overview.md#the-research-loop): every experiment reads frozen, point-in-time data from here.
The triage sheet calls getting real history the platform's main bottleneck.

## Intended design

- Each download keeps a receipt of where it came from and when it became available.
- Reads take an "as of" time and refuse anything not known at that time.
- Snapshots are immutable and identified by a hash of their content.
- Crypto data has its own governed store ([ADR-0032](../../../adr/0032-governed-crypto-data-house.md));
  daily stock data has one authoritative source ([ADR-0017](../../../adr/0017-authoritative-daily-data-and-broker-paper-boundary.md)).
- Development on the Dell uses synthetic data plus free real data (below), with Alpaca's free
  plan as the interim stock source
  ([ADR-0047](../../../adr/0047-alpaca-interim-stock-source.md)); other keyed providers and
  confirmation of real data wait for the Mac
  ([owner decisions](../owner-decisions.md#2026-11-14-dell-now-mac-later),
  [free real data](../owner-decisions-2.md#2026-11-14-free-real-data-on-the-dell-now)).

## What is real today

See the capabilities below on [STATUS.md](../../../../STATUS.md).

### Daily data health
`alpha data health` checks one stored daily series for adjustment, timestamp, gap and survivorship faults, and saves the report
with a hash of its inputs. Rule tests and setup runs look up the report for each series and stop on a failure unless the user records a reason.
Their summaries show the worst verdict. RD-Agent panels are next. [Tool card](../../../../research/tools/data-health.md)
### Context data
Macro series (Treasury yields, the VIX, FRED/ALFRED), SEC EDGAR filings and Form 4 insider transactions, and Binance and Bybit funding and
open interest are stored with the time each value was known, apart from the bar store. They explain research results and never feed a backtest.
The command is `alpha context`. Live checks of the SEC and FRED services are not yet run. Rules and details:
[data context rules](../../invariants/data-context.md).

### Real data on the Dell

Everything here is **not yet confirmed**: free sources, not the authoritative stock source of
ADR-0017, not checked against an independent source, and usable for personal research and backtests
only. Each capability's real-data line on [STATUS.md](../../../../STATUS.md) starts with
"not yet confirmed"; on the data itself the existing labels say the same (crypto archives:
`state: qualified`, which means only that the mechanical checks passed; the CCXT copy in the
stock store and the Yahoo stock prices: `quality_status: legacy_unqualified`; an Alpaca
download shows `quality_status: passed`, which means only that the mechanical checks passed).

What was downloaded (15 crypto pairs, 16 US stocks and ETFs, a small set of intraday bars), where it lives and how it was checked:
[free sources on the Dell](../../invariants/data-free-sources.md#real-data-on-the-dell).

### Limits

Free sources limit what the data may be used for: Yahoo prices are for personal research only, Alpaca's free plan has no latest-15-minutes data,
Binance publishes monthly files days late, and Stooq no longer answers its bot check. The terms and the exact limits are in
[provider limits](../../invariants/data-free-sources.md#stooq-and-yahoo-limits).

## Where it lives

- **Workspaces:** `packages/alpha-data`
- **Capabilities:** `stock-data`, `intraday-bars`, `crypto-data`, `crypto-backfill`,
  `data-health`, `data-health-on-runs`, `retained-coverage`, `crypto-snapshots`, `providers-and-jobs`, `macro-context`,
  `filing-events`, `crypto-derivatives-context`, `positioning-short-volume-context`, `published-factor-reference`
- Code: `packages/alpha-data/src/alpha_data/`; the `alpha data` and `alpha crypto-data` commands in
  `apps/alpha-cli/`.
- Tests: `tests/smoke/test_data_smoke.py`, `tests/smoke/test_crypto_data_smoke.py` (crypto downloads through an
  offline recorded provider, `tests/smoke/_recorded_provider.py`), and the data tests under `tests/unit/` and `tests/bias_guards/`.
- How to change it: [packages/alpha-data/CONTEXT.md](../../../../packages/alpha-data/CONTEXT.md).
- **Plan:** [stage 2](../../../roadmap/production-scope.md#2-data-and-context) of the checklist; [limits](../../../roadmap/backlog/data-provider-limits.md).
- Backlog: [offline price import](../../../roadmap/backlog/offline-data-import.md),
  [one crypto store for backtests](../../../roadmap/backlog/governed-crypto-for-backtests.md),
  [durable acquisition journal](../../../roadmap/backlog/controlstore-durable-acquisition.md).
- Decision records: [ADR-0004](../../../adr/0004-two-clock-corporate-actions.md),
  [ADR-0005](../../../adr/0005-point-in-time-firewall.md), [ADR-0017](../../../adr/0017-authoritative-daily-data-and-broker-paper-boundary.md),
  [ADR-0032](../../../adr/0032-governed-crypto-data-house.md),
  [ADR-0046](../../../adr/0046-crypto-snapshot-members-are-content-addressed.md),
  [ADR-0047](../../../adr/0047-alpaca-interim-stock-source.md),
  [ADR-0048](../../../adr/0048-daily-rule-lane-binding-and-named-months.md).

## Decisions and open questions

- The owner no longer uses QuantPad; the unused QuantPad code is removed and old records stay readable
  ([log](../owner-decisions.md#2026-11-14-quantpad-no-longer-used)).
- Triage 2026-11-14 ([sheet](../../../roadmap/triage-2026-11.md)): cards 1, 3, 4 KEEP; card 2 (download
  bookkeeping) was shelved, then deleted 2026-11-21. Card B (Bybit funding download modules)
  was shelved, then deleted 2026-11-18 (PR #261); funding context comes from the Binance importer and Bybit import.
- [Data health request](../owner-decisions-5.md#2026-11-18-request-one-data-health-report): built for rule tests and setups.

## Never

- Never let a read see data that was not knowable at its "as of" time.
- Never change a snapshot or receipt after it is written.
- The rules: [data invariants](../../invariants/data.md) and
  [point-in-time reads](../../invariants/research-integrity.md#point-in-time-reads).
