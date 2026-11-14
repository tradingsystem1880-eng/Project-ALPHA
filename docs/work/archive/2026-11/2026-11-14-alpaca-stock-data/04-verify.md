# Verification: Alpaca stock data, and free stock prices now

Run on the Dell on 2026-11-14 (UTC), branch `m5/alpaca-stock-data`. Every data command ran with
`export ALPHA_DATA_DIR=/home/hunta/alpha-clean-base/data`. All data here is **not yet confirmed**
([data layer](../../../../reference/project/components/data-layer.md#real-data-on-the-dell)).

## Alpaca: what the free plan provides and permits (read 2026-11-14)

Read with a generic client name, no account, no key. Page dates are each page's own
`updatedAt` metadata.

| Fact | Source | What it says |
|---|---|---|
| Endpoint | `docs.alpaca.markets/reference/stockbars` (updated 2026-05-27) | `GET https://data.alpaca.markets/v2/stocks/bars`; `symbols`, `timeframe` (`1Day`), `start`, `end` (inclusive), `limit` 1–10000 "not per symbol", `adjustment` `raw` (default), `split`, `dividend`, `spin-off`, `all`, `asof`, `feed` `sip` (default), `iex`, `boats`, `otc`, `currency`, `page_token`, `sort`. A page may hold fewer rows than the limit: "Always check the next_page_token for more pages." 429: "You hit the rate limit. Use the X-RateLimit-... response headers". |
| Authentication | `about-market-data-api`, `market-data-faq` | headers `APCA-API-KEY-ID` and `APCA-API-SECRET-KEY`; Alpaca's examples read `${APCA_API_KEY_ID}` and `${APCA_API_SECRET_KEY}`. |
| Free plan | `about-market-data-api` (updated 2026-10-06), plan table | Basic: free; real-time coverage IEX; historical data "Since 2016"; historical data limitation "latest 15 minutes"; historical API calls "200 / min" (Algo Trader Plus: $99 a month, 10,000 a minute, no restriction). |
| SIP on the free plan | `market-data-faq` (updated 2026-09-21) | "For historical queries, the end parameter must be at least 15 minutes old to query SIP data without a subscription." The historical-data page says of IEX "This is the only feed that can be used without a subscription", read as the real-time rule; the live answer is unverified until a key exists. |
| Feeds | `historical-stock-data-1` | IEX is one exchange, "approximately ~2.5% of the market volume"; SIP "accounts for 100% of the market volume". |
| Daily bars | `market-data-faq` | aggregated from trades; the trade timestamp is truncated "to the day (in New York) for daily bars"; example bars stamped `2022-06-06T04:00:00Z`. |
| Symbol changes | `market-data-faq` | `asof` links bars across a ticker change and defaults to the query day; ALPHA fixes it to the requested end. |
| Corporate actions | `reference/corporateactions-1` (updated 2026-05-27) | `GET /v1/corporate-actions`; splits carry `old_rate`/`new_rate` and `ex_date`, cash dividends `rate`, `special`, `foreign`, `ex_date`, `record_date`, `payable_date`; `start`/`end` sort and filter by `process_date`; no announcement date. "Currently Alpaca has no guarantees on the creation time of corporate actions." |
| Terms | `files.alpaca.markets/disclosures/library/TermsAndConditions.pdf`, last modified 2021-09-15 (sha256 `2dc774d4…9b859`) | "you agree to use the Services and Content solely for your own personal and non-commercial purposes"; Content may not be "copied, reproduced, republished, uploaded, posted, publicly displayed, ... transmitted or distributed in any way (including 'mirroring') to any other computer, server, web site or other medium for publication or distribution or for any commercial enterprise" without written consent. The Basic plan is "made available at no cost"; the exchange subscriber agreements are named for the paid plan. |

**Conclusion:** personal, non-commercial research on the owner's own computer is permitted;
publishing, sharing or committing the data is not. So the test fixtures are hand-built with
made-up prices, and no Alpaca data goes into git.

## Free keyless stock sources (checked before using Yahoo)

The earlier record ([free real data](../2026-11-14-free-real-data-dell/04-verify.md)) found Yahoo's
terms forbid automated collection and Stooq blocks automated clients with a bot check. ALPHA has no
other keyless stock adapter, and every other free stock API the project knows of (Tiingo, Alpaca)
needs a key. So the owner's decision of 2026-11-14 applied: use the existing `yfinance` downloader
for now.

## Starter Yahoo download

One sequential pass, three seconds between symbols, no retries beyond the adapter's own; the
existing crypto data was not touched (data folder 37,469,316 bytes before, 40,429,357 after;
the stock store holds 3,140,836 bytes).

```sh
for s in SPY QQQ IWM DIA TLT IEF GLD AAPL MSFT AMZN GOOGL NVDA META JPM XOM JNJ; do
  uv run alpha data pull $s --source yfinance --start 1990-01-01 --end 2026-11-14; sleep 3
done
uv run alpha data snapshot free-yfinance-stocks-2026-11-14 SPY QQQ IWM DIA TLT IEF GLD AAPL MSFT \
  AMZN GOOGL NVDA META JPM XOM JNJ --source yfinance
uv run alpha data verify free-yfinance-stocks-2026-11-14   # integrity OK
```

| Symbol | First bar | Last bar | Bars | Actions | Splits |
|---|---|---|---:|---:|---|
| SPY | 1993-01-29 | 2026-11-13 | 8507 | 136 | — |
| QQQ | 1999-03-10 | 2026-11-13 | 6965 | 91 | 2000-03-20 2:1 |
| IWM | 2000-05-26 | 2026-11-13 | 6657 | 108 | 2005-06-09 2:1 |
| DIA | 1998-01-20 | 2026-11-13 | 7251 | 341 | — |
| TLT | 2002-07-30 | 2026-11-13 | 6114 | 290 | — |
| IEF | 2002-07-30 | 2026-11-13 | 6114 | 292 | — |
| GLD | 2004-11-18 | 2026-11-13 | 5532 | 0 | — |
| AAPL | 1990-01-02 | 2026-11-13 | 9286 | 86 | 2000, 2005 2:1; 2014 7:1; 2020-08-31 4:1 |
| MSFT | 1990-01-02 | 2026-11-13 | 9286 | 99 | eight, last 2003-02-18 2:1 |
| AMZN | 1997-05-15 | 2026-11-13 | 7422 | 4 | three in 1998–99; 2022-06-06 20:1 |
| GOOGL | 2004-08-19 | 2026-11-13 | 5596 | 12 | 2014-04-03 "1.998" (Yahoo's figure for the class C issue); 2022-07-18 20:1 |
| NVDA | 1999-01-22 | 2026-11-13 | 6997 | 62 | four to 2007; 2021-07-20 4:1; 2024-06-10 10:1 |
| META | 2012-05-18 | 2026-11-13 | 3644 | 11 | — |
| JPM | 1990-01-02 | 2026-11-13 | 9286 | 150 | 1998 2:1; 2000 3:2 |
| XOM | 1990-01-02 | 2026-11-13 | 9286 | 150 | 1997, 2001 2:1 |
| JNJ | 1990-01-02 | 2026-11-13 | 9286 | 150 | 1992, 1996, 2001 2:1 |

Total 117,229 daily bars. Yahoo's first day for the 1990 names is the requested start, not
their listing. These are today's large companies: a survivor-biased set.

### As-of read across the AAPL 4:1 split of 2020-08-31

```text
$ uv run alpha data candles AAPL --snapshot free-yfinance-stocks-2026-11-14 --start 2020-08-26 --end 2020-08-28 --json
provenance: source yfinance, quality_status legacy_unqualified, knowledge_cutoff 2020-08-28T23:59:59.999999+00:00
2020-08-28 close 499.2300109863281        # the price actually traded that day
$ ... --end 2020-09-01
2020-08-28 close 124.80750274658203       # once the split is ex, history is rescaled by 1/4
2020-08-31 close 129.0399932861328
```

As of 28 August the reader shows the raw pre-split price (499.23, the known close); only after
the split is ex does it rescale. The small digits are Yahoo's float rounding.

## Live Alpaca download (key set by the owner, 2026-11-14)

The owner set a key in `~/.config/alpha/alpaca.env`. It was loaded only by sourcing that file
inside the one command that needed it (`bash -c 'set -a; . ~/.config/alpha/alpaca.env; set +a;
...'`); the file and the variables were never read, printed or recorded. Only the market-data host
was called (historical bars and corporate actions); no trading or account endpoint.

```text
$ ALPHA_DATA_DIR=/home/hunta/alpha-clean-base/data-alpaca uv run alpha provider check alpaca
alpaca: verified (2026-11-14T09:29:33.671367Z); No action required.
```

So the free plan does serve consolidated (SIP) daily history: the live path is verified.

The data went into its own folder, `/home/hunta/alpha-clean-base/data-alpaca`, not the main
`data` folder: the main folder already holds the same symbols from Yahoo, and ALPHA refuses to
mix two sources in one price series (ADR-0047). The crypto data was not touched.

```sh
END=2026-11-13   # the last completed New York session
for s in SPY QQQ IWM DIA TLT IEF GLD; do
  uv run alpha data pull "$s" --source alpaca --asset-class etf --start 2016-01-04 --end "$END"; done
for s in AAPL MSFT AMZN GOOGL NVDA META JPM XOM JNJ; do
  uv run alpha data pull "$s" --source alpaca --start 2016-01-04 --end "$END"; done
uv run alpha data snapshot alpaca-starter-2026-11-14 SPY IWM DIA TLT IEF GLD AAPL MSFT AMZN GOOGL \
  NVDA META JPM XOM JNJ --source alpaca
uv run alpha data verify alpaca-starter-2026-11-14   # integrity OK
```

- 15 of 16 symbols promoted, each with 2,733 daily bars from 2016-01-04 to 2026-11-13 and no
  calendar gap on the XNYS calendar: 40,995 bars in all; 15,692,153 bytes in the folder,
  receipts included. Every pull printed "not yet confirmed".
- Actions: SPY 41, IWM 43, DIA 129, TLT 129, IEF 129, GLD 0, AAPL 45, MSFT 43, AMZN 1, GOOGL 11,
  NVDA 45, META 11, JPM 44, XOM 43, JNJ 43. Every split in the window (AAPL 2020 4:1, AMZN 2022
  20:1, GOOGL 2022 20:1, NVDA 2021 4:1 and 2024 10:1) came as a forward split and passed the
  split cross-check.
- **QQQ refused**: "Alpaca dividends on 2022-09-19 disagree on record or pay date". Alpaca lists
  two cash-dividend records for that ex-date with the same amount (0.51856) and record date and
  different ids and pay dates (2022-09-23 and 2022-10-31): one dividend recorded twice, not two
  dividends. Summing them would have doubled the dividend; the adapter refuses instead. QQQ stays
  out until this is resolved (the Yahoo copy has it).
- Request count: about four requests per symbol (one bars page per adjustment, one or two action
  pages), paced 0.35 s apart; no pull failed on the rate limit.

As-of read across the NVDA 10:1 split of 2024-06-10:

```text
$ uv run alpha data candles NVDA --snapshot alpaca-starter-2026-11-14 --start 2024-06-05 --end 2024-06-07 --json
provenance: source alpaca, venue US, receipt 87e44a67…c625, quality_status passed, knowledge_cutoff 2024-06-07T23:59:59.999999+00:00
2024-06-07 close 1208.88          # the price traded that day
$ ... --end 2024-06-10
2024-06-07 close 120.888          # rescaled once the split is ex
2024-06-10 open 120.37 high 195.95 low 117.01 close 121.79
```

## Alpaca against Yahoo (same 15 symbols, 2016-01-04 to 2026-11-13)

40,995 common rows; both sources have exactly the same session dates and the same splits.

- **Prices agree almost everywhere:** the median relative difference of open, high, low and close
  is about 2e-8 (Yahoo's float rounding). Closes differ by more than 1% on 8 rows, all in March
  2020 (12, 16 and 18 March: SPY twice, IWM, DIA, GLD twice, MSFT, XOM), up to 2.9%.
- **Single bad prints in Alpaca's highs and lows:** NVDA high on 2024-06-10 is 195.95 in Alpaca
  against 123.10 in Yahoo (the split day; 195.95 is far outside the day's trading); META high
  2016-06-02 135.60 against 119.44; JPM high 2019-11-12 139.30 against 130.62; GLD low 2017-04-19
  110.03 against 121.28; XOM low 2023-01-24 99.23 against 104.87. Alpaca builds bars from trades,
  and a stray trade can set a daily high or low. Rules that use highs or lows should be aware.
- **Volume differs** on most days (median 0.5% to 11% by symbol): the two count consolidated
  volume differently. Do not treat volume as exact.
- **Dividends:** for the stocks they match exactly. For ETFs Alpaca misses some dividends Yahoo
  has: SPY 2016-03-18 (1.05) and 2018-06-15 (1.246), DIA 2016-03-18 (0.375), TLT and IEF
  2016-08-01; amounts differ on 2021-12-17 for SPY (1.636431 against 1.633) and DIA. The split
  cross-check does not cover dividends, so total-return work on Alpaca data can miss a dividend.

Neither source is confirmed; this comparison is evidence about both, not a qualification.

## Checks

- Offline tests: `tests/unit/test_alpaca_adapter.py` (100) and
  `tests/integration/test_data_alpaca_cli.py`, no key, no network; registry and provider tests
  updated. The live path was then run as above.
- `uv run python scripts/gate.py check`: see the pull request.
- Not run: a smoke test through the installed `alpha` with a recorded provider (the project has no
  offline-provider pattern for `alpha data pull`, and adding a test switch to production code was
  rejected); the CLI is tested end to end through `CliRunner` with a fake transport instead.

## Build and review

- Codex (`handoff.py build`, hard class) built the adapter, wiring and tests in 16 minutes with
  two fix rounds; the gate still failed on test type annotations and one provider-list test.
  Claude fixed those, corrected the corporate-action field names to Alpaca's schemas (spin-offs
  name `source_symbol`, unit splits `old_symbol` and `effective_date`), and made a replayed
  envelope prove its request (feed, adjustment, symbol, dates); `handoff.py verify` then passed.
- Independent review (a separate Claude reviewer, not the writer) found:

| # | Severity | Finding | Disposition |
|---|---|---|---|
| 1 | high | A key value with a line break makes the HTTP library raise an error that contains the secret | Fixed: values are stripped and must be printable ASCII without spaces, else a message naming only the variable; header and protocol errors become redacted errors; tests added |
| 2 | high | Corporate actions were queried only up to yesterday by process (pay) date, so a dividend not yet paid was silently missing | Fixed: query 90 days past the end, uncapped; ex-dates after the end are still dropped; the envelope check requires that end |
| 3 | medium | Alpaca could still merge into a series with no source label, and other sources could write into an Alpaca series | Fixed: refused both ways; tests added |
| 4 | medium | An identical dividend record listed twice was summed | Fixed: one record per Alpaca id (else per identical content); records that disagree on dates fail. The live QQQ case above is exactly this kind of fault |
| 5 | low | Alpaca rounds adjusted prices, so the split cross-check could reject penny stocks | Fixed: tolerance widened by the rounding (1e-4 / adjusted close) |
| 6 | low | A ticker renamed inside the window maps bars and actions differently | Recorded as a limit; such a symbol fails loud (cross-check or "another symbol") rather than silently |
| 7 | low | Some HTTP protocol errors escaped untyped | Fixed with finding 1 |

None open.
