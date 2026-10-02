# Investigation efficiency comparison

**Delivery state:** Completed — delivered as 77d6e94 with independent review and full-gate acceptance.

```json
{
  "schema_version": 1,
  "title": "Investigation efficiency comparison",
  "context": "Compare the delivered synthetic controller with deterministic inspection and a fixed-evidence advisory baseline; preserve d5f3cd4 and all historical evidence.",
  "assumptions": [
    {
      "statement": "Repeated fresh model calls may dominate cost; prompt compaction alone may not.",
      "verified_by": "Retained 12-call demo usage; this comparison measures actual transport usage."
    }
  ],
  "alternatives_considered": [
    "Specialist teams and SDK changes deferred until simpler orchestration is measured.",
    "Inspection-only advisory baseline rejected because it withholds available performance evidence."
  ],
  "pre_mortem": [
    "Compaction drops caveats: use lossless compact JSON only, with semantic round-trip test.",
    "Automatic checks escape budget: reserve and debit identical measurement attempts before execution.",
    "Savings hide failed synthesis: retain every attempt and usage; no success-only aggregation.",
    "Three designed cases mistaken for uplift: descriptive paired results only, independent evidence review, no statistical claim."
  ],
  "slices": [
    {
      "title": "Budgeted deterministic inspection and fixed-evidence synthesis",
      "verify": "uv run --project tools/alpha-eval pytest tools/alpha-eval/tests/test_investigation_efficiency.py",
      "expected": "Integrity failures block measurements; automatic work debits bounds; legacy behavior preserved.",
      "rollback": "Revert new mode and comparison additions; retain evidence.",
      "status": "done"
    },
    {
      "title": "Frozen comparison schedule and complete resource records",
      "verify": "uv run --project tools/alpha-eval pytest tools/alpha-eval/tests/test_investigation_comparison.py",
      "expected": "Same inputs/model/actions; preregistered schedule, missing usage is unknown, all failures retained.",
      "rollback": "Revert new mode and comparison additions; retain evidence.",
      "status": "done"
    },
    {
      "title": "Bounded nine-trial live comparison and independent evidence review",
      "verify": "uv run --project tools/alpha-eval alpha-eval investigate-compare --help",
      "expected": "Three modes by three existing designed cases; retained traces and honest cost-quality decision.",
      "rollback": "Revert new mode and comparison additions; retain evidence.",
      "status": "done"
    }
  ],
  "tier_impact": [
    "protected"
  ],
  "docs_to_update": [
    "CLAUDE.md",
    "docs/BUILD-STATUS.md",
    "tools/alpha-eval/README.md"
  ],
  "out_of_scope": [
    "Real data and engine reconciliation",
    "New statistical estimators",
    "Specialist agents, SDK migration or model change",
    "Production suggestion benchmark or general reliability claims"
  ],
  "files": [
    "tools/alpha-eval/src/alpha_eval/investigation_*.py",
    "tools/alpha-eval/src/alpha_eval/cli.py",
    "tools/alpha-eval/tests/test_investigation_*.py",
    "docs/"
  ]
}
```

Freeze three modes before live acquisition: legacy adaptive (up to five calls), prechecked adaptive (up to four calls), and fixed-evidence advisory (one synthesis after deterministic measurements). Each shares four measurement attempts, identical panel hashes, model, effort, question, action semantics and isolation. The fixed baseline is a synthetic all-evidence synthesis control, not production `diagnostic suggest`. Automatic measurement policy is an intentional treatment difference. Case order stays frozen; rotate mode order across the three cases to reduce simple order confounding. One trial per cell, no retries or selected replacements.

Acceptance requires no observed critical evidence/integrity regression under independent review. Resource target: prechecked adaptive uses fewer calls and at least 15% fewer total input tokens than legacy across all three cases, conditional on usable finals; report output/cached tokens, prompt bytes and wall time separately. Fixed advisory remains the simplicity comparator. Failure leaves existing default unchanged. Missing usage is unknown, never zero. No dollar estimate without billing data. No significance or broad uplift claim from this small designed panel.

DAG: evaluator only orchestrates isolated worker subprocesses; no new platform imports. Timing/statistical operators unchanged; no new look-ahead or inferential claims. Lossless JSON compaction preserves all fields, receipt IDs, provenance and caveats. Every call and automatic action is reserved before execution; no resume.


## Results and acceptance handoff

[Retained report](../../../tools/alpha-eval/results/investigation-efficiency-20261002/report.md)
records all nine trials with exact sources and evidence. Prechecked used 7 calls / 74126 input
tokens against legacy 12 / 127832; fixed used 3 / 32425. Independent evidence review found no
critical regression in the observed outputs. The prechecked 15% resource target was met, but
the simpler fixed-evidence comparator is cheaper on this narrow panel. Defaults stay unchanged.

Before committing, obtain exact-tree code approval, regenerate/check Atlas and run
`ALPHA_PLAYWRIGHT_PORT=18803 CI=1 PYTEST_XDIST_AUTO_NUM_WORKERS=4 uv run python scripts/gate.py full`.
Only its fresh stamp is engineering acceptance; this narrative is not a gate receipt.

Next experiment: frozen richer cases with meaningful optional-data costs, dated-context
relevance traps, hindsight-only regimes and provider failures, followed by repeated paired
acquisition. Keep contribution ablations separate; current savings combine inspection, compaction
and early stopping. Real-data export/reconciliation remains a prerequisite for owner-data use.
