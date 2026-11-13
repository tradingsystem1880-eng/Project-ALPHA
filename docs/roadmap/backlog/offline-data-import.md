# Offline price import from a local file

**Status:** Scoped
**Rough size:** M

## Problem / why

There is no offline way to get price data into ALPHA. Every `alpha data pull --source` (yfinance,
stooq, tiingo, ccxt) needs the network, and no command reads a file. The end-to-end smoke checks
therefore seed the store with a test helper (`tests.fixtures.cli_fixtures.seed_store`) instead of
the installed program, so "get prices in" is the one step of the stock-data workflow that is not
proven end to end, and the Dell (synthetic-data development machine) cannot load a data set
without network access.

Bars written by the test helper today carry no provenance file: a snapshot of them is labelled
with whatever `--source` says (default `yfinance`) while reads report `source: unknown` and
`legacy_unqualified`. An import command must not repeat that ambiguity.

## What "done" looks like

- One offline command, smallest form `alpha data pull SYMBOL --source local-file --path FILE
  --origin synthetic|external` (a new entry in the provider registry, so `data pull`, the provider
  catalog and the capability map pick it up without a new command group). No network; it never
  falls back to a provider.
- Input: a CSV or Parquet file of daily bars with exactly `ts` (UTC date or ISO instant), `open`,
  `high`, `low`, `close`, `volume`; unknown or missing columns, naive non-date timestamps,
  non-finite values, duplicate or disordered sessions and sub-daily spacing are refused (the
  existing `Bar` model and quality report rules). Corporate actions are not imported in the first
  version: prices are raw and the provenance says so.
- It goes through the existing receipt pipeline (`stage_and_promote`): the receipt's
  `response_sha256` is the file's SHA-256, `fetched_at` is the import time (the knowledge cutoff of
  the import), `request_metadata` records the file name and `origin`. Reruns of the same file are
  idempotent; a different file for the same symbol is a correction with old/new row hashes, as for
  provider pulls.
- Labelling, so imported data can never be mistaken for qualified provider data:
  `DatasetIdentity.provider = "local-file"`; a distinct quality status `imported` (not `passed` /
  `qualified`) on candle reads, the snapshot listing and the web data panel; `origin: synthetic`
  is shown wherever the source is shown. Existing authority checks already refuse it (IBKR warmup
  requires `tiingo`, crypto paper requires `ccxt:binance` plus provenance, research chart choices
  require registered Tiingo bars) and tests prove each refusal.
- `alpha data snapshot` takes its `source` from the stored provenance of the symbols (one source
  for all symbols, else refuse) rather than the `yfinance` default it uses today without looking
  at the data; this waits for the owner's decision on snapshot source labelling.
- The data smoke check replaces `seed_store` with the installed command and the designed skip
  `test_data_pull_offline` becomes a real check; the stock-data capability can then become
  Working.

Tests: unit tests for the adapter's parsing and refusals (each invalid-input class above); an
integration test for receipt → candidate → promotion, idempotent rerun and correction; refusal
tests for each authority check listed; a point-in-time test that an import never changes bars
already frozen in a snapshot; the smoke check above.

## Dependencies

Owner decision on how snapshots label their source (today: a `--source` default of `yfinance`,
never checked against bars that have no provenance file); a web
schema change for the new `imported` quality status (`openapi.json` and `generated.ts`
regenerated).

## Sources

- [Smoke check that skips the offline pull](../../../tests/smoke/test_data_smoke.py)
- [How the smoke checks seed data today](../../../tests/smoke/conftest.py)
- [ADR-0017: authoritative daily data and the receipt pipeline](../../adr/0017-authoritative-daily-data-and-broker-paper-boundary.md)
- [`alpha data pull` and `snapshot`](../../../apps/alpha-cli/src/alpha_cli/data_cmds.py)
- [Receipt, candidate, quality gate and promotion](../../../packages/alpha-data/src/alpha_data/pipeline.py)
