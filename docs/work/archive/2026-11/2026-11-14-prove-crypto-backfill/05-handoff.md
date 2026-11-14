## What changed for you

- **"Crypto history download that resumes safely" is proven end to end and counts as Working.**
  A new automatic check runs a two-coin, two-month Binance backfill with the real `alpha` program
  against a recorded copy of Binance on this computer: the one missing month fails loudly and
  alone; once it appears, a rerun first re-checks the three finished months and downloads only the
  missing one; a second backfill at the same time is refused; the status command answers without
  downloading or changing anything.
- **`--end` on the 1st no longer reaches into that month.** `--end 2026-11-01` means up to 31
  October, as the help says. Before, from 1 December a rerun of your downloads would have fetched
  November too, and the status listed November as "not published" although you never asked for it.
- **No false failure just after a month ends.** Binance publishes a finished month's file 1 to 7
  days after the month ends (once 12 days; measured on 2026-11-14 from the files' dates). For 14
  days a missing file is now "not published yet" and the next run tries again; after that it is a
  real failure, as before.
- Run for real on a copy of your data folder (details in the verification record).

## How to see it

```sh
uv run alpha crypto-data backfill binance market_bars --symbols BTCUSDT --quote USDT --category spot \
  --frequency 1d --start 2017-08-01 --end 2026-11-01 --ledger spot-1d-BTCUSDT --dry-run --json
```

## What I am unsure about

- The 14-day grace rests on twelve months of one coin's file dates; if Binance ever publishes later,
  the month is reported as a failure (loud, not silent) and a rerun picks it up.
- Bybit backfills are still not run end to end.
- `backfill-status` exits 0 when its inspection finishes even if a month failed; the failure is in
  its counts and `next_action`. That is the existing design, kept.
