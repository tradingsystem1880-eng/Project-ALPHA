**Delivery state:** Implemented – qualification pending — code only in uncommitted candidate a631e8e7; never merged or gated

```json
{
  "schema_version": 1,
  "title": "Correct stale-selector error coverage without changing product behavior",
  "context": "The original two stale-error absence locators omit the Error and API status prefix. Preserve frozen tree 5311a3cee3115e9bfbbbf93f389c81dee8ba40cf and its six-case evidence; create a separate test-only successor with a real stale-handler barrier, controlled poll holds, and an explicit seventh current-error positive control.",
  "assumptions": [
    {
      "statement": "The exact original show promise is native and the exercised poll continuations are terminal without another await.",
      "verified_by": "Source inspection of investigations.request and RunInvestigation.poll with original fixture closures; independent Revision 2 design review. Applied source review and runtime controls remain required."
    },
    {
      "statement": "Newly successful polls can erase a stale error, including parent replacement and repeated created-record polls.",
      "verified_by": "RunInvestigation setPollError(null), pollRevision and jobId effect dependencies; persistent per-ID holds keep those replies pending through the error assertions."
    }
  ],
  "alternatives_considered": [
    "Correcting text alone leaves settlement and successful-poll masking gaps.",
    "Awaiting creation first was rejected because it forces the second epoch advance before stale release; retain the original two scheduling ticks without treating them as settlement proof.",
    "Capture the same show promise and attach its observer only at later controlled release; no production hook, generic observer, extra sleep, timeout increase, or replacement fixture."
  ],
  "pre_mortem": [
    "Attaching an observer before returning show would run ahead of the component await; capture only and return the exact native promise.",
    "A one-shot created-poll hold can miss a jobId-triggered restart; hold every future current-ID show through the assertion.",
    "A mutation timeout or unrelated failure is not proof of assertion sensitivity; retain exact failure evidence and do not count it as a kill."
  ],
  "slices": [
    {
      "title": "Strengthen the existing selector fixture and error assertions",
      "verify": "Scoped installed oxlint, explicit no-emit TypeScript for both spec and TSX harness, syntax/AST inventory, and only the existing FeaturePlan validator. No browser execution in cloud.",
      "expected": "Original six cases retained, seventh current-error case explicit; correct full error text; same-promise late observer; original creation scheduling preserved.",
      "rollback": "Discard this separate successor; never overwrite frozen 5311 or old evidence.",
      "files": [
        "apps/alpha-web/frontend/e2e/fixtures/run-investigation-race-harness.tsx",
        "apps/alpha-web/frontend/e2e/investigations-selector-epoch.spec.ts"
      ],
      "status": "done"
    },
    {
      "title": "Freeze identities and review before controlled runtime validation",
      "verify": "Preserve all predecessor allowed source, evidence and index bytes; verify exactly two test files plus this plan differ and all 149 omitted references remain absent; independent frozen-source review before Dell delivery.",
      "expected": "Exact manifest/tree/patch/check bindings and compact private addendum. Future guarded seven-pass and separate two-error negative control remain unrun until authorized execution.",
      "rollback": "Retain failed receipts and discard only the new successor/transfer; preserve prior source and evidence.",
      "files": [
        "docs/work/2026-11-09-selector-error-test-correction/02-plan.md"
      ],
      "status": "pending"
    }
  ],
  "tier_impact": [
    "none"
  ],
  "docs_to_update": [
    "docs/work/2026-11-09-selector-error-test-correction/02-plan.md"
  ],
  "out_of_scope": [
    "Production/API/config/driver/manual/README changes, weakened assertions, increased timing, new fixtures/frameworks, or a claim of general transient/same-ID/unmount proof",
    "Full/default/native gates, Atlas/preflight, protected/historical bodies, owner data, installs, network/code fetch, model/provider calls, commits/publication/history repair",
    "Any catch-guard mutation in this candidate; a later authorized negative control may change only that catch in a clearly labeled disposable copy"
  ],
  "files": [
    "apps/alpha-web/frontend/e2e/fixtures/run-investigation-race-harness.tsx",
    "apps/alpha-web/frontend/e2e/investigations-selector-epoch.spec.ts",
    "docs/work/2026-11-09-selector-error-test-correction/02-plan.md"
  ]
}
```

**Delivery state:** Test-only implementation and scoped lint/type/syntax checks completed. Applied-source review, corrected browser execution and negative-control validation remain pending; no runtime result is claimed.

## Source and schedule

This plan is dated from the actual UTC execution date, 2026-11-09. The surrounding
handoff directories retain their existing 20261110 labels. The base is the frozen,
intentionally incomplete 5311 tree, not a repaired repository or new commit.
The scope is two existing public test files plus this required plan. All product,
API, config, fixture-driver, manual and README bytes remain unchanged.

The original error becomes `Error: Investigation request failed (503): stale parent
poll failure`, inside the existing status banner. The test-only wrapper records
and returns the exact show promise without registering a reaction. Later release
attaches an observer after the component's await. Native FIFO promise reactions
and this fixture's terminal continuation establish handler completion; awaited
React act flushes resulting updates. This is not a generic asynchronous UI barrier.
The original two ticks between releasing create and releasing stale remain only
as the original scheduling sequence, never as completion evidence.

Only the error cases persistently hold future current-ID polls: child for selection,
and parent plus created for new-case creation. This covers replacement/restarted
polls so a successful response cannot clear a wrongly accepted stale error before
the assertion. A pending current request and the existing ready status are asserted;
that status comes from the saved/created object, not a held reply. Isolated page
teardown disposes the remaining promises and test-only singleton wrapper.

## Validation boundaries

Scoped lint/type/syntax and schema checks use existing installed tools without npm,
installation, network calls or dependency copies. The normal e2e TS configuration
excludes the TSX harness, so a separate temporary config outside source explicitly
includes both changed test files and enables JSX. These checks are not browser proof.

After independent source review, use the original focused config and process owner
on the authorized installed Dell environment, retaining settings and explicit
`--project chromium-reference-only --no-deps`. Fresh native listing and execution
must identify all seven cases, each passing once. Source project dependencies stay
unchanged. Disable npm's update notifier through its verified per-command control;
no network-isolation claim is inferred from offline settings.

A separately labeled disposable negative-control copy may bypass only the poll
catch guard, leaving this candidate frozen. Exactly the two stale-error cases must
fail on the corrected absence assertion. Timeouts/unrelated failures are not kills.
The seventh positive case must show the current error on guarded product source.
All runtime controls, full/default/native gates and aggregate acceptance remain
unrun here. Prior six-case passes retain their original qualified scope.

No transient-free success, old-A-versus-new-A epoch, or attempted-update-after-unmount
proof is claimed. DAG, look-ahead/point-in-time, numerical determinism, research
admission and execution authority are unchanged. Generic Claude advice supplied
criteria only, not exact-source review or runtime verification.

## Documentation decision

The mandatory multi-file FeaturePlan is the sole documentation addition. README,
CLAUDE and BUILD-STATUS changes are not needed for this bounded test correction:
product behavior, setup, aggregate acceptance and user capabilities are unchanged.
This plan and external immutable evidence carry the corrected coverage and limits.
