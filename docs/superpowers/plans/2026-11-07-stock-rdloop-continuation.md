# Stock RDLoop synthetic continuation

**Delivery state:** Implementation and focused review complete; full qualification blocked, no activation.

```json
{
  "title": "Stock RDLoop synthetic continuation",
  "context": "Replace import-only stock-loop evidence with actual upstream RDLoop execution and bounded diagnostic trace validation; no production activation.",
  "assumptions": [
    {
      "statement": "Pinned native source is 484776c211e4fbbeef03e0ec00d6bbee7362a4f4; existing installed runtime used without setup.",
      "verified_by": "source_pin.py and isolated process checks"
    }
  ],
  "alternatives_considered": [
    "Extend custom NativeFixtureLoop: rejected because it does not execute stock RDLoop.",
    "Activate live subscription loop: blocked official CLI initialization and outside scope."
  ],
  "pre_mortem": [
    "Checkpoint restoration could replenish effect allowances: keep counters outside pickle and bind checkpoint bytes/request.",
    "Stock defaults could touch provider/data/container resources: fixed synthetic components, sterile environment and audit tripwires."
  ],
  "slices": [
    {
      "title": "Typed fixture request and diagnostic receipt bounds",
      "verify": "focused test_native_stock_fixture.py",
      "expected": "invalid or under-reserved requests and altered artifacts fail closed",
      "rollback": "remove additive fixture module/tests"
    },
    {
      "title": "Native RDLoop continuation with deterministic components",
      "verify": "same focused suite with explicit pinned native runtime/source",
      "expected": "native five-stage trace, original checkpoint retained, no repeated proposal/coding, no external calls",
      "rollback": "remove stock fixture worker entry/components"
    },
    {
      "title": "Documentation and independent review",
      "verify": "focused checks, Ruff and independent review",
      "expected": "synthetic-only evidence with remaining production gates explicit",
      "rollback": "retain candidate unactivated"
    }
  ],
  "tier_impact": [
    "risk",
    "dag",
    "determinism"
  ],
  "docs_to_update": [
    "CLAUDE.md",
    "docs/BUILD-STATUS.md",
    "workers/rdagent/README.md"
  ],
  "out_of_scope": [
    "live model calls/authentication",
    "scientific admission",
    "production dispatch registration",
    "owner data or protected inputs",
    "publication or merge",
    "cross-owner recovery or quota/dollar cap"
  ],
  "files": [
    "apps/alpha-cli/src/alpha_cli/native_stock_fixture.py",
    "workers/rdagent/stock_fixture.py",
    "workers/rdagent/stock_fixture_entry.py",
    "tests/unit/test_native_stock_fixture.py"
  ]
}
```

No data, strategy or statistical operator changes; no look-ahead impact. Worker stays subprocess-isolated. Semantic fixture output is deterministic; native logs/checkpoints include time-dependent bytes. Protected Atlas/full-gate access remains blocked and will not be retried. Root README will be reviewed against this additive, unactivated worker slice.

README review: `no_change` for root README. This is an additive, unactivated worker diagnostic; no application command, setup, scientific capability or deployment behavior changes. The worker README documents the new explicit path and limitations.

Admission scope: existing owner and reservation are read/validated, not consumed or settled. The existing closed NativeLaunch dispatcher is intentionally unchanged. Durable cross-process invocation consumption, live process ownership and scientific admission remain production dependencies; the fixture does not claim these solved.

Focused verification: explicit isolated native asset check produced `5 passed, 9 subtests passed` (28.61 seconds); actual RDLoop resume/cancel/exhaust/tamper modes and malformed/oversized binding rejection executed. Ruff passed for all four changed Python files; focused strict mypy passed for the ALPHA module; all 13 import contracts kept. Independent Codex source review APPROVE, including final test additions. Claude was unavailable through an authorized route. Exact receipts and hashes accompany the local handoff; no full/project qualification or merge is claimed.
