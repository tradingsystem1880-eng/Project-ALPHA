# Truthful durable cancellation publication

**Delivery state:** Implementation complete. Aggregate qualification, independent review and guarded delivery are recorded separately; this document does not claim acceptance.

```json
{
  "schema_version": 1,
  "title": "Truthful durable cancellation publication",
  "context": "Keep physical cleanup distinct from authoritative cancellation publication; recover lost responses through supported bounded CLI reads without duplicate transitions.",
  "assumptions": [
    {
      "statement": "This is an engineering lifecycle correction using artificial public fixtures only.",
      "verified_by": "Inspected DurableJobLease, web pump, ControlStore atomic terminal transitions and public lifecycle tests on 30047b077ffb10223bb2ce92532f1ffe625687af."
    }
  ],
  "alternatives_considered": [
    "Retry a failed status write as failed; rejected because the first transition may have committed."
  ],
  "pre_mortem": [
    "Physical cleanup succeeds but publication fails and UI incorrectly claims cancellation.",
    "A lost terminal response causes a duplicate or conflicting transition.",
    "Readback recovery exceeds the existing CLI deadline."
  ],
  "slices": [
    {
      "title": "Separate cleanup from cancellation publication",
      "verify": "uv run python scripts/run_owned_test.py -- uv run pytest -q tests/unit/test_durable_job_lease.py",
      "expected": "Publication failure raises a lifecycle error; cleanup failure retains capacity.",
      "rollback": "Revert lease and covering test changes together.",
      "status": "done"
    },
    {
      "title": "Truthful web status and bounded authoritative readback",
      "verify": "uv run python scripts/run_owned_test.py -- uv run pytest -q tests/unit/test_web_invoke.py tests/unit/test_web_cancellation_publication.py tests/integration/test_web_api_jobs.py",
      "expected": "Lost responses reconcile without another transition; uncertain publication retains capacity and reports failure.",
      "rollback": "Revert web publication changes and their tests together.",
      "status": "done"
    }
  ],
  "tier_impact": [
    "none"
  ],
  "docs_to_update": [
    "CLAUDE.md",
    "docs/BUILD-STATUS.md",
    "docs/operations/development-loop.md"
  ],
  "out_of_scope": [
    "History reader owned by another task",
    "Schema or accounting changes",
    "Real studies, allowances and trading",
    "Private test content"
  ],
  "files": [
    "apps/alpha-cli/src/alpha_cli/durable_lease.py",
    "apps/alpha-web/src/alpha_web/_invoke.py",
    "tests/unit/test_durable_job_lease.py",
    "tests/unit/test_web_invoke.py",
    "tests/unit/test_web_cancellation_publication.py"
  ]
}
```

No engine, PIT, seed or accounting semantics change. Production web reads remain subprocess CLI calls. An uncertain terminal write is read back only within its original deadline; no terminal write is retried. Failure retains the recorded durable state for reconciliation.

Public lifecycle/API verification: 92 passed through the Linux process owner. The first updated
lease regression failed on the old cancellation flag, then passed after the correction.
The four-workstream through-delivery absence exception recorded in
`.claude/agents/independent-reviewer.md` applies to this necessary cleanup correction; only
documented private-suite absence is nonblocking. Private coverage remains UNVERIFIED.

README review: no change. Its CLI-authority, bounded job monitoring and development-gate
statements remain accurate; the detailed cancellation/publication behavior belongs in the
linked development loop. Setup, research capabilities and authority limits do not change.
