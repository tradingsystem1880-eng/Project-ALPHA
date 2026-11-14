# Check a coin's whole downloaded daily history in one step

**Status:** Idea
**Rough size:** M

## Problem / why

Found on 2026-11-14 while proving `retained-coverage`. The completeness check
(`alpha crypto-data quality <manifest-id> --coverage-start ... --as-of ...`) reads one stored file
at a time, and the Binance backfill stores one file per month. Checking that every coin's history
on the Dell has no missing day took 1,426 separate runs, six at a time, driven by a script outside
ALPHA. Gaps between months, a month missing entirely, or two months
that overlap are invisible to a one-file check.

## What "done" looks like

- One read-only command, for example `alpha crypto-data history-coverage binance market_bars
  BTCUSDT --frequency 1d --start 2017-08-17 --end 2026-11-01 --as-of 2026-11-14T00:00:00Z`, takes
  every qualified manifest of that identity (repeated captures resolved by the ADR-0046 rule),
  joins them on the daily grid and reports missing days, duplicated or conflicting days across
  files, and off-grid rows, with the same bounds and exit codes as the one-file check.
- The Workstation's Coverage & Quality tab can show it for a chosen coin.

## Dependencies

None. New code goes in a new module (`crypto_data_cmds.py` may not grow).
