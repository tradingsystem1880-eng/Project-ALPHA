# Clean, reconcile and protect main

```json
{
  "schema_version": 1,
  "title": "Clean the working tree, reconcile the diverged main lineages, and protect main",
  "context": "Owner request 2026-10-05: commit all outstanding work, finish half-done items correctly, reconcile local main (edge-first) with origin/main (neurotrader888 port, PR #50), pass GitHub CI, and reach a production-grade baseline before research continues in a fresh session. The crypto-terminal working tree already carries a valid full stamp; the gaps are history divergence, an ADR number collision, a duplicate DefiLlama implementation, stale 'pending' documentation, scratch files and an unprotected main.",
  "assumptions": [
    {"statement": "The uncommitted crypto-terminal tree passed the full gate on 2026-10-04 13:46 UTC (tree 54b7f96e, 6/6 components, 969 s).", "verified_by": "uv run python scripts/gate.py check --tier full -> stamp valid; pytest 4879 passed / 0 failed; vitest 361 passed; ruff, format, lint-imports 13/13, semgrep exit 0 on 2026-10-05"},
    {"statement": "PR #51 (9a4ab43) already merges origin/main into the edge-first lineage and is CI-green.", "verified_by": "gh pr view 51: MERGEABLE/CLEAN, check/harness/frontend/qlib-worker/literature-worker SUCCESS; git merge-base --is-ancestor origin/main 9a4ab43"},
    {"statement": "The live control store is schema v6, readable only by the uncommitted control_store.py.", "verified_by": "worktree on origin/main fails with 'unsupported control store schema version 6'; working-tree control_store.py SCHEMA_VERSION = 6"},
    {"statement": "ADR-0036 is used twice (origin: DefiLlama, published and referenced from code; local: agent-neutral, unpublished).", "verified_by": "git ls-tree origin/main docs/adr and ls docs/adr"}
  ],
  "alternatives_considered": [
    "Rebase local main onto origin/main: rejected, rewrites 12 commits over 22 and discards PR #51's tested conflict resolutions.",
    "Push the reconciled main directly without a PR: rejected by owner; CI must be green before main moves."
  ],
  "pre_mortem": [
    "Browser timing budgets (scientific/market p99) flake on CI runners by 1-2 ms; one retry, then an explicit owner decision, never a silent relaxation.",
    "The two DefiLlama modules have incompatible defillama_url signatures; both test suites must pass after the union.",
    "An untracked file appears between gate and commit and the guard rejects the commit; check git status before every gate.",
    "Generated artifacts (OpenAPI, TS client, SPA bundle, Atlas) are hand-merged and drift; always regenerate instead."
  ],
  "slices": [
    {"title": "Finalize and commit the crypto-terminal working tree", "verify": "uv run python scripts/gate.py full", "expected": "6/6 components pass; review verdict APPROVE; one commit on feat/crypto-terminal-ui with an empty working tree", "rollback": "git tag pre-clean-2026-10-05 marks the prior HEAD; scratch archived at ~/Desktop/alpha-scratch-2026-10-05", "status": "done"},
    {"title": "Integration branch from PR #51 head with local main and crypto-terminal merged; superseding PR green", "verify": "gh pr checks <new> --watch", "expected": "check, harness, frontend, qlib-worker, literature-worker, atlas, eval all SUCCESS; PR merged; local main == origin/main", "rollback": "Close the new PR; origin/main is untouched until merge", "status": "in_progress"},
    {"title": "Post-merge hardening: nightly green, main protected, workstation restarted, closing record", "verify": "gh api repos/tradingsystem1880-eng/Project-ALPHA/branches/main/protection --jq '.required_status_checks.contexts'", "expected": "Seven required contexts; nightly semgrep/determinism pass; workstation serves merged code against the v6 store", "rollback": "gh api -X DELETE .../branches/main/protection", "status": "pending"}
  ],
  "tier_impact": ["protected", "quant", "dag"],
  "docs_to_update": ["docs/BUILD-STATUS.md", "CLAUDE.md", "docs/ARCHITECTURE.md", "docs/adr/README.md", ".claude/rules/alpha-data.md"],
  "out_of_scope": [
    "Strategy or research work (continues in a fresh session from main)",
    "New features",
    "History rewrite or force-push",
    "Deleting remote branches, worktrees or stashes (owner keeps them; inventoried below)"
  ]
}
```

**Delivery state:** In progress (2026-10-05).

## Owner decisions

- Restore the five deleted `research/*mizerxbt_eth*` files.
- Commit `output/data-hygiene/*.json` (cited audit receipts). Archive `tmp/` and `output/pdf/` to
  `~/Desktop/alpha-scratch-2026-10-05/` and ignore `tmp/`.
- Reach main through one new PR that supersedes #51, merged only after every CI job passes.
- Protect `main` with the seven CI contexts as required checks.
- Holdout exception: `tests/holdout` is absent from this checkout. The owner authorized
  proceeding without it for this plan's commits only; the reviewer records it as UNVERIFIED and
  every other check remains mandatory.

## ADR numbering

Published `0036-defillama-tvl-supplemental-research-family.md` keeps 0036. Local agent-neutral
engineering becomes ADR-0037. Local confirmation and terminal archive charts becomes ADR-0038.

## Leftover inventory (kept by owner decision)

| Item | State |
|---|---|
| `stash@{0}` "phase-c-c1-wip" | 29 lines (alpha_research panel exports, rules row); already landed in `b1b7510` |
| `stash@{1}` | `alpha_web/_charts.py` +2/−1, `tests/unit/test_web_forecast.py` +3/−2, from `audit/institutional-2026-07` |
| Worktree `.claude/worktrees/infallible-kalam-2f15ea` | PR #51 branch, clean |
| Worktree `.claude/worktrees/research-triple-tap-inverse-hs` | No commits; research restarts from main |
| Remote `claude/integrate-trader-github-xy6rxs`, `backup/local-main-2026-09-28` | Ancestors of the reconciled main |
| PR #52 (draft) | Cloud harness setup; will conflict on `scripts/claude_hooks.py` and the harness doc; owner to rebase |
