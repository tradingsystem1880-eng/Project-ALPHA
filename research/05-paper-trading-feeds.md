# 05 — Paper Trading & Free Real-Time Feeds

**Project ALPHA** · Personal, $0-budget, Python-first, backtest→paper code parity, institutional-grade methodology.
**Research date:** 2026-06-14
**Mission:** Recommend the best FREE path to paper trading with backtest→paper parity, plus the free real-time data feeds that power it.

---

## 0. TL;DR / Decision

**Primary recommendation: `nautilus_trader` as the single engine for both backtest and paper trading.** It is the only free, open-source, Python-first engine where *the exact same strategy class runs unchanged* in backtest and live, with a production-grade reconciliation layer. Critically, it ships a **`SandboxExecutionClient`** that runs the *same internal matching engine used in backtests*, fed by a *live data adapter* — giving you broker-independent paper trading with perfect code parity and zero cost, no broker paper account required.

Concrete free stack:

| Layer | Pick | Why | Cost |
|---|---|---|---|
| **Engine (backtest + paper)** | `nautilus_trader` | Same code both sides; reconciliation; stable adapters | Free (LGPL) |
| **Crypto data + exec (paper)** | Binance / Bybit **testnet** via Nautilus native adapters, OR `ccxt` `set_sandbox_mode(True)` | Genuinely free real-time L2 + trades; real exchange matching on testnet | Free |
| **Equities data (paper)** | **Alpaca free IEX websocket** feeding Nautilus `SandboxExecutionClient` | Only truly-free real-time US equity stream | Free (IEX-only) |
| **Equities exec alt.** | **IBKR paper account** via Nautilus IB adapter + delayed data | Realistic broker fills; `DELAYED_FROZEN` data is free | Free |

**Start by paper-trading CRYPTO.** Free crypto data is full-depth, real-time, and 24/7. Free US-equity data (Alpaca IEX) is thin and unrepresentative of true NBBO — fine for plumbing/parity validation, *not* for trusting fill quality or microstructure signals.

---

## 1. The Parity Question — Which engines deliver true backtest↔live/paper code reuse?

This is the make-or-break criterion. "Has a live mode" ≠ "same code runs in both." Findings:

### nautilus_trader — ✅ BEST PARITY (recommended)
- Explicit design goal: *"The same actors, strategies, and execution algorithms run against both the backtest engine and a live trading node."* ([live docs](https://nautilustrader.io/docs/latest/concepts/live/))
- Backtest uses `BacktestEngine`; live/paper uses a `TradingNode` (`TradingNodeConfig`). **Your `Strategy` subclass is identical** — only the node wiring (which data/exec client) changes.
- Rust-native core, event-driven, nanosecond clock, deterministic time model shared across research and live. This is the closest thing to institutional infra in the free tier.
- **Reconciliation engine** (see §6) is built-in — this is what separates it from toys.
- Sources: [nautilustrader.io](https://nautilustrader.io/), [GitHub](https://github.com/nautechsystems/nautilus_trader), [adapters docs](https://nautilustrader.io/docs/latest/concepts/adapters/).

### QuantConnect LEAN — ✅ Real parity, ⚠️ not really "free/local" for paper
- LEAN (the open-source engine) genuinely runs the same `QCAlgorithm` in backtest and live; the cloud offers paper ("live paper") deployment.
- Free tier exists for research/backtest, but **continuous live/paper deployment realistically pushes you to paid** ($/mo per live node) and ties you to the cloud + their data. Self-hosting LEAN live locally is possible but heavier to operate than Nautilus.
- Good fallback if you want managed infra; **not** the cleanest $0 self-hosted path. Sources: [lean.io](https://www.lean.io/), [QC review](https://www.newtrading.io/quantconnect-review/).

### backtrader — ⚠️ Parity in principle, project largely unmaintained
- Supports live via broker store integrations (e.g. IB, and historically an Alpaca community bridge `alpaca-backtrader-api`), and the *same* `Strategy` can run live.
- BUT: backtrader is **effectively unmaintained**, live broker bridges are community-maintained and brittle, and it lacks a real reconciliation layer. Acceptable for hobby use; **below the "institutional-grade" bar** you set. Sources: [comparison](https://chartswatcher.com/pages/blog/top-backtesting-software-comparison-for-2025), [alpaca-backtrader-api](https://github.com/alpacahq/alpaca-backtrader-api).

### Others (quick verdicts)
- **vectorbt / backtesting.py / zipline-reloaded** — backtest-only (or vectorized); **no first-class live/paper adapter**. Great for research, not for parity. Use for fast vectorized sweeps, then port the *winning* logic into the Nautilus strategy.
- **Roll-your-own event loop** — you'd reinvent reconciliation, partial-fill handling, and clock determinism. Not worth it.

**Verdict:** `nautilus_trader` is the answer to Question #1. LEAN is the managed-cloud runner-up.

---

## 2. Recommended Paper-Trading Architecture (reuses backtester code)

The elegant part: in Nautilus you swap the **execution client**, not the strategy.

```
                 ┌─────────────────────────────────────────────┐
                 │           YOUR STRATEGY CODE                 │
                 │   class MyStrat(Strategy):  # written ONCE   │
                 │     on_bar / on_quote_tick / on_order_filled │
                 └───────────────┬─────────────────────────────┘
                                 │  (identical in all 3 modes)
        ┌────────────────────────┼────────────────────────────────┐
        ▼                        ▼                                 ▼
  ┌───────────┐          ┌──────────────────┐            ┌──────────────────┐
  │ BACKTEST  │          │  PAPER (SANDBOX)  │            │ PAPER (VENUE)     │
  │ Engine    │          │  TradingNode +    │            │ TradingNode +     │
  │ historical│          │  SandboxExecClient│            │ real paper acct   │
  │ data      │          │  + LIVE data feed │            │ (Binance testnet, │
  └───────────┘          └──────────────────┘            │  IBKR DU account) │
   OrderMatching          SAME OrderMatching              real venue matching
   Engine (sim)           Engine (sim), but               on testnet/paper
                          driven by live ticks
```

### Two flavors of paper trading — use both, for different purposes

**Flavor A — Sandbox execution (`SandboxExecutionClient`): broker-independent, works for ANY data source.**
- Nautilus instantiates an internal **simulated exchange** (the *same* `OrderMatchingEngine` used in backtests) inside the live node, and feeds it **real-time data from a live data adapter** (e.g. Alpaca IEX, Binance market data, Databento).
- Your orders are matched against the live book/quotes locally. **No venue paper account needed**, works for US equities where you have *data* but no free exec sandbox.
- Confirmed behavior: *"Sandbox execution reuses the same matching engine and `book_type` configuration, ensuring paper trading simulations mirror backtest behavior consistently."* ([backtest internals](https://nautilustrader.io/docs/latest/concepts/backtesting/))
- ⚠️ Caveat the maintainers state explicitly: sandbox fills happen at **local latency (microseconds)** which is **unrealistically fast** vs. a real venue. So sandbox is optimistic on latency/queue position — model fills conservatively. ([issue #1677](https://github.com/nautechsystems/nautilus_trader/issues/1677))

**Flavor B — Real venue paper/testnet endpoints (most realistic fills).**
- **Crypto:** Binance / Bybit **testnet** via the native Nautilus adapters (`environment=BinanceEnvironment.TESTNET`, analogous enum for Bybit). Orders hit the exchange's *actual* matching engine on test infra — realistic partial fills, rejects, fees. ([binance.md](https://github.com/nautechsystems/nautilus_trader/blob/develop/docs/integrations/binance.md))
- **Equities/futures:** **IBKR paper account** (account id starts with `DU`) via the Nautilus IB adapter through IB Gateway/TWS. Realistic broker-side simulation. ([ib.md](https://raw.githubusercontent.com/nautechsystems/nautilus_trader/develop/docs/integrations/ib.md))

### The cleanest free combo (opinionated)
1. **Crypto first:** Nautilus + **Binance testnet** (native adapter) — full real-time L2 depth & trades for *free*, real exchange matching. Add Bybit testnet for a second venue/perps.
2. **Equities:** Nautilus + **Alpaca free IEX websocket → `SandboxExecutionClient`** for parity plumbing, AND in parallel an **IBKR paper account** for more realistic fills (with free delayed data while unfunded — see §4/§5).
3. Keep `ccxt` (+ `ccxt.pro` for websockets) in your toolbox as a **unified fallback/secondary** crypto path and for venues Nautilus doesn't natively support — `set_sandbox_mode(True)` flips ccxt to testnet across exchanges.

> ⚠️ **Reality check on Nautilus + Alpaca:** there is **no merged Alpaca adapter** in Nautilus. An RFC ([issue #3374](https://github.com/nautechsystems/nautilus_trader/issues/3374), opened 2026-01-01) proposes `AlpacaDataClient`/`AlpacaExecutionClient`, but as of this research it is **proposal-only, not implemented**. So to use Alpaca *inside* Nautilus today you must either (a) wait for/contribute to that adapter, or (b) write a thin custom `LiveMarketDataClient` that pushes Alpaca websocket ticks into the Nautilus message bus and pair it with `SandboxExecutionClient`. If you don't want to write an adapter, use the **IBKR adapter (stable, native)** for equities and run Alpaca standalone (see §3) as a simpler parallel track.

### Nautilus stable adapters relevant to us (from README, 2026)
| Adapter | ID | Type | Status | Free paper path |
|---|---|---|---|---|
| Binance | `BINANCE` | Crypto CEX | **Stable** | ✅ Testnet env |
| Bybit | `BYBIT` | Crypto CEX | **Stable** | ✅ Testnet env |
| OKX | `OKX` | Crypto CEX | **Stable** | ✅ Demo/testnet |
| Kraken | `KRAKEN` | Crypto CEX | **Stable** | (limited testnet) |
| Coinbase Intl | `COINBASE` | Crypto CEX | **Stable** | sandbox |
| Interactive Brokers | `INTERACTIVE_BROKERS` | Multi-venue broker | **Stable** | ✅ DU paper acct |
| Databento | `DATABENTO` | Data provider | **Stable** | (paid data) |
| Alpaca | — | Equities/crypto | **RFC only (#3374)** | ❌ not yet |

(Also stable: BitMEX, Deribit, dYdX, Hyperliquid, Polymarket, Tardis. Beta: Derive, Lighter.) Source: [README](https://github.com/nautechsystems/nautilus_trader).

---

## 3. Paper-Trading Venues — detailed

### 3.1 Alpaca Paper Trading (free) — `alpaca-py`
- **Cost:** Free. US equities + crypto + options. Paper account created instantly with an Alpaca login.
- **SDK:** `alpaca-py` (current, actively maintained; `971+` code snippets). Replaces the old `alpaca-trade-api`.
- **Paper toggle is a single flag** — same code, just `paper=True`:
  ```python
  from alpaca.trading.client import TradingClient
  from alpaca.trading.requests import MarketOrderRequest
  from alpaca.trading.enums import OrderSide, TimeInForce

  client = TradingClient("KEY", "SECRET", paper=True)   # paper sandbox
  client.submit_order(MarketOrderRequest(
      symbol="BTC/USD", qty=0.001, side=OrderSide.BUY, time_in_force=TimeInForce.DAY))
  ```
- **Order/fill stream (websocket):**
  ```python
  from alpaca.trading.stream import TradingStream
  ts = TradingStream("KEY", "SECRET", paper=True)
  async def on_update(data): print(data)   # new / partial_fill / fill / canceled ...
  ts.subscribe_trade_updates(on_update)
  ts.run()
  ```
- **Market data stream (the catch — see §4):**
  ```python
  from alpaca.data.live import StockDataStream
  s = StockDataStream("KEY", "SECRET")   # FREE = IEX feed only
  s.subscribe_quotes(handler, "SPY"); s.subscribe_trades(handler, "SPY")
  s.run()
  ```
- **Crypto data** is full and free (no IEX/SIP issue — crypto has no SIP). `CryptoDataStream` gives real-time crypto quotes/trades/bars at no cost.
- ⚠️ **Paper-only accounts are entitled to IEX market data only** (full SIP requires a paid plan even for paper). ([forum](https://forum.alpaca.markets/t/paper-trading-with-iex-streamed-data/16408), [paper-trading docs](https://docs.alpaca.markets/us/docs/paper-trading))
- 📌 Note: Alpaca paper fills are simulated and can be *optimistic*; reset the paper account from the dashboard if state drifts. (Also: PDT rules no longer enforced as of 2026-06-04, per Alpaca — irrelevant for paper but reduces friction if you ever go live.)

### 3.2 Interactive Brokers Paper Account (free) — `ib_async` / Nautilus IB adapter
- **Cost:** Free paper account with any IBKR login (even unfunded). Multi-asset: equities, futures, options, FX, some crypto.
- **Library:** **`ib_async`** is the actively-maintained successor to the now-archived `ib_insync` — use `ib_async`. (Both wrap the TWS API; you must run **IB Gateway or TWS**, or the dockerized gateway `gnzsnz/ib-gateway-docker` for headless/automated.)
- **Ports:** TWS paper `7497` / live `7496`; IB Gateway paper `4002` / live `4001`. Paper account ids start with **`DU`**.
- **Nautilus support is native & stable:** configure `account_id="DU…"`, point at the gateway port, set `trading_mode="paper"`. ([ib.md](https://raw.githubusercontent.com/nautechsystems/nautilus_trader/develop/docs/integrations/ib.md))
- ⚠️ **Market data is the gotcha (see §5):** real-time L1 via API requires a *funded* account ($500+) with paid subscriptions. **BUT** `IBMarketDataTypeEnum.DELAYED_FROZEN` gives **free delayed data for most markets via API** — usable for paper-trading logic/plumbing. FX & crypto need no subscription. The "free real-time in TWS" does **not** flow through the API.
- **Best role in ALPHA:** the most *realistic* free equities/futures fill simulator. Pair with delayed data for development, or with a separate real-time source (crypto/Alpaca) when you need live ticks.

### 3.3 Crypto Exchange Testnets (free) + `ccxt`
- **Binance Testnet** and **Bybit Testnet** are full-featured, mirror production APIs, give virtual balances, and are **free**. They exercise the *real* matching engine (realistic partial fills, rejects, fees, rate limits). ([Binance testnet example](https://github.com/FatherMonkey916/paper-trading-binance), [Bybit ccxt testnet](https://github.com/bipin0x01/TP_BybitBot))
- **`ccxt`** unifies 100+ exchanges; flip to testnet with one call **before** any other call:
  ```python
  import ccxt
  ex = ccxt.binance({"apiKey": K, "secret": S})
  ex.set_sandbox_mode(True)            # -> testnet endpoints, virtual funds
  ex.load_markets()
  ex.create_order("ETH/USDT", "limit", "buy", 0.01, 1000)
  ```
- **`ccxt.pro`** (merged into `ccxt`) adds websockets: `watch_order_book`, `watch_trades`, `watch_ticker`, plus `create_order_ws`. This is your **free real-time L2 depth + trades** firehose for crypto.
- **Role:** secondary/unified crypto path and the way to reach exchanges Nautilus lacks. For your *primary* crypto paper venue, prefer the **native Nautilus Binance/Bybit testnet adapters** (tighter integration with the matching/reconciliation engine) and keep ccxt as the flexible fallback.

---

## 4. Free Real-Time EQUITIES Data — the honest limitation

This is the single most important constraint to internalize.

| Provider | Free real-time? | What you actually get free | Real-time/full requires |
|---|---|---|---|
| **Alpaca** | ⚠️ Partial | **Real-time IEX** websocket (trades/quotes/bars) — *single exchange, ~2–3% of consolidated volume*; full crypto free | **SIP** = "Algo Trader Plus" **$99/mo** (CTA+UTP, 100% volume) |
| **Polygon.io** | ❌ No | **EOD only**, 5 calls/min, 2-yr history. **No real-time, no websocket on free.** | $29/mo Starter = 15-min delayed WS; **$79/mo Developer** = real-time WS |
| **IBKR API** | ❌ (equities) | **Delayed** (`DELAYED_FROZEN`) free; FX/crypto real-time free | Funded acct ($500+) + paid L1 subscriptions |

Sources: [Alpaca data](https://alpaca.markets/data), [Alpaca about-market-data](https://docs.alpaca.markets/us/docs/about-market-data-api), [Alpaca pricing](https://plans.apis.io/plans/alpaca/alpaca-plans-pricing/), [Polygon pricing](https://polygon.io/pricing), [IBKR market-data subs](https://www.interactivebrokers.com/campus/ibkr-api-page/market-data-subscriptions/), [IBKR paper delayed data](https://www.interactivebrokers.com/en/trading/papertrader-delayed-data.php).

### What "IEX-only" really means (practical implications)
- IEX is **one** exchange (~2–3% of US volume). Its top-of-book is **not** the NBBO. Trades print sparsely; many symbols have stale/empty quotes for stretches.
- **Consequences for paper trading on free Alpaca equity data:**
  - ✅ Fine for: validating the **plumbing/parity** (does my Nautilus strategy receive ticks, emit orders, get fills, reconcile?), low-frequency daily/hourly strategies on liquid large-caps where IEX still prints often enough.
  - ❌ **Not** fine for: anything HFT/microstructure, spread/queue/quote-driven signals, mid/small-caps, or trusting that a simulated fill at the "IEX quote" resembles a real NBBO fill. You will get a **falsely rosy or falsely pessimistic** picture.
- **Bottom line:** **paper-trade crypto first** (free data is full-depth & real-time), and use free Alpaca IEX for equities only to prove the pipeline and run slow, liquid-name strategies. Treat genuine equity-microstructure paper trading as **gated behind the $99/mo SIP** — out of scope at $0.

### Free real-time CRYPTO data — genuinely good
- Exchange websockets (Binance, Bybit, Coinbase, Kraken, OKX) provide **free, real-time, full L2 order-book depth + trade prints + funding**, 24/7, for essentially all symbols. Reach them via the **native Nautilus adapters** or **`ccxt.pro`**.
- This is the **only** asset class where your free paper-trading data is *representative of reality*. Lean into it.

### Latency / coverage / reconnection realities
- **Latency:** retail websockets from a home/cloud box add tens–hundreds of ms vs. colocated infra. Sandbox local fills are microsecond-fast (unrealistic). Net: do **not** paper-trade latency-sensitive strategies and expect the numbers to hold live.
- **Coverage:** crypto = broad & free; equities = IEX-thin unless you pay.
- **Reconnection reliability:** retail feeds *will* drop. You must implement **auto-reconnect with backoff, heartbeat/staleness detection, and re-subscription**. Good news: **Nautilus handles reconnect + post-reconnect reconciliation for its native adapters automatically**, and Binance listen-key recovery has had recent reliability fixes ([RELEASES.md](https://github.com/nautechsystems/nautilus_trader/blob/develop/RELEASES.md)). If you hand-roll an Alpaca/ccxt feed, you own this logic. `ccxt.pro` `watch_*` calls should be wrapped in a `while True: try/except` reconnect loop (see ccxt docs).

---

## 5. Free real-time feed picks (summary)

1. **Crypto (primary, fully free & full-depth):** Binance/Bybit/OKX websockets via **native Nautilus adapters** (or `ccxt.pro`). Real-time L2 + trades, 24/7.
2. **US equities (free, limited):** **Alpaca IEX** websocket via `alpaca-py` `StockDataStream`. Real-time but single-exchange/thin. Use for pipeline + liquid, low-freq names.
3. **Equities/futures dev (free delayed):** **IBKR `DELAYED_FROZEN`** via `ib_async`/Nautilus IB adapter — for logic/plumbing when you don't need live ticks.
4. **Avoid for free real-time equities:** Polygon free tier (EOD-only). Only worth it at $79/mo Developer for real-time WS — out of $0 scope.

---

## 6. Order Lifecycle, Fills, Partial Fills & Reconciliation in Paper Mode

### 6.1 Order/fill lifecycle (what to model)
Standard state machine you must handle in *all* modes (Nautilus emits these as events; Alpaca/ccxt expose equivalents):
`SUBMITTED → ACCEPTED → (PARTIALLY_FILLED)* → FILLED` with branches to `REJECTED`, `CANCELED`, `EXPIRED`, and pending states `PENDING_CANCEL`/`PENDING_UPDATE`.
- **Nautilus:** override `on_order_accepted`, `on_order_filled` (carries `last_qty`/`last_px` for *each* partial), `on_order_rejected`, `on_order_canceled`, `on_position_changed`. Same callbacks fire in backtest, sandbox, and live → **parity in your handling code too**.
- **Alpaca:** `TradingStream.subscribe_trade_updates` emits `new`, `partial_fill`, `fill`, `canceled`, `rejected`, etc.
- **ccxt:** poll `fetch_order`/`fetch_open_orders` or `watch_orders` (pro); inspect `status` ∈ `open/closed/canceled` and `filled` vs `amount`.

### 6.2 Partial fills — where paper modes differ
- **Backtest & Nautilus sandbox:** the `OrderMatchingEngine` produces realistic partials **only when fed L2/L3 depth** (it walks the book across levels). With L1 (quotes/bars/trades), it uses a probabilistic **`FillModel`** (`prob_slippage`, `prob_fill_on_limit`, etc.). → **For meaningful partial-fill behavior, feed order-book data (crypto) and configure `book_type=L2_MBP`.** ([backtest internals](https://nautilustrader.io/docs/latest/concepts/backtesting/))
- **Venue testnet/paper (Binance testnet, IBKR DU):** partials come from the *real* matching/sim engine — most realistic, no FillModel guesswork.
- **Alpaca paper:** fills simulated server-side; can be optimistic, especially marketable orders.

### 6.3 Reconciliation — the institutional-grade piece (Nautilus's killer feature)
Live/paper introduces a layer absent from backtest: **execution reconciliation** — aligning your internal state with venue reality. Nautilus does this automatically ([live docs](https://nautilustrader.io/docs/latest/concepts/live/)):
- **At startup:** reconstructs full order/position state from venue history within a configurable lookback window; orders it didn't originate are ingested as **EXTERNAL** (tagged `VENUE`/`RECONCILIATION`) rather than crashing.
- **Continuously:** monitors in-flight orders, polls open positions, audits the book; **generates the missing events** to close any gap (incl. synthetic fills to fix position drift while preserving PnL integrity).
- **Ambiguous outcomes:** on transport failure/timeout it does **not** assume — it waits for venue confirmation via reconciliation loops, only marking `REJECTED` after retries are exhausted. Pending cancels/modifies stay unresolved until the venue confirms.

**This is exactly what you'd otherwise have to build by hand** with Alpaca/ccxt (reconcile local order book vs `fetch_open_orders`/`fetch_positions` on every (re)connect, dedupe fills, recover from missed websocket messages). It's the strongest non-parity argument for routing everything through Nautilus.

### 6.4 Reconciliation checklist if you DON'T use Nautilus (e.g. raw `alpaca-py`/`ccxt`)
- On every startup/reconnect: pull `fetch_open_orders` + `fetch_positions` (ccxt) / `get_orders` + `get_all_positions` (alpaca) and diff against your local store.
- Assign every order a **client order id** (`client_order_id` in Alpaca; `clientOrderId`/`params` in ccxt) so you can dedupe across reconnects.
- Treat the websocket as best-effort; **REST is the source of truth** for state recovery.
- Detect partial fills via cumulative `filled_qty`; never assume a fill from a single missed message.
- Persist order/position state to disk (so a crash doesn't lose in-flight context).

---

## 7. Concrete Next Steps for ALPHA

1. **Install:** `pip install nautilus_trader alpaca-py ib_async ccxt` (ccxt includes pro websockets).
2. **Phase 1 — Crypto parity loop (best free path):** Write one `Strategy`. Run it in `BacktestEngine` on historical crypto data, then in a `TradingNode` with the **native Binance testnet adapter** (real-time free L2 + real matching). Confirm identical strategy code, verify fills/partials/reconciliation. This validates the entire parity thesis at $0 with *representative* data.
3. **Phase 2 — Equities pipeline:** Stand up an **IBKR paper (`DU`) account** + dockerized IB Gateway; run the same Nautilus strategy with `DELAYED_FROZEN` data to prove the equities path. In parallel, prototype an Alpaca IEX → Nautilus `SandboxExecutionClient` feed (custom `LiveMarketDataClient`) if you want real-time (thin) equity ticks, or run `alpaca-py` standalone for a quick win.
4. **Phase 3 — Decide on data spend:** Only if/when an *equity* strategy proves out on backtest do you consider the **$99/mo Alpaca SIP** (or $79/mo Polygon Developer) to paper-trade it with realistic NBBO. Until then, crypto carries the live-paper program.
5. **Watch [Nautilus issue #3374](https://github.com/nautechsystems/nautilus_trader/issues/3374)** — if/when the Alpaca adapter merges, equities-in-Nautilus becomes plug-and-play and supersedes the custom-feed workaround.

---

## 8. Sources
- NautilusTrader: [site](https://nautilustrader.io/) · [GitHub/README](https://github.com/nautechsystems/nautilus_trader) · [adapters](https://nautilustrader.io/docs/latest/concepts/adapters/) · [live/reconciliation](https://nautilustrader.io/docs/latest/concepts/live/) · [backtest internals](https://nautilustrader.io/docs/latest/concepts/backtesting/) · [IB adapter](https://raw.githubusercontent.com/nautechsystems/nautilus_trader/develop/docs/integrations/ib.md) · [Binance adapter](https://github.com/nautechsystems/nautilus_trader/blob/develop/docs/integrations/binance.md) · [sandbox latency issue #1677](https://github.com/nautechsystems/nautilus_trader/issues/1677) · [Alpaca RFC #3374](https://github.com/nautechsystems/nautilus_trader/issues/3374) · [RELEASES](https://github.com/nautechsystems/nautilus_trader/blob/develop/RELEASES.md)
- Alpaca: [data product](https://alpaca.markets/data) · [about market data](https://docs.alpaca.markets/us/docs/about-market-data-api) · [paper trading](https://docs.alpaca.markets/us/docs/paper-trading) · [market data FAQ](https://docs.alpaca.markets/us/docs/market-data-faq) · [IEX paper forum](https://forum.alpaca.markets/t/paper-trading-with-iex-streamed-data/16408) · [pricing](https://plans.apis.io/plans/alpaca/alpaca-plans-pricing/) · [alpaca-py](https://github.com/alpacahq/alpaca-py)
- IBKR: [market data subscriptions](https://www.interactivebrokers.com/campus/ibkr-api-page/market-data-subscriptions/) · [paper delayed data](https://www.interactivebrokers.com/en/trading/papertrader-delayed-data.php) · [ib_async](https://ib-api-reloaded.github.io/ib_async/) · [ib-gateway-docker](https://github.com/gnzsnz/ib-gateway-docker)
- ccxt: [GitHub](https://github.com/ccxt/ccxt) · [docs](https://docs.ccxt.com/) · [manual](https://github.com/ccxt/ccxt/wiki/manual) · [Bybit testnet example](https://github.com/bipin0x01/TP_BybitBot)
- Polygon: [pricing](https://polygon.io/pricing) · [API guide](https://www.ksred.com/the-complete-guide-to-financial-data-apis-building-your-own-stock-market-data-pipeline-in-2025/)
- Engine comparisons: [LEAN](https://www.lean.io/) · [QuantConnect review](https://www.newtrading.io/quantconnect-review/) · [backtesting software 2025](https://chartswatcher.com/pages/blog/top-backtesting-software-comparison-for-2025)
