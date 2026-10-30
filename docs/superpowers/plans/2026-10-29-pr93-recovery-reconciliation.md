# Reconcile retained PR93 recovery on PR95

**Delivery state:** Completed bounded engineering delivery through [PR96](https://github.com/tradingsystem1880-eng/Project-ALPHA/pull/96), merged at `f847581f2703f6b5b36aeccdf877c4354a19e176`. The [delivery reconciliation](#delivery-reconciliation-2026-10-30) records the verified head and CI. Private coverage remains UNVERIFIED; later cleanup does not inherit this delivery's exception.

```json
{
  "schema_version": 1,
  "title": "Reconcile retained PR93 recovery on PR95",
  "context": "Port PR93 82ec358a6a448e43f77210ec911ee1c1ed38a452 onto published PR95 2b967311be376cb1f96159d2137f964b05c03c77 in an isolated worktree. Preserve native-claim and ordinary D1/D2 ownership protections together. Claude owns PR95; this successor qualifies the retained recovery/cancellation work separately.",
  "assumptions": [{"statement": "PR92 substantive redaction is already retained and must not be replayed.", "verified_by": "Prior blob comparison against published Claude checkpoint and current source inspection."}],
  "alternatives_considered": ["Replace native-claim protection with research-kind protection: rejected because native claims can cover other job kinds.", "Merge historical Atlas blobs: rejected; regenerate actual inputs."],
  "pre_mortem": ["Stale heartbeat could incorrectly release an unverified owner slot.", "Wrong attempt or truncated global job inventory could hide or misidentify a publication.", "Historical full-gate receipts could be incorrectly reused for the reconciled tree."],
  "slices": [
    {"title": "Discriminating recovery and cancellation regressions", "verify": "uv run pytest -q tests/integration/test_research_cli.py -k 'cancel_does_not_clear or retry_recovers_published_d1'", "expected": "Controls fail on the published baseline before implementation.", "rollback": "Keep baseline and test patch separately.", "status": "done"},
    {"title": "Retain recovery, cancellation and both reconciliation protections", "verify": "Focused research CLI, control-store and native ownership tests plus changed-file static checks.", "expected": "Exact recovery and cancellation controls pass without releasing native or research capacity.", "rollback": "Retain isolated worktree and patch; do not alter PR95.", "status": "done"},
    {"title": "Review and preserve local reconciliation", "verify": "Atlas regeneration/freshness, plan-check, independent review and exact patch/tree hashes.", "expected": "Final-head reconciliation, independent review and hosted CI recorded for the bounded PR96 delivery.", "rollback": "Preserve evidence without commit or publication when repository gates remain pending.", "status": "done"}
  ],
  "tier_impact": ["risk", "dag", "determinism"],
  "docs_to_update": ["CLAUDE.md", ".claude/rules/alpha-cli.md", "docs/BUILD-STATUS.md", "docs/superpowers/plans/2026-10-24-d1-job-recovery.md"],
  "out_of_scope": ["PR92 replay", "PR95 branch or review record edits", "Statistical changes", "Automatic cross-host recovery", "Provider or trading operations", "Full-suite duplication before final integration", "Push or merge"],
  "files": ["apps/alpha-cli/src/alpha_cli/control_store.py", "apps/alpha-cli/src/alpha_cli/project_cmds.py", "apps/alpha-cli/src/alpha_cli/research_cmds.py", "apps/alpha-cli/src/alpha_cli/research_crypto_runtime.py", "apps/alpha-cli/src/alpha_cli/research_d1.py", "tests/integration/test_research_cli.py"]
}
```

The change stays in CLI orchestration and persistence: no dependency edge, numerical algorithm,
seed, point-in-time read, publication contract or owner authority changes. The prior PR93 packet
describes historical candidate checks; this reconciliation requires fresh evidence. A local patch
checkpoint is not a guarded commit or full-gate acceptance. Preserve Claude's final test fixes,
review appendices and regenerated Atlas from the final published head. Their source/test/reviewer records are retained unchanged.

The two baseline controls failed before production changes: cancellation incorrectly cleared a
concurrently started execution, and stale reconciliation released a D1 slot without owner-host
proof. After integration, 26 focused research cases, 6 generic job-store cases and 57 native/adjacent
compatibility cases passed. Changed Python lint/format, strict typing of five production files and
all 13 import contracts passed. Further producer, Atlas and independent-review outcomes belong
to the exact-tree evidence packet, not historical PR93 or PR95 qualification receipts.

Final PR95 commit `2b967311be376cb1f96159d2137f964b05c03c77` and tree
`142384333029ade2d10b11937cfff0da3eb69e3f` were verified after fetch. Its native-supervisor
validator preloading, deadline/elapsed disclosures, final tests and review appendices are preserved.
The owner approved the bounded absence-only private-suite exception for this recovery/cancellation
work through delivery (2026-10-29 20:04 UTC); private coverage stays UNVERIFIED, every other check
and independent review remain mandatory. See the scoped reviewer appendix.


## Delivery reconciliation (2026-10-30)

[PR96](https://github.com/tradingsystem1880-eng/Project-ALPHA/pull/96) is merged, with head
`e196fb3d24ab01976beb434bb7e53fdb62866359` and main merge
`f847581f2703f6b5b36aeccdf877c4354a19e176`. Its first parent is the PR95 merge
`dabdb08fee9ee4637339d26016d85acf16937546`; the final PR95 source is retained.
Direct GitHub read-back agrees with local Git parentage. Head CI
[40972171573](https://github.com/tradingsystem1880-eng/Project-ALPHA/actions/runs/40972171573)
completed successfully; all seven listed jobs succeeded. The PR's code-review summary names the
same head and reports no unresolved findings. This replaces the earlier in-progress delivery
status; the source/check history above remains preserved. The task's private-suite absence
exception applies to this recovery/cancellation delivery only. New cleanup/refactor work requires
its own qualification and owner decision; no old stamp or exception transfers.
