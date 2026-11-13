# Native stock worker boundary hardening

**Delivery state:** Implemented – qualification pending — code only in uncommitted candidate a631e8e7; never merged or gated

**Historical delivery state (as first recorded):** Scoped candidate; exact final source/runtime qualification is recorded in receipts.

```json
{
  "schema_version": 1,
  "title": "Harden the pinned native stock worker boundaries",
  "context": "Preserve910ee456; diagnose controller-only58 versus configurednative51diagnostics, correct actual typed/None/audit/protocol boundaries without rewriting upstream or canonical gates.",
  "assumptions": [
    {
      "statement": "Stock profile uses existing installed Python3.11.17 and exact pinned RD-Agent source",
      "verified_by": "Existing runtime receipts, source digest and configured mypy/native fixture preflight"
    },
    {
      "statement": "Local worker remains hash-bound as the same three-file manifest",
      "verified_by": "Derived old/current worker map and rejection of old910manifest before upstream import"
    }
  ],
  "alternatives_considered": [
    "Use actual pinned interfaces and runtime paths, not fake stubs, ignores, upstream edits, lock changes or a replacement loop."
  ],
  "pre_mortem": [
    "A missing ContextVar or recovered optional shape can fail opaquely; validate before effects/receipt publication.",
    "Metadata argv can disguise another executable and byte paths can bypass name checks; bind exact pairs and normalize byte/text paths without executing probes.",
    "Worker byte changes invalidate old profiles; derive new identity and preserve mismatch rejection rather than rewriting history."
  ],
  "slices": [
    {
      "title": "Diagnose configured interfaces and preserve baseline evidence",
      "verify": "Compare original58, configured51, pinned source callback declarations",
      "expected": "Unsupported exploratory assumptions separated from actual gaps",
      "rollback": "Retain910source/exports and beforecheck receipts",
      "status": "done"
    },
    {
      "title": "Implement typed boundaries and synthetic negative checks",
      "verify": "Two-file configured strict check, pure audit comparison and focused realnative checks",
      "expected": "No ignores, no upstream edits, no effects without context or malformed results",
      "rollback": "Keep old candidate; no stored profile/history mutation",
      "status": "done"
    },
    {
      "title": "Freeze current worker identity and run cumulative lifecycle",
      "verify": "Explicit10file owned regression, currentownerresult/API/builtbrowser and independent review",
      "expected": "Exact currentworker profile and source receipts; full/private qualification remains excluded",
      "rollback": "Preserve failures and old source; do not activate inference/publication",
      "status": "in_progress"
    }
  ],
  "tier_impact": [
    "none"
  ],
  "docs_to_update": [
    "docs/operations/native-worker-hardening.md",
    "workers/rdagent/README.md"
  ],
  "out_of_scope": [
    "Live inference/modelcalls/accounting changes",
    "Upstream/lock/gate target changes",
    "Acquisition/paper/science implementation",
    "Protected/private/full gates",
    "Installs/transfers/publication"
  ],
  "files": [
    "workers/rdagent/stock_fixture.py",
    "workers/rdagent/stock_fixture_entry.py",
    "workers/rdagent/README.md",
    "tests/unit/test_native_stock_fixture.py",
    "tests/unit/test_native_stock_worker_contract.py",
    "docs/operations/native-worker-hardening.md",
    "docs/operations/native-cumulative-regression.md"
  ]
}
```

Changes are restricted to hash-bound worker source, public synthetic tests and owned docs.
No admission, budget policy, source pin, canonical gate or upstream lifecycle replacement.
