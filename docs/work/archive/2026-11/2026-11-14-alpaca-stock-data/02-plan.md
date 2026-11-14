# Alpaca stock data, and free stock prices now

**Delivery state:** Completed — built, reviewed and run live on branch `m5/alpaca-stock-data`; done when its pull request merges.
**Build class:** hard — eight code and test files across `alpha_data` and `alpha_cli`; the documents are Claude's.

Filed straight into the archive, as `2026-11-14-free-real-data-dell` was: the work-in-progress
ceiling (34, a ratchet) admits no new live plan, and the work is finished in one sitting.

## For the owner

- Now: real daily prices for 16 US stocks and ETFs (SPY, QQQ, IWM, DIA, TLT, IEF, GLD, AAPL, MSFT,
  AMZN, GOOGL, NVDA, META, JPM, XOM, JNJ) from Yahoo through the existing `yfinance` downloader,
  as you decided after being told Yahoo's terms forbid automated collection. Frozen and checked.
- Next: a new `alpaca` downloader using the key you set in `~/.config/alpha/alpaca.env`
  (runbook: `docs/operations/alpaca-stock-data.md`). It never stores or prints the key. Alpaca
  replaces Yahoo for new downloads; 15 of the 16 symbols came in from Alpaca the same day.
- Everything stays labelled not yet confirmed: neither is the authoritative source (Tiingo,
  ADR-0017), and an Alpaca download can never overwrite Tiingo data.
- Nothing to decide now.

```json
{
  "schema_version": 1,
  "title": "Alpaca stock data, and free stock prices now",
  "context": "The owner chose a free stock source until the Mac (Alpaca or similar), then allowed any free source now with an Alpaca account to follow; the Dell held no stock prices.",
  "assumptions": [
    {"statement": "Alpaca historical bars: GET https://data.alpaca.markets/v2/stocks/bars with symbols, timeframe=1Day, start, end (inclusive), limit up to 10000 across symbols, adjustment raw|split|dividend|spin-off|all, asof, feed sip|iex|boats|otc, currency, page_token, sort; response {bars:{SYM:[{t,o,h,l,c,v,n,vw}]}, next_page_token, currency}; a page may hold fewer rows than the limit, so only next_page_token says whether more follow.", "verified_by": "docs.alpaca.markets/reference/stockbars, page updated 2026-05-27, read 2026-11-14"},
    {"statement": "Authentication is the APCA-API-KEY-ID and APCA-API-SECRET-KEY headers; Alpaca's own examples read them from APCA_API_KEY_ID and APCA_API_SECRET_KEY.", "verified_by": "docs.alpaca.markets about-market-data-api and market-data-faq, read 2026-11-14"},
    {"statement": "The free Basic plan: history since 2016, 200 historical calls per minute, and SIP data may be queried without a subscription when the end is at least 15 minutes old.", "verified_by": "about-market-data-api plan table and market-data-faq, read 2026-11-14"},
    {"statement": "Daily bars are aggregated from trades whose timestamp is truncated to the New York day; t is New York midnight in UTC (04:00Z or 05:00Z).", "verified_by": "market-data-faq 'How are bars aggregated' and its META example, read 2026-11-14"},
    {"statement": "GET /v1/corporate-actions returns forward_splits (old_rate, new_rate), reverse_splits, cash_dividends (rate, special, foreign), stock_dividends, spin_offs and others with ex_date, record_date, payable_date, process_date and next_page_token; start/end filter on process_date; there is no announcement date; Alpaca gives no guarantee on when an action appears.", "verified_by": "docs.alpaca.markets/reference/corporateactions-1 and its schema, read 2026-11-14"},
    {"statement": "Alpaca's Terms and Conditions allow use 'solely for your own personal and non-commercial purposes' and forbid copying or distributing Content to another computer, server or site for publication or distribution without written consent.", "verified_by": "files.alpaca.markets/disclosures/library/TermsAndConditions.pdf, last modified 2021-09-15, read 2026-11-14"},
    {"statement": "The receipt pipeline gates a candidate against the source the CLI names, checks exchange-calendar gaps for stocks, and labels a promoted receipt 'passed' in candle provenance.", "verified_by": "reading alpha_data/pipeline.py _quality_report and alpha_cli/data_cmds.py _candle_provenance"}
  ],
  "alternatives_considered": [
    "Store split- or all-adjusted Alpaca prices: rejected, the store holds raw prices and the point-in-time reader applies splits by their own clock.",
    "Use the IEX feed: rejected, it is one exchange (about 2.5% of volume), so its OHLCV is not the market's; SIP is allowed for history older than 15 minutes.",
    "Trust the corporate-actions list alone: rejected, Alpaca gives no guarantee it is complete, so a second split-adjusted bar request cross-checks every split.",
    "Quarantine every Alpaca candidate as non-authoritative under ADR-0017: rejected, it would need an owner repair per symbol; instead an Alpaca download may never replace Tiingo data, and labels say not yet confirmed.",
    "A test-only offline provider switch in production code for the smoke check: rejected, a back door; the CLI is tested end to end with a faked transport instead."
  ],
  "pre_mortem": [
    "Alpaca refuses SIP history on the free plan in practice: the adapter fails loud with Alpaca's message and never falls back to IEX; the live path is unverified until the owner sets a key.",
    "The corporate-actions list misses a split: the split-adjusted cross-check fails loud instead of storing prices with an unexplained jump.",
    "A symbol has a stock dividend or spin-off: the adapter refuses that symbol, naming the action, rather than store prices it cannot adjust.",
    "A stored test fixture copies real Alpaca data into this public repository: fixtures are hand-built, with made-up prices."
  ],
  "slices": [
    {"title": "Alpaca adapter: request, pagination, retries, parse, split cross-check, receipt (unit tests first)", "verify": "uv run pytest -q tests/unit/test_alpaca_adapter.py", "expected": "all pass, no network", "rollback": "delete alpaca_adapter.py and its test", "files": ["packages/alpha-data/src/alpha_data/adapters/alpaca_adapter.py", "tests/unit/test_alpaca_adapter.py"], "status": "pending"},
    {"title": "Provider registry entry, alpha provider check, and alpha data pull wiring with the Tiingo-replacement guard", "verify": "uv run pytest -q tests/unit/test_provider_registry.py tests/unit/test_provider_readiness.py tests/integration/test_data_alpaca_cli.py tests/integration/test_data_cli.py", "expected": "all pass", "rollback": "revert providers.py, provider_readiness.py and data_cmds.py", "files": ["apps/alpha-cli/src/alpha_cli/providers.py", "apps/alpha-cli/src/alpha_cli/provider_readiness.py", "apps/alpha-cli/src/alpha_cli/data_cmds.py", "tests/unit/test_provider_registry.py", "tests/integration/test_data_alpaca_cli.py"], "status": "pending"},
    {"title": "Starter yfinance download, snapshot, verify and as-of read on the Dell", "verify": "commands in 04-verify.md", "expected": "16 symbols, integrity OK, raw prices before a split", "rollback": "remove the 16 symbols and the snapshot from the data folder", "status": "done"},
    {"title": "Data-layer page, ADR-0047, runbook, capability map, command reference and status", "verify": "docs re-stamped by Claude after the build", "expected": "fs.py stale shows none of these", "rollback": "revert the document changes", "status": "done"}
  ],
  "tier_impact": ["none"],
  "docs_to_update": ["docs/reference/project/components/data-layer.md", "docs/adr/0047-alpaca-interim-stock-source.md", "docs/operations/alpaca-stock-data.md", "docs/roadmap/capabilities.toml", "docs/reference/commands.md", "STATUS.md"],
  "out_of_scope": ["packages/alpha-research/src", "packages/alpha-validation/src", "alpha_data/pipeline.py and store.py", "Tiingo, yfinance and stooq adapters", "daily-rule and crypto snapshot query files", "workers/rdagent", "Alpaca trading or paper API", "data files in git", "live provider calls in tests"],
  "files": [
    "packages/alpha-data/src/alpha_data/adapters/alpaca_adapter.py",
    "tests/unit/test_alpaca_adapter.py",
    "apps/alpha-cli/src/alpha_cli/providers.py",
    "apps/alpha-cli/src/alpha_cli/provider_readiness.py",
    "apps/alpha-cli/src/alpha_cli/data_cmds.py",
    "tests/unit/test_provider_registry.py",
    "tests/integration/test_data_alpaca_cli.py",
    "docs/work/archive/2026-11/2026-11-14-alpaca-stock-data/"
  ]
}
```

## Read first

| Read | Section | When |
|---|---|---|
| [alpha-data workspace](../../../../../packages/alpha-data/CONTEXT.md) | — | always |
| [data invariants](../../../../reference/invariants/data.md) | Point-in-time store, Corporate actions | always |
| [research integrity](../../../../reference/invariants/research-integrity.md) | Invalid data fails loud | always |
| [`adapters/base.py`](../../../../../packages/alpha-data/src/alpha_data/adapters/base.py) | — | always: the contract |
| [`adapters/tiingo_adapter.py`](../../../../../packages/alpha-data/src/alpha_data/adapters/tiingo_adapter.py) | — | always: the pattern to follow |
| [`pipeline.py`](../../../../../packages/alpha-data/src/alpha_data/pipeline.py) | `_quality_report`, `stage_and_promote` | read only; do not change |
| [`providers.py`](../../../../../apps/alpha-cli/src/alpha_cli/providers.py) | the `tiingo` definition | slice 2 |
| [`data_cmds.py`](../../../../../apps/alpha-cli/src/alpha_cli/data_cmds.py) | `_adapter`, `pull` | slice 2 |
| [`provider_readiness.py`](../../../../../apps/alpha-cli/src/alpha_cli/provider_readiness.py) | `_tiingo_check`, `_CHECKERS` | slice 2 |
| [`test_tiingo_bounded_fetch.py`](../../../../../tests/unit/test_tiingo_bounded_fetch.py) | — | how transports are faked |

## Slices

### 1. `alpha_data/adapters/alpaca_adapter.py` (new) and `tests/unit/test_alpaca_adapter.py` (new)

Constants: `_VERSION = "1"`, `PARSER_VERSION = "1"`, data host `https://data.alpaca.markets`,
`FEED = "sip"`, credential names `APCA_API_KEY_ID` and `APCA_API_SECRET_KEY`, client name
`Project-ALPHA/1.0`, page limit `10000` (bars) and `1000` (actions), at most 200 pages per request
series, at most 32 MiB per page, at most 3 attempts per request, minimum 0.35 s between requests
(under 200 a minute), retry waits capped at 60 s.

Transport: a small injectable seam so tests need no network, e.g.
`Transport = Callable[[str, Mapping[str, str], float], tuple[int, Mapping[str, str], bytes]]`
(url, headers, timeout → status, response headers, body), plus injectable `sleep` and `clock`
(`Callable[[], datetime]`, aware UTC). The default transport uses `urllib` with a no-redirect
opener, reads at most the page cap plus one byte, and returns HTTP error statuses (it does not
raise on them). Transport exceptions (`URLError`, `TimeoutError`, `OSError`,
`http.client.IncompleteRead`) become a retryable failure; after the last attempt raise
`DataError("Alpaca transport failed: <ExceptionClassName>")` with `from None`.

Credentials: read `APCA_API_KEY_ID` and `APCA_API_SECRET_KEY` from `os.environ` in `fetch` (the
constructor may take explicit values for tests). Missing or blank → `DataError` that names both
variables and says: "create a free Alpaca account, generate a key, and set both variables in your
own terminal; see docs/operations/alpaca-stock-data.md". The key values never appear in an
exception, a receipt, request metadata, the envelope or any log; tests assert this with a sentinel
key string. Credentials are checked before any request.

Requests for one `fetch(symbol, start, end)`:

1. Validate: `end >= start`; `start >= 2016-01-01` (Alpaca's history starts in 2016; earlier →
   `DataError` saying so); `end` strictly before today's date in `America/New_York` (from the
   injected clock) so only completed sessions are asked for, with a message naming the latest
   allowed end; symbol upper-cased, non-empty, only `A-Z0-9.-` (Alpaca uses `BRK.B`).
2. Raw bars: `/v2/stocks/bars` with exactly `symbols=SYM`, `timeframe=1Day`, `start`, `end`
   (`YYYY-MM-DD`), `adjustment=raw`, `feed=sip`, `asof=<end>` (fixed so the symbol mapping does not
   depend on the run date), `currency=USD`, `limit=10000`, `sort=asc`, then `page_token` while
   `next_page_token` is a non-empty string.
3. Split-adjusted bars: the same series with `adjustment=split` (cross-check only, never stored as
   prices).
4. Corporate actions: `/v1/corporate-actions` with `symbols=SYM`,
   `types=forward_split,reverse_split,cash_dividend,stock_dividend,spin_off,unit_split`,
   `start=<start>`, `end=min(end + 90 days, latest allowed end)` (the filter is on process date,
   which can follow the ex-date), `limit=1000`, `sort=asc`, plus `page_token` pages.

Every request sends the two key headers, `Accept: application/json` and the client name. Status
handling: 200 → page; 429 and 500–599 → wait (`Retry-After` seconds if a valid integer, else
`X-RateLimit-Reset` minus now if a valid future Unix time, else 1, 2, 4 s), capped at 60 s, then
retry within the attempt cap; 401 → `DataError("Alpaca rejected the key with HTTP 401 ...")`;
403 → `DataError("Alpaca refused the request with HTTP 403: <Alpaca message if the body is JSON
with a string 'message', truncated to 200 chars>")` and say the free plan may not cover it; never
fall back to another feed; any other status → `DataError(... HTTP <code> ...)`. Exhausted retries
on 429 → `DataError("Alpaca rate limit (HTTP 429) persisted after 3 attempts")`. Error messages
always contain `HTTP <code>` (the readiness classifier reads it).

Envelope (the `raw_response` kept in the receipt): canonical JSON bytes
(`sort_keys=True, separators=(",", ":")`, ASCII) of
`{"schema": "alpha.alpaca.daily.v1", "pages": [{"series": "bars_raw"|"bars_split"|"actions",
"path": "/v2/stocks/bars", "query": [[k, v], ...], "status": 200, "body_sha256": ...,
"body_b64": ...}, ...]}` in request order. Only successful pages are included; query pairs never
include a key. Same responses give the same bytes.

`parse_alpaca_daily(envelope, *, symbol, provider_symbol, asset_class, venue, calendar, currency,
start, end, fetched_at) -> FetchResult` is pure and builds everything from the envelope alone
(so a stored receipt can be re-parsed). It fails loud (`DataError`) on: invalid envelope JSON or
schema, a body whose sha256 differs, a page body that is not JSON or not an object, a missing or
non-object `bars`, a `bars` key other than the requested symbol, a `currency` other than `USD`
when present, `next_page_token` missing or not a string/null, a pages sequence whose continuation
does not match (each later page's `page_token` must equal the previous page's
`next_page_token`; the last page of each series must have a null or empty token; a repeated token
fails), a missing series, a bar that is not an object or lacks `t,o,h,l,c,v`, a non-numeric,
boolean or non-finite value, a non-positive price, negative volume, `t` that is not RFC 3339 with
an offset, `t` not exactly midnight in `America/New_York`, a session date outside `start..end`,
duplicate or descending dates, any `Bar` invariant failure (construct `alpha_core.Bar`), raw and
split series whose session dates differ, an empty result ("Alpaca returned no bars for SYM
start..end"). Empty intermediate pages are allowed; the bounded page count still applies.

Bars: `ts` is the New York session date at 00:00 UTC (the store's daily convention, as Tiingo),
columns `ts, open, high, low, close, volume` as Float64, sorted.

Actions: forward and reverse splits → `ActionType.SPLIT`, `ratio = new_rate / old_rate`
(finite, > 0, not 1); cash dividends → `ActionType.DIVIDEND`, `amount = rate` (> 0), currency
USD or null, otherwise fail; cash dividends sharing an ex-date are summed into one action; two
splits on one ex-date fail. Set `record_date` and `pay_date` (`payable_date`) when present;
`announce_date` stays `None` (Alpaca has none, so knowledge falls back to the ex-date, the
conservative clock). Keep only actions whose `ex_date` is within `start..end`. A stock dividend,
spin-off or unit split with a date in `start..end` → `DataError` naming the type and date and
saying ALPHA cannot adjust it, so the symbol is refused. An action for another symbol fails.

Split cross-check: for each session, `f = raw_close / split_close`. With `f_last` for the last
session, `f / f_last` must equal the product of in-window split ratios with `ex_date` after that
session, within a relative tolerance of 1e-3; otherwise `DataError("Alpaca split cross-check
failed for SYM on DATE: ...")`. This catches a split missing from the actions list and a series
that is not raw.

Identity and receipt: `DatasetIdentity(provider="alpaca", provider_symbol=SYM, venue, asset_class
in {"stock","etf"}, timeframe "1D", calendar, currency "USD", price_basis "raw")`;
`FetchReceipt.create(...)` over the envelope with `request_metadata` holding `endpoint_bars`,
`endpoint_actions`, `feed`, `adjustment` ("raw; split used as cross-check"), `asof`, and `pages`
(count). `FetchResult` carries identity, receipt and `raw_response=envelope`.

`AlpacaAdapter`: `name = "alpaca"`, `version`, `parser_version`; constructor keywords
`asset_class="stock"`, `venue="US"`, `calendar="XNYS"`, `currency="USD"` (only USD accepted),
plus test seams (`api_key_id`, `api_secret_key`, `transport`, `sleep`, `clock`). Construction
never touches the network or the environment's keys.

Tests (hand-built fixtures with made-up prices; never real Alpaca data): a two-page happy path
with a dividend and a 2:1 split (raw prices, actions, receipt counts, envelope determinism, query
pairs, headers, no key in envelope or receipt); continuation token mismatch and repeated token;
an empty final page with no bars at all; an empty intermediate page; a session outside the range;
a non-midnight timestamp; duplicate dates; malformed JSON; wrong body hash; a wrong symbol key;
a bar missing a field; boolean and NaN values; raw and split session sets differing; a split
missing from the actions (cross-check fails); a stock dividend and a spin-off refused; 429 with
`Retry-After` then success (sleep called with the wait, no real sleeping); 429 three times;
500 then success; 401 and 403 messages contain the code and no key; transport error redacted;
missing either credential refused before any request, message names both variables; `end` equal
to today in New York refused; `start` before 2016 refused; the request pacing (sleep between
requests).

### 2. Registry, readiness check and `alpha data pull`

- `providers.py`: add `alpaca` after `tiingo`: label "Alpaca Market Data (free plan)",
  capabilities `historical_bars`, `corporate_actions`; module
  `alpha_data.adapters.alpaca_adapter`; credential names `APCA_API_KEY_ID`, `APCA_API_SECRET_KEY`;
  option `asset_class` (stock, etf; default stock); limitations: "Free Basic plan: SIP daily
  history since 2016, 200 calls a minute; personal, non-commercial use only; never redistribute.",
  "Interim, not yet confirmed: not the authoritative stock source (ADR-0017); never replaces Tiingo
  data."; asset classes stock, etf; timeframes 1D; `research_authority=False`;
  `paper_execution=False`; `budget_tier="free_basic"`; factory `AlpacaAdapter`.
- `provider_readiness.py`: `_alpaca_check` like `_tiingo_check`, fetching SPY (`asset_class="etf"`)
  for the 14 days ending yesterday; register it in `_CHECKERS`.
- `data_cmds.py`: `_adapter` applies the Tiingo `asset_class`/`venue`/`calendar`/`currency`
  handling to `alpaca` too (choices from `provider_option_choices("alpaca", "asset_class")`), and
  the `pull` option help says "Tiingo or Alpaca". In `pull`, before `stage_and_promote` on the
  receipt path, refuse when the stored provenance source is `tiingo` and the adapter is not
  (the same message the legacy path uses), so no other source replaces canonical Tiingo data.
  When the adapter is `alpaca`, the success line ends with "; not yet confirmed (interim source,
  not the authoritative Tiingo source)".
- `tests/unit/test_provider_registry.py`: add `alpaca` to the expected id sets and assert its
  credential names, `research_authority is False` and redacted projection (presence only).
- `tests/integration/test_data_alpaca_cli.py` (new): through `typer.testing.CliRunner` and
  `alpha_cli.main.app`, with `_ADAPTERS` set to a factory that builds `AlpacaAdapter` with a fake
  transport and keys, a fixed clock: `alpha data pull SPY --source alpaca --asset-class etf`
  promotes a receipt, prints "not yet confirmed", stores raw bars and actions, keeps the envelope
  under `store/receipts/alpaca/<id>/response.bin`, and `alpha data candles SPY --json` reads the
  bars back as of a date; a pull without keys fails with exit code 2 and names both variables;
  a pull onto a symbol whose provenance is `tiingo` is refused and leaves the store unchanged;
  a calendar gap in the fake data is quarantined.

## Test plan

All new tests are offline: fake transports, fixed clocks, hand-built responses, sentinel keys.
The live Alpaca path is not exercised (no key exists); `04-verify.md` says so. The starter
`yfinance` download is checked by hand on the Dell and recorded in `04-verify.md`.

## Look-ahead, determinism and import impact

The adapter writes only through the existing receipt pipeline and store; it adds no read path, so
no new future-poison guard is needed (the existing ones cover the reader). Actions carry no
announcement date, so knowledge falls back to the ex-date; a split rescales history only once it
is ex at the cutoff. The envelope is canonical, so the same responses give the same receipt.
`alpha_data` still imports only `alpha_core` (plus the standard library); `zoneinfo` gives the New
York date.
