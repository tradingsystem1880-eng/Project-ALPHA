**Delivery state:** In progress

# Cancellation regression, commit, and research walkthrough

```json
{
  "schema_version": 1,
  "title": "Cancellation regression, commit, and research walkthrough",
  "context": "Owner requested resolution of the intermittent ML cancellation test, then a reviewed commit, then a research-only screening/replay/context walkthrough.",
  "assumptions": [
    {"statement": "The earlier failure's exact assertion was not retained; reproduce a concrete failure before attributing its cause.", "verified_by": "deterministic fault injection and captured pytest output"},
    {"statement": "Existing Phase C panel primitives are prerequisites; quantitative review may add citations but must not change executable behavior.", "verified_by": "non-docstring AST hash and preservation hashes for all other prior files"}
  ],
  "alternatives_considered": ["Reject blindly extending the five-second wait or weakening terminal-state assertions.", "Retain the real process/store cancellation contract while separating it from unrelated CLI startup timing where appropriate."],
  "pre_mortem": ["A cancellation test passes while leaving a child or capacity claim alive; assert process cleanup and terminal journal stability.", "A broad commit silently changes existing owner work; compare baseline hashes and inspect the complete staged manifest.", "A walkthrough claims real-data success with synthetic inputs; identify exact frozen inputs and report unavailable data honestly."],
  "slices": [
    {"title": "1 Reproduce and repair cancellation test", "verify": "targeted cancellation tests, adversarial delay and full parallel coverage", "expected": "Discriminating stable test without weakened runtime cancellation controls", "rollback": "Revert only the scoped test/runtime fix", "status": "done"},
    {"title": "2 Review and commit", "verify": "full gate, independent review, quant source report, staged manifest and preservation hashes", "expected": "Verified exact-tree conventional commit with no bypass", "rollback": "A reviewed revert, never destructive reset", "status": "in_progress"},
    {"title": "3 Research-only walkthrough", "verify": "frozen scan, repeat/replay, context reference integrity", "expected": "Inspectable evidence with authority none and no provider or trading actions", "rollback": "Retain immutable walkthrough evidence; no owner approvals to undo", "status": "pending"}
  ],
  "tier_impact": ["protected", "risk", "quant"],
  "docs_to_update": ["docs/BUILD-STATUS.md", "AGENTS.md", "docs/operations/claude-code-harness.md"],
  "out_of_scope": ["New statistical estimators", "Owner approvals", "Provider acquisition", "Paper or live orders"],
  "files": ["tests/unit/test_web_ml.py", "scripts/git_guard.py", "tests/unit/test_git_guard.py", "packages/alpha-research/src/alpha_research/panel.py", "tests/oracles/test_panel_cost_accounting.py", "docs/", "AGENTS.md"]
}
```

Execution results belong in the final handoff and ignored `.alpha/state/` receipts so
post-verification reporting does not invalidate the tested source tree. The prior
[refactor record](2026-09-16-agent-neutral-reproducible-research.md) remains the source
of the accepted refactor scope and its historical verification evidence.

## Commit review findings and patch queue

| id | severity | area / location | issue / impact | proposed_fix | source | status |
|---|---|---|---|---|---|---|
| R1 | high | Git guard: `scripts/git_guard.py`, staged path collection | Rename detection hid the original protected/quant path and could omit review requirements. | Disable rename coalescing for staged classification; test original protected and quant paths. | independent commit reviewer | Fixed; three red regressions, eleven guard tests passed. |
| R2 | high | Review availability: `.claude/agents/independent-reviewer.md` | Required `tests/holdout` suite is absent; its execution is unverified, not passed. | Restore owner-supplied suite or obtain an explicit documented owner exception; do not invent a suite or bypass checks. | independent commit reviewer | Owner authorized the scoped absence exception on 2026-09-17; suite remains UNVERIFIED; independent re-review required. |

## Owner-authorized missing-suite exception — 2026-09-17

The owner answered “yes” to the explicit request to document the missing-suite
exception, finish independent review, commit, and run the research walkthrough.
This applies only to the integrated 2026-09-16 refactor and this cancellation
follow-up. It grants no application owner approvals or trading authority.

`uv run pytest tests/holdout -q` exited 4: `ERROR: file or directory not found:
tests/holdout`; no tests ran. Git history, fetched remote branch trees, the other
local worktree, and scoped local/external backup-directory checks found no copy.
No hidden source was read or fabricated. The suite remains **UNVERIFIED**, not
passing. Its absence alone may be nonblocking for this commit; every other test,
independent review, quantitative attestation and installed Git guard remains
required. Existing failures and future missing-suite cases are not waived.
| Q1 | medium | Citations: `packages/alpha-research/src/alpha_research/panel.py`, public docstrings | Module bibliography did not identify each function's sources or distinguish local policies from literature. | Add individual source/design references; correct tie wording; preserve executable AST. | independent quant reviewer | PASS report: 13 verified claims, six numerical checks, 117 tests passed. |
| Q2 | medium | Oracles: `tests/oracles/test_panel_cost_accounting.py` | Cost helper lacked an independent trade-notional oracle. | Compare explicit long/short weight changes with one-way costs. | independent quant reviewer | 36 passed; intentionally wrong factor two fails 18 cases. |

The sole deliberate change to prior Phase C source is documentation in `panel.py`.
Its executable AST excluding docstrings remains SHA256
`54fbefd901607ce4b6ca714095bf637b64718c588c93dcbea5ebf42b38837b43`.
The original Phase C plan is preserved as historical input. Clarification of its
quantile remainder wording: implemented/tested extremes each have `n//q` names;
the remainder is shared by inner buckets, or left unbucketed only when `q=2`.
Common-name turnover and cost remain replacement-only screening proxies, not a
complete portfolio cost model. No inference or trading authority follows.

## Cancellation evidence

Injecting 2.6 seconds of startup delay into each real journal CLI reproduced the
unchanged test's `cancelled ML process was not reaped` assertion after 5.08 seconds.
Each RPC retained its five-second limit; eventual status was `cancelled`, capacity
was zero, and no worker threads remained. This proves an aggregate-deadline defect;
the unretained assertion from the earlier run is not retroactively claimed known.

The test now waits for the first heartbeat checkpoint instead of sleeping 50ms.
Its completion budget covers an in-flight heartbeat, the heartbeat observing the
request, and the terminal journal call, plus the existing TERM/KILL/reap grace.
The budget is 21.03 seconds, below the child's natural 30-second lifetime. Normal
and delayed real-CLI cases retain the same cancelled-state, released-capacity and
stable-journal assertions. Cleanup joins the bounded worker before fixtures close.
Production timeouts and lease behavior are unchanged. Both cases passed locally
and independently; full parallel verification remains recorded by gate receipts.

The research walkthrough is prepared but not executed: five qualified Bybit daily
series (901 rows each, 2022-01-01 through 2024-06-19), acquired 2026-09-10. A
2026-09-11 knowledge cutoff is required; a 2024 cutoff would precede acquisition.
This is retrospective provenance testing, not a current-market signal. Execution
waits until the requested commit step is legitimately satisfied.
