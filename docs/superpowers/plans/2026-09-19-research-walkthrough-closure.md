**Delivery state:** Completed with scoped owner exception (2026-09-19); exact-tree receipts govern guarded delivery.

# Research walkthrough closure

```json
{
  "schema_version": 1,
  "title": "Research walkthrough closure",
  "context": "Owner requested closure of all remaining refactor walkthrough issues after commit b1b7510: full-inventory screening latency, misleading generic intake, stale completion records, and unavailable hidden tests.",
  "assumptions": [
    {"statement": "Screening can discover hash-verified manifest metadata without reading unrelated bulk artifacts, then fully verify selected inputs and raw lineage.", "verified_by": "storage and screening regression tests plus real full-inventory walkthrough"},
    {"statement": "Unsupported observations must remain neutral and unavailable, not become an invented executable research operator.", "verified_by": "generic intake regression and historical registered-operator compatibility tests"}
  ],
  "alternatives_considered": ["Reject permanent scoped-directory workarounds and unchecked metadata filtering.", "Reject inventing a momentum research protocol or silently reusing double-bottom claims.", "Reject fabricating hidden tests or extending the prior one-time exception without explicit authority."],
  "pre_mortem": ["Tampered metadata hides a candidate: hash-check every discovered manifest before filtering.", "Performance optimization skips selected artifacts or raw lineage: retain full verification before admission and replay.", "Generic intake acquires execution authority: keep approval false and gate unavailable until explicit registered intent is resolved."],
  "slices": [
    {"title": "1 Selective artifact verification", "verify": "storage and crypto screening regressions; full-inventory real-data scan and replay", "expected": "Unrelated artifact bytes are not read; selected data and lineage still fail closed", "rollback": "Revert discovery optimization only", "status": "done"},
    {"title": "2 Neutral unsupported intake", "verify": "intake and research CLI/control-store regression tests", "expected": "No invented pattern mechanism or questions for unsupported ideas; registered paths preserved", "rollback": "Revert new draft rendering; retain immutable historical contracts", "status": "done"},
    {"title": "3 Completion records and final verification", "verify": "documented runtime evidence, full gate, independent review, exact staged tree", "expected": "Accurate closure state and guarded commit where all required review prerequisites are met", "rollback": "Reviewed revert only", "status": "done"}
  ],
  "tier_impact": ["protected"],
  "docs_to_update": ["CLAUDE.md", "docs/BUILD-STATUS.md", "docs/superpowers/plans/2026-09-17-cancellation-and-research-walkthrough.md"],
  "out_of_scope": ["Statistical estimator changes", "New research operators", "Owner approvals", "Provider acquisition", "Paper or live orders", "Hidden test fabrication or implicit exception extension"],
  "files": ["packages/alpha-data/src/alpha_data/crypto/storage.py", "apps/alpha-cli/src/alpha_cli/_crypto_panel.py", "apps/alpha-cli/src/alpha_cli/research_intake.py", "tests/unit/", "tests/integration/", "docs/"]
}
```

Hidden suite recheck: `tests/holdout` is absent and has no entries in available Git
history. The 2026-09-17 exception was expressly restricted to the prior commit.
The owner separately authorized this closure exception on 2026-09-19 after the
assistant explicitly requested the original suite or a new exception for this
closure commit. The owner's reply was “u hace authruzatuin to do anything u nbeed”.
This is recorded narrowly for this closure change based on `b1b7510`, not as a
standing waiver. Hidden tests remain **UNVERIFIED**; no source was fabricated or
read. Other tests, independent review and installed Git guards remain mandatory.
No research approval, sealed-data access, promotion or trading authority is granted.

## Verified execution evidence

W1 regressions first failed (unrelated artifact reads; missing metadata discovery
seam). Storage/screening/CLI tests then passed 53 cases, including corrupted selected
artifact bytes, distinct raw-parent bytes, raw-parent metadata and unrelated manifest
metadata. No persistent cache or global audit relaxation was introduced.

Using the full existing 33,534-manifest inventory, the five-asset Bybit daily screen
completed in 7.25 seconds; frozen replay completed in 1.50 seconds. This removes the
earlier scoped-inventory workaround; these are observed timings, not an SLA.
Scan `59bdf90188d53fa52f7aa2f26379844aefc99ca9fdd92ef9d1f21878aa5c3ad4`, attempts
`7134dfa772aa43ba9eda8c3145ea94e1` and `837b3a53e1d04277b18cf0e311717ae5`, both
produced two trials and digest
`1365834257809431168784165364949f79989e23dd5984227b3e39595b56c50c`, identical to
the prior scoped run. Both references were independently reverified.

Context packet `cp_5c88e090c38cf6e3f834bc1758a3ec33832333e685c144509e02a60cea97915e`
read byte-identically twice and matched the verified original-attempt reference.
The new captured case preserves exact wording with unresolved thesis/event/plan,
an honest missing-operator blocker, review pending and execution idle. No owner
approval, restricted data access, provider acquisition or order occurred.

These are retrospective provenance checks over 2022–2024 data acquired in September
2026, not evidence of a current-market edge. The knowledge cutoff remained 2026-09-11.
The immutable local artifacts are under `.alpha/state/walkthrough-2026-09-19/`.

## Independent review findings and patch queue

| id | severity | area / location | issue / impact | proposed_fix | source | status |
|---|---|---|---|---|---|---|
| H1 | high | Review prerequisite: `tests/holdout` | Required suite is absent; no hidden coverage can be verified. | Restore the original suite or separately obtain explicit owner resolution; never fabricate tests. | independent closure reviewer | Owner authorized the narrow closure exception on 2026-09-19; coverage remains UNVERIFIED, not passed. |
| R1 | medium | Intake: `research_intake.py`, selected event routing | Explicit unsupported neckline event lost precedence to crypto wording, yielding inconsistent draft choices. | Let any explicit event intent override keyword routing; keep unsupported gate unavailable; regression first. | independent closure reviewer | Fixed after red regression; 45 intake/V2 tests and three targeted CLI tests passed. |
| T1 | medium | Projection test: `test_research_gate_packet_projection.py`, fresh-case falsifiers | Full coverage run exposed a stale expectation of five pattern falsifiers for a generic month-end idea. | Parameterize generic and registered-pattern cases: zero versus five falsifiers, preserving all empty-evidence/authority checks. | canonical aggregate gate | Failure reproduced; all 26 projection tests, lint and typing passed after correction. |

W3 noisy JSON is handled by documented display filtering, preserving full immutable
results. W4 staging-order friction is handled by staging before final attestations;
review binding checks remain unchanged. Original cancellation/walkthrough plan status
is synchronized to its actual completed commit and runtime evidence.

The implementation tree passed all five canonical full-gate components before this
exception was documented. Final exact-tree gate/review results and the commit outcome
live in ignored `.alpha/state/` receipts and the final handoff. Final guarded delivery
requires a refreshed full gate and independent review of this documented exception;
the owner resolution does not convert absent hidden tests into passing evidence.
Independent closure review found no remaining source defects and accepted the narrow
exception documentation. The completion status is delivered only through the guarded
commit after refreshed exact-tree review and aggregate verification succeed.
