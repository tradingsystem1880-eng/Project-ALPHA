# Verify: daily-rule approval binding gap, and the daily price reader over many months

## Build

- Codex (`handoff.py build`, hard class, `gpt-6-astra` `high`). The first run stopped before
  editing: the plan asked for an edit to `research_cmds.py`, already 3,539 lines and pinned in the
  size baseline. The plan was clarified (that edit must be line-neutral) and the build re-run:
  60m40s, one build round and two fix rounds, 15.7M input tokens (15.2M cached), 94k output.
  Record: `03-build.json`.
- The fix rounds left two `tests/integration/test_daily_rule_report.py` failures. Both came from
  the build worktree lacking the built web bundle (`alpha_web/static`), not from the change. They
  pass in this worktree once the ignored bundle is copied in from the main checkout.

## Review and dispositions

| Reviewer | Finding | Disposition |
|---|---|---|
| Independent agent, diff only | HIGH: the exemption for `_artifacts → _native_tearsheet` was wrong. Daily artifacts run `write_run_sidecars` → `write_native_tearsheet` (confirmed at run time) | Fixed in `698bb152`: `_native_tearsheet.py` bound, exemption removed |
| same | MEDIUM: "imported but not called" is not safe, because importing runs top-level code. Imports that execute on daily paths: `_native_stock_launch` (type checks on every launch), `research_readiness` (module level), `research_runtime` (D0 reservation) | Fixed: those modules, `native_stock_fixture.py` and `__init__.py` are bound. Exemptions are now allowed only for imports that never execute on a daily path |
| same | LOW: the tracer skips `import alpha_cli`, subpackages and `__init__.py` | Fixed: every alpha_cli import adds `__init__.py` (bound), and subpackage imports fail |
| same | LOW: no test for the 32 MiB aggregate normalized ceiling | Fixed: new test |
| same | LOW: other coins in a snapshot are now ignored, not refused | Kept, documented in ADR-0047: rows are unaffected and the snapshot id still binds them |
| same | LOW: study validator caps members at 100, reader at 200 | Kept: both fail loud; the study needs 36 |
| same | LOW: the V2 validator does not cross-check member ranges against rows | Kept: every consumer reopens the query and requires the exact document and hash |
| same | Remaining: alpha_validation (tearsheet) and alpha_research run unbound on daily paths | Not fixed: owner decision, ADR-0047 and 05-handoff |
| same, re-check of `698bb152` | All findings fixed for alpha_cli. Every remaining exemption's import never executes on a daily path. The `_structural_digest` exemption holds only if it binds its own bytes | Confirmed: `binding_digest` writes `rules_sha256 = _own_bytes_sha256()` |
| Codex (`handoff.py review --built-by claude`, base `0ee3c3b1`, covering the hand fixes and documents) | 0 findings | — |

## Checks

- `uv run python scripts/gate.py check` on `a540e9a2`: ruff, format, import contracts and pytest
  passed (27 mapped test files plus the research guards). mypy failed on one line of the new 32 MiB
  test. That line was fixed and the gate re-run; the result is in the pull request.
- New tests: `test_daily_guard_boundary.py`, `test_daily_guard_binding.py` (logic edit changes the
  code hash, and a comment edit does not, for each of the 13 structurally bound new files;
  byte-bound files change on any edit), `test_crypto_price_snapshot_months.py`,
  `test_daily_rule_months_study.py`, and bias guard `test_daily_price_months_future_poison.py`.
- One-month identity: `test_crypto_price_snapshot_query.py` pins content hash `4498ebb4…e3ca`,
  computed on `origin/main` before the change. Existing assertions are unchanged; only the keyword
  was renamed.
- `uv run python scripts/fs.py stale`: 0 stale after re-reading and re-stamping the 17 documents
  whose sources changed.

## Real data, read-only

The proof ran on a copy of the Dell data folder at `/home/hunta/alpha-clean-base/tmp/data-proof-daily`.
The copy's storage config points at the copy.

```text
snapshot-create, 36 BTCUSDT months 2020-01..2022-12      -> member_count 36, snapshot 561a39bf…8b95
snapshot-verify 561a39bf…8b95                            -> eligible true, blockers []
query 2020-01-01..2023-01-01, 36 named manifests         -> V2, 36 members, 1,096 rows,
                                                            2020-01-01 .. 2022-12-31, sha 32b1319f…a387
same ids shuffled                                         -> identical document
one month left out                                        -> refused: overlapping snapshot member is not named
bind_daily_study on the result                            -> binds (query hash equal)
```

The real folder's SHA-256 list was taken before the build and compared afterwards. It differed
by exactly two new files, both written at about 19:37 by another session (its handoff run
`2026-11-14-first-real-study`), not by this task:

- `control/workstation.sqlite3`;
- `crypto/snapshots/561a39bf…8b95.json`, the same 36-month snapshot.

This task wrote only to the copy, at 20:15.

## Pending daily-rule approvals

- The default data folder (`data/` in the checkout) has no control store.
- The Dell's data folder now has one (above). Read-only inspection (`sqlite3` `mode=ro`) found one
  generic exploration research contract, `rc_b0843ac5…`, with no protocol (not a daily-rule
  contract) and no `research_contract_review_events` rows.
- Only test approvals in temporary pytest stores exist. No real daily-rule approval is pending, so
  this change invalidates none in practice.
