---
owner: command line market and crypto data
sources:
  - apps/alpha-cli/src/alpha_cli/crypto_*.py
  - apps/alpha-cli/src/alpha_cli/_crypto_*.py
  - apps/alpha-cli/src/alpha_cli/_chart_data.py
  - apps/alpha-cli/src/alpha_cli/data_cmds.py
  - tests/unit/test_crypto_*.py
  - tests/integration/test_crypto_*.py
  - tests/integration/test_data_*.py
verified: aa600e57932d
---

# Command line data invariants

What must not break when changing `alpha data` and the governed crypto data house
(`alpha crypto-data`, `crypto_*` and `_crypto_*` modules), on top of the provider parsing, quality and snapshot contracts
that `alpha_data` owns. Project-wide rules: [research integrity § Point-in-time reads](research-integrity.md#point-in-time-reads)
and [research integrity § Invalid data fails loud](research-integrity.md#invalid-data-fails-loud).

## Daily market data

- Tiingo bytes become receipt, candidate, quality report and only then canonical promotion
  (`stage_and_promote`). [ADR-0017](../../adr/0017-authoritative-daily-data-and-broker-paper-boundary.md)
- Once a symbol's canonical source is Tiingo, Yahoo and Stooq pulls are audit-only and must fail rather than replace
  it (`data_cmds.pull`).
- `data pull` rejects `--end` before `--start`, normalises the symbol (ambiguous input fails with the accepted forms), and
  for CCXT refuses a start before the first listed bar with a "Start there?" hint. Never clamp silently.
- `data candles` and `data symbols` read through the same point-in-time loader a backtest uses (`_runner.load_bars`).
- `data universe` and `--with-actions` are read projections with no authority; the plain `--json` picker output stays
  unchanged.
- Binance spot daily REST reads take an opt-in `RequestBudget` (attempts and body bytes; see
  [crypto providers § Shared fetch boundary](crypto-providers.md#shared-fetch-boundary)).
- On malformed provider bars, CLI callers raise their typed usage error and publish no run.

## Provider-native datasets

- Keep each provider's dataset family separate. No provider is a universal crypto price, and no fallback may change
  venue, quote asset, units, frequency or evidence. [ADR-0032](../../adr/0032-governed-crypto-data-house.md)
- Join assets by network plus contract address or a reviewed native mapping; ticker-only joins fail
  (`alpha_data.crypto.asset_master`).
- CCXT snapshots and the `ccxt:binance` paper warm-up path are a separate, unchanged lane.

## Bulk storage

- The external bulk store opens only from explicit operator configuration (`crypto_bulk_store.py`); no storage is
  provisioned and no durability is assumed. Configured volume identity and free-space reserve are checked first.
- The free-space reserve defaults to the larger of 15% of the disk and 100 GB. Only the owner may lower it, through an
  optional `free_space_reserve` object in the storage settings file (never below 10 GB; the code validates it and never
  supplies it). A write that would leave less than the reserve is refused before any byte is written; below the advisory
  threshold `crypto-data storage` prints a low-space notice but never refuses. [ADR-0043](../../adr/0043-storage-reserve-is-owner-set.md)
- The storage config path must contain no symlink component and stay under 8 KiB.
- Inventory and verification output show counts and hashes, never private absolute paths.
- `cache-clean` needs `--confirm`, deletes only `bulk/cache`, and reports zero immutable artifacts removed. Staging, raw,
  normalized, snapshot, manifest and control roots are never cleaned.

## Immutable documents

- Crypto JSON documents are written once with exact bytes (`_crypto_persistence.write_immutable_json`): an identical
  repeat is kept, a different payload at the same id fails as an identity collision.
- Coverage batches freeze their task slice in a content-addressed plan with `execution_authority: false`; at most
  25 tasks, and the checkpoint must match the plan exactly or the batch fails integrity (`_crypto_coverage.py`).
- Only failed checkpoints resume, and they retry only unfinished membership; a completed resume is offline.
- Coverage profiles, liquidity memberships and research selections are scheduling provenance, not evidence approval
  or execution authority.

## Research-bound acquisition

- High-frequency derivative trades and books require `--case-id`, `--expected-case-revision` and `--reason`; the scope
  is refused for any other family (`crypto_data_cmds._acquisition_scope`).
- Before such capture the current case revision must equal the expected one, else refresh and retry.
- A Binance one-minute research selection binds 1 to 50 unique markets to one case revision and re-checks the revision
  after publishing its receipt.
- Unscoped historical high-frequency artifacts stay readable but fail governed snapshot creation and re-verification.

## Backfill

- `_crypto_backfill.py` plans windows strictly under each provider page limit and calls the unchanged single-window
  acquisition per window, so every manifest is what a hand-typed `acquire` would produce. A full page splits the window.
- The JSON ledger under `data_dir/crypto/backfill/` is operational progress, not evidence; manifests remain the only
  evidence. A provider `DataError` on one window is recorded and the run continues; an accounting refusal
  (`FixtureAccountingBlocked`) stops the run and never splits or retries.
- One owner at a time: the ledger takes a non-blocking `flock` on a persistent `.lock` sidecar and checks the sidecar
  identity; never delete the sidecar or unlock an inherited descriptor in a child.
- Binance publishes a monthly archive only after the month ends. A Binance backfill never plans a month that has
  not ended at run time: it lists it under `not_published_yet` and records nothing for it in the ledger. A month
  that has ended but whose file is missing is still a recorded failure. `backfill-status` names the same months
  under `not_published_yet`, so a shortened plan is never silent. The current month comes from the bounded REST
  tail (`acquire ... --start/--end`); daily archive files are not read.
- Backfill has no research, quota or execution authority. Inspection (`_crypto_backfill_inspection.py`) is read-only.

## Read-only queries

- `crypto-data snapshot-query` reopens one `defi_tvl` member only after verifying snapshot membership, normalized bytes,
  raw lineage, units and schema. Limits: 32 MiB per Parquet artifact, 50,000 input rows, 1,000 rows per page.
  [ADR-0036](../../adr/0036-defillama-tvl-supplemental-research-family.md)
- Its `available_at` filter follows the parser's next-UTC-day convention; it does not prove a publication time.
- `crypto_price_snapshot_query.py`, `_chart_data.py` and `_crypto_bar_coverage.py` are bounded diagnostics. They never
  write to snapshots or artifacts and grant no admission.

## Crypto research edge

- `snapshot-create` and every verification (`snapshot-verify`, `storage-verify`, research registration) resolve a member through
  one rule in `_crypto_snapshot_members.py`; the rule itself is in [data § Crypto storage](data.md#crypto-storage).
- Research may consume crypto data only through a registered snapshot re-verified at use; see
  [command line research § Research data and crypto research](cli-research.md#research-data-and-crypto-research).
