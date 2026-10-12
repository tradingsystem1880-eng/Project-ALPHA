# Wheel zoom and chart resize ordering

**Delivery state:** Preparation; complete fixed browser and combined target acceptance pending.

```json
{
  "schema_version": 1,
  "title": "Preserve wheel zoom across pending chart resize restoration",
  "context": "Harness final full on bf0fd3bb failed one-wheel quant workspace assertion. Retained trace has live canvas and chart height 538\u2192504. Actual controlled resize/wheel test proves old queued restoration erases wheel at next draw; no listener-late claim or timeout weakening.",
  "assumptions": [
    {
      "statement": "Restoration must finish before a later native gesture",
      "verified_by": "Baseline controlled draw-completion regression fails with span 499 in all three viewports; two-call ordering fix passes all 18 focused browser cases"
    }
  ],
  "alternatives_considered": [
    "Extra wheel gestures/retries/sleeps rejected",
    "Delayed native wheel listener rejected:5.2.0 constructor attaches synchronously",
    "No-op height-only resize rejected because width changes need same ordering contract"
  ],
  "pre_mortem": [
    "Transient contraction fools poll before pending draw: new control waits for released draw completion",
    "Render artifact or source candidate diverges from final combined harness target: regenerate/review/full/CI on exact final tree"
  ],
  "slices": [
    {
      "title": "Prove actual resize/native wheel ordering with deterministic negative control",
      "verify": "New actual-component browser test controls resize/draw ordering with one trusted wheel and asserts settled contracted span",
      "expected": "Old source fails after draw; original gestures/assertions unchanged",
      "rollback": "Retain diagnostic receipts outside repo and remove owned diagnostic code",
      "status": "done"
    },
    {
      "title": "Complete queued restoration during synchronous resize paint",
      "verify": "npm run build;18 focused browser cases;frontend coverage/lint/types",
      "expected": "Single wheel survives; ordinary range/lifetime cases pass",
      "rollback": "Revert only PriceChartCanvas call ordering and new regression",
      "status": "done"
    },
    {
      "title": "Verify full browser interaction and accepted combined target",
      "verify": "Complete 311-case browser suite, independent review, then mutation owner final combined canonical full/current hosted/postmerge CI",
      "expected": "No isolated-pass success claim; exact final accepted tree required",
      "rollback": "Recover binary/source patch; preserve frozen harness and extreme-tick preparations",
      "status": "in_progress"
    }
  ],
  "tier_impact": [
    "none"
  ],
  "docs_to_update": [
    "docs/BUILD-STATUS.md"
  ],
  "out_of_scope": [
    "Extra gestures, retries, timeouts or assertion weakening",
    "Extreme-tick candidate",
    "Private source/execution",
    "Mutation floors, exclusions, inventories or exhaustive sweep",
    "Frozen Git fixture repair source",
    "Unverified canonical or hosted acceptance claims"
  ]
}
```

This is an imperative frontend ordering correction, with no DAG, statistical, trading, seed, data or owner-authority change. Restore the captured range before `chart.resize(width, height, true)` so its pending invalidation is painted in the same operation and cannot erase a subsequent wheel. The new actual-component test owns frame ordering and confirms one trusted wheel plus settled span contraction. Historical full-suite failure and diagnostic passes remain retained. Normal review/full/CI apply; actual paths do not trigger specialised private-suite exception.
