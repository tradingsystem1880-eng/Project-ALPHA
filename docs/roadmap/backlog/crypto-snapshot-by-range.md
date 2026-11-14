# Freeze a crypto snapshot by coin and date range

**Status:** Idea
**Rough size:** M

## Problem / why

Found on 2026-11-14 while proving `crypto-snapshots`. Freezing one coin's full daily history
means passing every monthly manifest id by hand: the BTC and ETH history on the Dell needed 222
`--manifest-id` options, collected from `alpha crypto-data coverage --json` with a script, and a
month downloaded twice had to be resolved to one id by hand. That is the slowest step between
downloaded data and a research-ready snapshot, and a hand-built list can silently leave out a
month.

## What "done" looks like

- One command, for example `alpha crypto-data snapshot-create --select binance:market_bars:1d
  --instruments BTCUSDT,ETHUSDT --start 2017-08-01 --end 2026-11-01`, picks every qualified
  monthly manifest of those identities that covers the range, resolves repeated captures with
  the ADR-0046 rule, and refuses when a day is missing, two members overlap or a month is not
  qualified (listing them), instead of freezing a gappy snapshot.
- The selection is deterministic: the same store and arguments give the same snapshot id, and the
  output lists the chosen manifest ids so the snapshot can be re-created by hand.
- The existing explicit `--manifest-id` form is unchanged.

## Dependencies

None. New code goes in a new module (`crypto_data_cmds.py` may not grow).
