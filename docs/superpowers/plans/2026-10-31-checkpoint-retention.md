# Non-destructive checkpoint retention and branch recovery

**Delivery state:** Implemented; coordinated main delivery pending.

```json
{
  "schema_version": 1,
  "title": "Non-destructive checkpoint retention and branch recovery",
  "context": "Close the existing unbounded checkpoint retention gap with verified archive preparation and reconcile historical branch delivery while preserving every source. Current base is 2a8aa50b; README and bootstrap work remain separately owned.",
  "assumptions": [
    {
      "statement": "Existing gate preservation has no inventory/archive route and never prunes incomplete staging.",
      "verified_by": "gate_components.py preservation implementation and native foundation stage contract."
    }
  ],
  "alternatives_considered": [
    "Automatic age-based deletion rejected: evidence may still be uniquely required.",
    "New branch management framework rejected: Git refs, bundles and existing delivery records suffice."
  ],
  "pre_mortem": [
    "An untrusted manifest could name private files: validate the exact existing evidence allowlist and reject symlinks before opening payloads.",
    "A failed archive or concurrent source change must never replace an existing archive or delete the source.",
    "A historical nonancestor branch is not necessarily unfinished work; reconcile delivered slices with successors and preserve exact refs."
  ],
  "slices": [
    {
      "title": "Add dry-run inventory and non-destructive verified archives",
      "verify": "uv run pytest -q tests/unit/test_gate_checkpoints.py tests/unit/test_gate_components.py tests/unit/test_gate_preflight.py",
      "expected": "Current/recent/incomplete exclusions; exact manifest checks, verified round trip, tamper and race rejection; originals preserved.",
      "rollback": "Revert checkpoint command and tests; retain all created local archives and evidence.",
      "status": "done"
    },
    {
      "title": "Preserve and reconcile the remote branch inventory",
      "verify": "git bundle verify plus exact bundle-head/manifest comparison and successor ancestry/content checks",
      "expected": "Every remote tip has commit/tree and recovery ref; active work excluded; no remote deletion.",
      "rollback": "Keep bundle and manifests; no remote state changed.",
      "status": "done"
    },
    {
      "title": "Qualify, independently review and deliver the assembled candidate",
      "verify": "uv run python scripts/gate.py full",
      "expected": "Fresh exact-tree gate and independent review; private tests absent and UNVERIFIED under scoped owner consent.",
      "rollback": "Retain candidate and failed receipts without publication.",
      "status": "pending"
    }
  ],
  "tier_impact": [
    "protected"
  ],
  "docs_to_update": [
    "docs/operations/claude-code-harness.md",
    "docs/superpowers/plans/2026-10-08-repository-hygiene.md",
    "docs/superpowers/plans/2026-10-26-native-rule-authority.md",
    "docs/BUILD-STATUS.md"
  ],
  "out_of_scope": [
    "README/bootstrap implementation",
    "Remote branch deletion or main merge",
    "Permanent checkpoint deletion",
    "Mac-only inventory",
    "Product/research/trading authority"
  ],
  "files": [
    "architecture/atlas/generated/",
    "scripts/gate.py",
    "scripts/gate_checkpoints.py",
    "tests/unit/test_gate_checkpoints.py",
    "docs/operations/claude-code-harness.md",
    "docs/superpowers/plans/2026-10-08-repository-hygiene.md",
    "docs/superpowers/plans/2026-10-26-native-rule-authority.md",
    "docs/BUILD-STATUS.md"
  ]
}
```

No import-DAG, point-in-time, seed, product feature or scientific authority changes.
Original receipts, incomplete copies and branch histories stay preserved. Private inventories and
Git bundles stay under `.alpha/state/`; the tracked docs contain commands and disposition rules.

Focused verification: 290 tests and two subtests pass through the owned runner; scoped strict
typing, Ruff, harness lint and plan validation pass. The official generator refreshed the three
changed Atlas JSON outputs; all eight outputs pass freshness. One older checkpoint was archived
and verified in the retained cloud worktree, with every source file kept. Final public qualification
and independent review must bind the assembled tree rather than these focused receipts.

Independent review of the first frozen tree found that a FIFO substituted for a manifest or
existing archive could hang inventory. Both bounded probes timed out before the repair. The
repaired reader opens evidence without blocking, rejects nonregular descriptors and bounds
manifest reads; archive verification streams only the expected unique regular members. Bounded
real-CLI FIFO and archive-copy regressions retain the special files and enforce prompt rejection. Original review
and gate receipts are preserved; no absence exception waives this software defect.

The repaired source passes 294 focused tests and two subtests, strict typing and Ruff. The
superseded aggregate was deliberately interrupted after backend checks passed; it is not a full
pass. Its source, partial receipts, independent BLOCK and FIFO probes are sealed separately.
Fresh final qualification applies only to the repaired tree.
