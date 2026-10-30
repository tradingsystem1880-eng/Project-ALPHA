**Delivery state:** Completed implementation; exact-tree qualification and delivery results are recorded separately. Historical implementation checks below are not current-main acceptance.

# Bounded crypto snapshot query

```json
{
  "schema_version": 1,
  "title": "Bounded crypto snapshot query",
  "context": "Owner-approved isolated implementation of one read-only snapshot query seam on the verified e635e6cb baseline. Keep the existing snapshot/artifact contracts, provider boundary, and source time semantics; no full gate or publication before parent coordination.",
  "assumptions": [
    {
      "statement": "One exact CryptoSnapshotV1 with exactly one DefiLlama defi_tvl member is sufficient for the first query/reopen workflow.",
      "verified_by": "Snapshot identity, member, lineage, schema, and CLI reopen tests use synthetic public fixtures."
    },
    {
      "statement": "DefiLlama available_at is a next-UTC-day parser convention and does not prove source publication time.",
      "verified_by": "The returned contract always sets point_in_time_claim=false and preserves raw receipt fetched_at."
    }
  ],
  "alternatives_considered": [
    "Rejected arbitrary SQL, new ingestion, a DuckDB migration, and another report/UI/API surface.",
    "Rejected eager unbounded materialization and silent truncation; enforce input/output bounds and explicit page continuation."
  ],
  "pre_mortem": [
    "A valid compressed Parquet file could expand beyond a practical decoded-row budget; inspect schema first and cap rows before materializing fixed-width columns.",
    "A later capture could be mistaken for historical point-in-time evidence; expose fetch time, availability convention, cutoff relation, and a false PIT claim.",
    "A returned page could be mistaken for a complete result; expose available row count, has_more, and next_offset."
  ],
  "slices": [
    {
      "title": "Verified bounded artifact read",
      "verify": "uv run pytest -q tests/unit/test_crypto_storage.py",
      "expected": "Normalized artifact kind, manifest, lineage, exact payload hash, mounted UUID, and byte ceiling are verified before bytes are returned.",
      "rollback": "Remove the verified read method and its storage tests.",
      "files": ["packages/alpha-data/src/alpha_data/crypto/storage.py", "tests/unit/test_crypto_storage.py"],
      "status": "done"
    },
    {
      "title": "DefiLlama snapshot query and paged CLI",
      "verify": "Focused crypto storage/snapshot/CLI tests; strict mypy; Ruff check/format; import contracts; Atlas freshness.",
      "expected": "One exact member reopens deterministically under explicit byte/row/page limits, preserves old revisions, rejects unsupported data, exposes continuation, and makes no historical PIT claim.",
      "rollback": "Remove the reader and CLI command; retain immutable snapshots and prior receipts.",
      "files": ["apps/alpha-cli/src/alpha_cli/crypto_snapshot_query.py", "apps/alpha-cli/src/alpha_cli/crypto_data_cmds.py", "tests/unit/test_crypto_snapshot_query.py", "tests/integration/test_crypto_snapshot_query_cli.py", "CLAUDE.md", "docs/operations/research-platform-contracts.md", "docs/ARCHITECTURE.md", "docs/BUILD-STATUS.md", "tools/alpha-atlas/architecture/atlas/cache/cli-commands.json", "architecture/atlas/generated/graph.json", "architecture/atlas/generated/inputs.json", "architecture/atlas/generated/views/unknowns.json", "docs/atlas/cli-flow.md", "docs/atlas/data-lineage.md", "docs/atlas/frontend-flow.md", "docs/atlas/research-flow.md", "docs/atlas/system-map.md"],
      "status": "done"
    }
  ],
  "tier_impact": ["dag", "determinism"],
  "docs_to_update": ["CLAUDE.md", "docs/operations/research-platform-contracts.md", "docs/ARCHITECTURE.md", "docs/BUILD-STATUS.md", "architecture/atlas/generated/graph.json", "architecture/atlas/generated/inputs.json", "architecture/atlas/generated/views/unknowns.json", "docs/atlas/cli-flow.md", "docs/atlas/data-lineage.md", "docs/atlas/frontend-flow.md", "docs/atlas/research-flow.md", "docs/atlas/system-map.md"],
  "out_of_scope": [
    "Full gate, commit, publication, merge, or deployment before parent coordination.",
    "New dependencies, DuckDB/PostgreSQL, schema migration, live provider calls, execution routes, report/UI/API changes, or D1 recovery work."
  ],
  "files": [
    "packages/alpha-data/src/alpha_data/crypto/storage.py",
    "apps/alpha-cli/src/alpha_cli/crypto_snapshot_query.py",
    "apps/alpha-cli/src/alpha_cli/crypto_data_cmds.py",
    "tests/unit/test_crypto_storage.py",
    "tests/unit/test_crypto_snapshot_query.py",
    "tests/integration/test_crypto_snapshot_query_cli.py",
    "CLAUDE.md",
    "docs/operations/research-platform-contracts.md",
    "docs/ARCHITECTURE.md",
    "docs/BUILD-STATUS.md",
    "tools/alpha-atlas/architecture/atlas/cache/cli-commands.json",
    "architecture/atlas/generated/graph.json",
    "architecture/atlas/generated/inputs.json",
    "architecture/atlas/generated/views/unknowns.json",
    "docs/atlas/cli-flow.md",
    "docs/atlas/data-lineage.md",
    "docs/atlas/frontend-flow.md",
    "docs/atlas/research-flow.md",
    "docs/atlas/system-map.md"
  ]
}
```

## Goal

Add one read-only query/reopen path for a `defi_tvl` member selected from an exact
`CryptoSnapshotV1`. Reuse the existing provider receipt, normalized Parquet, manifest,
qualification, and path-confinement contracts. Do not add ingestion, live requests, SQL, a
report/UI surface, dependencies, or a storage migration.

## Contract

- Accept one exact snapshot ID and require exactly one supported `defi_tvl` member; ambiguity or
  any unsupported family fails closed.
- Reuse snapshot/member verification, then reverify the selected normalized manifest and its raw
  lineage before reading bounded bytes.
- Require the exact provider identity and exact `chain, observed_at, tvl_usd, available_at` schema.
  Preserve `units=usd`, observation time, next-day availability convention, source receipt fetch
  time, parser/provider schema versions, and hashes in output.
- Bound Parquet bytes to 32 MiB, decoded input rows to 50,000, output rows to 1,000 per page, and
  offset to 100,000. Schema-check before decoding; materialize only fixed-width timestamp and value
  columns, and derive chain from the bounded dataset identity. Return `has_more` and `next_offset`
  so a page never silently stands in for the full result. An optional UTC `available_at` cutoff
  filters rows. Describe it as the provider's next-day availability convention; source `fetched_at`
  is retrieval evidence, not historical publication time. Do not call a later-fetched snapshot
  historically point-in-time.
- Reading must not change snapshots, manifests, or artifacts. A revision produces a distinct
  snapshot and leaves prior IDs reopenable.

## Slices and verification

1. Add a bounded verified normalized-byte read to `CryptoBulkStore`, with unit tests for valid
   reads, wrong artifact kind, tampering, and size limits. Verify with the focused storage test.
2. Add the typed `defi_tvl` snapshot reader and CLI command, with synthetic snapshot fixtures for
   deterministic reopen, schema/member rejection, row/availability bounds, and revision replay.
   Verify focused unit and CLI integration tests, canonical typing, and lint. Inspect the final diff
   independently. Do not run the full gate or publish/merge.

## Files

- `packages/alpha-data/src/alpha_data/crypto/storage.py`
- `apps/alpha-cli/src/alpha_cli/crypto_snapshot_query.py` (new)
- `apps/alpha-cli/src/alpha_cli/crypto_data_cmds.py`
- `tests/unit/test_crypto_storage.py`
- `tests/unit/test_crypto_snapshot_query.py` (new)
- `tests/integration/test_crypto_snapshot_query_cli.py` (new)
- `CLAUDE.md`
- `docs/operations/research-platform-contracts.md`
- `docs/ARCHITECTURE.md`
- `docs/BUILD-STATUS.md`
- `tools/alpha-atlas/architecture/atlas/cache/cli-commands.json`
- `architecture/atlas/generated/graph.json`
- `architecture/atlas/generated/inputs.json`
- `architecture/atlas/generated/views/unknowns.json`
- `docs/atlas/cli-flow.md`
- `docs/atlas/data-lineage.md`
- `docs/atlas/frontend-flow.md`
- `docs/atlas/research-flow.md`
- `docs/atlas/system-map.md`

## Architecture and causal impact

The implementation stays in `alpha_data` storage and the `alpha_cli` composition layer, preserving
the repository dependency DAG. It only reads already-frozen data. `available_at` is a deterministic
next-UTC-day convention emitted by the DefiLlama parser, while receipt `fetched_at` is the recorded
response retrieval time. A filter on `available_at` does not establish when DefiLlama first
published a historical point; results from a capture after a queried cutoff remain retrospective.
No strategy, execution, report/UI, D1 recovery, or historical equity behavior changes.

## Cleanup recovery — 2026-10-30

The owner clarified that cleanup includes integrating useful retained branch work into main.
This recovers existing commit `4710a00392cc40739f97ed49890a85ac911ec6e0` from
`codex/saved-snapshot-query-e635e6cb` onto verified main
`f847581f2703f6b5b36aeccdf877c4354a19e176`; original branch/history remain intact.
The original temporary hold on full verification/publication is superseded by this explicit
parent-coordinated recovery assignment. No broader query/data-platform capability is added.

Reconciliation preserves main's PR95/96 protections and Binance budgets. It verifies only the
selected member and raw lineage, checks normalized/raw sizes before payload hashing, rejects
mixed-family snapshots and unsafe metadata/snapshot paths, and preserves availability disclosures.
The chain label comes from manifest identity; variable-width stored chain cells are schema-checked
but not decoded or independently validated. Generic snapshot verification/admission stays separate.

Repeated captures can share normalized bytes while binding different raw receipts: existing snapshot
IDs do not encode that distinction. Retain `normalized_manifest_id` from query output and pass
`--manifest-id` on reopen to bind the exact original provenance. Without that selector, ambiguous
captures fail closed rather than silently selecting newer provenance. This additive selector changes
no snapshot contract or historical bytes. Wrong member/hash/manifest combinations fail closed.

The inherited focused selection passed 39 cases. Four new discriminating regressions reproduced
pre-cap hashing, mixed members, symlinked metadata and unrelated-payload coupling before correction.
A retired-qualified-TVL test had an invalid premise: existing retirement correctly permits only
quarantined data or the known stablecoin unit error. It was removed; ordinary revision replay
continues to verify immutable reopening without changing retirement/admission. The corrected
selection passed 45 cases including an availability future-poison/control. Independent early
review then identified unchanged-recapture ambiguity; exact-manifest replay now covers it.
Final full/review/commit/CI results belong to exact candidate evidence, not historical source
narratives. CLI cache and Atlas must be regenerated from the actual combined tree.

### Task-scoped missing-private-suite decision

The owner approved the missing-private-suite exception through delivery for cleanup/refactor,
file-system, Software Team and the two-bug follow-up: user message
`Sentinel_98705aca9ff081919c43e10c7856c9fe`, 2026-10-30 05:41 UTC, “Yes I approve”,
answering explicit proposal `Sentinel_f34bce300f4881919c0e610ebafb67fa` at 03:51 UTC.
The subsequent 05:42 UTC all-useful-branches cleanup clarification
`Sentinel_9b37e75fb0748191a5be1db505a1d9b2` and parent assignment include necessary
recovery of this stranded slice. Only documented absence of `tests/holdout/` is nonblocking.
Private coverage stays UNVERIFIED; no private contents are read or modified. All public failures,
other unavailable required checks, independent review and normal Git/CI guards still block.
This grants no research acceptance, trading authority or standing future exception.

### Public coverage correction

The first recovered full gate stopped correctly: all 6,716 backend cases passed (61 skipped,
two subtests passed), but aggregate coverage was 92.98%, below the unchanged 93% floor.
Added public regressions cover malformed cutoff/unit/qualification/selector inputs, invalid
values/row counts/Parquet/clocks, empty data, decode failures and raw-lineage mismatches.
No production code, assertions, thresholds or selection were weakened. The failed full log
and failed backend receipt remain evidence; only a fresh complete gate can accept the new tree.
