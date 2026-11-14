## What changed for you

- **Real stock prices are on the Dell**, from two free sources, both labelled not yet confirmed:
  - **Yahoo**, as you decided: 16 US stocks and ETFs (SPY, QQQ, IWM, DIA, TLT, IEF, GLD, AAPL,
    MSFT, AMZN, GOOGL, NVDA, META, JPM, XOM, JNJ), each from its first day on Yahoo (1990 at the
    earliest) to 13 November 2026, in the main data folder, snapshot
    `free-yfinance-stocks-2026-11-14`.
  - **Alpaca**, with the key you set: the same symbols except QQQ, 2016 to 13 November 2026, in
    their own folder `/home/hunta/alpha-clean-base/data-alpaca`, snapshot
    `alpaca-starter-2026-11-14`. ALPHA never mixes two sources in one price series, which is why
    Alpaca has its own folder.
- **A new `alpaca` downloader** (`alpha data pull --source alpaca`). It keeps every Alpaca answer
  byte for byte, stores raw prices with splits and dividends, cross-checks every split against
  Alpaca's own split-adjusted prices, and refuses anything it cannot get exactly right. Your key
  is read only from the two variables and never stored or shown.
- **Alpaca's terms**: free for your own personal, non-commercial use; never publish or share the
  data. History starts in 2016.

## What the comparison showed

Alpaca and Yahoo agree on prices on almost every day. They differ on a few days in March 2020,
on a handful of single stray highs and lows in Alpaca (NVDA's high on 10 June 2024 reads 195.95
when the day traded near 120), on volume, and Alpaca is missing a few older ETF dividends (SPY in
March 2016 and June 2018, for example). Details: `04-verify.md`.

## How to see it

```sh
cd /home/hunta/alpha-clean-base/Project-ALPHA
ALPHA_DATA_DIR=/home/hunta/alpha-clean-base/data uv run alpha data snapshots
ALPHA_DATA_DIR=/home/hunta/alpha-clean-base/data-alpaca uv run alpha data snapshots
ALPHA_DATA_DIR=/home/hunta/alpha-clean-base/data-alpaca uv run alpha data candles NVDA \
  --snapshot alpaca-starter-2026-11-14 --start 2024-06-05 --end 2024-06-10 --json
```

Future downloads: `docs/operations/alpaca-stock-data.md`.

## Checks run

Offline tests with made-up responses (no key, no network), the project gate, one live provider
check, the live starter download, snapshots verified, as-of reads across a split, and the
Alpaca-against-Yahoo comparison. All in `04-verify.md`.

## Who built and who reviewed

- Codex built the downloader, its wiring and tests from the plan (hard class, 16 minutes, two
  fix rounds); Claude finished the gate fixes, corrected the corporate-action field names, and
  wrote the documents.
- A separate Claude reviewer found two high, two medium and three low problems; all were fixed
  or recorded (table in `04-verify.md`). Then CI.

## What I am unsure about

- QQQ is refused: Alpaca lists its September 2022 dividend twice with different pay dates. The
  Yahoo copy of QQQ is unaffected. Fixing this needs a rule for which record to trust; not built.
- Alpaca misses some older ETF dividends, and nothing checks dividends the way splits are checked.
  Returns that include dividends can be slightly low on Alpaca data. A dividend cross-check
  (Alpaca's dividend-adjusted series) would close this; not built.
- Stray trades can set a daily high or low in Alpaca's bars; rules that use highs or lows should
  be aware.
- A ticker renamed inside the requested window fails loud rather than being handled.

## Protected files touched

None.
