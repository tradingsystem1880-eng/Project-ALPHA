# ADR-0032: Govern crypto data by dataset family

**Status:** Accepted
**Date:** 2026-08-14
**Deciders:** Owner-approved crypto data-house plan and AI build agents

## Context

ALPHA's original crypto history boundary treated the CCXT daily-candle adapter as one global
authority. That seam remains useful and its stored snapshots must remain readable, but it cannot
represent venue-native futures archives, funding intervals, open interest, options, DEX pools,
on-chain metrics, or point-in-time asset identity. Treating any provider as a universal crypto
price would silently change venue, quote asset, units, timestamp semantics, or evidence.

Large public datasets also do not belong beside the internal control database. The permanently
attached Expansion volume can hold public bulk bytes, provided ALPHA verifies its stable volume
identity and publishes internal authority records only after external content is durable.

## Decision

Keep the subsystem inside the existing `alpha_data` layer and compose it only through `alpha_cli`.
Assign exactly one primary acquisition authority to each dataset family:

| Dataset family | Authority | Boundary |
|---|---|---|
| CEX spot and futures market history and membership | Binance exchange-info, native archives, and public REST tail | Active membership plus venue-native bars/trades; spot, USD-M, and COIN-M remain distinct |
| advanced derivatives and options | Bybit public V5 interfaces | Complete instrument catalogs, funding, OI, ratios, trade/mark/index/premium bars, recent executions, exact books, volatility, chains, IV, and Greeks retain native units and clocks |
| asset identity and broad market reference | CoinGecko | Identity and reference statistics only; never execution-price evidence |
| DEX pools, liquidity, and pool OHLCV | GeckoTerminal | Network-plus-contract/pool identity; manipulation and thin-liquidity warnings remain explicit |
| on-chain and network metric catalog | Coin Metrics Community catalog | Supplemental exact membership evidence; only reviewed Community metrics are scheduled |
| on-chain and network metrics | Coin Metrics Community timeseries | Research observations only when their exact asset/metric/frequency exists in the qualified frozen catalog |
| independent market-data comparison | Coinbase through the existing CCXT adapter | Diagnostic comparison only; never automatic substitution |

CCXT remains a supported legacy and comparison seam. Existing CCXT provenance and snapshot bytes
are never rewritten. The existing `ccxt:binance` paper warmup contract is unchanged until a later
parity ADR and evidence gate prove an exact native-snapshot replacement.

High-frequency Bybit derivative trades and order-book snapshots are case-bound event captures.
Before provider access, ALPHA requires an existing research case, its expected revision, and a
bounded reason; it rechecks that revision after fetch before publication. The normalized manifest
commits to `CryptoAcquisitionScopeV1`. Historical unscoped event artifacts remain readable and
immutable but cannot enter or reverify as governed research evidence.

Coinbase through `ccxt:coinbase` is the sole primary authority for `comparison_bars`. Bybit spot
bars are an explicitly non-authoritative diagnostic input and cannot enter a frozen snapshot.
Cross-venue diagnostics require exact base, quote, spot market type, and frequency equality; USD,
USDT, and USDC are never compared as if interchangeable. The derived report retains all venue
values and may warn or quarantine the primary, but never substitutes another provider.

No automatic fallback may change provider, venue, market type, quote asset, unit, frequency, or
timestamp convention. USDT, USDC, and USD are separate quote assets. Provider corrections create
new immutable receipts; unexplained changes quarantine rather than overwrite evidence.

Binance `market_membership` is a distinct supplemental family and does not displace Bybit's
advanced-derivative `instrument_catalog` authority. Three exact, qualified spot/USD-M/COIN-M
membership receipts define daily coverage point-in-time. Active spot markets and perpetuals are
included; dated, inactive, and future-launched contracts are excluded. Provider-native Unicode
symbols remain exact identities and are percent-encoded only at URL path boundaries. Each scheduled
daily bar task requests only the immediately previous complete UTC day.
Hourly liquidity membership freezes only after every active market in one exact category/quote
scope has one qualified observation for the complete prior UTC day. Spot and USD-M rank the native
quote-volume field; COIN-M ranks exact contract count multiplied by the catalog contract size.
USD, USDT, and other quote scopes are never cross-ranked. Each immutable selection is capped at 250,
commits to the complete input universe, and becomes a source of the next content-addressed profile;
hourly tasks then request only the previous complete UTC hour.
The one-minute tier is never liquidity-inferred. `profile-select-one-minute` requires an existing
research case, its exact fresh revision, a bounded reason, and 1–50 human-readable
`category:symbol` identities already present in frozen daily membership. It publishes an immutable
case-bound selection receipt, rechecks the case before profile publication, and schedules only the
previous complete hour. Selection and acquisition grant no evidence or execution authority.

The internal data root stores control state, manifests, qualification records, provider-check
receipts, and sensitive research metadata. Bulk public bytes live beneath the configured external
root. `ALPHA_BULK_DATA_DIR` selects that root and `ALPHA_BULK_VOLUME_UUID` pins the expected volume.
Before acquisition ALPHA verifies the mounted volume identity, writability, and a reserve of at
least 15 percent and 100 GB. External content is atomically published first and the internal
manifest is the final completion marker. Missing, substituted, low-space, interrupted, or tampered
storage fails closed. Binance archive acquisition fetches the official checksum first, preserves
interrupted bytes only under request-and-checksum-bound staging metadata, and resumes only when the
server returns the exact remaining HTTP byte range. Completed checksum-verified ZIPs may enter the
explicitly disposable external cache; an ignored range, changed checksum, or mismatched bytes fails
without splicing provider responses or publishing a manifest.

Research consumes one exact qualified `CryptoSnapshotV1`. Dataset identity includes provider,
venue, market type, family, instrument, frequency, units, and timestamp convention. Asset joins use
network plus contract address or an explicitly reviewed native-asset mapping; ticker-only joins
fail. A frozen asset master commits to the exact qualified source-manifest IDs as well as its
ordered identities; non-legacy snapshots reverify that content identity before every read.
Availability time is part of every observation and derived feature.

ADR-0033 is the sole initial empirical extension of this data boundary. It registers one exact
Bybit linear BTCUSDT/USDT crowding-reversal question and keeps the later Bybit-perpetual/Binance-spot
basis candidate sandbox-only. No other crypto snapshot, feature, instrument, quote, or venue gains
research or strategy authority by analogy.

No crypto-data command or UI route receives exchange credentials, paper-entry authority, research
gate authority, broker authority, or order authority. CoinGecko's Demo key is retrieved from macOS
Keychain only by the existing allowlisted launcher and injected into one bounded process. Its fixed
`catalog` and `reference` actions accept no caller-selected provider, family, instrument, or output
path. Binance,
Bybit, Coinbase, GeckoTerminal, and Coin Metrics use only public interfaces in this program.
Bybit option instruments, quotes, and historical volatility require an explicit `option` market
selection; the system must not accept a misleading linear/inverse selection and silently relabel
the normalized identity.
CoinGecko's daily `all` market-reference acquisition freezes every ordered 250-row page through
the first bounded terminal page. GeckoTerminal top-pool catalogs freeze five exact 20-row pages per
declared network. Each page has its own raw receipt and the normalized catalog commits to their
ordered membership; incomplete pages or a CoinGecko universe beyond 100 pages fail closed. The
keyless GeckoTerminal client paces catalog pages and uses bounded exponential backoff only for HTTP
429; it never loops indefinitely or records vendor response text.
Default breadth is planned before acquisition in a content-addressed `CryptoCoverageProfileV1`
bound to exact qualified Bybit catalog, option-chain, and Coin Metrics Community catalog manifests.
On-chain tasks are derived only from exact qualified catalog rows known by the profile `as_of`;
ALPHA never advertises an unavailable Community metric. Profile membership excludes
future-launched and dated contracts, preserves native provider/category/quote/frequency identity,
separates daily/hourly/five-minute/funding cadences, and limits the fast option tier to three
underlyings ranked from complete aggregate-OI inputs. Missing rank inputs fail profile creation;
creating or inspecting a profile performs no provider request and grants no evidence or execution
authority. Executing a profile requires an explicit confirmation and a bounded cadence slice of at
most 25 tasks. The immutable batch plan binds the profile, slice, task identities, and one knowledge
time; an atomic checkpoint records only completed normalized manifests. Resume re-verifies the
profile sources and exact task membership, rejects altered plans or checkpoints, and starts at the
first unfinished task. Batch execution never grants research, paper, broker, or order authority.

## Provider retention and removal policy

- Preserve exact response/checksum bytes only for the owner's private local research where the
  provider permits it; never redistribute raw datasets or expose them through a hosted surface.
- Record provider, endpoint family, request, response hash, fetch time, schema/parser version,
  pagination, correction lineage, access tier, attribution note, and retention note in receipts.
- A provider takedown, terms change, retraction, or removal request disables new acquisition first.
  Then remove the affected external public blobs through an explicit inventory operation while
  retaining a non-reconstructive internal tombstone, content hash, reason, and affected snapshot
  list. Qualified snapshots depending on removed bytes become unavailable, never silently rebuilt.
- Derived data is not presumed free of upstream terms. Its manifests retain input identities and
  the same removal lineage.

## Consequences

- ALPHA can represent advanced crypto evidence without inventing a synthetic universal candle.
- More provider-native contracts and quality rules are required; comparison warnings cannot repair
  or replace missing primary evidence.
- The external drive is a capacity dependency, not an authority store. Losing it blocks reads and
  acquisition but cannot corrupt internal control state.
- Public API availability, rate limits, revisions, retention, and service terms remain external
  constraints. A successful check proves only the capability named in its receipt.
- Any execution integration, paid plan, continuous tick mirror, automatic provider fallback, drive
  reformat, or hosted/distributed use requires a new decision and evidence review.

## Implementation anchors

- `packages/alpha-data/src/alpha_data/crypto/`
- `apps/alpha-cli/src/alpha_cli/crypto_data_cmds.py`
- `apps/alpha-cli/src/alpha_cli/providers.py`
- `apps/alpha-cli/src/alpha_cli/provider_readiness.py`
- `apps/alpha-web/frontend/src/panels/ResearchDataExplorer.tsx`
- `tests/unit/test_crypto_*.py` and `tests/integration/test_crypto_data_house.py`
