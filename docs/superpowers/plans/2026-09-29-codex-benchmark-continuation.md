**Delivery state:** Completed.

# Codex-only benchmark continuation

```json
{
  "schema_version": 1,
  "title": "Codex-only benchmark continuation",
  "context": "Owner approved 2026-09-29: preserve all Claude evidence, use Codex only, finish research capability audit and fill evidence gaps without platform runtime fixes.",
  "assumptions": [
    {
      "statement": "Historical evidence remains byte-identical; new attempts and score revisions are append-only.",
      "verified_by": "before/after SHA256 inventory"
    },
    {
      "statement": "Live trials require enforced filesystem and MCP isolation.",
      "verified_by": "boundary preflight and adversarial smoke; no unrestricted fallback"
    }
  ],
  "alternatives_considered": [
    "Full campaign rerun rejected: score retained evidence first.",
    "Platform fixes deferred to separately governed work."
  ],
  "pre_mortem": [
    "Historical provenance is incomplete: label unknown rather than invent fingerprints.",
    "Permission profiles may fail in managed environment: block live trials, continue historical audit."
  ],
  "slices": [
    {
      "title": "Preserve historical evidence and append-only attempts",
      "verify": "cd tools/alpha-eval && uv run pytest -q tests/test_preservation.py",
      "expected": "Tests pass and evidence recorded",
      "rollback": "Revert only this continuation change; never delete historical evidence",
      "status": "done"
    },
    {
      "title": "Codex-only scoring revisions and provenance",
      "verify": "cd tools/alpha-eval && uv run pytest -q tests/test_runner.py",
      "expected": "Tests pass and evidence recorded",
      "rollback": "Revert only this continuation change; never delete historical evidence",
      "status": "done"
    },
    {
      "title": "Stream trials and enforce isolation",
      "verify": "cd tools/alpha-eval && uv run pytest -q tests/test_harness.py",
      "expected": "Tests pass and evidence recorded",
      "rollback": "Revert only this continuation change; never delete historical evidence",
      "status": "done"
    },
    {
      "title": "Model-neutral audit and bounded gap campaign",
      "verify": "cd tools/alpha-eval && uv run pytest -q",
      "expected": "Tests pass and evidence recorded",
      "rollback": "Revert only this continuation change; never delete historical evidence",
      "status": "done"
    },
    {
      "title": "Independent review and aggregate verification",
      "verify": "uv run python scripts/gate.py full",
      "expected": "Tests pass and evidence recorded",
      "rollback": "Revert only this continuation change; never delete historical evidence",
      "status": "done"
    }
  ],
  "tier_impact": [
    "protected"
  ],
  "docs_to_update": [
    "CLAUDE.md",
    "docs/BUILD-STATUS.md",
    "tools/alpha-eval/README.md",
    "docs/audit/2026-09-29-codex-capability-audit.md"
  ],
  "out_of_scope": [
    "Platform runtime changes",
    "New Claude calls",
    "Trading or owner authority",
    "Reading or editing hidden holdout tests"
  ],
  "files": [
    "tools/alpha-eval/",
    "scripts/codex_bridge.py",
    "tests/unit/test_claude_harness_codex_bridge.py",
    "docs/",
    "CLAUDE.md"
  ]
}
```

## Execution contract

New trials and judges: gpt-6-astra, medium effort, concurrency two. Preserve legacy artifacts; new scoring revisions carry exact input hashes. Freeze platform/scenario/world/config before resume. Use the same platform export for setup, CLI and MCP. Stream partial traces and stop on limits. Require read isolation before live trials. Score retained evidence, then fill missing realistic coverage and at most two diagnostic follow-ups per disputed scenario. Adaptive results stay separate from fixed-cohort rates. Independent same-model trace review is not cross-model validation.

## Current state

Codex-only implementation and evidence audit are complete. All 57,664 original evidence files
remain byte-identical. The 15 missing realistic variants completed with verified isolation and
unchanged owner state: 12 pass, 3 fail, no critical or invalid runs. Historical realistic V4
contains 132 cards; all 128 primary judgments were reused from V3 without new model calls.
The audit qualifies all 11 automated critical cards and all eight retained positive/null controls.

## Verification checkpoint

- Evaluator: 84 tests passed; strict typing passed for 22 source files.
- Affected bridge/gate tests: 44 passed (`--no-cov`); manual checks: 23 passed.
- Live boundary checks denied hidden reads and export writes; sandboxed MCP exposed 62 tools.
- Independent review completed with no remaining concrete code blocker.
- Frozen-copy full gate: backend passed with four workers, including coverage, slow oracles and
  mutation checks. Frontend lint/types/coverage/API checks passed; browser results were 188 passed,
  1 failed, 4 not run. Minimum-width scan deletion remained visible (`workflow.spec.ts:86`).
  Frontend asset regeneration also changed the verification tree. No aggregate pass is claimed.
- Final aggregate slice remains open for the unrelated UI repair and a fresh full gate. Concurrent
  UI work is preserved; this continuation does not modify that workflow.
- See [audit](../../audit/2026-09-29-codex-capability-audit.md) and
  [verification evidence](../../../tools/alpha-eval/results/2026-09-29-continuation/verification.json).

## 2026-09-30 closure

All six canonical full-gate components passed on one stable tree, verified against the live
checkout before this documentation update. The prior UI deletion and generated-output blockers
are cleared. Independent final audit found no remaining benchmark delivery gap. This completion
record follows the tested tree; it does not claim a fresh exact-tree stamp after documentation
edits. No commit or push was made; hidden-suite and live-provider acceptance remain unclaimed.
See [current verification receipt](../../../tools/alpha-eval/results/2026-09-29-continuation/verification-2026-09-30.json).
