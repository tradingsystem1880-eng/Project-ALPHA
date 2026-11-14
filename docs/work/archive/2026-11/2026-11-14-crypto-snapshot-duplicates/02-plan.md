# Crypto snapshot faults from the first real data run

**Delivery state:** In progress — building on branch `m5/crypto-snapshot-duplicates`.
**Build class:** hard — data-integrity code that decides which frozen crypto data research may use (raised from standard with `--class hard`); the Stooq change is a separate small build.

Filed straight into the archive, as `2026-11-14-free-real-data-dell` was: the work-in-progress
ceiling admits no new live plan, and the work is finished in one sitting.

## For the owner

- A crypto snapshot that ALPHA lets you create can now always be checked again later. Downloading
  the same Binance file twice no longer breaks anything; if two downloads of the same file ever
  disagree in any recorded detail, both creating and checking a snapshot of it fail loudly.
- Your stuck BTC January 2024 snapshot checks out again and the whole-store check passes; nothing
  stored was edited or deleted.
- A backfill no longer records a failure for the current month; it says "not published yet".
- A snapshot can hold many months of many coins, and its name no longer depends on the order you
  list them in. The daily-rule reader still reads one month (changing it would void approvals).
- The Stooq downloader no longer gets past Stooq's browser check; it refuses instead.
- Nothing for you to decide here; one follow-up is listed at the end.

```json
{
  "schema_version": 1,
  "title": "Crypto snapshot faults from the first real data run",
  "context": "The first real data run on the Dell (2026-11-14) found that snapshot creation and verification disagree on repeated downloads, which leaves storage-verify failing on the real data folder; that the Binance backfill records a failure for the unfinished month; that snapshot identity depends on option order; and that the stooq adapter solves a bot check.",
  "assumptions": [
    {"statement": "Two downloads of one Binance month produce normalized manifests with identical artifact key, hash, dataset and quality, differing only in manifest id and raw input ids; the raw inputs differ only in manifest id, storage key, receipt id and fetch time.", "verified_by": "reading manifests 901e60dd... and f358f49a... and their raw inputs in /home/hunta/alpha-clean-base/data/crypto/manifests"},
    {"statement": "A snapshot member binds content only (dataset, artifact key, artifact hash), not a manifest id.", "verified_by": "packages/alpha-data/src/alpha_data/crypto/contracts.py CryptoSnapshotMemberV1"},
    {"statement": "snapshot-create already accepts several --manifest-id options; identity hashes members in the given order.", "verified_by": "crypto_data_cmds.snapshot_create and CryptoSnapshotV1._identity"},
    {"statement": "The crypto store reads only Binance monthly archives plus a bounded REST tail; it has no daily-archive reader.", "verified_by": "alpha_data/crypto/providers/binance.py archive_url builds monthly URLs only"},
    {"statement": "crypto_bulk_store.py, crypto_price_snapshot_query.py and control_store.py are daily-rule guard files; crypto_data_cmds.py, _crypto_analysis.py and _crypto_backfill.py are not.", "verified_by": "apps/alpha-cli/src/alpha_cli/_native_rule_environment.py DAILY_GUARD_FILES"}
  ],
  "alternatives_considered": [
    "Apply verification's 'exactly one manifest' rule at creation too: rejected, an honest repeat download would still break every snapshot of that month.",
    "Refuse or skip a repeat download at fetch time: rejected, it hides a real re-observation and leaves stores that already hold duplicates stuck.",
    "Add a superseded-snapshot record: not needed, the stuck snapshot verifies under the corrected rule.",
    "Read Binance daily archive files for the current month: rejected, the store is not designed for them; the REST tail is the designed path.",
    "Let the daily price query read many members: deferred, it is a daily-rule guard file and changing it voids pending daily-rule approvals (follow-up below)."
  ],
  "pre_mortem": [
    "The equivalence rule drops a field that matters, so two different captures pass as one: the signature drops only named per-fetch fields, and a unit test changes each kept field and expects a refusal.",
    "The overlap check refuses a legitimate stored snapshot: real snapshots hold one member each; verification of the real folder is recorded in 04-verify.md.",
    "Skipping unfinished months hides a missing file: only months that have not ended are skipped; an ended month without a file is still a recorded failure."
  ],
  "slices": [
    {"title": "One member rule for create and verify; canonical order; disjoint ranges", "verify": "uv run pytest tests/unit/test_crypto_snapshot_members.py tests/integration/test_crypto_snapshot_duplicates_cli.py -q", "expected": "all pass; the duplicate-download test fails on main", "rollback": "revert the merge of build/crypto-snapshot-members", "status": "pending"},
    {"title": "Binance backfill skips months that have not ended", "verify": "uv run pytest tests/unit/test_crypto_backfill.py -q", "expected": "all pass; the unpublished-month tests fail on main", "rollback": "revert _crypto_backfill.py", "status": "pending"},
    {"title": "Stooq refuses its bot check", "verify": "uv run pytest tests/unit/test_stooq_adapter.py tests/unit/test_stooq_parser.py -q", "expected": "all pass; the one-request challenge test fails on main", "rollback": "revert the merge of build/stooq-no-bot-check", "status": "pending"},
    {"title": "Real data folder verifies; documents", "verify": "ALPHA_DATA_DIR=/home/hunta/alpha-clean-base/data uv run alpha crypto-data storage-verify --json", "expected": "state verified, 2 snapshots", "rollback": "none needed, read-only", "status": "pending"}
  ],
  "tier_impact": ["determinism"],
  "docs_to_update": ["docs/adr/0046-crypto-snapshot-members-are-content-addressed.md", "docs/reference/invariants/data.md", "docs/reference/invariants/cli-crypto-data.md", "docs/reference/project/components/data-layer.md", "docs/roadmap/capabilities.toml", "docs/reference/commands.md", "STATUS.md"],
  "out_of_scope": ["packages/alpha-research/src", "packages/alpha-validation/src", "daily-rule guard files", "apps/alpha-cli/src/alpha_cli/research_*.py", "stored data", "yfinance adapter removal"],
  "files": [
    "apps/alpha-cli/src/alpha_cli/_crypto_snapshot_members.py",
    "apps/alpha-cli/src/alpha_cli/crypto_data_cmds.py",
    "apps/alpha-cli/src/alpha_cli/_crypto_backfill.py",
    "tests/unit/test_crypto_snapshot_members.py",
    "tests/integration/test_crypto_snapshot_duplicates_cli.py",
    "tests/unit/test_crypto_backfill.py",
    "packages/alpha-data/src/alpha_data/adapters/stooq_adapter.py",
    "tests/unit/test_stooq_adapter.py",
    "tests/integration/test_stooq_live.py",
    ".claude/code-size-baseline.json",
    "docs/adr/0046-crypto-snapshot-members-are-content-addressed.md",
    "docs/adr/README.md",
    "docs/reference/invariants/data.md",
    "docs/reference/invariants/cli-crypto-data.md",
    "docs/reference/project/components/data-layer.md",
    "docs/reference/commands.md",
    "docs/roadmap/capabilities.toml",
    "docs/roadmap/README.md",
    "STATUS.md",
    "docs/work/archive/2026-11/2026-11-14-crypto-snapshot-duplicates/"
  ]
}
```

## Read first

| Read | Section | When |
|---|---|---|
| [command line crypto data](../../../../reference/invariants/cli-crypto-data.md) | Backfill; Immutable documents | always |
| [data invariants](../../../../reference/invariants/data.md) | Crypto storage; Adapters and authority | always |
| [ADR-0032](../../../../adr/0032-governed-crypto-data-house.md) | Decision | snapshot rules |
| [ADR-0045](../../../../adr/0045-approvals-bind-code-structure.md) | Consequences | which files bind approvals |
| [first real data run](../2026-11-14-free-real-data-dell/04-verify.md) | Snapshots | the faults as found |

## Slices

As in the JSON block. Codex builds the first two slices from one brief (hard class) and the Stooq
slice from a second (small class), each in its own worktree; Claude merges, lowers the code-size
baseline entry for `crypto_data_cmds.py`, writes the documents and runs the real-folder proof.

## Test plan

Each fault gets a test that fails on `origin/main` first: two identical synthetic Binance
downloads (create, verify, storage-verify), a divergent third capture (refused at create and at
verify), option order (same id), a capture named twice, overlapping members, an unfinished month
in the backfill plan and run, and one request with no solver for a Stooq challenge. Existing crypto
CLI, backfill and Stooq tests must keep passing unchanged.

## Look-ahead, determinism and import impact

No read path changes what a reader sees at an as-of time. Snapshot identity becomes independent of
option order (canonical member order); member resolution picks the smallest manifest id. The new
module imports only the standard library, `alpha_core`, `alpha_data` and one private `alpha_cli`
sibling.

## Follow-up: many months in the daily rule lane (not built here)

`crypto_price_snapshot_query.query_binance_daily_price_snapshot` requires exactly one member and
one named normalized manifest. Letting a daily-rule study read a multi-month snapshot means:
accept several members of the one Binance daily identity, require them in canonical order with
disjoint ranges, take one named manifest per member (or resolve each with the ADR-0046 rule),
check that consecutive months join without a missing day, and cap total rows. That file and
`daily_native_cmds.py` are daily-rule guard files, so the change invalidates every pending daily
rule approval (the owner re-drafts and re-approves). It is a separate task for when the owner wants
a multi-year daily-rule study.
