# Crypto data workstation and timeframe coverage

Owner direction: crypto-only market research; make supported markets easy to find and pull, make the existing expansion-drive archive useful, and expose useful chart intervals. Keep source, venue, market type, quote, frequency, units, and exact manifest identity visible.

## Decisions and constraints

- Reuse existing CCXT, Binance public archives, Bybit, CoinGecko, Coin Metrics, and GeckoTerminal adapters before adding a new provider or package.
- Use the Binance public archive's native OHLCV intervals as separate immutable datasets. Do not synthesize weekly/3-day/4-hour bars from daily data, merge quote currencies, or let chart discovery imply research admission.
- Keep canonical backtests on the existing daily PIT store until a separately reviewed contract supports other frequencies. Archive chart selection verifies the exact artifact and lineage; it grants no strategy authority.
- Capability and coverage summaries are discovery projections. Explicit full storage verification remains a distinct, clearly labeled operation.
- Preserve all pre-existing workspace changes and user data. Do not read or edit `tests/holdout/`.

## Slices

1. **Restore crypto data discovery responsiveness** — capability projection must not re-hash every artifact on every screen open; keep selected-artifact verification and full inventory verification explicit. Verify with a regression test and live API latency under a large manifest fixture.
2. **Find any supported spot pair — complete** — Data Manager searches the latest qualified local Binance spot membership catalog through bounded CLI/API reads; selecting a listing chooses the Binance venue and keeps “listed” separate from “history downloaded”. A manual exact pair remains available. The CLI verifies the selected catalog artifact. A fresh keyless Binance spot listing snapshot was acquired on 2026-10-01 and its source date/staleness are visible.
3. **Native multi-timeframe crypto archives — complete** — Binance OHLCV acquisition and archive charts support native `1m`, `5m`, `15m`, `30m`, `1h`, `2h`, `4h`, `6h`, `8h`, `12h`, `1d`, `3d`, and `1w` intervals. Each frequency, venue, market and quote stays in its own immutable manifest. Exact-compatible monthly segments are verified before charting; identical boundary bars coalesce and conflicts fail. Canonical daily backtests are unchanged. A live 43-segment AAVEUSDT 1h series opened with 41,113 unique bars.
4. **Crypto-first workspace polish and API audit — complete for this slice** — added typed local market discovery, empty/unconfigured and stale-catalog states, interval filtering and bounded archive metadata; verified market catalog, capability, chart discovery and 41k-bar chart reads through the live API. The full backend suite and frontend component gate passed separately; a single aggregate exact-tree full-gate stamp was not produced because the generated API/static assets were synchronized between those runs.

Each slice must remain independently testable. No live trade/order paths, research-gate changes, implicit provider fallback, or claims of current live quotes from stored candles.
