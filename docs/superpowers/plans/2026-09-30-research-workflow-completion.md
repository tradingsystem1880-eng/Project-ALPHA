**Delivery state:** Completed

# Research workflow completion

```json
{
  "schema_version": 1,
  "title": "Research workflow completion and typed specialist assessment",
  "context": "Owner authorized all tear-sheet recommendations and research into Pydantic specialist agents on 2026-09-30. Work is isolated from concurrent UI/CLI changes at e54aa7a.",
  "assumptions": [
    {
      "statement": "New trials remain Codex-only; old scenarios, worlds, traces and scores remain immutable.",
      "verified_by": "Versioned new fixtures/scenarios and before/after inventories."
    },
    {
      "statement": "Current Qlib contract cannot answer the one-asset weekly-close classification target.",
      "verified_by": "ml_input fixed alpha158/open-to-open recipe; ml_contract 20-symbol minimum."
    }
  ],
  "alternatives_considered": [
    "Force custom target through Qlib rejected because target identity changes.",
    "Immediate multi-agent swarm/PydanticAI migration deferred pending evidence that typed handoffs and existing isolated runtime are insufficient.",
    "Broad campaign rerun rejected; initial paired budget is ten trials."
  ],
  "pre_mortem": [
    "Fixture repairs could reveal planted truth or erase historical calibration; version separately and keep truth hidden.",
    "A diagnostic command could bypass governed research authority; label outputs non-admitted discovery evidence and preserve existing gates.",
    "Multiple specialist opinions could add cost without completing research; deterministic checks and artifact requirements precede optional opinions."
  ],
  "slices": [
    {
      "title": "Version R20 calendar and mark-to-market fixtures",
      "verify": "uv run pytest -q tests/unit/test_eval_fixture_v2.py --no-cov",
      "expected": "Reproduced failure is corrected with honest evidence and no historical rewrite.",
      "rollback": "Revert only new versioned code; retain historical and newly acquired evidence.",
      "status": "done"
    },
    {
      "title": "Calibrate R21 controls and separate completion from rubric outcomes",
      "verify": "cd tools/alpha-eval && uv run pytest -q",
      "expected": "Reproduced failure is corrected with honest evidence and no historical rewrite.",
      "rollback": "Revert only new versioned code; retain historical and newly acquired evidence.",
      "status": "done"
    },
    {
      "title": "Add a bounded weekly-classification diagnostic with baseline and chronological evidence",
      "verify": "uv run pytest -q tests/unit/test_research_diagnostic.py tests/oracles/test_research_diagnostic.py --no-cov",
      "expected": "Reproduced failure is corrected with honest evidence and no historical rewrite.",
      "rollback": "Revert only new versioned code; retain historical and newly acquired evidence.",
      "status": "done"
    },
    {
      "title": "Make feasibility, regime diagnosis and search termination explicit",
      "verify": "uv run pytest -q tests/unit/test_research_diagnostic.py --no-cov",
      "expected": "Reproduced failure is corrected with honest evidence and no historical rewrite.",
      "rollback": "Revert only new versioned code; retain historical and newly acquired evidence.",
      "status": "done"
    },
    {
      "title": "Research typed specialist architecture and bind workflow evidence",
      "verify": "cd tools/alpha-eval && uv run pytest -q",
      "expected": "Reproduced failure is corrected with honest evidence and no historical rewrite.",
      "rollback": "Revert only new versioned code; retain historical and newly acquired evidence.",
      "status": "done"
    },
    {
      "title": "Run frozen baseline/candidate ten-trial diagnostic panel and adjudicate",
      "verify": "cd tools/alpha-eval && uv run alpha-eval --help",
      "expected": "Reproduced failure is corrected with honest evidence and no historical rewrite.",
      "rollback": "Revert only new versioned code; retain historical and newly acquired evidence.",
      "status": "done"
    },
    {
      "title": "Independent source/code review and exact-tree aggregate verification",
      "verify": "uv run python scripts/gate.py full",
      "expected": "Reproduced failure is corrected with honest evidence and no historical rewrite.",
      "rollback": "Revert only new versioned code; retain historical and newly acquired evidence.",
      "status": "done"
    }
  ],
  "tier_impact": [
    "quant",
    "protected"
  ],
  "docs_to_update": [
    "CLAUDE.md",
    "docs/BUILD-STATUS.md",
    "tools/alpha-eval/README.md",
    "docs/audit/2026-09-30-research-workflow-completion.md"
  ],
  "out_of_scope": [
    "Owner approval, D2, paper, broker or live capital authority",
    "New Claude execution",
    "Rewriting historical results",
    "Unbounded agent swarm or replacing deterministic statistics with model votes",
    "Concurrent UI/owner-auth changes"
  ],
  "files": [
    "tools/alpha-eval/",
    "packages/alpha-research/src/alpha_research/",
    "apps/alpha-cli/src/alpha_cli/",
    "tests/",
    "docs/"
  ]
}
```

## Execution contract

One mutator per slice. Primary-source statistical verification and independent code review are required. The baseline/candidate panel uses identical repaired fixtures and runtime conditions; only the specified workflow treatment differs. No pooled historical improvement claim. Default Codex model gpt-6-astra, medium effort, concurrency two. New diagnostic outputs are not governed confirmation or deployment approval.

Calibration qualification: R21 is a latent-trend fixture, not a verified positive strategy control. Actual failures must permit an evidence-consistent reject. The paired panel remains diagnostic; no positive-control sensitivity claim is authorized by this data.


## Delivery evidence and residual failures

Implementation `8d0db28` passed canonical full verification, independent APPROVE, quant PASS and mutation testing. The planned ten trials completed (one candidate capped); original acquisition/scoring evidence remains immutable. See [paired results](../../../tools/alpha-eval/results/workflow-v2-20260930/README.md). Delivery completion does not mean all benchmark tasks pass: R08 lacks measured regime/filter evidence; R19 exhausted its budget before synthesis and exposed later prices during inspection; ORCA omitted denied orders; R21 positive-control sensitivity remains unverified. PydanticAI migration is deferred with explicit acceptance criteria, not delivered as a runtime.
