# Current native stock profile verification

**Delivery state:** Implemented – qualification pending — code only in uncommitted candidate a631e8e7; never merged or gated

```json
{
  "schema_version": 1,
  "title": "Current native stock profile verification",
  "context": "Canonical v9 W02/T10 requires identity-bound truthful evidence; rebuild the recorded invocation in a read-only snapshot and compare it with an explicitly selected current stock profile, reporting verified/mismatch/unavailable. Front block added 2026-11-13 during the plan status pass; every field restates this plan's own text. Implementation slices are marked done because the named code and tests exist in candidate a631e8e7; review slices stay pending unless the text records a review.",
  "assumptions": [
    {
      "statement": "Runtime identity is limited to the existing profile fields, not every installed package.",
      "verified_by": "Plan text."
    },
    {
      "statement": "Predecessor bac7a0d5 and every earlier export are preserved.",
      "verified_by": "Plan text."
    }
  ],
  "alternatives_considered": [
    "Inferring mode from snapshots or selecting another runtime on mismatch; rejected: explicit selectors only, mismatch never grants permission."
  ],
  "pre_mortem": [
    "Profile comparison could call command, request, spawn or admission paths; it must only reuse constructor/measurement.",
    "Missing or unstable proof could be reported as verified; it must be unavailable."
  ],
  "slices": [
    {
      "title": "Rebuild recorded invocation from contract/reservation",
      "verify": "Pinned read-only snapshot tests using _d1_native_spec and exact content identity",
      "expected": "Existing consumed stock profile required; recorded CPU/5/2/2 limits validated",
      "rollback": "Not stated in the original plan text; revert this slice's candidate changes.",
      "files": [
        "apps/alpha-cli/src/alpha_cli/native_stock_profile.py"
      ],
      "status": "done"
    },
    {
      "title": "Compare complete recorded identity with explicit selectors",
      "verify": "Pure synthetic failure tests",
      "expected": "Reports verified/mismatch/unavailable scoped to current-files-match-recorded-only",
      "rollback": "Not stated in the original plan text; revert this slice's candidate changes.",
      "files": [],
      "status": "done"
    },
    {
      "title": "Bind artifact/advisory declarations to worker manifest and review",
      "verify": "Real disposable offline native success/failure modes; independent review",
      "expected": "Exact successor/delta metadata preserved",
      "rollback": "Not stated in the original plan text; revert this slice's candidate changes.",
      "files": [],
      "status": "pending"
    }
  ],
  "tier_impact": [
    "none"
  ],
  "docs_to_update": [
    "docs/operations/native-stock-inspection.md"
  ],
  "out_of_scope": [
    "T07 continuation, spending or ownership authority.",
    "Proof of historical worker execution or durable stock receipt binding.",
    "Credentials, provider/API calls and protected test contents.",
    "Data, statistics, as-of, look-ahead or accounting changes.",
    "Broad/full or private gates, publication, transfers and installs.",
    "Shared generated outputs and shared README/CLAUDE documentation."
  ]
}
```

Canonical v9 W02/T10 (Library libfile_181ac6079dcc8191b222b76c1f10bf17) requires
identity-bound truthful evidence. Preserve bac7a0d5b62d3d6ed3f33a45e30d35b037d7f0ee
and every earlier export. No T07 continuation, spending or ownership authority.

1. Rebuild the recorded invocation from its existing contract/reservation in a pinned
   read-only snapshot, using _d1_native_spec and exact content identity. Require the
   existing consumed stock profile and validate separate recorded CPU/5/2/2 limits.
2. With explicit public source/runtime/mode selectors only, reuse StockFixtureLaunch
   constructor/measurement and compare complete recorded identity. Never call command,
   request, spawn, admission or authority. Report verified/mismatch/unavailable and
   scope current-files-match-recorded-only. Missing or unstable proof is unavailable.
3. Bind current artifact/advisory request declarations separately to selected worker
   manifest, explicit mode and recorded CPU limits. Do not infer mode from snapshots.
   Test pure synthetic failures and real disposable offline native success/failure modes;
   independently review and preserve exact successor/delta metadata.

Runtime identity is limited to the existing profile fields, not every installed package.
No historical worker execution or durable stock receipt binding is proven. The latter
remains absent from existing outcome records. Source pin/profile mismatch never grants
permission or selects another runtime. No credentials, provider/API calls, installation,
protected test contents, broad/private gate, shared generated edits, transfers/publication.
DAG unchanged; no data, statistics, as-of, look-ahead or accounting changes. README/CLAUDE
no_change: owned operator guide documents this unqualified diagnostic; shared docs are
outside scope. Native qualification remains incomplete. Claude unavailable via existing
catalog/command; use honest independent Codex review without setup changes.
