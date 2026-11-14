# Document the daily rule lane in the research stages

**Delivery state:** Completed on branch `m8/first-real-study`; done when its pull request merges
(filed straight into the archive). Documentation only.
**Build class:** small.

## For the owner

- What changes: the research instructions now say how the Packet 3 study is drafted and that you
  approve it in the Workstation (the command-line approval refuses it, by design).
- Nothing in the program changes; no approval is invalidated; nothing is approved by this work.

```json
{
  "schema_version": 1,
  "title": "Document the daily rule lane in the research stages",
  "context": "Walking Packet 3 on real data found that the research stage documents never name the daily rule lane (alpha research draft-daily), and that stage 02 says any contract can be approved with the CLI. A fixed-rule contract can only be approved through the Workstation's local confirmation: ControlStore.review_research_contract already refuses a bare CLI approval of a rule contract (is_rule_contract plus require_rule_confirmation) before any review or phase change. A code change first planned here (a CLI refusal) was withdrawn when the builder showed the store already enforces it. What remains is documentation.",
  "assumptions": [
    {
      "statement": "A bare CLI approval of a rule contract is refused before any review or phase change.",
      "verified_by": "Builder investigation 2026-11-14, confirmed by reading control_store.py review_research_contract (is_rule_contract, require_rule_confirmation) on origin/main 947d911e; the builder's new test of a CLI approval without a receipt saw the refusal, no review row and the phase unchanged."
    }
  ],
  "alternatives_considered": [
    "Keep the CLI-refusal helper as an error-message improvement: rejected, it duplicates an existing rule and the clearer message would need control_store.py, which daily approvals are bound to."
  ],
  "pre_mortem": [
    "Documents state a rule the code does not have: each statement names the function that enforces it.",
    "The stage 02 note goes stale when draft-daily takes one manifest id per month (wt-daily): that change owns updating the option in the same note."
  ],
  "slices": [
    {
      "title": "Stage 02 names the daily rule lane",
      "verify": "uv run pytest -q tests/unit/test_filesystem_contract.py",
      "expected": "Stage 02 says how a Packet 3 case is drafted and that it is approved in the Workstation only; the file stays under 80 lines.",
      "rollback": "Revert the stage 02 edit.",
      "files": [
        "research/stages/02-data/CONTEXT.md"
      ],
      "status": "done"
    },
    {
      "title": "cli-native states the rule-contract approval route",
      "verify": "uv run python scripts/gate.py check",
      "expected": "One bullet under Approval fingerprints names review_research_contract and the Workstation route.",
      "rollback": "Revert the bullet.",
      "files": [
        "docs/reference/invariants/cli-native.md"
      ],
      "status": "done"
    }
  ],
  "tier_impact": [
    "none"
  ],
  "docs_to_update": [
    "docs/reference/invariants/cli-native.md",
    "research/stages/02-data/CONTEXT.md"
  ],
  "out_of_scope": [
    "Any code change",
    "Approving, re-approving or promoting anything",
    "The daily price reader (wt-daily)"
  ],
  "files": [
    "research/stages/02-data/CONTEXT.md",
    "docs/reference/invariants/cli-native.md"
  ]
}
```

## Withdrawn build

A command-line refusal for rule contracts was planned and sent to the builder. Its test-first
run showed the refusal already exists in `ControlStore.review_research_contract`, so the build was
stopped and nothing from it is used. The earlier reading of the code that called this a defect
was wrong: it missed that check.
