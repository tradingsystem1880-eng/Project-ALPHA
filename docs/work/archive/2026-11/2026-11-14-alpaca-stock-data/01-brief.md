# Alpaca stock data, and free stock prices now

## What the owner wants

Two decisions on 2026-11-14:

- "Yes just use free stock api like finance or alpaca for now until mac is available"
  ([owner decisions](../../../../reference/project/owner-decisions-2.md#2026-11-14-free-stock-prices-from-a-free-service-until-the-mac)).
- "Just use any free api. I can make an alpaca account in a few hours whej I have time tho"
  ([owner decisions](../../../../reference/project/owner-decisions-2.md#2026-11-14-any-free-stock-source-now-alpaca-account-to-follow)).
  The owner had been told that Yahoo's terms forbid automated collection.

In one sentence: real daily stock and ETF prices on the Dell now from the existing `yfinance`
downloader, and an `alpaca` downloader ready for the moment the owner sets an Alpaca key, both
labelled not yet confirmed.

## What done looks like

- Alpaca's current documentation and terms read and quoted, with dates, before any code.
- A modest starter download through `alpha data pull --source yfinance` (one polite sequential
  pass), frozen in a snapshot, verified, and read back as of a date.
- An `alpaca` adapter following the adapter contract: exact provider bytes kept in an immutable
  receipt, raw prices plus split and dividend actions, fail loud on gaps, pagination faults,
  malformed or partial responses, bounded retries that respect the rate limit, keys only from
  `APCA_API_KEY_ID` and `APCA_API_SECRET_KEY`, never written or printed.
- Wired into `alpha data pull`, the provider registry and `alpha provider check`.
- Offline tests with hand-built responses; no key, no network.
- An owner runbook: create the account, make the key, set the two variables, run the download.
- Honest labels: everything here is not yet confirmed; Tiingo stays the authoritative source.

## How they will see it

`export ALPHA_DATA_DIR=/home/hunta/alpha-clean-base/data`, then `uv run alpha data snapshots` and
`uv run alpha data candles AAPL --snapshot free-yfinance-stocks-2026-11-14 --end 2020-08-28 --json`;
after setting a key, the runbook in `docs/operations/alpaca-stock-data.md`.

## Out of scope

Live Alpaca calls (no key exists yet), Alpaca trading or paper accounts, Tiingo, hash-bound
research or validation code, the daily-rule files and RD-Agent worker other agents are changing,
data files in git, and getting past any bot check (Stooq stays refused).
