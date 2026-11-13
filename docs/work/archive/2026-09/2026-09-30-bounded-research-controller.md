**Delivery state:** Completed

# Bounded research controller

```json
{
  "schema_version": 1,
  "title": "Bounded baseline controller and verified execution digest",
  "context": "Continue measured workflow improvements without adding specialist transport or mutating concurrent UI checkout.",
  "assumptions": [
    {
      "statement": "Controller bounds its own operations, not the surrounding agent information access.",
      "verified_by": "No arbitrary commands; exact snapshot and cutoff checked on results; receipt explicitly disclaims agent-wide isolation."
    }
  ],
  "alternatives_considered": [
    "Unbounded specialist swarm deferred until controller improves measured completion.",
    "Temporal filesystem isolation remains separate work; as_of alone is not such isolation."
  ],
  "pre_mortem": [
    "Timeout could strand children or lose results; reuse process-group cleanup and always publish terminal evidence.",
    "Restart could reset search budget; durable prelaunch attempts prevent automatic retries.",
    "Model narrative could omit denials; digest derives counts from verified sidecars."
  ],
  "slices": [
    {
      "title": "Verify execution digests against immutable run artifacts and semantic counts",
      "verify": "uv run pytest -q tests/unit/test_research_execution.py --no-cov",
      "expected": "Bounded operations and honest immutable results; no inferred authority.",
      "rollback": "Revert added runtime; preserve prior immutable evidence.",
      "status": "done"
    },
    {
      "title": "Execute frozen baseline and validation with deadline reserve and durable attempt accounting",
      "verify": "uv run pytest -q tests/unit/test_research_execution.py --no-cov",
      "expected": "Bounded operations and honest immutable results; no inferred authority.",
      "rollback": "Revert added runtime; preserve prior immutable evidence.",
      "status": "done"
    },
    {
      "title": "Expose CLI commands and exercise retained evidence plus failure lifecycle",
      "verify": "uv run pytest -q tests/unit/test_research_execution.py --no-cov",
      "expected": "Bounded operations and honest immutable results; no inferred authority.",
      "rollback": "Revert added runtime; preserve prior immutable evidence.",
      "status": "done"
    },
    {
      "title": "Independent review and canonical aggregate verification",
      "verify": "uv run python scripts/gate.py full",
      "expected": "Bounded operations and honest immutable results; no inferred authority.",
      "rollback": "Revert added runtime; preserve prior immutable evidence.",
      "status": "done"
    }
  ],
  "tier_impact": [
    "protected"
  ],
  "docs_to_update": [
    "CLAUDE.md",
    "docs/BUILD-STATUS.md",
    "docs/operations/bounded-research-workflow.md"
  ],
  "out_of_scope": [
    "Agent-wide temporal sandbox certification",
    "Candidate search or autonomous specialist agents",
    "Owner authority, D2, promotion, paper, web or MCP changes",
    "Historical evidence modification"
  ],
  "files": [
    "apps/alpha-cli/src/alpha_cli/research_execution.py",
    "apps/alpha-cli/src/alpha_cli/research_execution_digest.py",
    "apps/alpha-cli/src/alpha_cli/research_diagnostic_cmds.py",
    "tests/unit/test_research_execution.py",
    "docs/"
  ]
}
```

DAG: CLI composition only. No statistical estimator changes. Cutoff is required for every controller operation; previously exposed external information remains outside the guarantee. One mutator in an isolated branch based on 09418e5. Baseline and validation populations are reported separately.

Acceptance is conditional on the delivered tree having a fresh canonical full-gate stamp and independent APPROVE. Do not treat this prepared delivery record as a substitute for those receipts. Scope is the fixed momentum controller; autonomous task completion, rules-based dead-end coverage and agent-wide temporal isolation remain unverified.
