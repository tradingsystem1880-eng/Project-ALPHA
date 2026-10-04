# Codex-first research runtime

**Delivery state:** Completed

This delivery state covers the four slices of the first runtime increment below. The remaining
accepted roadmap is not complete.

```json
{
  "schema_version": 1,
  "title": "Codex-first research runtime",
  "context": "Implement the accepted Codex-first design from delivered research checkout 8a00b27; preserve concurrent primary UI work and historical Claude results.",
  "assumptions": [
    {
      "statement": "The primary assistant depends on uncommitted workstation interfaces; research CLI and verified diagnostic seams are available in the clean research checkout.",
      "verified_by": "Navigator inspection of assistant_context, research_suggestions and research_execution_digest on 2026-10-03."
    }
  ],
  "alternatives_considered": [
    "Importing the provisional workstation assistant wholesale rejected because it couples to concurrent uncommitted interfaces.",
    "Enabling broad MCP rejected: prompt-only scoping does not constrain run or data access.",
    "Local Qwen vision and hosted finance reasoning deferred per owner direction; Codex owns reasoning and image input."
  ],
  "pre_mortem": [
    "A model cites invented evidence: validate receipt identities and label narrative interpretation advisory.",
    "A resumed conversation receives fresh budgets: reserve attempts durably before dispatch and keep failures.",
    "MCP bypasses sandbox scope: fixed case service with no arbitrary paths, flags, identifiers or owner-authority tools.",
    "Current Codex protocol differs from website: use installed 0.159.0 generated schema and real handshake."
  ],
  "slices": [
    {
      "title": "Codex JSONL transport and lifecycle",
      "verify": "uv run pytest -q tests/unit/test_codex_rpc.py",
      "expected": "Interleaved events, errors, timeouts and process cleanup are bounded.",
      "rollback": "Remove new optional CLI runtime; preserve evidence and existing research behavior.",
      "status": "done"
    },
    {
      "title": "Run-bound evidence tools and durable budget",
      "verify": "uv run pytest -q tests/unit/test_investigation_case.py",
      "expected": "Run mutation, unknown actions and replay cannot bypass evidence or budget checks.",
      "rollback": "Remove new optional CLI runtime; preserve evidence and existing research behavior.",
      "status": "done"
    },
    {
      "title": "Scoped MCP and Codex session integration",
      "verify": "uv run pytest -q tests/unit/test_codex_investigation.py",
      "expected": "Only bound diagnostic tools are exposed, with persisted turns and checked citations.",
      "rollback": "Remove new optional CLI runtime; preserve evidence and existing research behavior.",
      "status": "done"
    },
    {
      "title": "Actual process and recorded-run acceptance",
      "verify": "uv run pytest -q tests/unit/test_codex_investigation.py",
      "expected": "CLI handshake, isolation probes, live Codex tool use and full gate have recorded outcomes.",
      "rollback": "Remove new optional CLI runtime; preserve evidence and existing research behavior.",
      "status": "done"
    }
  ],
  "tier_impact": [
    "protected",
    "dag"
  ],
  "docs_to_update": [
    "CLAUDE.md",
    "docs/BUILD-STATUS.md",
    "docs/operations/codex-investigations.md"
  ],
  "out_of_scope": [
    "No trading authority, D2 access, historical artifact alteration or automatic skill activation in this first increment.",
    "No claim that three diagnostic tools deliver the complete accepted roadmap."
  ],
  "files": [
    "apps/alpha-cli/src/alpha_cli/codex_*.py",
    "apps/alpha-cli/src/alpha_cli/investigation_*.py",
    "apps/alpha-mcp/src/alpha_mcp/investigation_server.py",
    "tests/unit/test_codex_*.py",
    "tests/unit/test_investigation_case.py",
    "docs/"
  ]
}
```

## Execution sequence

Implement transport and durable tool service independently in small tested increments, then integrate the existing CLI before workstation wiring. Tests precede each behavioral slice; run the fast gate, independent review and canonical full gate on the final tree. No statistical estimators change. CLI remains sole composer and MCP subprocesses CLI. Evidence retains the source cutoff and retrospective exposure; thread history cannot establish untouched data. Operational IDs and model prose are nondeterministic, while evidence content hashes and source verification remain deterministic.

## Remaining accepted roadmap

1. Connect Codex sessions and one real recorded-run investigation (this increment).
2. [Frozen comparison evidence and missing-data blockers](2026-10-03-codex-comparison-evidence.md) are implemented. [Bounded acquisition](2026-10-04-bounded-comparison-acquisition.md) and [workstation sessions, follow-ups and cancellation](2026-10-04-workstation-investigations.md) are implemented on the isolated runtime branch. Live-provider acceptance, combined-tree workstation verification, active-turn steering and chart context remain outstanding.
3. Strategy capability bridge: isolated development, causal tests, independent review, immutable registration, explicit case revision.
4. Evaluated learning: staged candidate procedures, untouched evaluation, activation between cases, rollback and cumulative search budgets; amend governance explicitly before activation.
5. Expand regime, pattern and portfolio investigations against measured gaps; use small local numeric specialists only after baseline comparison. Preserve large-model research for later GPU experiments.

Better means supported claims, useful completed investigations, correct abstention, fewer repeated attempts/questions and bounded resource use. Three inspection tools alone cannot investigate macro causes, establish regimes or prove profitability. Those limitations must remain visible in reports.

## Verified development evidence

On 2026-10-03, 65 targeted tests passed. The real MSFT recorded-run smoke completed with three successful native MCP tools and three evidence receipts; CLI checkpoint resume returned identical findings with one total model turn retained. Native App Server resume also retained the same thread, model, permission profile and exact tool inventory without starting a model turn. Earlier isolation/tool-discovery/tool-approval failures remain recorded rather than relabeled as successful trials. Independent review found no blocking findings and recomputed all three successful receipts against source.

All six canonical full-gate components passed on implementation tree
`888226d9e650dbc895a16226a53d06408e5a874c3d4e0005211ae2796b6756fe`, with
`ALPHA_GATE_BASE=8a00b2749984f937c994c0b7bc6b261de297cc89`, four pytest workers and browser
port 8817. This verifies the 25-file runtime increment, not the cumulative research branch against
main. No statistical code changed within this scope. The delivery-record update requires a fresh
final-tree full stamp before commit. The gate log is retained privately at
`/private/tmp/alpha-codex-full-gate-v4.log`.
