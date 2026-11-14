# Verification: "Crypto history download that resumes safely" end to end

Run on the Dell on 2026-11-14 (UTC), branch `m8/prove-crypto-backfill` (based on the unmerged
`m8/prove-crypto-data`, which holds the recorded provider).

## Faults confirmed before the fix (real folder, read-only)

```text
$ ALPHA_DATA_DIR=/home/hunta/alpha-clean-base/data alpha crypto-data backfill-status binance market_bars \
    --symbols BTCUSDT --quote USDT --category spot --frequency 1d --start 2017-08-01 --end 2026-11-01 \
    --ledger spot-1d-BTCUSDT --max-ledger-bytes 10000000 --max-windows 1000 --max-verify-artifact-bytes 1000000000 --json
-> inspection complete, 111 completed_verified, "not_published_yet": ["2026-11"]   (November was never requested)
```

The same dry run on a copy listed `not_published_yet: ["2026-11"]`. Reading `plan_windows` showed
the month walk includes the month of `--end`, so from 1 December the same command would fetch
November. Publication delay, measured with HEAD requests on Binance's own files
(`BTCUSDT-1d-YYYY-MM.zip` Last-Modified): 2025-11 +1 day, 2025-12 +5, 2026-01 +2, 2026-02 +2,
2026-03 +6, 2026-04 +4, 2026-05 +1, 2026-06 +6, 2026-07 +3, 2026-08 +7, 2026-09 +5, 2026-10 +2,
2024-02 +12. So a run in the first week after a month ends records a false failure.

## Offline, through the installed program (the smoke check)

`tests/smoke/test_crypto_backfill_smoke.py`, 1 passed (15 s): a dry run plans 4 windows and makes
no request; the first run exits 1 with done 3, failed 1 (ETHUSDT 2024-02, `HTTP 404`), nothing
asked for March; `backfill-status` makes no request and leaves the ledger's bytes unchanged; a
held ledger lock makes a second run exit 2 ("already owned") with no request; a 1-byte
verification budget refuses before any request; after the month is recorded the rerun verifies
the 3 finished months first and fetches only ETHUSDT 2024-02 (checksum, then archive); the final
status is complete with 4 verified; a 1-byte metadata bound stops the inspection loudly.

Deviation from the plan, recorded: the plan expected `backfill-status` to exit 1 while a month
was failed. It exits 0, because the inspection itself completed; the failure is in `counts` and
`next_action` (`review_failures_unrecorded_work_and_existing_admission`). That is the command's
existing design; the smoke check asserts it as it is.

## For real, on a copy of the data folder

`/home/hunta/alpha-clean-base/tmp/prove-crypto/data` (a `cp -a` copy with its own storage
settings; the real folder was not written), with this branch's installed `alpha`:

```text
backfill ... --symbols BTCUSDT ... --end 2026-11-01 --ledger spot-1d-BTCUSDT --dry-run --json
-> windows_total 111, skipped 111, not_published_yet []          (before the fix: ["2026-11"])
backfill ... --symbols BTCUSDT,ETHUSDT ... --end 2026-11-01 --ledger spot-1d-BTCUSDT --json
-> windows_total 222, verified_completed 111, skipped 111, done 111, failed 0, 7 min 56 s
```

The second command re-verified all 111 finished BTC months before anything else, then ran the
111 ETH months new to that ledger: each month's checksum came live from Binance, one request at a
time, and the archive bytes came from the checksum-keyed local cache (all 1,425 archives were
already cached), so no archive was downloaded twice. Afterwards `storage-verify` on the copy:
`verified`, 3,080 manifests, 3 snapshots; the 222-month BTC and ETH snapshot still verifies.

## Checks

- New unit tests: 12 fail on `m8/prove-crypto-data` (end boundary, grace in and out, other
  statuses, CLI listing); all 33 pass after. Two pre-existing tests encoded the old inclusive
  month walk directly and were updated to the exclusive one.
- `tests/unit/test_code_size.py`: `run_backfill` had grown past its limit; its summary moved to
  `_summary`, and the ratchet entry dropped from 209 to 205 (`.claude/code-size-baseline.json`).
  `crypto_data_cmds.py` stays at 4,704 lines.
- `uv run python scripts/gate.py check --all`: see the pull request.

## Review

Codex-built (standard class), three rounds; its own checks failed on a mypy typing slip in the
new tests, the function-size ratchet and the status exit code above. Claude (orchestrator)
reviewed the diff and fixed all three by hand. The grace logic matches only HTTP 404 found on
the exception chain (causes before contexts, bounded at 64), only for Binance monthly windows,
only within 14 days after month end.

## Plans closed

Proven by the smoke check and moved to the archive: `2026-11-07-backfill-ledger-exclusion`
(second writer refused), `2026-11-07-backfill-resume-evidence` (finished months verified before
resume), `2026-11-07-backfill-verification-budget` (artifact byte cap refuses),
`2026-11-08-backfill-metadata-bounds` (metadata byte cap stops status),
`2026-11-08-backfill-readonly-status` (no request, no write). The umbrella
`2026-09-10-edge-first-phase-b-feed-the-machine` stays live.

## Not proven here

Bybit backfills; the grace path on the real clock (only in unit tests, since no month is in its
grace today).
