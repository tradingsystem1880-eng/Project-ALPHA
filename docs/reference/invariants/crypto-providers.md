---
owner: crypto provider adapters
sources:
  - packages/alpha-data/src/alpha_data/crypto/providers/**
  - packages/alpha-data/src/alpha_data/crypto/profiles.py
  - packages/alpha-data/src/alpha_data/crypto/funding_ingestion.py
  - tests/unit/test_bybit_funding_*.py
  - tests/unit/test_funding_*.py
  - tests/unit/test_crypto_defillama*.py
  - tests/bias_guards/test_defillama_availability.py
  - tests/bias_guards/test_crypto_profiles_future_poison.py
verified: 1c2a00531591
---

# Crypto provider invariants

What must hold in the provider modules of the crypto data house (`packages/alpha-data/src/alpha_data/crypto/providers/`)
and the coverage profiles built from their catalogs. Storage, identity and feature rules are in
[data § Crypto storage](data.md#crypto-storage) and [data § Crypto identity and features](data.md#crypto-identity-and-features);
the commands that drive these modules are in [command line crypto data](cli-crypto-data.md).

## Shared fetch boundary

- Every provider request goes through `providers/_wire.py`: an allowlisted endpoint and parameter set
  (`resolve_endpoint`), and `fetch_bounded` with that provider's own host prefix, MIME set, byte cap and timeout.
  Anything outside them raises `DataError`; a provider never falls back to another host or a looser cap.
- An opt-in `RequestBudget` (used for Binance spot daily REST reads) counts one invocation's HTTP attempts and
  application body bytes across every page. Returned chunks, partial reads and overflow probes all count.
- After a transport failure the budget is marked failed and is never reused. Redirects are refused whenever a
  budget hook is installed. Socket and TLS traffic and hidden transport buffering are outside this accounting:
  never describe the budget as a network-traffic or quota guarantee.

## Binance

- An HTTP error from the archive host names its status (`Binance archive request failed with HTTP 404`); only a
  transport interruption says "rerun to resume".
- Archives are checksum-first: the cache is keyed by the expected SHA-256, a resume uses an exact HTTP `Range`
  from verified resume metadata, and a mismatched checksum, unsafe path or refused range fails loud.
- Kline parsing accepts millisecond and microsecond timestamps and keeps every native field. A REST tail joins
  an archive only when every overlapping provider value is identical (`reconcile_archive_tail`).
- Provider symbols are preserved exactly, Unicode included. The liquid universe is chosen from the last fully
  available session before `as_of` (`point_in_time_liquid_universe`), never the current one.

## Bybit

- Requests are closed, credential-free V5 public calls to the pinned host. Option families require the truthful
  `option` market at the CLI and UI boundaries.
- Linear and inverse units, lifecycle clocks, execution ids, crossed or locked books, mark/index/premium
  discrepancies and stale snapshots (server lag over 60 s) stay explicit fields or failures, never smoothed away.
- Funding pages bind the exact instrument and bounds, keep native signed rates, and never annualize or assume an
  interval. Empty, duplicate, conflicting, foreign or future-settlement pages fail closed; a short page never
  proves coverage ([platform contracts](../../operations/research-platform-contracts.md)).
- Funding collection is offline. `bybit_funding.collect_funding_pages` drives a caller-supplied page callback
  within call and byte limits and always reports `coverage_complete=False`; `funding_ingestion` retains each raw
  body and re-verifies it before any decoder reads it. Neither adds transport, a CLI route or acquisition
  authority; production full bounded-page acquisition stays refused.

## CoinGecko and GeckoTerminal

- Both stay provider-native. An asset detail for one explicitly requested CoinGecko id is bounded descriptive
  metadata without prose or links (`coingecko.py`); it is never asset-master catalog input
  (`alpha_cli/_crypto_asset_master_sources.py` accepts only the `asset_metadata` `all` catalog).
- GeckoTerminal top-pool pages are limited to pages 1 to 5 per network.

## DefiLlama

- Chain TVL `available_at` is the next UTC day boundary, set by the parser. A current download cannot qualify as
  historically known (`tests/bias_guards/test_defillama_availability.py`); the convention is not a publication
  timestamp. [ADR-0036](../../adr/0036-defillama-tvl-supplemental-research-family.md)
- Protocol TVL, stablecoin supply, the current yield-pool catalog and exact-pool yield history use allowlisted
  public endpoints. Catalog snapshots and historical observations are distinct datasets; all carry retrieval
  availability, stay provider-native USD reference data, and fail closed on malformed, empty or non-finite input.

## Coverage profiles

- Universe selectors ignore catalog rows fetched after the cutoff, and a fully future catalog fails loud
  (`tests/bias_guards/test_crypto_profiles_future_poison.py`).
- `CryptoCoverageProfileV1` membership comes point-in-time from qualified Bybit and Binance catalog manifests:
  only trading, launched, not-yet-delivered spot and perpetual identities; daily, hourly, five-minute and native
  funding cadences stay separate; the fast option tier is capped at the top three underlyings by open interest.
- Coverage profiles, liquidity memberships and research selections are scheduling provenance — no research-gate
  or execution authority.
