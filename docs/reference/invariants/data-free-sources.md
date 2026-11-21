---
owner: data layer
sources:
  - packages/alpha-data/src/alpha_data/adapters/**
  - packages/alpha-data/src/alpha_data/ingest.py
  - apps/alpha-cli/src/alpha_cli/data_cmds.py
verified: 9fb21bc8f6eaf330
---

# Data layer: free sources on the Dell and provider limits

What was downloaded from free sources for development on the Dell, and what each provider does and does not allow.
None of it is confirmed real data. The rules for reads and storage are in [data.md](data.md).

## Real data on the Dell

- **Where:** `/home/hunta/alpha-clean-base/data`, outside any git tree, set up with `bash scripts/setup.sh --data-dir
  /home/hunta/alpha-clean-base/data --storage-reserve-gb 10`. Every command needs `export
  ALPHA_DATA_DIR=/home/hunta/alpha-clean-base/data` first.
- **Crypto, 2026-11-14:** Binance spot daily bars, quote USDT, for BTC, ETH, BNB, LTC, ADA, XRP, TRX, XLM, LINK, ATOM,
  DOGE, BCH, SOL, DOT and AVAX, from each pair's first full month on Binance to October 2026, from Binance's free
  monthly archives through `alpha crypto-data backfill`; plus one Binance spot market list (`market_membership`). BTC
  and ETH daily bars also went through `alpha data pull --source ccxt --exchange binance` into the stock store, so the
  stock backtest commands can read them. Totals and the exact commands: [verification record][free-data].
- **Binance's terms** (Binance Vision Dataset Terms, version 1.0, last updated 26 August 2026): free under CC BY-NC-SA
  4.0 for, among other uses, "algorithmic historical backtesting for purely personal non-production research"; live
  trading on the data is not allowed. Raw files must never be published or shared.

## Stocks and intraday bars on the Dell

- **Stocks, 2026-11-14:** daily bars from Yahoo through `alpha data pull --source yfinance` for SPY, QQQ, IWM, DIA,
  TLT, IEF, GLD, AAPL, MSFT, AMZN, GOOGL, NVDA, META, JPM, XOM and JNJ, each from its first day on Yahoo (1990 at the
  earliest) to 13 November 2026: 117,229 bars, with splits and dividends, frozen in snapshot
  `free-yfinance-stocks-2026-11-14`. These are today's large companies, so the set is survivor-biased; use it for
  plumbing and exploration, not for claims about a universe. Totals and commands: [verification record][alpaca-data].
- **Stocks from Alpaca, 2026-11-14:** `alpha data pull --source alpaca` (Alpaca's free plan, consolidated SIP daily
  history, raw prices plus splits and dividends, [ADR-0047](../../adr/0047-alpaca-interim-stock-source.md)) for the
  same set minus QQQ, 2016-01-04 to 2026-11-13: 15 symbols, 40,995 bars, snapshot `alpaca-starter-2026-11-14`, in its
  own folder `/home/hunta/alpha-clean-base/data-alpaca` (one source per price series). QQQ was refused: Alpaca lists
  one 2022 dividend twice with different pay dates. Against Yahoo, prices match almost everywhere; the differences
  (March 2020 closes, a few stray highs and lows in Alpaca, volume, missing ETF dividends in Alpaca) are in the
  verification record. Owner steps: [Alpaca runbook](../../operations/alpaca-stock-data.md).
- **Intraday bars, 2026-11-14** (owner decision 2026-11-15: no daily-only rule; never high-frequency trading, so time
  bars of one minute or longer only), all in their own folder `/home/hunta/alpha-clean-base/data-intraday`, so the
  daily data is never rewritten:
  - Crypto through `alpha crypto-data backfill binance market_bars --category spot`: BTCUSDT and ETHUSDT 1-hour bars,
    Nov 2025 to Oct 2026 (8,760 each), and 5-minute bars, Aug to Oct 2026 (26,496 each), all qualified; crypto
    snapshot `55870c28d0a3...`, verified.
  - Stocks through `alpha data pull --source alpaca --timeframe 5m|1h`: SPY and AAPL, 3 Aug to 13 Nov 2026, 5-minute
    (14,184 and 14,168 bars, pre-market and after-hours included) and 1-hour (1,184 each), all passing the quality
    gate; snapshots `alpaca-intraday-5m-2026-11-14` and `alpaca-intraday-1h-2026-11-14`.
  - Rules: [bar timeframes](data-bar-timeframes.md). Two system-test backtests read them (BTC 1-hour moving-average
    run `c5b121832b4e4df9`; SPY 5-minute breakout run `e7554b11b3ccbb4f`, on the snapshot as `2a71a809e51adc11`).

## Stooq and Yahoo limits

- **Stooq:** since 2026-11-14 the `stooq` downloader no longer answers Stooq's "verify your browser" check itself (it
  used to solve the check and pose as a desktop browser; getting past a bot check is not acceptable here). It now
  sends one request under a generic client name and, when challenged, refuses with a clear message. Stooq data already
  stored stays readable.
- **Yahoo (`yfinance`):** Yahoo's terms forbid collecting data from its services "using any automated means" without
  Yahoo's express prior permission, and Yahoo has not given it. The owner was told this on 2026-11-14 and decided to
  use the `yfinance` downloader for now, for personal research only, until Alpaca or the Mac is ready ([owner
  decisions](../project/owner-decisions-2.md#2026-11-14-any-free-stock-source-now-alpaca-account-to-follow)). One
  modest sequential download was made (above). The owner's Alpaca key was set the same day, so Alpaca replaces Yahoo
  for new stock downloads; the Yahoo copy stays for comparison. Yahoo's prices are rebuilt from its split-adjusted
  series (the adapter multiplies the splits back), so they carry small rounding.

## Alpaca limits

- **Alpaca intraday:** bars of 1 to 59 minutes and 1 to 23 hours come from the same free plan and feed; each bar is
  stamped at its start and covers all hours Alpaca returns (04:00 to 20:00 New York). Hourly bars follow the clock
  (the 09:00 bar holds 09:00-09:59, half pre-market), so session hours are resampled from minute bars. No bar exists
  for a minute without qualifying trades, so illiquid names at 1 minute will fail the gap check. A full 2016-onward
  1-minute pull exceeds the 200-page cap. Whether Alpaca later revises historical minute bars is not documented.
- **Alpaca:** free Basic plan only: history since 2016; the latest 15 minutes are not available, so ALPHA asks only
  for completed sessions; 200 calls a minute; personal, non-commercial use, and the data must never be published,
  shared or committed. The corporate-actions list has no announcement date, so an action is treated as known only from
  its ex-date. A symbol with a stock dividend, spin-off or unit split in the requested window is refused, and a split
  the price series contradicts fails loud; dividends have no such cross-check, and Alpaca misses some older ETF
  dividends (SPY 2016-03-18 and 2018-06-15, for example). Daily highs and lows are built from trades and can carry a
  stray print (NVDA 2024-06-10 high 195.95). An Alpaca download never replaces Tiingo data and never shares a series
  with another source, either way (hence its own data folder).

## Binance monthly archives

- **Binance monthly archives:** a month's file exists only after the month ends, and Binance publishes it 1 to 7 days
  later (once 12; measured 2026-11-14), so a backfill lists the current month, and a just-ended month whose file is
  still missing for up to 14 days, as "not published yet" rather than failing; the current month comes from the
  bounded live-service tail. A governed crypto snapshot may hold many months of many coins; the daily price reader
  used by the daily rule lane reads every month named for BTCUSDT (one stored copy per month), refusing gaps, overlaps
  and unnamed months in the range ([ADR-0048](../../adr/0048-daily-rule-lane-binding-and-named-months.md)).

[free-data]:
  https://github.com/tradingsystem1880-eng/Project-ALPHA/blob/pre-thin-2026-11-14/docs/work/archive/2026-11/2026-11-14-free-real-data-dell/04-verify.md
[alpaca-data]:
  https://github.com/tradingsystem1880-eng/Project-ALPHA/blob/pre-thin-2026-11-14/docs/work/archive/2026-11/2026-11-14-alpaca-stock-data/04-verify.md
