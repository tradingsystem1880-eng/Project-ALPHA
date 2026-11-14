# Project ALPHA — Free Market Data Sources (Research Brief 01)

**Date:** 2026-06-14
**Scope constraint:** Personal (single-user), $0 budget, Python-first, backtesting + statistical validation + PAPER trading only. Free tiers / open-source self-hosted only.
**Purpose:** Feed the data-layer architecture decision with a concrete, opinionated recommendation per asset class.

---

## 0. TL;DR — The Honest Ceiling on "Free"

| Asset class | Tick data | L2 order book | 1-min bars | Daily/EOD | Fundamentals | Corp actions | Verdict |
|---|---|---|---|---|---|---|---|
| **Crypto** | ✅ FREE, full | ✅ FREE, full depth | ✅ FREE | ✅ FREE | n/a | n/a | **Institutional-grade is genuinely free** |
| **US equities** | ❌ not free (SIP) | ❌ not free | ⚠️ partial (IEX-only free) | ✅ FREE | ✅ FREE (SEC) | ✅ FREE | **Daily/fundamentals excellent; tick/L2 effectively NOT free** |
| **FX** | ✅ FREE (Dukascopy) | ❌ no true L2 (decentralized mkt) | ✅ FREE | ✅ FREE | n/a | n/a | **Tick is free; no consolidated L2 exists anywhere** |
| **Futures** | ⚠️ trial credits only | ⚠️ trial credits only | ⚠️ limited | ⚠️ limited | n/a | n/a (roll/continuous is the work) | **Weakest free class — crypto perps are the free substitute** |
| **Options** | ❌ | ❌ | ❌ | ⚠️ snapshot-only (yfinance) | n/a | n/a | **No real free historical options. Build your own snapshots.** |

**The single most important architectural fact:** crypto exchanges give away tick-by-tick trades AND full-depth order books for free, forever, with no key. US equities tick/L2 (the consolidated SIP feed) is a five-figure/year institutional product and has **no free path**. Therefore: if your research requires genuine microstructure (order-book imbalance, queue dynamics, tick-level execution modeling), **do that research in crypto**, and treat US equities as a daily/minute-bar + fundamentals universe.

---

## 1. Recommended Free Data Stack (the decision)

| Asset class | PRIMARY | BACKUP | Notes |
|---|---|---|---|
| **US equities — daily/EOD + adjusted** | **Stooq** (bulk CSV, splits-adjusted, deep history, no key) | **Tiingo** (clean adjusted EOD, 500 symbols/mo) → **yfinance** (unlimited but ToS/reliability caveat) | Stooq for the bulk universe pull; Tiingo for clean point-in-time; yfinance for ad-hoc. |
| **US equities — 1-min intraday** | **Alpaca** (IEX feed, free, since 2016) | **Twelve Data** (800 calls/day) / **Finnhub** (60 cal/min) | Alpaca = best free intraday + integrated paper trading. IEX-only ≈ 2% volume (gotcha). |
| **US equities — fundamentals** | **SEC EDGAR `companyfacts`/`frames` API** (free, no key, source-of-truth XBRL) | **Finnhub** basic fundamentals / **Tiingo** | EDGAR is point-in-time-correct and authoritative. Use `edgartools`. |
| **US equities — corporate actions (splits/divs)** | **yfinance** (`.actions`) for quick, **Tiingo** for clean | **Nasdaq Data Link** legacy free + **EDGAR** (8-K) | See §4 — verify against a 2nd source; yfinance occasionally wrong. |
| **Crypto — OHLCV/historical** | **ccxt** (unified, 100+ exchanges) | **data.binance.vision** bulk dumps | ccxt for live/recent; Binance Vision for bulk backfill. |
| **Crypto — tick (trades)** | **data.binance.vision** (`aggTrades`/`trades`, bulk) | **ccxt** `fetch_trades` / exchange REST | Free full tick history. THE free microstructure dataset. |
| **Crypto — L2 order book** | **ccxt.pro / native websocket** (record live) + **Bybit** bulk orderbook dumps | Tardis.dev (sample data free; full = paid) | Record your own depth via WS; Bybit publishes downloadable L2 (from ~2023; orderbook bulk expanded 2025). |
| **FX — tick** | **Dukascopy** (`dukascopy-python` / `dukascopy-node`), tick back to ~2003 | **HistData.com** (free 1-min, manual) | True free tick FX. No real L2 in FX (OTC market). |
| **FX/crypto — broker-style paper** | **Alpaca** (crypto + equities paper) | **OANDA** practice (FX, free demo key) | OANDA v20 REST has free practice acct for FX paper. |
| **Futures** | **Databento $125 one-time credit** (institutional CME data, spend wisely) → then **crypto perpetuals via ccxt** as the free substitute | yfinance continuous `=F` tickers (low quality) | No sustainable free futures tick. Use crypto perps for ongoing microstructure research. |
| **Macro / rates** | **FRED API** (`fredapi`, 120 req/min, free key) | Nasdaq Data Link, BLS/BEA APIs | 800k+ series. Best-in-class, no caveats. |

---

## 2. Source-by-Source Detail

### 2.1 yfinance / Yahoo Finance
- **Data types:** Daily/EOD (adjusted + raw), 1-min (last 7d) up to 60-min (last ~730d) intraday, splits/dividends (`.actions`), basic fundamentals, **options chains + implied vol snapshots** (`.option_chain`), holders.
- **History depth:** Daily back to inception for most US tickers (decades). Intraday is shallow (1-min only ~7 days rolling).
- **Rate limits / quotas:** No official limit — it scrapes Yahoo's public endpoints. Yahoo throttles by IP/pattern; **429 "Too Many Requests" / `YFRateLimitError` is common in 2025+** ([#2422](https://github.com/ranaroussi/yfinance/issues/2422), [#2128](https://github.com/ranaroussi/yfinance/issues/2128)). Mitigate with caching (`requests_cache`), backoff, batching.
- **Python library:** `yfinance` — **actively maintained**; hit a major **v1.0 (Dec 2025)** and **v1.4.1 (May 2026)** ([PyPI](https://pypi.org/project/yfinance/)). This is healthier than its reputation suggests.
- **Licensing:** Unofficial; Yahoo's API is **"intended for personal use only"** per the library's own disclaimer ([PyPI](https://pypi.org/project/yfinance/)). For a single-user personal platform this is acceptable; it is **not** licensable for commercial/redistribution use.
- **Gotchas:** (1) Occasionally returns **wrong split/dividend/adjusted values** — verify against a 2nd source ([MarketXLS](https://marketxls.com/blog/yahoo-finance-api-ultimate-guide)). (2) Endpoint can break overnight when Yahoo changes its site. (3) Not for low-latency. **Treat as convenience/backup, never as your system-of-record.**

### 2.2 Alpaca (free market data + paper trading) — *best free intraday + paper combo*
- **Data types:** Equities trades/quotes/bars (1-min, etc.), crypto bars/trades/quotes, options (indicative only on free). Real-time **IEX** feed on free Basic.
- **History depth:** Equities **since 2016** ([docs](https://docs.alpaca.markets/docs/about-market-data-api)). Crypto historical is free (no auth needed for crypto history).
- **Rate limits:** Basic plan **200 req/min**; Algo Trader Plus 10,000/min (paid). SIP queries must end ≥15 min in the past on free.
- **Python library:** `alpaca-py` (official, maintained).
- **Licensing:** Free with account; personal use fine.
- **Gotchas:** **The big one — free = IEX feed only (~2% of consolidated volume).** Bars built from IEX have thin/❗misleading volume and can miss prints vs SIP. Fine for signal research on liquid names; **not** an accurate microstructure/VWAP source. Paper accounts are entitled to IEX only. **Paper trading is genuinely excellent and free** — this is the recommended paper-execution venue.

### 2.3 Polygon.io (free tier)
- **Data types (free):** End-of-day aggregates, reference/ticker data, basic fundamentals. (Tick/trades/quotes and minute aggregates are **paid**.)
- **History depth:** ~2 years on free EOD.
- **Rate limits:** **5 API calls/min** on free Basic ([knowledge base](https://polygon.io/knowledge-base/article/what-is-the-request-limit-for-polygons-restful-apis)).
- **Python library:** `polygon-api-client` (official).
- **Gotchas:** 5/min is punishing for any bulk pull; 2-yr depth is shallow. Free tier is a **demo**, not a workhorse. Skip unless you later pay.

### 2.4 Tiingo — *best free clean adjusted EOD + corp actions*
- **Data types:** EOD (clean adjusted), intraday (IEX), news, **crypto (40+ exchanges, 2,100+ tickers)**, FX. Splits & dividends APIs. Fundamentals are a **paid add-on**.
- **History depth:** Decades of EOD for US equities.
- **Rate limits (free):** **50 req/hr, 1,000 req/day, 1 GB/mo, 500 unique symbols/month** ([pricing](https://www.tiingo.com/about/pricing)).
- **Python library:** `tiingo` (official-ish, maintained) or plain `requests`.
- **Licensing:** Personal/free tier OK; offers academic pricing.
- **Gotchas:** The **500-unique-symbols/month cap** is the real constraint — great for a focused watchlist, not a full-market scan. Adjusted-close quality is high (better than yfinance).

### 2.5 Alpha Vantage
- **Data types:** EOD, intraday, FX, crypto, technical indicators, some fundamentals, basic options.
- **Rate limits (free):** **25 requests/day, 5/min** ([Macroption](https://www.macroption.com/alpha-vantage-api-limits/)) — drastically reduced from the old 500/day.
- **Python library:** `alpha_vantage`.
- **Gotchas:** **25/day is near-useless** for systematic work in 2025. Keep only as an emergency fallback for a single series.

### 2.6 Finnhub
- **Data types:** Real-time US quotes, company fundamentals, earnings calendar, SEC filings, news, **websocket tick stream**, FX/crypto.
- **Rate limits (free):** **60 calls/min** (30/sec internal cap) ([docs](https://finnhub.io/docs/api/rate-limit)). Note: some premium endpoints blocked on free.
- **Python library:** `finnhub-python` (official).
- **Gotchas:** Generous call rate, but **a lot of the genuinely useful historical/fundamental endpoints are premium-gated**; free is mostly real-time quotes + news. Good as a secondary fundamentals/news source.

### 2.7 Twelve Data
- **Data types:** US equities, FX, crypto; real-time + historical; technical indicators.
- **Rate limits (free):** **8 calls/min, 800/day**, 8 trial websocket credits ([pricing](https://twelvedata.com/pricing)).
- **Python library:** `twelvedata` (official).
- **Gotchas:** 800/day is workable for a modest universe; credit accounting (batch requests cost more credits) trips people up. Solid #2 intraday backup behind Alpaca.

### 2.8 EOD Historical Data (EODHD)
- **Data types:** EOD, intraday, fundamentals, splits/dividends, options (paid add-on).
- **Rate limits (free):** **20 API calls/day, last 1 year of history only** ([API limits](https://eodhd.com/financial-apis/api-limits)). Paid plans from €19.99/mo.
- **Gotchas:** Free tier is a **trial** (20/day, 1-yr). Not viable as a free workhorse; listed for completeness. Their **paid** splits/dividends + options are well-regarded if budget ever appears.

### 2.9 FRED (macro) — *no caveats, use it*
- **Data types:** 800k+ macro/financial time series (rates, CPI, GDP, spreads, yields, unemployment). ALFRED = vintage/point-in-time.
- **Rate limits:** **120 requests/min**, free API key.
- **Python library:** `fredapi` (mature) or `fedfred` (modern async client).
- **Gotchas:** None material. This is the gold standard for free macro. Use ALFRED endpoints when you need point-in-time (no look-ahead) macro for backtests.

### 2.10 Stooq — *best free bulk EOD, no key*
- **Data types:** Daily OHLCV for ~21k+ global equities/ETFs, ~1,900 FX pairs, ~130 crypto. Splits-adjusted history.
- **History depth:** Deep (US back decades; e.g., indices to 1980s).
- **Access:** **Bulk zipped CSV** downloads (no key, no rate limit) at [stooq.com/db/h](https://stooq.com/db/h/), or `pandas_datareader.data.DataReader(ticker, 'stooq')`.
- **Gotchas:** Per-symbol web pulls get soft-rate-limited (use the bulk DB dumps instead); ticker suffix conventions differ (`.US`); occasional gaps on thin names. **Excellent for a one-shot full-universe backfill at zero cost.**

### 2.11 Nasdaq Data Link (formerly Quandl)
- **Data types:** Mixed — **some free** publisher datasets (e.g., WIKI legacy is frozen/stale, but various free macro & alt sets remain), most premium (Sharadar = paid).
- **Python library:** `nasdaqdatalink` (successor to `quandl`).
- **Gotchas:** The famous **WIKI EOD equities dataset is deprecated/frozen** (no data after 2018) — do not rely on it for current prices. **Sharadar (high-quality point-in-time US fundamentals) is paid.** Treat NDL as a grab-bag: useful free macro/alt series, but not a primary equities feed.

### 2.12 ccxt (+ crypto exchanges) — *the crown jewel of free data*
- **Data types:** Unified API across 100+ exchanges for **OHLCV, tick trades (`fetch_trades`), full order book (`fetch_order_book`), tickers**. `ccxt.pro` (now bundled, free for personal use) adds **websocket streaming** (`watch_order_book`, `watch_trades`) for real-time L2 depth + tick.
- **History depth:** Varies by exchange; recent via REST. For deep tick history use bulk dumps (below).
- **Rate limits:** Per-exchange public limits (e.g., Binance spot REST weight 6,000/min). ccxt has built-in throttling.
- **Python library:** `ccxt` (extremely active, certified tier-1 support Binance/Coinbase/Kraken/Bybit).
- **Licensing:** MIT, free. Public market data needs **no API key**.
- **Gotchas:** `fetch_ohlcv` caps ~500–1000 candles/call → paginate. Order-book depth via REST is a **snapshot**; for true L2 you must **subscribe to the websocket and persist diffs yourself**. Exchange-specific quirks (timestamp units, symbol formats) are abstracted but not 100%.

**Per-exchange free specifics:**
- **Binance** — bulk historical at **data.binance.vision**: `klines` (1s–1mo), `trades`, **`aggTrades`** for spot + USD-M/COIN-M futures, daily/monthly zips, SHA256 checksums, **no key** ([repo](https://github.com/binance/binance-public-data)). ❗**Order-book depth is NOT in the bulk dumps** — record it live via websocket.
- **Kraken** — downloadable **OHLCVT CSV** from market inception ([support](https://support.kraken.com/articles/360047124832)); REST `Trades` gives full tick history (rebuild any OHLC); WS v2 for live depth.
- **Coinbase (Advanced Trade)** — candles **max 300/call**, granularities {1m,5m,15m,1h,6h,1d}, 10 req/s; WS for live book. Shallow REST history → paginate hard.
- **Bybit** — public endpoints need no key; **downloadable historical trades (from 2020) and klines**, with **bulk order-book dumps** (orderbook coverage expanded in **2025**) at [bybit.com/derivatives/.../history-data](https://www.bybit.com/derivatives/en/history-data). One of the few venues publishing **downloadable L2** for free.

### 2.13 Dukascopy (free FX tick) — *the free FX microstructure source*
- **Data types:** Tick (bid/ask) + aggregated bars for ~1,000+ instruments (FX, metals, indices, some crypto/CFD).
- **History depth:** Tick back to ~2003 for majors (some series to 1990s–2000).
- **Access (Python):** `dukascopy-python` (PyPI), `duka`, or `TickVault` (resume/gap-detection/pandas). Node alt: `dukascopy-node`.
- **Gotchas:** It's broker feed (Dukascopy liquidity), not a consolidated market — fine for FX research since **FX has no central tape anyway**. Downloads are slow (~10 min/instrument/year). No true L2 (none exists for spot FX). Intended for research/educational use.

### 2.14 Databento (free credits) — *futures lifeline, then it's paid*
- **What's free:** **$125 one-time sign-up credit**, historical data only ([stocks page](https://databento.com/stocks)). As of **Jan 13, 2025**, paid subscriptions include unlimited live + free historical, but that's **paid**.
- **What's paid:** Everything after the $125 burns down — and institutional tick/L2 burns it fast.
- **Coverage:** Institutional-grade **futures (CME), equities, options**, 45+ venues, 15+ yrs, MBO/MBP order-book data.
- **Python library:** `databento` (excellent, official).
- **Gotchas:** This is your **one shot at real CME futures order-book/tick data for free.** Don't waste it on equities (covered elsewhere) — spend the $125 on a **targeted futures microstructure dataset** you specifically need, export to Parquet, done.

### 2.15 SEC EDGAR — *the authoritative free fundamentals + corp-actions source*
- **Data types:** `companyfacts` (every XBRL financial fact a filer ever reported), `frames` (one concept across all filers for a period), full filings (10-K/10-Q/8-K/Form 4 insider).
- **Rate limits:** ~10 req/s, **no key**, just a descriptive `User-Agent` with contact email.
- **Python library:** **`edgartools`** (MIT, production-grade) or `sec-edgar-api`.
- **Gotchas:** XBRL tag inconsistency across filers requires normalization (edgartools handles much of it). This is **point-in-time correct** (filing dates known) → ideal for look-ahead-free fundamental backtests. **Strongly recommended as fundamentals system-of-record.**

### 2.16 PAID — explicitly out of budget (named so you don't chase them)
- **Norgate Data** — excellent survivorship-bias-free US equities/futures with delisted tickers + continuous contracts, **but paid (subscription).**
- **Polygon paid, Tiingo fundamentals add-on, EODHD paid, Sharadar (via NDL), Tardis.dev full crypto L2 history, ThetaData/Market Data.app options** — all paid. ThetaData has a limited free tier worth a look only if options become a priority.

---

## 3. Decisive Answers to the Key Questions

**Q1 — Realistic ceiling on FREE data per asset class?**
- *Crypto:* effectively unlimited and institutional-grade — full tick history + recordable full-depth L2, free, no key. This is the **only** asset class where free = institutional.
- *US equities:* **daily/EOD + fundamentals + corporate actions are fully solved for free** and to a high quality (Stooq + Tiingo + SEC EDGAR). **Intraday is partially solved** (Alpaca IEX 1-min, but IEX-only volume). **Tick/quote (SIP) and L2 depth are NOT free and have no free path** — this is the hard ceiling.
- *FX:* **tick is free** (Dukascopy). True consolidated L2 **does not exist anywhere** (FX is OTC), so you aren't missing a free product — there is no product.
- *Futures:* **weakest.** No sustainable free tick/L2. One-time Databento $125 credit, otherwise substitute **crypto perpetual futures** (free tick + L2) for microstructure research.
- *Options:* **no genuine free historical** chain/IV dataset. Only realistic free path is **recording your own yfinance option-chain snapshots daily** to build a forward history.

**Q2 — Where do you get free TICK and ORDER-BOOK data?**
**Crypto exchanges, full stop.** Tick: `data.binance.vision` (`trades`/`aggTrades`, bulk), Kraken `Trades`, Bybit downloads, or ccxt `fetch_trades`. **L2 order book:** subscribe to exchange websockets via **ccxt.pro** (`watch_order_book`) and persist the diffs, and/or download **Bybit's bulk order-book dumps**. For FX tick (not L2): **Dukascopy**. For US-equity/futures tick/L2: only via Databento's one-time $125 credit (then paid).

**Q3 — Best free corporate actions (splits/dividends) for US equities?**
For convenience: **yfinance `.actions`** (instant, free, but ~verify). For clean/reliable: **Tiingo** splits & dividends APIs (within the 500-symbol/mo cap). For authoritative/point-in-time: **SEC EDGAR** (dividends declared in 8-Ks; splits in filings). **Recommendation: use Tiingo as primary corp-actions feed for your tracked universe, cross-check anomalies against yfinance and EDGAR.** Never trust a single source's adjusted close for backtests.

**Q4 — Concrete free stack per asset class:** see **§1 table** (primary + backup each).

---

## 4. Critical Warnings / Gotchas (read before building)

1. **yfinance is convenience, not infrastructure.** ToS = personal-use-only; endpoints break; split/div values occasionally wrong; 429s are routine. Cache aggressively, add backoff, and **always have Stooq/Tiingo as the real source-of-record.** (It IS, however, actively maintained — v1.x in 2025/2026 — so the "abandoned" reputation is outdated.)
2. **Alpaca free = IEX feed (~2% volume).** Great for signals on liquid names + paper execution; **wrong for VWAP/microstructure/illiquid names.**
3. **Survivorship bias is the silent killer.** Free US-equity feeds (Stooq, yfinance, Tiingo free) are **current-listings-centric** and weak on delisted tickers → backtests are optimistically biased. Norgate solves this but is paid. **Document this limitation explicitly in any equities backtest.** (Crypto and SEC EDGAR don't have this problem the same way.)
4. **Polygon free (5/min, 2yr) and Alpha Vantage free (25/day) are demos**, not workhorses. Don't architect around them.
5. **Binance bulk dumps have no order book** — depth must be recorded live. Budget storage: full-depth crypto L2 is GB/day per symbol.
6. **NDL/Quandl WIKI equities is frozen (pre-2018).** Don't use for live prices.
7. **Rate limits move constantly** — every figure here is current as of mid-2026; re-verify the pricing/limits page before committing code. Build a thin per-source adapter layer so swapping a provider is cheap.
8. **Licensing:** all sources above are fine for **single-user personal/research** use. None of this is licensed for redistribution or commercial productization — which matches Project ALPHA's stated personal scope.

---

## 5. Suggested Build Order (data layer)
1. **FRED + SEC EDGAR** (zero-caveat, authoritative) — stand these up first.
2. **Stooq bulk backfill** → local Parquet store of full US-equity daily universe.
3. **Tiingo** adapter for clean adjusted EOD + corp actions on your tracked watchlist.
4. **Alpaca** for 1-min intraday + as the **paper-trading execution venue**.
5. **ccxt + Binance Vision** for crypto OHLCV/tick; add a **ccxt.pro websocket recorder** for L2 depth on your target pairs.
6. **Dukascopy** tick pull for FX research.
7. Spend the **Databento $125** on one targeted futures dataset only when a specific futures study demands real CME data.
8. yfinance wired in last, as a labeled "best-effort/backup" adapter behind a cache.

---

### Sources
- yfinance: [PyPI](https://pypi.org/project/yfinance/), [rate-limit issue #2422](https://github.com/ranaroussi/yfinance/issues/2422), [#2128](https://github.com/ranaroussi/yfinance/issues/2128), [MarketXLS guide](https://marketxls.com/blog/yahoo-finance-api-ultimate-guide), [Medium: blocked](https://medium.com/@trading.dude/why-yfinance-keeps-getting-blocked-and-what-to-use-instead-92d84bb2cc01)
- Alpaca: [About Market Data API](https://docs.alpaca.markets/docs/about-market-data-api), [Market Data FAQ](https://docs.alpaca.markets/us/docs/market-data-faq), [Paper Trading](https://docs.alpaca.markets/us/docs/paper-trading)
- Polygon: [request limits KB](https://polygon.io/knowledge-base/article/what-is-the-request-limit-for-polygons-restful-apis)
- Tiingo: [pricing](https://www.tiingo.com/about/pricing), [crypto](https://www.tiingo.com/products/crypto-api), [splits](https://www.tiingo.com/documentation/corporate-actions/splits), [dividends](https://www.tiingo.com/documentation/corporate-actions/dividends)
- Alpha Vantage: [Macroption limits](https://www.macroption.com/alpha-vantage-api-limits/), [premium](https://www.alphavantage.co/premium/)
- Finnhub: [rate limit docs](https://finnhub.io/docs/api/rate-limit), [pricing](https://finnhub.io/pricing-stock-api-market-data)
- Twelve Data: [pricing](https://twelvedata.com/pricing), [trial](https://support.twelvedata.com/en/articles/5335783-trial)
- EODHD: [API limits](https://eodhd.com/financial-apis/api-limits), [pricing](https://eodhd.com/pricing)
- FRED: [fredapi GitHub](https://github.com/mortada/fredapi), [PyPI](https://pypi.org/project/fredapi)
- Stooq: [bulk DB](https://stooq.com/db/h/), [pandas-datareader](https://pandas-datareader.readthedocs.io/en/latest/readers/stooq.html), [QuantStart](https://www.quantstart.com/articles/an-introduction-to-stooq-pricing-data/)
- Nasdaq Data Link: [QDL publisher](https://data.nasdaq.com/publishers/QDL), [rate limits](https://docs.data.nasdaq.com/docs/rate-limits)
- ccxt: [GitHub](https://github.com/ccxt/ccxt), [npm](https://www.npmjs.com/package/ccxt)
- Binance: [public-data repo](https://github.com/binance/binance-public-data), [spot API docs](https://developers.binance.com/docs/binance-spot-api-docs)
- Kraken: [downloadable OHLCVT](https://support.kraken.com/articles/360047124832-downloadable-historical-ohlcvt-open-high-low-close-volume-trades-data), [time & sales](https://support.kraken.com/articles/360047543791-downloadable-historical-market-data-time-and-sales-)
- Coinbase: [get product candles](https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-candles)
- Bybit: [history data](https://www.bybit.com/derivatives/en/history-data), [kline docs](https://bybit-exchange.github.io/docs/v5/market/kline)
- Dukascopy: [dukascopy-python](https://pypi.org/project/dukascopy-python/), [dukascopy-node](https://github.com/Leo4815162342/dukascopy-node), [TickVault](https://github.com/keyhankamyar/TickVault)
- Databento: [pricing](https://databento.com/pricing), [stocks $125 credit](https://databento.com/stocks), [Jan 2025 pricing change](https://databento.com/blog/upcoming-changes-to-pricing-plans-in-january-2025)
- SEC EDGAR: [EDGAR APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces), [edgartools](https://github.com/dgunning/edgartools)
- Options (free landscape): [QuantVPS options APIs](https://www.quantvps.com/blog/best-apis-for-historical-options-market-data-volatility)
