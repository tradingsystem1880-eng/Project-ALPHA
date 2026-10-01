# Immutable rules in bounded research execution

**Delivery state:** Implementation delivered; acceptance tracked by exact-tree receipts

```json
{
  "schema_version": 1,
  "title": "Immutable rules in bounded research execution",
  "context": "Close the measured rules-based workflow gap without adding agent transport or changing strategy mathematics.",
  "assumptions": [
    {
      "statement": "Saved rule names are mutable; exact canonical rule bytes must define both operations.",
      "verified_by": "rules_cmds resolver and existing RunSpec identity inspection."
    }
  ],
  "alternatives_considered": [
    "Unbounded specialist swarm deferred until controller improves measured completion.",
    "Temporal filesystem isolation remains separate work; as_of alone is not such isolation."
  ],
  "pre_mortem": [
    "Rule file changes between stages; each child verifies frozen canonical hash before execution.",
    "Returned run uses another rule; collector checks exact canonical specification."
  ],
  "slices": [
    {
      "title": "Hash-bound file resolver and public CLI options",
      "verify": "uv run pytest -q tests/unit/test_research_execution.py tests/integration/test_cli_rules.py --no-cov",
      "expected": "Bounded operations and honest immutable results; no inferred authority.",
      "rollback": "Revert added runtime; preserve prior immutable evidence.",
      "status": "done"
    },
    {
      "title": "Canonical embedded rule plan and immutable dispatch",
      "verify": "uv run pytest -q tests/unit/test_research_execution.py tests/integration/test_cli_rules.py --no-cov",
      "expected": "Bounded operations and honest immutable results; no inferred authority.",
      "rollback": "Revert added runtime; preserve prior immutable evidence.",
      "status": "done"
    },
    {
      "title": "Tamper, replay and retained rules operator smoke",
      "verify": "uv run pytest -q tests/unit/test_research_execution.py tests/integration/test_cli_rules.py --no-cov",
      "expected": "Bounded operations and honest immutable results; no inferred authority.",
      "rollback": "Revert added runtime; preserve prior immutable evidence.",
      "status": "done"
    },
    {
      "title": "Independent review and canonical verification",
      "verify": "uv run python scripts/gate.py full",
      "expected": "Bounded operations and honest immutable results; no inferred authority.",
      "rollback": "Revert added runtime; preserve prior immutable evidence.",
      "status": "pending"
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
    "apps/alpha-cli/src/alpha_cli/rules_cmds.py",
    "apps/alpha-cli/src/alpha_cli/backtest_cmds.py",
    "apps/alpha-cli/src/alpha_cli/validate_cmds.py",
    "apps/alpha-cli/src/alpha_cli/research_execution.py",
    "tests/integration/test_cli_rules.py",
    "tests/unit/test_research_execution.py",
    "apps/alpha-cli/src/alpha_cli/info_cmds.py"
  ]
}
```

DAG: CLI reuses the existing strategies parser; no new package edge. Look-ahead: existing snapshot/as_of unchanged; no agent-wide information-isolation claim. Determinism: canonical rule bytes enter plan and existing run identity. No statistical or strategy formula changes.

The final verification slice is intentionally receipt-driven: consult the matching full-gate and independent-review receipts, not this pre-verification plan, for acceptance. Combined UI/main integration is separate.
