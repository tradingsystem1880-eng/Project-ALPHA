# Report: delete the download bookkeeping code (m77)

Result: the four accounting modules, their tests and the optional accounting parameters are gone.

## Proof each file was unreached
`grep` over apps, packages, workers, tests, scripts and docs found imports only inside the four modules, the deleted tests,
`_crypto_backfill.py` (optional parameters) and one import in `crypto_data_cmds.py`. No command, `python -m` or subprocess call names them.

## Deleted
- `_crypto_http_replay.py` (814), `_crypto_http_accounting.py` (297), `_crypto_backfill_accounting.py` (356),
  `_market_data_acquisition_accounting.py` (541).
- Tests: `test_bound_http_replay*`, `test_accounted_*` (4 files), `test_complete_http_accounting`,
  `test_market_data_acquisition_transactions`, and `tests/unit/test_market_data_acquisition_accounting.py` (it only tests deleted code).
- `run_backfill`: the parameters `fixture_accounting`, `fixture_http_accounting`, `fixture_http_response_evidence` and the code that used them.
- Capability `download-bookkeeping`, its trace row, the production-scope row, and text in `data-layer.md` and `cli-crypto-data.md`.
  `docs/ARCHITECTURE.md` had no row for these modules. The triage sheet is history; I left it.
- Protected, not edited: `scripts/gate_test_durations.json` still lists `tests/unit/test_market_data_acquisition_accounting.py` (line 371). The orchestrator should remove that entry.

## Decisions
1. `FixtureAccountingBlocked` is still raised by live code in `crypto_data_cmds.py`. I moved it to the new
   `_crypto_acquisition_errors.py` (13 lines) instead of defining it in `crypto_data_cmds.py`, because that file may not grow
   (baseline 4704 lines). I dropped the unused `reconciliation_persisted` field.
2. Added `test_backfill_without_accounting_arguments_keeps_its_result_and_ledger`. It passed on the unchanged code first, then after the change.
3. Regenerated `STATUS.md`. `commands.md` did not change.

## Lines
About 5,090 removed, 49 added (git diff, whole branch against the brief branch).

## Checks
- `lint-imports`: 13 kept, 0 broken. Research-cut and follow-separation guards pass.
- Full gate pytest: 1004 passed, 1 failed (the expected one below).
- `test_crypto_backfill_lock_process.py` needs `scripts/run_owned_test.py`; with it, it passes.
- Stale documents (listed, not blocked): `apps/alpha-cli/CONTEXT.md`, `apps/alpha-cli/README.md`, `cli-crypto-data.md`, `data-crypto.md`, `data.md`.

## The one red test: `tests/unit/test_code_size.py::test_baseline_entries_are_exact`
The orchestrator must remove these entries from `.claude/code-size-baseline.json`:
- `apps/alpha-cli/src/alpha_cli/_crypto_backfill.py::run_backfill`
- `apps/alpha-cli/src/alpha_cli/_crypto_http_replay.py::FixtureBoundHttpAccounting._dispatch_bound` (272)
- `apps/alpha-cli/src/alpha_cli/_crypto_http_replay.py::FixtureBoundHttpAccounting._validate` (164)
