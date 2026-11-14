# Prove "Freeze crypto data into exact snapshots and check them" end to end

## What the owner wants

From the owner's direction of 2026-11-14 ("All 31 unproven features. Prove, built, implement,
improve all of them. 1 by 1."), passed on by the orchestrating session: run `crypto-snapshots`
from start to finish through the installed `alpha`, offline against the recorded provider and for
real on the Dell's Binance history, fix what that run finds, and add the smoke check that lets it
become Working.

## What done looks like

- A smoke check downloads several months of two coins through the recorded provider with the
  installed `alpha`, freezes them into one snapshot (same name in any option order), verifies it
  for research, sees the whole-store check pass, survives a repeat download of a month already in
  the snapshot, refuses overlapping members, and refuses the snapshot once a frozen file is
  changed. The installed `alpha-web` verifies the snapshot through its API.
- The real run on the Dell is written down: the existing snapshots and the whole store verify on
  the real folder; a full-history BTC and ETH snapshot (222 months) is created and verified on a
  copy of it.

## How they will see it

```sh
uv run alpha crypto-data snapshot-create --manifest-id <id> --manifest-id <id> --json
uv run alpha crypto-data snapshot-verify <snapshot-id> --required-family market_bars --json
```

## Out of scope

`snapshot-query` (it reads DefiLlama TVL pages only, a provider the recorded provider does not
serve); the daily-rule price reader (approval-bound); stored real data.
