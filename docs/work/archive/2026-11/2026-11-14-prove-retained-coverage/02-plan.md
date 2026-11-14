# Prove the "Are my downloaded daily bars complete?" check end to end

**Delivery state:** Completed — built, reviewed and verified on branch `m8/prove-retained-coverage`; done when its pull request merges.
**Build class:** small — one smoke check and one optional argument in the recorded provider; based on the unmerged recorded provider of `m8/prove-crypto-data`.

Filed straight into the archive, as `2026-11-14-crypto-snapshot-duplicates` was: the
work-in-progress ceiling admits no new live plan, and the work is finished in one sitting.

## For the owner

- A new automatic check downloads a full month and a month with one missing day with the real
  `alpha` program, and the completeness check finds exactly that day, from the command line and
  from the Workstation's API.
- Every one of the Dell's real monthly Binance files was checked against its calendar month (see
  the verification record).
- Nothing for you to decide here; a check across all months of a coin at once is filed as a
  backlog item.

```json
{
  "schema_version": 1,
  "title": "Prove the daily bar completeness check end to end",
  "context": "retained-coverage is Partial: in-process tests and a Playwright journey against a test server, no smoke check through the installed programs. The recorded provider from m8/prove-crypto-data lets the installed alpha download a month offline, so the grid audit (alpha crypto-data quality with --coverage-start/--coverage-end/--as-of/--expected-cadence-seconds/--max-verify-artifact-bytes, and POST /api/crypto-data/quality/{manifest_id}/retained-coverage) can run end to end. On the Dell's real folder the audit of BTCUSDT 2026-10 reported 31 of 31 days (exit 0) and a wider declared grid reported the exact missing ranges (exit 1).",
  "assumptions": [
    {"statement": "The grid audit exits 0 when the declared grid is satisfied and 1 when it is inspected with findings; it makes no provider call and no write.", "verified_by": "real run on BTCUSDT 2026-10, 2026-11-14; tests/integration/test_web_retained_coverage.py"},
    {"statement": "The web route takes coverage_start, coverage_end, as_of, expected_cadence_seconds (86400) and max_verify_artifact_bytes.", "verified_by": "apps/alpha-web/src/alpha_web/api/retained_coverage_models.py"}
  ],
  "alternatives_considered": [
    "Build a whole-history check across every monthly file of one coin now: deferred to the backlog, it is a new command and a larger change.",
    "Seed a gapped dataset with tests.fixtures.retained_coverage_web_fixture: rejected for the smoke check, it bypasses the installed download step."
  ],
  "pre_mortem": [
    "The gapped month is quarantined at download and the audit refuses quarantined data: the plan records the download state as observed and asserts the audit's findings, not a guessed state; if the audit refuses, the build stops and reports.",
    "The audit's exit code differs between CLI and web: the web test asserts the same missing range and the API's own status field, not the CLI exit code."
  ],
  "slices": [
    {"title": "Recorded months can leave out days", "verify": "uv run python scripts/run_owned_test.py --timeout 900 -- uv run pytest -q -m smoke -n 0 tests/smoke/test_crypto_data_smoke.py", "expected": "2 passed (unchanged behaviour by default)", "rollback": "revert _recorded_provider.py", "status": "done"},
    {"title": "Completeness smoke check through the recorded provider", "verify": "uv run python scripts/run_owned_test.py --timeout 900 -- uv run pytest -q -m smoke -n 0 tests/smoke/test_retained_coverage_smoke.py", "expected": "2 passed", "rollback": "delete the smoke file", "status": "done"}
  ],
  "tier_impact": ["none"],
  "docs_to_update": ["docs/roadmap/capabilities.toml", "STATUS.md", "docs/roadmap/README.md", "docs/roadmap/wip-limit.json"],
  "out_of_scope": ["apps/alpha-cli/src/alpha_cli/crypto_data_cmds.py", "apps/alpha-web/src/", "packages/", "stored data"],
  "files": [
    "tests/smoke/_recorded_provider.py",
    "tests/smoke/test_retained_coverage_smoke.py"
  ]
}
```

## Read first

| Read | Section | When |
|---|---|---|
| [command line crypto data](../../../../reference/invariants/cli-crypto-data.md) | Read-only queries | always |
| [tests workspace](../../../../../tests/CONTEXT.md) | How to change it | always |
| [crypto-data smoke check](../../../../../tests/smoke/test_crypto_data_smoke.py) | — | the pattern to follow |
| [recorded provider](../../../../../tests/smoke/_recorded_provider.py) | — | always |
| [web retained coverage test](../../../../../tests/integration/test_web_retained_coverage.py) | — | the request and response shape |

## Slices

### 1. Recorded months can leave out days

`binance_monthly_klines(symbol, year, month, *, missing_days: Collection[int] = ())` leaves out the
rows of those days of the month (1-based); the default output is byte-identical to today's.

### 2. Completeness smoke check

`tests/smoke/test_retained_coverage_smoke.py` (`crypto_home`, `RecordedProvider`):

1. `test_completeness_check_finds_the_missing_day_without_provider_calls(crypto_home)`: record
   BTCUSDT 2024-01 complete and ETHUSDT 2024-01 with day 15 missing; acquire both with the
   installed `alpha` (record each download's `state` in the assertion message; do not assume it).
   Then with the provider still running and `env=provider.env()`:
   - `crypto-data quality <BTC id> --coverage-start 2024-01-01T00:00:00Z --coverage-end
     2024-02-01T00:00:00Z --as-of 2024-03-01T00:00:00Z --expected-cadence-seconds 86400
     --max-verify-artifact-bytes 100000000 --json`: exit 0; `row_audit.expected_slots` 31,
     `covered_slots` 31, `missing_slots` 0, `declared_grid_satisfied` true.
   - The same for the ETH id: exit 1; `missing_slots` 1 and `missing_ranges` exactly
     `[{"start": "2024-01-15T00:00:00+00:00", "end": "2024-01-16T00:00:00+00:00", "slots": 1}]`.
   - A declared grid wider than the month (2023-12-30 to 2024-02-02) for the BTC id: exit 1 and
     the two edge ranges.
   - `--as-of 2024-01-31T12:00:00Z` for the BTC id: the 31 January bar has not closed, so it is
     not counted as covered (assert what the report says about it; it must not be counted as a
     complete day).
   - No new provider request after the downloads (`provider.requests` unchanged) and the data
     folder's file list and bytes are unchanged by the audits (hash every file before and after).
2. `test_workstation_reports_the_same_missing_day(crypto_home)`: download the gapped ETH month as
   above, start `web_server(crypto_home)` and `POST
   /api/crypto-data/quality/<ETH id>/retained-coverage` with the same grid as JSON; the response
   reports the same single missing range. Use `post_json` from `tests/smoke/_harness.py` if it
   exists on the branch, else a local `urllib.request` helper in the test file.

If the installed program does not behave as listed, stop and report the exact output instead of
adjusting the expectation.

## Test plan

Slice 1 keeps the existing smoke checks byte-identical; slice 2 runs outside any sandbox. The
real-data audit of every Dell month is recorded by the orchestrator in `04-verify.md`.

## Look-ahead, determinism and import impact

No product code changes. The as-of case asserts an unclosed bar is never counted as complete.
