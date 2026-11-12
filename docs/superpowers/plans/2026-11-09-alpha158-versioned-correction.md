# Explicit partial Alpha158 correction

**Delivery state:** Implemented – qualification pending — code only in uncommitted candidate a631e8e7; never merged or gated

**Historical delivery state (as first recorded):** Local candidate; focused verification passed, final frozen-tree review pending. Full gate and native
whole-recipe equivalence remain unverified.

The preserved feature version 1 is an Alpha158-style recipe, not verified numerical Qlib
parity. A provider-free diagnostic on two original fabricated 65-row panels measured differences
in eight window-5 features. This change offers an explicit version 2 correction for those eight
families at windows 5, 10, 20, 30 and 60. It does not label 40 columns as full 158-feature parity.

```json
{
  "schema_version": 1,
  "title": "Explicit partial Alpha158 correction",
  "context": "Reuse pinned Qlib 0.9.7 operators for 40 measured-family columns while preserving historical version 1 and all defaults.",
  "assumptions": [
    {"statement": "Request envelope versions select model families independently of feature recipe versions.", "verified_by": "CLI and worker validators and three request descriptors."},
    {"statement": "Canonical input has OHLCV but no vendor VWAP or pre-panel history.", "verified_by": "Canonical panel schema and existing typical-price provenance."}
  ],
  "alternatives_considered": [
    "Do not silently repair version 1 or relabel old results.",
    "Do not build a general expression parser/provider or claim a full native handler replacement.",
    "Use actual Qlib operators with one content-keyed in-memory Expression leaf."
  ],
  "pre_mortem": [
    "Identical feature names can hide changed numbers or warm-up masks; test masks separately from finite values.",
    "A cache keyed only by instrument can reuse another panel; include version, exact values and timestamps.",
    "Defaulted producer fields can silently change historical digests; compare original builder bytes.",
    "New code fingerprints must not be mistaken for a recipe-1 semantic migration."
  ],
  "slices": [
    {"title": "Provider-free numerical correction", "verify": "workers/qlib/tests/test_feature_recipes.py", "expected": "40 columns match pinned conventions and hand-checkable anchors; 118 inherited columns and v1 remain exact", "rollback": "Remove opt-in modules only; preserve v1 and artifacts", "status": "done"},
    {"title": "Explicit contracts and immutable lineage", "verify": "workers/qlib/tests/test_feature_recipe_contract.py and tests/unit/test_feature_recipe_versions.py", "expected": "Explicit v2 accepted, defaults unchanged, unsupported identities and lineage reuse rejected", "rollback": "Revert additive reader support; old readers reject v2", "status": "done"},
    {"title": "Provenance, generated projections and review", "verify": "Focused web/refit checks, API generation, lint/types and independent source review", "expected": "Honest partial scope, no native parity claim, source and upstream bindings", "rollback": "Retain unqualified candidate and failed evidence; no publication", "status": "pending"}
  ],
  "dag_impact": "No new cross-package engine dependency. Qlib remains isolated and lazily imported only for feature v2.",
  "lookahead_impact": "Only trailing rows in immutable input; prefix and future-poison checks without protected test access.",
  "determinism_impact": "Exact versioned request/config identity, content-addressed operator cache and pinned numerical sources."
}
```

## Contract and compatibility

- Opt in with `stage_config.ml.feature_recipe_version: 2`, or an explicit exchange feature
  recipe `{"name":"alpha158","version":2,"parameters":{}}`. Absent selection remains 1;
  the producer does not insert a default field into the experiment. Request envelopes 1/2/3
  and result shapes remain unchanged. Unknown/noninteger feature versions fail.
- Old CLI/worker readers and descriptors reject version 2, rather than silently using 1.
  Worker rejection happens before optional Qlib initialization or model execution, though
  canonical panel validation and ordinary module imports happen earlier.
- `config_hash` already covers the complete feature recipe; prediction readers require that
  hash. Use the request/config identity and worker lock alongside the model hash. A model
  hash by itself is not a complete feature-compatibility key. Existing model-only comparison
  rejects differing feature recipes. There is no new persisted-model loader or cache migration.
- Genuine new implementation fingerprints change, including for version-1 jobs whose protocol
  covers worker source. Frozen refit protocols must match their original code; this candidate
  does not reinterpret or rewrite them. The new modules join current fingerprint inventories. The refit reader also recognizes complete
  predecessor seven-file inventories for feature v1; partial inventories and feature v2 with
  legacy code are rejected.
  V1 tear-sheet API projections omit the new correction field when absent. Capability/v2
  projection changes require a coordinated worker/web upgrade, not an unsupported mixed-service
  compatibility claim. Numeric v1 behavior, default request bytes and config digests remain unchanged. No historical
  artifact is modified, recomputed or relabeled.
- V2 uses native `Mean`, `Std`, `Rank`, `IdxMax`, `IdxMin`, `Ref`, `Abs` and arithmetic for
  MA/STD/VSTD/RANK/IMAX/IMIN/IMXD/WVMA. Qlib sample deviations, average tied ranks,
  one-based earliest extrema and fractional price-change weighting are retained. Corrected
  columns use upstream partial-window behavior; remaining columns retain v1 warm-up. Undefined
  NaNs are kept, and infinities are converted to NaN as in the existing worker.
- Remaining 118 columns are inherited, including `VWAP0`'s causal typical-price proxy. Neither
  provider/calendar/corporate-action or full-handler equivalence nor vendor VWAP is established.
  Existing input alignment is unchanged; comparisons use the same supplied row-indexed series. Diagnostics enumerate
  corrected/inherited columns, warm-up/input limits, source hashes and pinned upstream versions.
  The existing UI name shows the 40/118 split; full metadata remains in the typed API/result.

## Verification boundary

Only synthetic operator computations, request/result transport, source hashing and read-only
engineering protocol checks are in scope. No real fitting/inference, provider initialization,
market acquisition, broker operation, owner store or GPU work is authorized. Full gate, Atlas,
protected test suites, deployment and scientific acceptance are not claimed. No commit or fetch.
