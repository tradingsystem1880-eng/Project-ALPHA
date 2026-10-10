# Bounded mutation sweep checkpoints

```json
{
  "schema_version": 1,
  "title": "Durable bounded mutation sweep",
  "context": "Serial nightly cancellation requires durable exhaustive hosted measurements; owner selected weekly cadence and authorized focused publication, hosted verification and policy-compliant merge on 2026-10-10.",
  "assumptions": [
    {
      "statement": "Weekly cadence is owner-selected in current staged checkout",
      "verified_by": "Direct owner instruction: preserve owner-selected weekly cadence; current shared checkout staged weekly scheduling decision."
    }
  ],
  "alternatives_considered": [
    "Fixed multi-module shards rejected because worst-case sequential phases exceed six hours",
    "Increasing serial timeout rejected"
  ],
  "pre_mortem": [
    "A cancelled worker leaves unfinished checkpoint: aggregate rejects it",
    "Upload fails: missing exact module result fails aggregate"
  ],
  "slices": [
    {
      "title": "Isolate staging and clean process groups",
      "verify": "pytest tests/unit/test_claude_harness_gate.py -k QuantRigorTooling",
      "expected": "Local unavailable and score semantics preserved",
      "rollback": "Revert only new harness edits",
      "status": "done"
    },
    {
      "title": "Checkpoint and validate exhaustive identity-bound results",
      "verify": "pytest tests/unit/test_mutation_sweep.py tests/unit/test_mutation_report.py",
      "expected": "Partial and stale results rejected; score failures report-only",
      "rollback": "Revert sweep script and new tests",
      "status": "done"
    },
    {
      "title": "Wire workflow artifacts, document and verify final tree",
      "verify": "uv run python scripts/gate.py full",
      "expected": "Fresh full verification or explicit blocker; hosted completion separately unverified",
      "rollback": "Revert only new weekly workflow edits",
      "status": "in_progress"
    },
    {
      "title": "Publish focused PR, prove hosted completeness and merge under normal policy",
      "verify": "Required CI plus complete mutation sweep, normal merge and exact merged-SHA post-merge CI",
      "expected": "Verified exact commit, expected module artifacts and honest score/infrastructure distinction",
      "rollback": "Revert focused PR through normal protections",
      "status": "pending"
    }
  ],
  "tier_impact": [
    "protected"
  ],
  "docs_to_update": [
    "CLAUDE.md",
    "docs/BUILD-STATUS.md",
    "docs/operations/claude-code-harness.md"
  ],
  "out_of_scope": [
    "Baseline edits",
    "Hidden source access",
    "Unrelated cleanup changes",
    "Unrelated deployment",
    "Paid upgrades",
    "Gate bypasses",
    "Cadence changes"
  ]
}
```

Preserve the owner-selected weekly cadence and existing staged cleanup changes. One isolated
job per module is the deterministic exhaustive partition; eight jobs at most, two mutmut
children per job. Preserve all module/test selection and mutation floors.

Slices: (1) isolated harness staging and checked export; verify existing quant tooling tests;
(2) identity-bound inventory, atomic checkpoints, process-group deadlines and exact aggregate;
verify focused sweep tests; (3) always-upload workflow and honest docs; verify workflow contracts,
lint/types, then canonical `uv run python scripts/gate.py full`.

No package DAG, research authority, baseline, hidden-test source, or score semantics changes.
Hosted completion remains unverified until the authorized hosted checks and full mutation sweep finish. Merge also requires fresh independent review and all seven protected branch checks.

## Scoped owner decision — 2026-10-10

Asked: "Do you approve a one-time exception only for this mutation-check fix, leaving
private coverage marked UNVERIFIED? Codex would still require public checks, hosted CI,
the complete hosted mutation sweep and fresh independent review before merging. This
wouldn't waive failed tests, grant private-source access or apply to future work."
The owner answered "yes". This applies only to changes under this plan. Metadata confirms
`tests/holdout/` is absent in both checkouts. Its rejected execution was not retried and
no private source was read. Record that coverage UNVERIFIED; absence alone is nonblocking
for this fix. The receipt is in `.claude/agents/independent-reviewer.md`; all public gates,
fresh review, hosted completeness and normal Git/branch protections remain required.
