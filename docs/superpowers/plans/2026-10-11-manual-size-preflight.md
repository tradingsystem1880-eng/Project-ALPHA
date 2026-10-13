**Delivery state:** Completed implementation; release acceptance is bound to final verification receipts.

# Early manual-size preflight

```json
{
  "schema_version": 1,
  "title": "Early manual-size preflight",
  "context": "Owner authorized preparing one isolated behaviour-preserving optimisation slice during PR54 sweep wait. Frozen cleanup delta, mutation and original checkout remain untouched. No publication or final acceptance until integrated target settles.",
  "assumptions": [
    {
      "statement": "The public manual-size assertion remains the authoritative 6000-byte guard.",
      "verified_by": "Reuse its exact existing pytest node; boundary and fail-stop regressions."
    }
  ],
  "alternatives_considered": [
    "Rejected a second manual validator, gate caching, test removal and browser parallelism."
  ],
  "pre_mortem": [
    "A stale backend receipt must not survive adding a new command definition.",
    "The extra pytest startup adds cost to passing gates; measure it and retain the original coverage assertion."
  ],
  "slices": [
    {
      "title": "Characterize ordering and failed receipt",
      "verify": "uv run pytest -q tests/unit/test_gate_components.py -k manual",
      "expected": "Red before insertion; unchanged existing steps, valid6000 boundary and invalid6001 boundary, no passing receipt on failure.",
      "rollback": "Remove only new regression tests.",
      "status": "done"
    },
    {
      "title": "Insert existing size guard after locked setup",
      "verify": "uv run pytest -q tests/unit/test_gate_components.py tests/unit/test_claude_md_relocation.py",
      "expected": "Guard runs before lint/types/coverage; all original steps remain. Final full acceptance deferred to settled target.",
      "rollback": "Remove inserted preflight and revert scoped documentation.",
      "status": "done"
    }
  ],
  "tier_impact": [],
  "docs_to_update": [
    "CLAUDE.md",
    "docs/BUILD-STATUS.md"
  ],
  "out_of_scope": [
    "Private suite access or policy change",
    "Any mutation/feature/research change",
    "Frozen20-path cleanup",
    "Speculative caching or reduced browser coverage",
    "Publication before settled target"
  ],
  "files": [
    "scripts/gate_components.py",
    "tests/unit/test_gate_components.py",
    "CLAUDE.md",
    "docs/BUILD-STATUS.md"
  ]
}
```

This slice improves failure latency for an invalid manual, not successful full-gate throughput. It adds one pytest startup and repeats the existing assertion during coverage. No browser test identity, assertion, snapshot or real-backend journey changes. Atlas must be regenerated and final acceptance repeated on the eventual integration target.

## Accepted integration target

Integrated only this scoped followup on accepted main `31479cad` after PR56 exact-head and post-merge CI passed. Historical preparation remains recoverable. Final public full, independent review, hosted CI and post-merge receipts bind the actual target; preparation receipts do not establish acceptance. The four-followup absence-only decision is recorded in `docs/operations/2026-10-12-four-followup-private-suite-exception.md`; private coverage remains UNVERIFIED. Renderer/readiness stays separate, and no new exhaustive mutation sweep is included.
