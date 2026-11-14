# Prove "Crypto history download that resumes safely" end to end

## What the owner wants

From the owner's direction of 2026-11-14 ("All 31 unproven features. Prove, built, implement,
improve all of them. 1 by 1."), passed on by the orchestrating session: run `crypto-backfill`
from start to finish through the installed `alpha`, offline against the recorded provider and for
real on the Dell's Binance history, fix what that run finds, and add the smoke check that lets it
become Working. Two known faults to confirm and fix if real: the Binance backfill plans the whole
month containing `--end` even when `--end` is the 1st; and a month that has only just ended may
not be published yet.

## What done looks like

- `--end 2026-11-01` (exclusive) plans nothing in November and lists nothing as "not published".
- A month that ended recently and is still missing on Binance is reported "not published yet"
  and is retried by the next run, instead of being recorded as a failure; an older missing month
  is still a loud failure.
- A smoke check runs the installed `alpha` through the recorded provider: a two-coin, two-month
  backfill with one missing month fails loud for that month only; after the month appears a rerun
  downloads only that month and verifies the finished ones first; a second writer is refused;
  the status command reports progress without any provider call or write.
- The real run on the Dell (on a copy of the data folder) is written down.

## How they will see it

```sh
uv run alpha crypto-data backfill binance market_bars --symbols BTCUSDT --quote USDT --category spot \
  --frequency 1d --start 2017-08-01 --end 2026-11-01 --ledger spot-1d-BTCUSDT --dry-run --json
```

## Out of scope

Bybit backfills (not run here); other Binance families; stored real data.
