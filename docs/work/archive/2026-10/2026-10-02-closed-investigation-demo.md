# Closed synthetic investigation demo

**Delivery state:** Completed — delivered as d5f3cd4 with independent review and full-gate acceptance.

```json
{
  "schema_version": 1,
  "title": "Closed synthetic investigation demo",
  "context": "Implement the next retrospective development demo after advisory teammate commit 535a461. Synthetic panels only; no owner data, trading evidence or SDK migration.",
  "assumptions": [
    {
      "statement": "Existing general-tool harness cannot enforce a four-action broker or immutable input boundary.",
      "verified_by": "Navigator and independent invariants audit of isolation.py, sandbox.py and harness.py."
    }
  ],
  "alternatives_considered": [
    "General MCP agent rejected because action budgets would be prompt-only.",
    "Multi-agent and PydanticAI migration deferred until useful investigation behavior is measured."
  ],
  "pre_mortem": [
    "Model reads truth or rewrites inputs: use blank reasoning workspace, tools disabled, denied source/truth paths, worker read-only exports and real preflight.",
    "Failed or repeated proposals reset budget: fresh append-only trial, attempt before execution, no resume.",
    "Conditional hindsight overclaims: frozen indicator t conditions next return, descriptive only, no uncertainty or confirmation claim.",
    "Synthetic fixture is misrepresented as backtest success: label every receipt and report synthetic, retrospective, non-admitted."
  ],
  "slices": [
    {
      "title": "Export neutral cutoff-scoped synthetic inputs and fixed descriptive actions",
      "verify": "uv run --project tools/alpha-eval pytest tools/alpha-eval/tests/test_investigation_worker.py",
      "expected": "Future poisoning cannot alter permitted payload; calibrated controls reconcile or fail explicitly.",
      "rollback": "Revert demo additions; preserve historical trials.",
      "status": "done"
    },
    {
      "title": "Enforce read-only worker boundaries and closed durable action budget",
      "verify": "uv run --project tools/alpha-eval pytest tools/alpha-eval/tests/test_investigation_demo.py",
      "expected": "Unknown/failed/repeated requests debit bounds; no interpretation after integrity failure.",
      "rollback": "Revert demo additions; preserve historical trials.",
      "status": "done"
    },
    {
      "title": "Run bounded Codex proposals with real traces and honest case report",
      "verify": "uv run --project tools/alpha-eval alpha-eval investigate-demo --help",
      "expected": "No model tool calls; genuine model choices and all receipts retained; no empirical uplift inferred.",
      "rollback": "Revert demo additions; preserve historical trials.",
      "status": "done"
    },
    {
      "title": "Independent review and exact-tree aggregate gate",
      "verify": "uv run python scripts/gate.py full",
      "expected": "Fresh full pass plus reviewed exact tree.",
      "rollback": "Revert demo additions; preserve historical trials.",
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
    "Real user data exports",
    "Inferential regime validation",
    "Predictive or untouched confirmation",
    "General autonomous tools, specialist teams or new SDK dependencies",
    "Historical benchmark modifications"
  ],
  "files": [
    "tools/alpha-eval/src/alpha_eval/investigation_*.py",
    "tools/alpha-eval/worlds/investigation_worker.py",
    "tools/alpha-eval/tests/test_investigation_*.py",
    "tools/alpha-eval/src/alpha_eval/cli.py",
    "docs/"
  ]
}
```

The model proposes one of four action names or a final response. No action arguments, paths or code are accepted. Controller-selected inputs and budgets stay outside model control. A final synthesis slot is reserved. Synthetic accounting checks are cash plus marked position identity checks, not an engine audit. All observed periods remain retrospective.

The implementation deliberately uses a synthetic panel instead of claiming an ordinary run is an
engine-tested strategy. The negative is a frozen-indicator null, not pure noise. The worker checks
cash plus marked-position identity only; real execution reconciliation remains separate work.
Runtime code is copied explicitly without evaluator truth, tests or repository documentation.
The actual /tmp denial probe caught and corrected implicit temporary-directory access before live
trials. Model refusal smoke and worker physical enforcement are distinct evidence.


Verification amendment: concurrent checkouts repeatedly collided on Playwright's fixed port.
The test-only backend and Playwright config now share validated `ALPHA_PLAYWRIGHT_PORT`
(default 8802; owner port 8801 rejected), and refuse server reuse. This enables the canonical
full gate on an independent port while retaining disposable data and disabled paper settings.
Eight focused port tests plus browser checks cover the amendment; independent review is required.
