# Verification: free real market data on the Dell

Run on the Dell on 2026-11-14 (UTC) from branch `m5/free-real-data` at `ccf5b56a`. Every
command below ran with `export ALPHA_DATA_DIR=/home/hunta/alpha-clean-base/data`. All data
here is **not yet confirmed** (free sources; see the
[data layer](../../../../reference/project/components/data-layer.md#real-data-on-the-dell)).

## Data folder

`bash scripts/setup.sh --data-dir /home/hunta/alpha-clean-base/data --storage-reserve-gb 10`
created `crypto/storage-config.json` (disk identity of `/dev/sda2`, ext4) with the owner's
reserve and printed: `free: 58.9 GB of 122.3 GB`,
`reserve: 10.0 GB — owner-set reserve 10.0 GB, decided by owner on 2026-11-14`.
`alpha crypto-data storage` then reported `"state": "ready"`.

Total stored after all downloads: 37,469,316 bytes (about 37 MB; budget 8 GB), of which raw
Binance archives 29 MB, normalized Parquet 12 MB, manifests 12 MB, checksum-verified download
cache 5.8 MB.

## Sources and their terms (checked before any bulk download)

| Source | What was checked | Result |
|---|---|---|
| Binance Vision archives (`data.binance.vision`) | Binance Vision Dataset Terms PDF, version 1.0, last updated 26 August 2026 (sha256 `0ec62cd2…121f`) | Used. CC BY-NC-SA 4.0; permitted uses include "algorithmic historical backtesting for purely personal non-production research"; section 4.2 forbids live proprietary trading on the data; 4.3 forbids hosting or redistributing it; 7.1 asks to keep to posted rate limits. No rate limit is published for the archive host (inferred: none stated). Downloads ran one file at a time. |
| Binance public REST (`api.binance.com`, through CCXT) | The Vision terms cover "data.binance.vision and associated endpoints"; Binance's general Terms of Use page renders by script and could not be read | Used for 2 symbols, a few dozen requests with CCXT's built-in rate limiting. Whether the REST API falls under the Vision terms is inferred, not confirmed. |
| Yahoo Finance (`query1.finance.yahoo.com`) | Yahoo Terms of Service section 2(d); `robots.txt` | Not used. The terms forbid collecting data from the services "using any automated means" without Yahoo's "express, prior permission"; `robots.txt` on the data host is `Disallow: /` for every agent. One probe request was made before reading them. |
| Stooq (`stooq.com`) | One request with a generic client name; `robots.txt` | Not used. It answered with a JavaScript "verify your browser" page; `robots.txt` allows only Bingbot and Googlebot. ALPHA's `stooq` adapter solves that check itself, so it was not run. |

Every request sent a generic client name (`Project-ALPHA/1.0`, CCXT's default, or
`alpha-research-client/0.1` for the probes); no personal details.

## Downloads

Crypto archives, one ledger per pair, sequential (script kept outside the repository):

```sh
uv run alpha crypto-data backfill binance market_bars --symbols BTCUSDT --quote USDT \
  --category spot --frequency 1d --start 2017-08-01 --end 2026-11-01 --ledger spot-1d-BTCUSDT --json
# then the same for ETH (2017-08-01), BNB (2017-11-01), LTC (2017-12-01), ADA (2018-04-01),
# XRP (2018-05-01), TRX and XLM (2018-06-01), LINK (2019-01-01), ATOM (2019-04-01),
# DOGE (2019-07-01), BCH (2019-11-01), SOL and DOT (2020-08-01), AVAX (2020-09-01)
uv run alpha crypto-data acquire binance market_membership spot --base NONE --quote NONE --category spot --json
```

Each pair finished with every month `done` and exactly one failure, the November 2026 month
(`Binance archive request failed`): the planner includes the month containing `--end`, and
Binance publishes a monthly file only after the month ends. Recorded, nothing stored for it.
The market list came back `"state": "qualified"`.

| Pair | First bar | Last bar | Daily bars | Monthly files | Quality |
|---|---|---|---:|---:|---|
| ADAUSDT | 2018-04-17 | 2026-10-31 | 3120 | 103 | qualified |
| ATOMUSDT | 2019-04-29 | 2026-10-31 | 2743 | 91 | qualified |
| AVAXUSDT | 2020-09-22 | 2026-10-31 | 2231 | 74 | qualified |
| BCHUSDT | 2019-11-28 | 2026-10-31 | 2530 | 84 | qualified |
| BNBUSDT | 2017-11-06 | 2026-10-31 | 3282 | 108 | qualified |
| BTCUSDT | 2017-08-17 | 2026-10-31 | 3363 | 111 | qualified |
| DOGEUSDT | 2019-07-05 | 2026-10-31 | 2676 | 88 | qualified |
| DOTUSDT | 2020-08-18 | 2026-10-31 | 2266 | 75 | qualified |
| ETHUSDT | 2017-08-17 | 2026-10-31 | 3363 | 111 | qualified |
| LINKUSDT | 2019-01-16 | 2026-10-31 | 2846 | 94 | qualified |
| LTCUSDT | 2017-12-13 | 2026-10-31 | 3245 | 107 | qualified |
| SOLUSDT | 2020-08-11 | 2026-10-31 | 2273 | 75 | qualified |
| TRXUSDT | 2018-06-11 | 2026-10-31 | 3065 | 101 | qualified |
| XLMUSDT | 2018-06-01 | 2026-10-31 | 3075 | 101 | qualified |
| XRPUSDT | 2018-05-04 | 2026-10-31 | 3103 | 102 | qualified |

Every pair has one bar for every calendar day from its first bar to 31 October 2026 (no gaps).
Total 43,181 daily bars from 1,425 monthly files.

Stock store (for the backtest commands), Binance REST through CCXT:

```text
$ uv run alpha data pull BTC/USDT --source ccxt --exchange binance --start 2017-09-01 --end 2026-11-13
pulled BTC/USDT from ccxt: 3361 bars, 0 actions
$ uv run alpha data pull ETH/USDT --source ccxt --exchange binance --start 2017-09-01 --end 2026-11-13
pulled ETH/USDT from ccxt: 3361 bars, 0 actions
```

No stock or ETF data was downloaded (see the table above).

## As-of reads return real rows, never early

```text
$ uv run alpha data candles BTCUSDT --manifest-id 29ffeda24074285b6ce3607292856b0ce0e0ec38a67c008dcb9a68946956f3df \
    --start 2022-06-27 --end 2022-06-30 --json
provenance: source binance:market_bars, quality_status qualified,
            history_kind reconstructed_from_verified_archive, knowledge_cutoff 2022-06-30T23:59:59.999999+00:00
2022-06-27 open 21038.08 close 20742.56
2022-06-28 open 20742.57 close 20281.29
2022-06-29 open 20281.28 close 20123.01
```

The 30 June bar is not returned: it closes at 00:00 UTC on 1 July, after the cutoff. The same read
from the stock-store snapshot returns the 30 June bar as well (open 20123.00, close 19942.21) with
`quality_status: legacy_unqualified`: that store keys a daily bar by its date and treats it as
known at the end of that date, the existing stock-store convention.

## Snapshots

```text
$ uv run alpha data snapshot free-binance-btc-eth-2026-11-14 BTC/USDT ETH/USDT --source ccxt --exchange binance
snapshot free-binance-btc-eth-2026-11-14 created for ['BTC/USDT', 'ETH/USDT']
$ uv run alpha data verify free-binance-btc-eth-2026-11-14
snapshot free-binance-btc-eth-2026-11-14: integrity OK
$ uv run alpha crypto-data snapshot-create --manifest-id 7dc51a939bb7ac6e246b34e8cc45a4da6ddf292ba9dfb5849f395c0e632f4eec --json
"snapshot_id": "a9202603af8f76be8e7f7d9dae52c599a3958e8b6ea7c8364501ad66d74c7b6a", "state": "frozen", "member_count": 1
$ uv run alpha crypto-data snapshot-verify a9202603…7b6a --purpose research --required-family market_bars --json
"eligible": true, "blockers": [], "qualified_families": ["market_bars"], "execution_authority": false
```

A governed crypto snapshot takes one normalized manifest, which for the archives is one month of
one pair (BTCUSDT, February 2024, 29 bars, above).

**Defect found.** Before the backfill, one test `acquire` of BTCUSDT January 2024 was made; the
backfill then fetched the same month again, so two byte-identical captures exist. A snapshot of
that month (`c8ab0d2a…6226`) was created without complaint, but `snapshot-verify` refuses it
("member manifest is ambiguous"), and so does `alpha crypto-data storage-verify` for the whole
store, because it re-verifies every snapshot. The refusal is fail-closed and safe, but snapshot
creation and verification disagree, and any repeated download of a month that is already in a
snapshot would break that snapshot. Snapshots are immutable, so the stuck one was left in place.
Proposed fix (not built here): make `snapshot-create` apply the same one-capture rule, and decide
whether byte-identical captures should count as one.

## One study command on the real snapshot

```text
$ uv run alpha backtest run BTC/USDT --snapshot free-binance-btc-eth-2026-11-14 \
    --periods-per-year 365 --fee-bps 10 --slippage-bps 5 --account-type MARGIN
backtest BTC/USDT -> run ff506d053cd92d0e: 107 orders, 107 fills, 9 trades, final equity 1888131.65
```

The run manifest binds `snapshot_id` and `snapshot_hash` `d56fb4ec…79f6d`. It is a plumbing
check of the default momentum rule on real data, not research evidence, and it is not
confirmed.

## Two Binance routes compared

Daily bars from the archive and from the live REST service, read through ALPHA, 2017-09-01 to
2026-10-30 (3,347 common days per pair): open, high, low and close agree on every day for BTC and
ETH. Volume differs on 10 BTC days and 9 ETH days, by up to 2.5% (largest: BTC 2021-01-21,
131,803.18 in the archive against 135,004.08 live). Both routes are Binance, so this is not an
independent check, but it shows old volume figures can change.

## Checks

- `uv run python scripts/gate.py check --all`: see the pull request; first run found two
  document-shape problems (fixed).
- Not run: `gate.py full` (needs owner-provided RD-Agent paths), any stock download, any
  research-case study (needs owner approval), Bybit downloads.

## Review findings

- Codex (`gpt-6-astra`, medium, via `scripts/handoff.py review`), low: the plan said
  `Build class: none`, which the plan contract does not allow. Fixed: `small`.

None open.
