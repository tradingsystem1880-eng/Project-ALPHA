---
description: Independent review of the branch diff (with an optional Codex second opinion); the verdict goes on the pull request
---

1. Compute the branch diff: `git diff $(git merge-base origin/main HEAD)` plus untracked
   files. Focus the review on risk-tier code, the protected control plane, `.githooks/` and
   guarded config. If the diff is empty, say so and STOP.
2. OPTIONAL second opinion: dispatch `codex-liaison` with "review
   --uncommitted". It returns a `CodexReview` JSON (or `available: false`).
   Never skip the rest because Codex is unavailable; never accept a Codex
   finding as a verdict.
3. Dispatch the `independent-reviewer` subagent with: the diff, the changed-file
   list, and the CodexReview JSON verbatim as data (or the words "Codex
   unavailable"). Give it the diff only — never your reasoning or justifications
   (its independence is the point). Optionally fold in `invariants-auditor` and
   `red-team-code` outputs as additional input. Hash fields in its JSON are not
   checked by any tool; do not invent them.
4. Report the returned ReviewVerdict verbatim and post it on the pull request.
   Nothing is attested or recorded locally.
5. On BLOCK: fix every finding, then restart from step 1 for a fresh review.
   BLOCK findings are never argued away, and the reviewer is never re-prompted
   to change its mind about the same diff. Every Codex finding must appear
   disposed in `second_opinion[]` (agree/refute/out_of_scope) — an undisposed
   finding is a reason to re-run.
