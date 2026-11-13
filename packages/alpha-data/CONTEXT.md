---
owner: data layer
sources:
  - packages/alpha-data/src/**
  - packages/alpha-data/pyproject.toml
verified: 1ac86fc02443
---

# alpha-data workspace

## Purpose

Data ingestion and storage: vendor adapters with receipts, the raw Parquet store, the
point-in-time `as_of` reader, corporate-action clocks, universe membership, immutable hashed
snapshots, and the crypto data house storage. It imports only `alpha_core` (import-linter
contract "alpha_data depends only on core"); `alpha_backtest`, `alpha_study` and `alpha_cli`
import it. It must never let a read see data that was not knowable at the cutoff.

## Read first

| Read | Section | When |
|---|---|---|
| [data invariants](../../docs/reference/invariants/data.md) | — | always |
| [research integrity](../../docs/reference/invariants/research-integrity.md) | Point-in-time reads | always |
| [research integrity](../../docs/reference/invariants/research-integrity.md) | Invalid data fails loud | always |
| [architecture](../../docs/ARCHITECTURE.md) | Runtime data-directory layout | changing where data is stored |
| [research integrity](../../docs/reference/invariants/research-integrity.md) | Corporate actions: two clocks | changing splits, dividends or symbol changes |
| [research integrity](../../docs/reference/invariants/research-integrity.md) | Immutable, hash-bound artefacts | changing snapshots or receipts |
| [crypto provider invariants](../../docs/reference/invariants/crypto-providers.md) | — | changing `crypto/providers/` or coverage profiles |
| [command line crypto data](../../docs/reference/invariants/cli-crypto-data.md) | — | the change is driven by an `alpha crypto-data` command |
| [engineering rules](../../docs/reference/invariants/engineering.md) | Polars by default | touching an adapter or adding a dataframe library |

## How to change it

- Code: `packages/alpha-data/src/alpha_data/`; vendor adapters in `adapters/`, the crypto data
  house in `crypto/` and `crypto/providers/`.
- Tests: `tests/unit/test_pit_*.py`, `test_parquet_store.py`, `test_snapshot.py`, `test_ingest*.py`,
  `test_corporate_actions.py`, `test_dividends_pit.py`, `test_universe_store.py`, `test_tiingo_*`,
  `test_crypto_*` (all in `tests/unit/`); bias guards `tests/bias_guards/test_pit_*.py`,
  `test_survivorship.py`, `test_candles_pit.py`, `test_crypto_*_future_poison.py`; integration
  `tests/integration/test_data_cli.py` and `tests/integration/test_crypto_*`.
- A new or changed read path needs its future-poison guard with a must-fail leaky twin
  (pattern: `tests/bias_guards/test_future_poison_pattern.py`).
- Check: `uv run python scripts/gate.py check` (lint, `lint-imports`, mypy, mapped tests and every
  bias guard). Pass aware UTC cutoffs in tests; `tests/unit/test_pit_tz.py` covers naive and DST cases.

## Outputs

- Tests: the bias guard for any read change; unit tests for new failure modes (typed `DataError`).
- The owning document: `docs/reference/invariants/data.md` (crypto providers:
  `docs/reference/invariants/crypto-providers.md`; crypto commands: `docs/reference/invariants/cli-crypto-data.md`).
