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
