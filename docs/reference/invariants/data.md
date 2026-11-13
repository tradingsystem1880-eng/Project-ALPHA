---
owner: data layer
sources:
  - packages/alpha-data/src/**
  - tests/unit/test_pit*.py
  - tests/unit/test_parquet_store.py
  - tests/unit/test_snapshot.py
  - tests/unit/test_ingest_pipeline.py
  - tests/unit/test_crypto_*.py
  - tests/bias_guards/test_pit_*.py
  - tests/bias_guards/test_source_future_poison.py
  - tests/bias_guards/test_universe_survivorship.py
verified: 1724a5befe5d
---

# Data layer invariants

What must hold in `alpha_data` (`packages/alpha-data/src/alpha_data/`): the raw store, the point-in-time
(PIT) readers, vendor receipts and promotion, snapshots, and the crypto data house. Project-wide rules are
stated once in [research integrity](research-integrity.md); this file holds the data-layer mechanics.

## Package boundary

- Import only `alpha_core` (plus numpy/polars) — import-linter contract `alpha_data depends only on core`
  in `pyproject.toml`. See [engineering § Import layers](engineering.md#import-layers).
- Never import `alpha_patterns` for a shared formula — copy the closed form and pin it equal by test.
  `crypto/features.py` re-implements `alpha_patterns.vsa.rolling_ols_residual`; parity is pinned in
  `tests/unit/test_crypto_defi_tvl_feature.py`.
- pandas appears only in `adapters/yfinance_adapter.py` — [engineering § Polars by default](engineering.md#polars-by-default).
- No commands or composition here; `alpha_cli` composes data operations.

## Point-in-time store

General rule: [research integrity § Point-in-time reads](research-integrity.md#point-in-time-reads).
[ADR-0005](../../adr/0005-point-in-time-firewall.md).

- Feed strategies, backtests and charts only through `PointInTimeSource.as_of` (typed `Bar`s) or
  `PointInTimeReader.as_of` (frame). Never hand `ParquetStore.read_bars` output to a decision. Full-history
  loads also go through the source with a far-future cutoff (`alpha_cli._runner.load_bars`).
- The firewall is `filter(ts <= when)` — inclusive. Keep `<=`. Enforced by
  `tests/bias_guards/test_pit_future_poison.py` (future poison plus a non-vacuity edit at `when`).
- `PointInTimeReader.as_of` raises `DataError` on a naive cutoff before reading any data, and converts a
  named-zone cutoff to UTC before comparing, so the inclusive instant survives DST. The host time zone never
  supplies an offset. Enforced by `tests/unit/test_pit_tz.py`.
- `dividends_as_of` also raises `DataError` on a naive cutoff, for the same reason: `astimezone(UTC)` would
  read the host zone.
- Typed reads validate bars only after cutoff filtering: an invalid future bar cannot break a past read; an
  invalid visible bar raises chained `DataError` with symbol, timestamp and reason. Never skip or coerce it.
  Enforced by `tests/bias_guards/test_source_future_poison.py`.
- A UTC cutoff says nothing about when a provider published or revised a value.
- The store holds raw, unadjusted bars and does not enforce `Bar` invariants (zero volume is legal).
  Validation happens at ingest and at the typed read.
- `write_bars` replaces a symbol wholesale and atomically (temp sibling, then `os.replace`). It rejects missing
  columns, a tz-naive `ts`, and duplicate timestamps, and sorts by `ts` — positional readers rely on one
  sorted, tz-aware row per session.
- Store paths reject empty, `..`, backslash and absolute names. A slash symbol (`BTC/USD`) becomes a
  subdirectory, so it never collides with `BTC_USD`.

## Corporate actions

General rule: [research integrity § Corporate actions: two clocks](research-integrity.md#corporate-actions-two-clocks).
[ADR-0004](../../adr/0004-two-clock-corporate-actions.md).

- Knowledge gate: `known_actions` keeps actions whose `knowledge_time` is on or before the cutoff's UTC date.
  `knowledge_time` is `announce_date`, else `ex_date` (flagged `knowledge_is_estimated`).
- Application gate: prices rescale only for splits that are known and already ex (`ex_date` on or before the
  cutoff date). `split_factor` applies `1/ratio` to bars strictly before `ex_date`; volume divides by the same
  factor. An announced future split leaves every visible price untouched.
  Enforced by `tests/bias_guards/test_pit_corporate_action.py`.
- Dividends never touch prices. `dividends_as_of` returns knowledge-gated dividends (visible before ex) for
  the engine to credit at `pay_date`. Enforced by `tests/bias_guards/test_pit_dividend_event.py`.
- A split without `ratio` or a dividend without `amount` raises `DataError`.

## Universe membership

- A universe is a list of `alpha_core.UniverseMembership` intervals: `effective_from` inclusive,
  `effective_to` exclusive, optional `delisting_return`. It is stored wholesale as `universe/<name>.json`.
- The only sanctioned read is `alpha_core.members_as_of(memberships, when)`: it keeps names that later left
  and hides future additions. Never filter by current constituents. Enforced by
  `tests/bias_guards/test_universe_survivorship.py`, whose survivors-only leaky twin must fail.
- A symbol that later stopped trading stays readable as of dates it traded (`tests/bias_guards/test_survivorship.py`).
- `parse_universe_csv` fails loud on missing columns, an invalid row, or no rows.

## Vendor receipts and promotion

[ADR-0017](../../adr/0017-authoritative-daily-data-and-broker-paper-boundary.md). Path for every daily pull:
provider → immutable receipt → candidate → quality gate → canonical Parquet → snapshot.

- `stage_and_promote` refuses a `FetchResult` without identity, receipt and raw response, or whose symbol or
  row/action counts disagree with the receipt. The receipt's response hash and length must match the raw bytes.
- A candidate is quarantined, never promoted, on any of: duplicate timestamps; non-numeric, non-finite or
  non-positive prices; inconsistent OHLC; negative volume; a provider other than the configured authority;
  exchange-calendar gaps (stock/ETF); a stored session missing from the new pull; conflicting corporate actions
  (same type and ex-date); or a cross-source close difference above the threshold (default 1%, skipped on
  action dates). Enforced by `tests/unit/test_ingest_pipeline.py`.
- Corrections stay visible: the quality report lists changed timestamps with old and new row hashes.
- Only `promote_quarantined(..., approve_differences=True)` promotes a quarantined receipt — an explicit,
  owner-reviewed repair. It re-verifies the stored receipt bytes and candidate identity first.
- Promotion writes an immutable pre-promotion backup and a fail-closed marker before touching canonical
  files. An in-process failure restores the exact prior bytes. After a process interruption the marker stays
  and every read of that symbol raises until `rollback_interrupted_promotion(..., acknowledge=True)`.
- Immutable receipt, candidate and quarantine directories may be republished only with identical bytes.
- Provenance v2 embeds `DatasetIdentity` and `FetchReceipt`; three-field legacy provenance stays readable.
  `DatasetIdentity` accepts only daily (`1D`) raw-price datasets.

## Snapshots

General rule: [research integrity § Immutable, hash-bound artefacts](research-integrity.md#immutable-hash-bound-artefacts).

- `create_snapshot` refuses an existing id, builds in private staging, and publishes with one `os.rename`;
  concurrent writers publish exactly one complete snapshot. Never edit a published snapshot.
- Snapshot ids and manifest paths cannot escape the root: no `/`, `\`, `..` or leading `.` in ids; no
  absolute or parent paths and no symlinks in manifests.
- The copy is bound to the source inodes. If bars, actions or provenance change during the copy, or a
  promotion is pending, creation fails.
- Source relabelling is refused: stored provenance must equal the declared source, adapter and parser
  versions, and a `ccxt:` snapshot requires provenance.
- `verify_snapshot` re-hashes every file against the manifest. `snapshot_manifest_hash` verifies first and
  then hashes the manifest bytes — that digest is what run identity binds.
- Tests: `tests/unit/test_snapshot.py`; promotion/snapshot interplay in `tests/unit/test_ingest_pipeline.py`.

## Adapters and authority

- Tiingo EOD is the authority for stock/ETF daily history. yfinance and Stooq are comparison only and never
  replace qualified Tiingo history.
- Adapters return raw prices plus explicit actions. Yahoo serves split-adjusted OHLCV, so
  `parse_yfinance_history` reconstructs raw prices and fails loud if a split's ex-date jump is missing.
- Tiingo parsing rejects naive or out-of-range dates, non-finite or non-positive prices, and adjusted/raw
  ratios that disagree within a row. Transport failures expose only the exception type, with context
  suppressed; the API key travels only in a header. A bounded read keeps its byte ceiling (1 byte to 32 MiB).
  Enforced by `tests/unit/test_tiingo_adapter.py` and `tests/unit/test_tiingo_bounded_fetch.py`.
- Stooq fails loud on its per-IP "Access denied", challenge pages and HTML bodies; HTTP errors and interrupted
  reads (`IncompleteRead`, timeouts, connection errors) become a typed `DataError`.
- CCXT accepts only `coinbase` and `binance`, returns completed intervals only, never sends `since=0` (Coinbase
  answers it with the latest bars), and keeps venue-qualified `ccxt:<exchange>` provenance byte-compatible.
  It paginates past per-call caps; the daily `fetch(date, date)` contract delegates to `fetch_timeframe`.
- `CCXTAdapter.first_bar` is a daily-only listing-date probe, never a history read: it checks `load_markets`,
  scans forward from 2009 in page-sized windows, and fails loud on an unknown market, no history, or a bar
  earlier than requested. It stores nothing.
- QuantPad is no longer a provider: its adapter and archive code were removed on 2026-11-14
  ([ADR-0018 note](../../adr/0018-quantpad-external-research-data-boundary.md#owner-supersession--2026-11-14)).
  Datasets registered earlier from a QuantPad receipt stay readable and research-only.

## Crypto storage

[ADR-0032](../../adr/0032-governed-crypto-data-house.md).

- Bulk bytes live on the configured external volume; manifests and the control database stay internal.
  Before any write, `verify_ready` checks volume UUID, writability and the free-space reserve, failing closed.
  `verify_readable` checks mount and UUID only, without a write probe.
- Publish external bytes first and the internal manifest last. A manifest id is the SHA-256 of its canonical
  body; an existing path may be republished only with identical bytes.
- Normalized bytes publish only after every input raw manifest re-verifies and the bytes match the quality
  report hash. Derived artifacts accept only normalized inputs.
- Bybit derivative trades and order-book snapshots require a `CryptoAcquisitionScopeV1` (research case,
  revision, reason); any other family refuses a scope. Unscoped historical captures stay readable but cannot
  enter governed snapshots.
- Storage paths are confined to their root; symlinks are refused.
- Cleanup deletes only `bulk/cache`. Staging, raw, normalized, snapshot, manifest and control roots are never
  removed.
- Retirement appends a hash-bound receipt under the admission lock and never deletes manifests, raw lineage or
  payloads. Only `inactive_quarantined` and `revoked_units_error` are valid reasons. Retired inputs are
  excluded from new admission and active inventories; full audits include them. `scripts/crypto_data_hygiene.py`
  audits references (`--report`) and repeats the audit under the lock before `--apply`; it fails closed on
  unreadable evidence and never retires referenced artifacts.
- Normalized reads are capped at 32 MiB and re-verify the artifact while reading.
- Archive charts ([ADR-0038](../../adr/0038-local-confirmation-and-terminal-archive-charts.md)): inventory is
  discovery only; a chart read runs full manifest and raw-lineage verification, then checks dataset identity,
  units and the completed-bar cutoff. Reconstructed archive history does not establish point-in-time
  availability or research admission. A listed venue pair is no proof that bars are stored.
- A chart group joins archive segments only for one identical identity; overlapping bars must agree exactly or
  the read fails loud (`alpha_cli/_chart_data.py`).

## Crypto identity and features

- One primary authority per dataset family: Binance (CEX spot/futures), Bybit (derivatives/options),
  CoinGecko (identity/reference), GeckoTerminal (DEX pools), Coin Metrics Community (on-chain), Coinbase via
  CCXT (comparison only). No fallback changes venue, quote asset, units, frequency or evidence.
- Never merge USD, USDT and USDC. Keep each interval, venue, market type and quote currency a separate identity.
- Ticker-only joins are prohibited: `AssetMaster.resolve_ticker` always raises. Contract lookups need network
  plus contract address; native assets resolve only through a reviewed mapping.
- Reviewed native masters are label-frozen: `reviewed-native-v1` bytes never change; new assets go in a new
  label. An unknown label fails loud. Digests are pinned in `tests/fixtures/crypto/reviewed_native_asset_masters.json`
  and checked by `tests/unit/test_crypto_asset_master.py`. `reviewed-native-v1` (BTC, ETH) stays the default;
  `reviewed-native-v2` adds XRP and SOL and seeds `build_cross_provider_asset_master`.
- A feature's availability may never precede an input observation or its source availability, and no
  feature reads a later observation. Enforced by `tests/bias_guards/test_crypto_features_future_poison.py`.
- Per-provider fetch, parse, budget and availability rules (Binance, Bybit, CoinGecko, GeckoTerminal,
  DefiLlama) and coverage profiles are in [crypto providers](crypto-providers.md).
