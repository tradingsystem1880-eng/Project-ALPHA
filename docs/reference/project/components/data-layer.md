---
owner: project layer
sources:
  - packages/alpha-data/CONTEXT.md
  - docs/roadmap/capabilities.toml
  - docs/roadmap/triage-2026-11.md
verified: f89aa1bb78af
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
- Development on the Dell uses synthetic data; real providers are confirmed on the Mac later
  ([owner decisions](../owner-decisions.md#2026-11-14-dell-now-mac-later)).

## What is real today

See the capabilities below on [STATUS.md](../../../../STATUS.md).

## Where it lives

- **Workspaces:** `packages/alpha-data`
- **Capabilities:** `stock-data`, `crypto-data`, `crypto-backfill`, `download-bookkeeping`,
  `funding-download`, `retained-coverage`, `crypto-snapshots`, `providers-and-jobs`, `quantpad-archive`
- Code: `packages/alpha-data/src/alpha_data/`; the `alpha data` and `alpha crypto-data` commands in
  `apps/alpha-cli/`.
- Tests: `tests/smoke/test_data_smoke.py`, and the data tests under `tests/unit/` and `tests/bias_guards/`.
- How to change it: [packages/alpha-data/CONTEXT.md](../../../../packages/alpha-data/CONTEXT.md).
- Plans: the `plans` of each capability above in `docs/roadmap/capabilities.toml`.
- Backlog: [offline price import](../../../roadmap/backlog/offline-data-import.md),
  [durable acquisition journal](../../../roadmap/backlog/controlstore-durable-acquisition.md),
  [QuantPad code removal](../../../roadmap/backlog/quantpad-code-removal.md).
- Decision records: [ADR-0004](../../../adr/0004-two-clock-corporate-actions.md),
  [ADR-0005](../../../adr/0005-point-in-time-firewall.md), [ADR-0017](../../../adr/0017-authoritative-daily-data-and-broker-paper-boundary.md),
  [ADR-0032](../../../adr/0032-governed-crypto-data-house.md).

## Decisions and open questions

- The owner no longer uses QuantPad ([log](../owner-decisions.md#2026-11-14-quantpad-no-longer-used)).
  Owner to confirm: delete the remaining QuantPad code now (triage card D), keeping old records readable?
- Triage cards 1, 2, 3, 4 and B are waiting for the owner ([triage sheet](../../../roadmap/triage-2026-11.md)).
  Card 2 and B depend on whether the owner wants download budgets at all (question 2 on that sheet).

## Never

- Never let a read see data that was not knowable at its "as of" time.
- Never change a snapshot or receipt after it is written.
- The rules: [data invariants](../../invariants/data.md) and
  [point-in-time reads](../../invariants/research-integrity.md#point-in-time-reads).
