```json
{
  "schema_version": 1,
  "title": "Strict risk JSON serialization of legacy provenance",
  "context": "Confirmed real CLI emits NaN/Infinity/-Infinity copied from permissively parsed legacy command/snapshot_id fields, in legacy and opted payloads. Serialize before echo with allow_nan=False and fixed BadParameter on ValueError. Preserve valid bytes and all financial formulas/defaults. Separately confirmed huge annualization OverflowError is converted to a fixed CLI parameter error without a cap or formula change.",
  "assumptions": [
    {
      "statement": "Original combined candidate bytes are exact and preserved",
      "verified_by": "risk_cmds SHA256d45a32cbf42980b808b8a4088a5834616948ab281fdd47e0f287abe25a36e7e4; RiskMetricBasis SHA25622985eb8f01f6031fe374bcac8ff75cef5d8659224dc2e5872a3f48e4e661bb6; initial successor tree23cedef2294df7c8d9223f580506f91db95e1bda"
    },
    {
      "statement": "This is a real CLI serialization defect, not evidence that initial-anchor/stress formulas are wrong",
      "verified_by": "12 actual subprocess rejection regressions failed beforefix with exit0 and nonstandardJSON;2validcasespassed; preceding Claude static advisory and parent exact-base helper review bounded unsupported claims"
    }
  ],
  "alternatives_considered": [
    "Keep legacy reader and immutable artifacts unchanged; reject only report serialization",
    "Do not scrub values or replace unknown provenance silently",
    "Do not change metric/UI language, initial wealth, VaR/CVaR, confidence, annualization or stress policy based on unsupported advisory"
  ],
  "pre_mortem": [
    "Reject text NaN accidentally: valid literal string regression",
    "Print partialJSON before failure: encode completely beforeecho and assert emptystdout",
    "Change valid legacybytes or optedschema: exact pairedpre/post payload comparison plusexistingcontracttests"
  ],
  "slices": [
    {
      "title": "Real subprocess defect reproduction and byte baselines",
      "verify": "New public14cases beforefix; save2real validCLIoutputs",
      "expected": "12invalidcasesfail on old successfulCLI,2validcasespass",
      "rollback": "Remove newtestfile and localreceipts only",
      "files": [
        "tests/integration/test_risk_strict_json.py"
      ],
      "status": "done"
    },
    {
      "title": "Bounded strictserialization and covering public checks",
      "verify": "Newpublicregressions plusclock/CLI/API/metricbasis cases; scopedruff/mypy; independent advisoryreview",
      "expected": "Fixederror, noJSON on nonfinite provenance; validbytesunchanged; existingguards retained",
      "rollback": "Revert both serialization and OverflowError boundary hunks; remove successor-only tests/plan for whole-slice rollback; preserved23cedef2 unchanged",
      "files": [
        "apps/alpha-cli/src/alpha_cli/risk_cmds.py",
        "tests/integration/test_risk_strict_json.py",
        "docs/superpowers/plans/2026-11-08-risk-strict-json.md"
      ],
      "status": "done"
    }
  ],
  "tier_impact": [
    "none"
  ],
  "docs_to_update": [
    "docs/superpowers/plans/2026-11-08-risk-strict-json.md"
  ],
  "out_of_scope": [
    "Financial formulas/defaults/UIlanguage; calibration/causality/realdataqualification",
    "Sharedreader/models/frontend/generatedassets/otherowners/BUILD-STATUS",
    "Protectedtests/oracles/holdouts; installs/fullgates/fits/models/providers/commit/publication/transfer/liveaction"
  ],
  "files": [
    "apps/alpha-cli/src/alpha_cli/risk_cmds.py",
    "tests/integration/test_risk_strict_json.py",
    "docs/superpowers/plans/2026-11-08-risk-strict-json.md"
  ]
}
```

**Delivery state:** Completed — bounded CLI serialization and malformed-option handling; no full or scientific qualification.

Separate branch codex/risk-strict-json-20261108 on main snapshot3f7b23185c29b2542605bd41b9485016c2ef3e79 first reproduced preserved23cedef2 exactly. The original source/patch/receipts remain unchanged. This task uses preceding Claude two-file static advisory plus independent Codex actual-source/CLI verification; unsupported advisory concerns are not adopted.

The synthetic UTC curve [100,95,100] has a legitimate full stress panel. The [100,80,100] example has base drawdown-20% but its full-5sigma stress path becomes nonpositive, so its rejection is not evidence of a missing initial anchor. Scenario._equity already prepends a normalized1.0 level, metrics validate equity/confidence and the consumer validates UTC chronology. No such formula or policy changes are warranted here.

README/manual/current-state decision: existing setup,command and fail-loud/nonfinite invariants remain accurate; validreportbytes/options are unchanged. No README/manual cosmetic edits or sharedBUILD-STATUS append are needed in this isolated source slice. This scoped plan records the invalid-output correction and exact evidence; parent serializes landing/current-state updates. No full/scientific qualification is claimed.


## Confirmed behavior and final checks

The original two supplied source hashes matched exactly before any use as evidence. Through the actual alpha executable, all12 provenance combinations (command/snapshot_id times NaN/Infinity/-Infinity times legacy/opted JSON) exited0 before the fix; the rejection regressions therefore failed. Both finite control cases passed. The successor encodes the whole report with allow_nan=False before echo, converting ValueError to the fixed BadParameter message “risk report contains non-finite values”. No partial report or raw provenance constant is printed on that failure. Literal string “NaN” remains valid.

A separate actual CLI probe confirmed periods_per_year=10**309 exited1 with an uncaught OverflowError. Ordinary invalid confidence1 and annualization0 already returned clean parameter errors. The existing computation boundary now converts OverflowError to “risk inputs exceed supported numeric range”; no arbitrary annualization cap, changed default or shared-metric edit is introduced. A separate red receipt records1failed/2passed for these options before the conversion. Both flag modes are covered in the final tests.

Final focused public run:75passed in57.35s across the new20 real-subprocess cases and the existing55 clock/CLI/HTTP/disclosure/model cases. Earlier serialization-only covering run returned69passed; receipts are retained separately rather than relabeled as final. The final scoped Ruff/format and mypy checks pass for risk_cmds.py and the new test file. Initial mypy found a test-only invariant-dict annotation issue; that annotation was corrected and the failure receipt retained. Tests do not mock CLI, metrics or serialization for the new defect cases. Existing clock tripwire tests remain scoped pre-return guards, not new statistical evidence.

Exact real CLI finite-payload byte parity was checked before and after both final corrections: legacy1786bytes SHA256ffc5b59f77727c9c61c0b262aba3e1a80d9128db764cb69025ce73ed135b5fa7; opted2258bytes SHA256fd97d3eb20f642a91199fbc56e48b05bd3d90cbd31667548a2ec7f166d292d34. The fixture uses [100,95,100], verifiedUTC clocks and a literal-string snapshot ID “NaN”; its base drawdown is-0.05 and total return0. These are deterministic synthetic expectations, not a market study.

No imports, frontend source/UI copy, metric formulas, shared readers, APIs/models, risk defaults, source artifacts or statistical policies changed. Frontend build/browser results from23cedef2 remain historical, not newly requalified. No new build/browser suite is warranted by this CLI-only error-boundary change. Preceding Claude advisory remains static two-file review; independent Codex source/CLI verification confirms only the defects above. A separate exact-diff independent Codex advisory review is retained with local receipts and is not a formal gate attestation. Protected/full gates, installed-runtime empirical reconciliation, scientific acceptance and publication remain unrun. Parent-owned shared README/manual/current-state landing decisions remain recorded above; no unsupported global readiness claim follows.
