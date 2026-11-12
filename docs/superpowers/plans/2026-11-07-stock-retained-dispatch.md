# Retained stock RDLoop dispatch

**Delivery state:** Implemented and focused-tested; full qualification/activation remain blocked.

```json
{
  "title": "Retained stock RDLoop dispatch and invocation consumption",
  "context": "Successor to reviewed403da80e: reuse exact retained NativeLaunch owner path and existing job_events for one consumption before Popen; preserve full reservation and no scientific authority.",
  "assumptions": [
    {
      "statement": "Pinned native source is 484776c211e4fbbeef03e0ec00d6bbee7362a4f4; existing installed runtime used without setup.",
      "verified_by": "source_pin.py and isolated process checks"
    }
  ],
  "alternatives_considered": [
    "Use the existing model allowance unchanged: rejected because it has a different closed scope and unstarted-success owner, not stock dispatch.",
    "Use only native_claim as invocation audit: it prevents relaunch but does not distinguish reservation/owner acquisition from attempted payload dispatch.",
    "Create another ledger/owner: rejected; extend existing journal and sealed launch registry."
  ],
  "pre_mortem": [
    "Checkpoint restoration could replenish effect allowances: keep counters outside pickle and bind checkpoint bytes/request.",
    "Stock defaults could touch provider/data/container resources: fixed synthetic components, sterile environment and audit tripwires."
  ],
  "slices": [
    {
      "title": "Closed stock launch/runtime identity and consumption",
      "verify": "focused test_native_stock_dispatch.py",
      "expected": "atomic no-remint commit before spawn, rollback prevents spawn",
      "rollback": "preserve predecessor403da80e; remove additive stock dispatch hooks"
    },
    {
      "title": "Existing owner end-to-end dispatch and failures",
      "verify": "same public suite plus native fixture regression",
      "expected": "retained child cleanup, sequence claim/consume/start/outcome, exact unchanged reservation",
      "rollback": "keep dispatcher unactivated"
    },
    {
      "title": "Independent review/docs and focused checks",
      "verify": "Ruff/mypy/import contracts + independent review",
      "expected": "reviewable synthetic-only candidate; full qualification explicitly blocked",
      "rollback": "retain candidate unmerged"
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
    "apps/alpha-cli/src/alpha_cli/_native_stock_launch.py",
    "apps/alpha-cli/src/alpha_cli/_native_fixture_store.py",
    "apps/alpha-cli/src/alpha_cli/native_supervisor.py",
    "workers/rdagent/stock_fixture_entry.py",
    "tests/unit/test_native_stock_dispatch.py"
  ]
}
```

This is a separate successor; predecessor candidate403da80e and older accounting candidate27593266 remain untouched. Full/protected Atlas processing remains blocked and will not be retried. No live inference, credentials, owner data or installations. New event lives only in canonical job_events, not a balance/usage ledger; full existing reservation remains charged. Runtime selector fingerprints existing interpreter/config/lock bytes but does not qualify installed dependencies or enforce CPU/USD/token limits. No data/statistical changes; DAG remains worker isolated.

Verification: public focused suites plus three legacy exact-type/fabricated-owner regressions passed 16 tests and 9 subtests (41.20 seconds). The explicit legacy/null-profile regression was observed failing before its fix. Post-insertion rollback, process creation failure, cancellation after commit, races/reopen/no-remint and receipt replacement are covered. Strict mypy passes all three touched control modules; final Ruff/import logs accompany the handoff. No full gate or protected input processing was attempted.

README review: no_change for root README; this adds only closed internal synthetic dispatch, no public research command, installation workflow, production activation or empirical capability. Worker README describes the exact additional type and limits.
