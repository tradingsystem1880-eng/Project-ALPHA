# Verification: crypto snapshot faults from the first real data run

Run on the Dell on 2026-11-14 (UTC), branch `m5/crypto-snapshot-duplicates`. Real-folder
commands ran with `export ALPHA_DATA_DIR=/home/hunta/alpha-clean-base/data`.

## Commands run

**Reproduction on the real folder, before the fix** (commit `7d9d1099`, main):

```text
$ uv run alpha crypto-data snapshot-verify c8ab0d2a0ad8b0faff797569521c16b1aa7f615e9d80a3818a92b95e1f5f6226 --json
Invalid value: crypto snapshot member manifest is ambiguous; frozen membership does not identify one retained capture
$ uv run alpha crypto-data storage-verify --json
Invalid value: crypto snapshot member manifest is ambiguous; frozen membership does not identify one retained capture
$ uv run alpha crypto-data backfill-status binance market_bars --symbols BTCUSDT --quote USDT --category spot \
    --frequency 1d --start 2017-08-01 --end 2026-11-01 --ledger spot-1d-BTCUSDT \
    --max-ledger-bytes 1000000 --max-windows 500 --max-verify-artifact-bytes 100000000 --json
complete; completed_verified 111, recorded_failure 1 (period 2026-11); next_action review_failures_unrecorded_work_and_existing_admission
```

The two January 2024 manifests (`901e60dd…`, `f358f49a…`) differ only in `manifest_id` and
`input_manifest_ids`; their raw inputs differ only in manifest id, storage key, receipt id and
`fetched_at` (both responses `474c1ce6…`).

**Fail-first on synthetic data.** The new tests, run against main's source
(`PYTHONPATH` set to a clean `origin/main` worktree): 16 failed, 29 passed. Each fault failed by
assertion: the repeated download gave main's exact "ambiguous" refusal at `snapshot-verify`; a
divergent capture, a capture named twice and overlapping members were all accepted by
`snapshot-create`; reversed option order gave a different snapshot id; the backfill fetched the
unfinished month and recorded it as failed; the Stooq adapter sent more than one request on a
challenge, and its messages pointed to yfinance. `tests/unit/test_crypto_snapshot_members.py`
fails on main because the module does not exist.

**After the fix, on the real folder** (commit `50882023`):

```text
$ uv run alpha crypto-data snapshot-verify c8ab0d2a…6226 --purpose research --required-family market_bars --json
"eligible": true, "blockers": [], "qualified_families": ["market_bars"]
$ uv run alpha crypto-data snapshot-verify a9202603…7b6a --purpose research --required-family market_bars --json
"eligible": true, "blockers": []
$ uv run alpha crypto-data storage-verify --json
"state": "verified", "manifest_count": 2854, "snapshot_count": 2, "research_eligible_snapshot_count": 2
$ uv run alpha crypto-data backfill-status … (same arguments as above) --json
complete; completed_verified 111, recorded_failure 0; next_action no_unfinished_work_recorded_for_request; not_published_yet ["2026-11"]
$ uv run alpha crypto-data backfill binance market_bars --symbols BTCUSDT --quote USDT --category spot \
    --frequency 1d --start 2026-10-01 --end 2026-11-20 --ledger spot-1d-BTCUSDT --dry-run --json
windows ["None|None|2026-10"], not_published_yet ["2026-11"], failed 0
```

A SHA-256 list of every file in the real folder was taken before any command and compared after
all of them: identical. Nothing in the real folder was written, edited or deleted. The old
`2026-11` failure entries remain inside the 15 ledger files (operational progress, not
evidence), outside every plan, so no status reports them.

**Multi-month snapshot, on a copy** (`/home/hunta/alpha-clean-base/tmp/data-proof`, its storage
config pointed at the copy, so the real folder was not written):

```text
snapshot-create, the 12 BTCUSDT 2024 months, ascending  -> member_count 12, snapshot_id cf0917f1…a381
snapshot-create, the same 12, descending                -> snapshot_id cf0917f1…a381 (same)
snapshot-verify cf0917f1…a381                           -> eligible true, blockers []
snapshot-create naming both January 2024 captures       -> refused: names the same capture more than once
storage-verify                                          -> verified, 3 snapshots, 3 eligible
```

**Checks:**

- `uv run pytest tests/integration/test_crypto_snapshot_duplicates_cli.py tests/unit/test_crypto_snapshot_members.py tests/unit/test_crypto_backfill.py tests/unit/test_code_size.py tests/integration/test_crypto_backfill_status_cli.py -q`
  (commit `50882023`): 104 passed.
- `handoff.py build` ran `gate.py check --base origin/main` and the brief's test lists on each
  Codex worktree: all passed (snapshot build: 73 new plus 114 existing crypto tests).
- `uv run python scripts/gate.py check --all` (commit `50882023` plus the documents): see the pull
  request; the run before the close-out documents failed only on the five generated-document and
  archived-plan-state tests (3,517 passed).

## End-to-end check

`tests/integration/test_crypto_snapshot_duplicates_cli.py` drives the real `alpha crypto-data`
commands through acquisition of synthetic Binance months, `snapshot-create`, `snapshot-verify`,
`storage-verify`, `backfill` and `backfill-status`. The real-folder runs above are the end-to-end
proof on real data.

## Not run

- CI lanes beyond `gate.py check --all` (they run on the pull request).
- `tests/integration/test_stooq_live.py` (network; Stooq was not contacted). No request to
  `data.binance.vision` was needed: every new test is offline.
- `research data register-crypto` on a multi-month snapshot of real data (it writes the control
  store); its multi-member path is unchanged and covered by existing tests.
- UNVERIFIED: how many days after a month ends Binance publishes its file (see finding O3).

## Review findings

Built by Codex: snapshot and backfill fix `gpt-6-astra`, effort high, hard class (raised from
standard with `--class hard`), 17m36s, 1 fix round (typing in the new test); a first attempt stopped
at a contradiction in the brief (an import rule), the brief was corrected and re-run. Stooq fix
`gpt-6.1-sol`, effort medium, small class, 5m45s, no fix round. Claude (Opus) wrote the documents,
lowered the code-size baseline, and made the hand fixes below.

Reviewers: an independent Claude Opus reviewer on the whole diff (route required: protected file
touched), and Codex (`gpt-6-astra`, medium, `handoff.py review`) on the whole diff and again on the
review-fix commit.

| # | Reviewer, severity | Finding | Disposition |
|---|---|---|---|
| O1 | Opus, medium | `backfill-status` silently drops unfinished months | Fixed: it reports `not_published_yet`; test added |
| O2 | Opus, medium | The verify-time overlap check is untested; could break stored snapshots | Fixed: test writes an overlapping snapshot directly and expects `snapshot-verify` and `storage-verify` to refuse. Real folder scanned: both snapshots have one member and verify |
| O3 | Opus, low | A month that has ended but is not yet published still records a failure for a few days | Rejected for now: the publication lag is not measured, and a guessed grace period could hide a real missing file. It fails loud and a later run retries it. Recorded in the invariants |
| O4 / C1 | Opus low, Codex medium | `not_published_yet` read the clock again after the run; at a month boundary a month could be neither fetched nor reported | Fixed: one clock reading for the plan and the report |
| O5 | Opus, low | Legacy raw inputs (no `artifact_kind`, key `raw/…`) refused as broken lineage | Fixed: same raw test as `publish_normalized`; test added |
| O6 | Opus, low | No test that snapshots stored in non-canonical order still verify | Fixed: test added |
| B1 | Claude, low (own review of the Stooq build) | A genuine "No data" answer was labelled a possible anti-bot refusal | Fixed by hand; test adjusted so only blocked bodies carry `anti-bot` |
| C2 | Codex, second review | 0 findings on the review-fix commit | — |

None open.
