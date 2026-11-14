# Verification: the "Are my downloaded daily bars complete?" check end to end

Run on the Dell on 2026-11-14 (UTC), branch `m8/prove-retained-coverage` (based on the unmerged
`m8/prove-crypto-data`, which holds the recorded provider).

## Offline, through the installed program (the smoke check)

`tests/smoke/test_retained_coverage_smoke.py`, 2 passed (15 s), and the crypto-data smoke checks
still pass with the recorded provider's new optional `missing_days`. Steps: a complete BTCUSDT
January 2024 downloads `qualified`; an ETHUSDT January with 15 January left out downloads as
`warning` with `cadence_gap` (the download's own check already flags it). With every file in the
data folder hashed before and after, and no new provider request:

- BTC, grid 1 January to 1 February, as of 1 March: exit 0, 31 of 31 days, satisfied.
- ETH, same grid: exit 1, one missing day, exactly 15 to 16 January.
- BTC, grid 30 December to 2 February: exit 1, the two edge ranges (2 days and 1 day).
- BTC, as of noon on 31 January: exit 1, `audit_state` `unavailable`
  (`RETAINED_BAR_AUDIT_UNAVAILABLE`), no row audit: a grid that has not closed at the cutoff is
  refused, so the still-open 31 January bar is never counted as a complete day.

Through the installed `alpha-web`, `POST /api/crypto-data/quality/<id>/retained-coverage` reports
the same single missing day. (The POST goes to `localhost`: `alpha-web` redirects `127.0.0.1`
there with a 307 and urllib does not resend a POST body.)

Deviation from the plan, recorded: the plan expected the noon-cutoff audit to report the last day
as not covered; the program instead refuses the whole audit (the web request model has the same
`closed_grid` rule). Both keep the open bar out; the check asserts what the program does.

## For real, every month on the Dell

Read-only on the real folder (`ALPHA_DATA_DIR=/home/hunta/alpha-clean-base/data`), main's
installed `alpha`: for every Binance daily `market_bars` manifest (1,426, from
`crypto-data coverage --json`), `crypto-data quality <id> --coverage-start <first of its month>
--coverage-end <first of next month> --as-of 2026-11-14T00:00:00Z --expected-cadence-seconds 86400
--max-verify-artifact-bytes 100000000 --json`, six at a time, driven by a script outside the
repository.

- 1,412 months: exit 0, every day covered (42,984 of 42,984 expected days).
- 14 months: exit 1, each pair's first month, which starts on its listing day (for example BTC and
  ETH from 17 August 2017: 15 of 31 days); XLM's first month starts on the 1st and is complete.
- No duplicate, conflicting or off-grid row and no failure anywhere; no provider call.

So the Dell's Binance daily history has no missing day after each pair's first bar. The check
covers one file at a time; gaps between files are not checked by it. The verification record of
the original download already showed a contiguous history per pair; a one-step whole-history
check is filed as backlog `crypto-history-completeness`.

## Real data folder untouched

A SHA-256 list of every file in `/home/hunta/alpha-clean-base/data` was taken before any of the
four proofs and again at the end: no existing file changed or disappeared. Four files were added
during the day that none of these proofs wrote: one crypto snapshot (`561a39bf…`, 36 BTCUSDT
members, created 09:37 UTC) and the `control/workstation.sqlite3` files, from another session
working on the daily-rule lane at the same time.

## Checks

- `uv run python scripts/gate.py check --all`: see the pull request.

## Review

Codex built the recorded-provider option and the smoke check (small class, two fix rounds); its
gate kept failing on the noon-cutoff expectation above, which was the plan's error. Claude
(orchestrator) reviewed the diff, replaced that step with the program's actual refusal and added
assertions on the two downloads' stored states.

## Plans closed

`2026-11-08-retained-daily-bar-grid` (the command-line grid audit) moved to the archive.
`2026-11-08-retained-bar-quality-ui`, `2026-11-08-retained-bar-production-assembly` and
`2026-11-08-retained-project-production-smoke` stay live: their browser screens are covered by
Playwright journeys, not by this smoke check.

## Not proven here

The browser screen itself (its Playwright journey runs against a test server); a check across all
files of a coin at once.
