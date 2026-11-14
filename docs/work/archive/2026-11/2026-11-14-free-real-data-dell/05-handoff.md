## What changed for you

- The Dell now holds real market data, not only made-up data. It lives in
  `/home/hunta/alpha-clean-base/data`, outside the code, with your 10 GB free-space reserve.
- **Crypto:** daily prices from Binance's free monthly archives for 15 major coins against USDT
  (BTC, ETH, BNB, LTC, ADA, XRP, TRX, XLM, LINK, ATOM, DOGE, BCH, SOL, DOT, AVAX), from each
  coin's first full month on Binance (August 2017 for BTC and ETH) to 31 October 2026, plus one
  list of every Binance spot market. All came in through ALPHA's own download command, which
  checks Binance's published checksum and every bar. BTC and ETH were also copied into the store
  the ordinary backtest commands read, and one backtest ran on them.
- **Stocks: none, on purpose.** Yahoo's terms forbid automated downloading without Yahoo's
  permission, and Stooq blocks automated downloads with a "verify your browser" check. Neither
  was used. One decision for you, below.
- **Everything is labelled not yet confirmed**, on the status page and in the data-layer page.
  Binance's terms allow this data for personal backtesting and research only, not for live
  trading.

**One decision for you: where free stock prices should come from.** Options:
1. Wait for the Mac and use Tiingo (the authoritative source already chosen; needs a key).
2. You download stock files yourself in a browser from a site whose terms allow personal use,
   and ALPHA gets an offline import command (scoped in the backlog as medium-sized; it also needs
   your decision on how snapshots name their source).
3. Ask Yahoo for permission, or accept their terms' risk yourself, and use the existing `yfinance`
   downloader. Not recommended.
Reply with the number.

## How to see it

In a terminal on the Dell, in the repository folder:

```sh
export ALPHA_DATA_DIR=/home/hunta/alpha-clean-base/data
uv run alpha data chart-datasets            # the 15 crypto price series, their dates and row counts
uv run alpha data snapshots                 # the frozen BTC and ETH snapshot
uv run alpha data verify free-binance-btc-eth-2026-11-14
```

The Workstation's chart picker shows the same series. Full commands and outputs:
`docs/work/archive/2026-11/2026-11-14-free-real-data-dell/04-verify.md`.

## Checks run

See `04-verify.md`: real downloads, as-of reads, two snapshots verified, one backtest, a
Binance archive-versus-live comparison, and `uv run python scripts/gate.py check --all`.

## Who built and who reviewed

- No code was written; every step used existing commands. Claude (Opus) ran the downloads and
  wrote the documents.
- Review: Codex through `scripts/handoff.py review` (see `04-verify.md`), then CI.

## The one document updated

`docs/reference/project/components/data-layer.md` (section "Real data on the Dell"), plus the
owner-decisions log entry, the capability map's real-data lines and the regenerated status page.

## What I am unsure about

- The Binance archive and Binance's live price service agree on every price but not on volume on
  about 10 days per coin (up to 2.5%), so trading volume on old days can be revised.
- A fault in the existing crypto snapshot checks: downloading a month twice (it happened once
  here, BTC January 2024) makes a snapshot of that month fail verification, and with it the
  whole-store check `alpha crypto-data storage-verify`. Nothing wrong is ever accepted, but that
  one test snapshot is now permanently refused. A small fix is proposed in `04-verify.md`.
- A governed crypto snapshot holds one month of one coin; a multi-year crypto study needs that
  limit lifted (not done here).
- ALPHA's existing `stooq` downloader answers Stooq's browser check itself; that is getting past a
  bot check, and you may want it removed or disabled.

## Protected files touched

None.
