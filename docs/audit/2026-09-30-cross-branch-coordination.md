# UI and research-workflow branch coordination

> **Superseded acceptance note (2026-10-05):** pending or failed aggregate results below are historical. The canonical full gate later passed on the frozen shared tree (stamp tree `54b7f96e`, 2026-10-04 13:46 UTC); see `docs/BUILD-STATUS.md`.

2026-09-30. User explicitly requested collaboration between the two Codex sessions.
This is a handoff for the benchmark/research-workflow agent, not a merge or acceptance receipt.
The handoff is also copied beside that agent's report files; receipt/read acknowledgement is unknown.

## Verified current state

- UI checkout: `/Users/hunternovotny/Desktop/Project-ALPHA`, branch `feat/agentic-benchmark`, base e54aa7a, uncommitted terminal/auth/archive work.
- Research checkout: `/private/tmp/alpha-research-workflow-20260930`, branch `feat/research-workflow-completion`, clean at 8d0db28 when inspected. Its archived implementation gate says full PASS; this does not validate the combined tree.
- Research candidate panel is still running. Completed trajectory metadata inspected: R06 classifier, 19 calls; R08 regime, 34 calls. The research agent reports classifier artifact metrics matched independent calibration and compares 19 calls with 26 for baseline blocked work. Final paired scoring is pending; no general improvement conclusion yet.

## Information for the research agent

UI now uses local click confirmation by owner request (ADR-0038), not mandatory biometric presence. V6 preserves historical WebAuthn receipts and records local-confirmation method honestly. Do not restore mandatory Touch ID wording when integrating documentation.

External archive charts discover 2,178 compatible exact datasets, then verify selected normalized bytes/raw lineage and completed-bar cutoff. Archive identity, venue, market type and volume units remain separate from canonical strategy context. An archive chart is NOT a verified research snapshot, admitted data or point-in-time availability proof. Weekly classifier inputs must continue requiring the canonical immutable snapshot and cutoff.

UI verification: 4,740 Python tests, 314 frontend unit tests, 196 browser scenarios passed. A concurrent heavy-load ML cancellation test failed once; isolated and final broad tests passed without deadline changes. Full root gate is blocked by 198 lint errors in the earlier PDF scratch script `tmp/pdfs/alpha-benchmark-2026-09-30/build_report.py`. Please move or clean that scratch work as its owner when appropriate; this session has not edited it.

Read `docs/audit/2026-09-30-terminal-usability.md` and `docs/audit/2026-09-30-open-source-component-review.md` in the UI checkout. Existing chart/CCXT/Qlib/Nautilus boundaries are retained. Dockview/Perspective/TA-Lib/OpenBB adapters are candidates, not installed capabilities. Your PydanticAI migration should likewise be compared against completed evidence per budget and verified isolation, not adopted just for more roles.

## Proposed split and next integration

1. Research agent owns remaining candidate trials, corrected paired scoring, classifier/regime/variant-budget semantics and CLI evidence contracts. Please publish final outcomes, exact JSON artifact contract, retained limits and reproducible baseline commands. Do not change this UI checkout during its verification.
2. UI agent owns terminal interactions, archive charts, local confirmation and future presentation of your measured diagnostics. Next useful shared owner journey: select a verified canonical snapshot and cutoff, run one bounded baseline diagnostic, inspect chronological benchmark/economic results and artifact provenance, then obtain specialist review. Show completed null evidence separately from an honest blocked workflow.
3. Add a narrow typed read/job seam for the diagnostic only after its CLI contract is accepted. Web should call CLI; numerical computation stays in Python. Do not silently feed archive bars into the classifier or expose arbitrary code execution.
4. Preserve both changesets before combining. Current same-file overlap is only CLAUDE.md, BUILD-STATUS and generated atlas files. Merge manual decisions deliberately, retain append-only history and regenerate atlas; do not merge generated JSON by hand. New CLI registration may require refreshing the web command catalogue/OpenAPI/static assets on the combined tree.
5. Run combined-tree backend, frontend, quant-source verification where applicable, independent review and full gate. Separate prior branch passes are not a combined acceptance.

## Requested reply

The research agent can leave `ui-coordination-reply.md` beside this copy in `/private/tmp/alpha-workflow-report/`, listing final panel results, contract stability, remaining blockers and any conflicting ownership. No reply has been received as of this handoff.

## Research branch closure received

The separate checkout delivered clean closure commit
`09418e59ff44f0f34962856102d164f5e5a2b3ad`, parent implementation `8d0db28`, base `e54aa7a`.
Its delivery reports all six components passing and independent approval on its own tree
`a95f68a0a3251525a81c7a7bf7a92a578e0344ef6f72b194a7db480181104d76`.
The main agent verified the commit log and read the immutable delivery handoff. These are
separate-checkout receipts, not combined acceptance. No bundle, helper or branch merge has been
applied during the connected edge workspace implementation. Later integration still needs diff
review, explicit ownership of overlapping docs and whole-tree verification.
