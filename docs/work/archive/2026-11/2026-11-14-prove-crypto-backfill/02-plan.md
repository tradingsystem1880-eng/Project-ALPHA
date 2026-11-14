# Prove "Crypto history download that resumes safely" end to end

**Delivery state:** Completed — built, reviewed and verified on branch `m8/prove-crypto-backfill`; done when its pull request merges.
**Build class:** standard — backfill planning and failure classification plus one smoke check; based on the unmerged recorded provider of `m8/prove-crypto-data`.

Filed straight into the archive, as `2026-11-14-crypto-snapshot-duplicates` was: the
work-in-progress ceiling admits no new live plan, and the work is finished in one sitting.

## For the owner

- A backfill whose end date is the 1st of a month no longer reaches into that month: `--end
  2026-11-01` means "up to 31 October", as the option's help already says.
- Binance publishes a finished month's file some days after the month ends (measured: 1 to 7 days
  in the last year, 12 days once in 2024). For 14 days after a month ends, a missing file is now
  reported as "not published yet" and the next run tries again; after that it is a real failure.
- A new automatic check runs a two-coin backfill with the real `alpha` program against a recorded
  copy of Binance: one missing month fails loudly, a rerun after it appears downloads only that
  month, a second run at the same time is refused, and the status command changes nothing.
- Nothing for you to decide here.

```json
{
  "schema_version": 1,
  "title": "Prove Crypto history download that resumes safely end to end",
  "context": "crypto-backfill is Partial (in-process tests only). Running it on the Dell's real history showed `backfill-status ... --end 2026-11-01` lists 2026-11 as not published: plan_windows and unpublished_binance_periods walk months up to and including end's month although --end is exclusive, so from 1 December a rerun with --end 2026-11-01 would download November, outside the request. A month that has just ended is planned at once, but Binance publishes monthly archives later (Last-Modified of BTCUSDT 1d monthly archives, measured 2026-11-14: 2025-11 +1 day, 2025-12 +5, 2026-01 +2, 2026-02 +2, 2026-03 +6, 2026-04 +4, 2026-05 +1, 2026-06 +6, 2026-07 +3, 2026-08 +7, 2026-09 +5, 2026-10 +2; 2024-02 +12), so the first run after month end records a false failure (HTTP 404).",
  "assumptions": [
    {"statement": "An unpublished archive answers HTTP 404 on its CHECKSUM sidecar, which is fetched first; after the crypto-data change the DataError chain holds the urllib HTTPError and the message says 'HTTP 404'.", "verified_by": "packages/alpha-data/src/alpha_data/crypto/providers/binance.py fetch_binance_checksum; m8/prove-crypto-data slice 1; recorded-provider smoke"},
    {"statement": "_backfill_acquire re-raises typer.BadParameter as DataError(str(exc)) from exc, so the HTTPError stays reachable through __cause__/__context__.", "verified_by": "crypto_data_cmds._backfill_acquire and _acquire_result"},
    {"statement": "The ledger lock is a nonblocking flock on <ledger>.json.lock; a held lock makes backfill fail with 'backfill progress already owned'.", "verified_by": "_crypto_backfill.Ledger.exclusive"},
    {"statement": "crypto_data_cmds.py may not grow (code-size ratchet).", "verified_by": ".claude/code-size-baseline.json"}
  ],
  "alternatives_considered": [
    "Skip every month that ended less than 14 days ago without asking Binance: rejected, it would hide a month that is already published (most are within 1 to 7 days).",
    "Treat any failure in the grace period as not published: rejected, only HTTP 404 means 'not there yet'; timeouts, checksum mismatches and other statuses stay failures.",
    "A longer grace (30 days): rejected for now, the longest measured delay is 12 days; 14 covers it with margin and a later 404 still fails loud."
  ],
  "pre_mortem": [
    "The end fix drops a month that was asked for: an end on any day after the 1st still plans its month; unit tests cover end on the 1st, the 2nd and the last day.",
    "A real outage inside the grace period is reported as not published: only HTTP 404 is classified, the period is listed in not_published_yet, and the run never records it done, so a rerun retries it.",
    "Existing ledgers hold a failed entry for a month the fixed planner no longer plans: that entry is outside the request and no status lists it (verified on a copy of the real folder)."
  ],
  "slices": [
    {"title": "An exclusive --end on the 1st plans nothing in that month", "verify": "uv run pytest -q tests/unit/test_crypto_backfill.py", "expected": "all pass; the new end-boundary tests fail on main", "rollback": "revert _crypto_backfill.py and its tests", "status": "done"},
    {"title": "A recently ended month answering HTTP 404 is not published yet, not a failure", "verify": "uv run pytest -q tests/unit/test_crypto_backfill.py tests/integration/test_crypto_backfill_resume_cli.py tests/integration/test_crypto_backfill_status_cli.py", "expected": "all pass; the grace tests fail on main", "rollback": "revert _crypto_backfill.py, crypto_data_cmds.py and the tests", "status": "done"},
    {"title": "Backfill smoke check through the recorded provider", "verify": "uv run python scripts/run_owned_test.py --timeout 900 -- uv run pytest -q -m smoke -n 0 tests/smoke/test_crypto_backfill_smoke.py", "expected": "1 passed", "rollback": "delete the smoke file", "status": "done"}
  ],
  "tier_impact": ["none"],
  "docs_to_update": ["docs/reference/invariants/cli-crypto-data.md", "docs/reference/project/components/data-layer.md", "docs/roadmap/capabilities.toml", "STATUS.md", "docs/roadmap/README.md", "docs/roadmap/wip-limit.json"],
  "out_of_scope": ["packages/alpha-data/src/alpha_data/crypto/providers/", "apps/alpha-cli/src/alpha_cli/crypto_price_snapshot_query.py", "packages/alpha-research/src", "packages/alpha-validation/src", "stored data"],
  "files": [
    "apps/alpha-cli/src/alpha_cli/_crypto_backfill.py",
    "apps/alpha-cli/src/alpha_cli/crypto_data_cmds.py",
    "tests/unit/test_crypto_backfill.py",
    "tests/smoke/test_crypto_backfill_smoke.py"
  ]
}
```

## Read first

| Read | Section | When |
|---|---|---|
| [command line crypto data](../../../../reference/invariants/cli-crypto-data.md) | Backfill | always |
| [tests workspace](../../../../../tests/CONTEXT.md) | How to change it | always |
| [recorded provider](../../../../../tests/smoke/_recorded_provider.py) | — | slice 3 |
| [crypto-data smoke check](../../../../../tests/smoke/test_crypto_data_smoke.py) | — | slice 3: the pattern to follow |

## Slices

### 1. An exclusive `--end` on the 1st plans nothing in that month

In `apps/alpha-cli/src/alpha_cli/_crypto_backfill.py`, the Binance month walk in `plan_windows`
and in `unpublished_binance_periods` ends at the month containing `end - 1 day` (the last day
inside the exclusive range), not the month containing `end`. One private helper does the month
walk for both. Bybit planning is unchanged. Tests in `tests/unit/test_crypto_backfill.py`:
start 2026-09-01, end 2026-11-01 plans exactly 2026-09 and 2026-10 and
`unpublished_binance_periods(..., now=2026-11-14)` is empty; end 2026-11-02 plans 2026-09,
2026-10 and lists 2026-11 as unpublished; end 2026-10-31 plans 2026-09 and 2026-10; start and end
inside one month (2024-01-05 to 2024-01-20) plans 2024-01. Update existing tests that encoded the
old inclusive walk only if they assert it directly, and say so in the report.

### 2. A recently ended month answering HTTP 404 is "not published yet"

- `_crypto_backfill.py`: `BINANCE_PUBLICATION_GRACE = timedelta(days=14)` with a comment citing
  the measurement in this plan's context (dates and source). In `run_backfill`, for provider
  `binance` only: when acquiring a window raises `DataError`, the window's month ended at or
  before `now` and less than the grace before `now`, and an `urllib.error.HTTPError` with code 404
  is found by walking `__cause__` then `__context__` (bounded, cycle-safe), the window is not
  recorded in the ledger, not counted in `failed` or `failures`, and its period is appended to a
  new summary list `awaiting_publication` (in plan order); with `log`, write
  `not published yet {key}`. Every other error, and a 404 after the grace, keeps today's
  failure path. The summary always has `awaiting_publication` (empty list when none).
- `crypto_data_cmds.py` `backfill` command: `not_published_yet` becomes the sorted union of
  `unpublished_binance_periods(...)` and `summary["awaiting_publication"]`. Net line count of
  `crypto_data_cmds.py` must not grow (`tests/unit/test_code_size.py`).
- Tests (unit, `tests/unit/test_crypto_backfill.py`, with a fake `acquire` raising the real chain
  shape `DataError` from `typer.BadParameter` from `DataError` from `HTTPError(404)`): within the
  grace the window is in `awaiting_publication`, the ledger has no entry, `failed` is 0, and a
  rerun calls `acquire` for it again; the same 404 fifteen days after month end is a recorded
  failure; a 500 or a plain `DataError` within the grace is a recorded failure; and the CLI's
  `not_published_yet` includes an awaiting period (in-process CLI test following
  `tests/integration/test_crypto_backfill_resume_cli.py`'s fixture style, or a unit test of the
  command if that is simpler).

### 3. Backfill smoke check

`tests/smoke/test_crypto_backfill_smoke.py`, following `tests/smoke/test_crypto_data_smoke.py`
(fixture `crypto_home`, `RecordedProvider`, `alpha(..., env=provider.env())`), one test
`test_binance_backfill_resumes_only_unfinished_months_and_refuses_a_second_writer`:

1. Record BTCUSDT 2024-01 and 2024-02 and ETHUSDT 2024-01 (not ETHUSDT 2024-02).
2. `crypto-data backfill binance market_bars --symbols BTCUSDT,ETHUSDT --quote USDT --category
   spot --frequency 1d --start 2024-01-01 --end 2024-03-01 --ledger smoke --dry-run --json`:
   exit 0, four windows planned, no provider request.
3. The same without `--dry-run`: exit 1; `done` 3, `failed` 1, the failure key is ETHUSDT 2024-02
   and its error contains `HTTP 404`; `not_published_yet` and `awaiting_publication` are empty
   (February 2024 is long past the grace). No request for any 2024-03 file was made.
4. `crypto-data backfill-status binance market_bars --symbols BTCUSDT,ETHUSDT --quote USDT
   --category spot --frequency 1d --start 2024-01-01 --end 2024-03-01 --ledger smoke
   --max-ledger-bytes 1000000 --max-windows 100 --max-verify-artifact-bytes 100000000 --json`:
   exit 1 (not complete), counts `completed_verified` 3 and `recorded_failure` 1, no provider
   request, ledger file bytes unchanged.
5. While the test process holds `fcntl.flock(LOCK_EX)` on `<data>/crypto/backfill/smoke.json.lock`,
   the backfill exits 2 with "already owned" and makes no request; release the lock.
6. With `--max-verify-artifact-bytes 1`, the backfill refuses before any request (exit not 0,
   ledger bytes unchanged).
7. Record ETHUSDT 2024-02; rerun the backfill: exit 0, `done` 1, `skipped` 3,
   `verified_completed` 3, `resume_verification` `verified`; the only new requests are the
   ETHUSDT 2024-02 checksum and archive, in that order.
8. `backfill-status` again: exit 0, `inspection_state` `complete`, `completed_verified` 4.

If the installed program does not behave as listed, stop and report the exact output instead of
adjusting the expectation.

## Test plan

Slices 1 and 2 are test-first and fail on `m8/prove-crypto-data`. Slice 3 runs outside any
sandbox. The real-data proof (dry run, rerun and status on a copy of the Dell's data folder) is
recorded in `04-verify.md` by the orchestrator.

## Look-ahead, determinism and import impact

No read path changes. Planning stays a pure function of start, end and now. `_crypto_backfill.py`
gains a standard-library `urllib.error` import only.
