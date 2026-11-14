---
owner: data layer
sources:
  - packages/alpha-data/src/alpha_data/timeframe.py
  - packages/alpha-data/src/alpha_data/pipeline.py
  - packages/alpha-data/src/alpha_data/snapshot.py
  - packages/alpha-data/src/alpha_data/adapters/alpaca_adapter.py
  - packages/alpha-data/src/alpha_data/adapters/ccxt_adapter.py
verified: b4b36f41caa0
---

# Bar timeframes

What must hold for bars of any timeframe in the stock/ETF/CCXT store. The rest of the data layer:
[data invariants](data.md).

## Rules

Owner decision 2026-11-15: there is no daily-only rule. Daily (`1D`) is the default, not a limit.

- `BarTimeframe` covers 1 to 59 minutes, 1 to 23 whole hours, and one day; canonical spellings are
  `1D`, `<n>m`, `<n>h`. Longer bars are a design limit (resample stored daily bars).
- The one refusal is the no-high-frequency-trading boundary: sub-minute bars and tick, trade, quote or
  order-book data raise `DataError` naming the owner's rule (`parse_timeframe`).
- A stored bar's `ts` is the START of its interval in UTC; an intraday bar is known only at `ts + duration`.
  Daily bars keep the session-date 00:00 UTC stamp. Every intraday bar start lies on one grid that restarts
  at each UTC midnight (`BarTimeframe.is_aligned`).
- Each timeframe has its own complete store root: `store` for daily, `store-<canonical>` (for example
  `store-5m`) otherwise (`store_dir`). Receipts, quality, promotion and provenance work per root, so
  intraday bars never mix with daily bars. A snapshot of a non-daily store records `"timeframe"` in its
  manifest; daily manifests have no such key (`snapshot_timeframe` reads it, default `1D`).
  `verify_snapshot` and `snapshot_manifest_hash` take the timeframe the caller will read, default `1D`, so
  every daily consumer refuses an intraday snapshot instead of reading its bars as days.
- Intraday stock pulls are bounded by exchange-local session dates (New York midnight to midnight), so the
  "stored session missing from the new pull" check compares in that timezone: a winter after-hours bar
  stamped after 00:00 UTC belongs to the earlier session.
- `parse_timeframe` refuses `1M`, weeks and years rather than guess (`1M` is a month in pandas and CCXT).
- Intraday stock/ETF quality: per exchange session (DST and half days from `exchange_calendars`), every
  timeframe-aligned bar whose interval meets regular hours must be present (`intraday_gap`), a session with
  none is a `calendar_gap`, and an off-grid bar is `misaligned_bar`; all critical. Pre-market and
  after-hours bars are kept and counted (`extended_hours_rows`). Tests: `tests/unit/test_bar_timeframe.py`,
  `tests/unit/test_ingest_pipeline_intraday.py`.

## Adapters

- Alpaca intraday: the SIP feed, bars exactly as Alpaca returns them (pre-market and after-hours
  included), stamped at the bar start; requests run from New York midnight of the first session date to
  the second before New York midnight after the last; the split cross-check uses each bar's New York
  date. Alpaca hourly bars are clock-aligned (the 09:00 New York bar holds 09:00-09:59), so hours that
  start at the 09:30 open are resampled from minute bars. Tests: `tests/unit/test_alpaca_adapter.py`.
- CCXT intraday: an intraday series must be a contiguous grid; a missing bar fails loud (crypto trades
  24/7; Coinbase omits buckets with no trades, so sparse pairs at short bars are refused). CCXT pulls keep
  no receipt or raw pages (legacy provenance). Tests: `tests/unit/test_ccxt_intraday_timeframe.py`.
