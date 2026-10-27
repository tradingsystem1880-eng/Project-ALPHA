---
description: Independent review of the review-scope diff (with an optional Codex second opinion), then attest the verdict
---

1. Compute the review-scope diff: `git diff HEAD` restricted to `gate.matches_review`
   (risk-tier, protected control plane, `.githooks/` and guarded config — the scope the
   Git guard enforces; see step 2). If empty, say so and STOP.
2. Get the binding hashes:
   `uv run python -c "import sys; sys.path.insert(0,'scripts'); import gate; r=gate.repo_root(); print(gate.compute_tree_hash(r)); print(gate.scoped_diff_hash(r, gate.matches_risk)); print(sorted(gate.scoped_changed_paths(r, gate.matches_review)))"`
   (tree hash, risk-tier diff hash, review-scope files).
3. OPTIONAL second opinion: dispatch `codex-liaison` with "review
   --uncommitted". It returns a `CodexReview` JSON (or `available: false`).
   Never skip the rest because Codex is unavailable; never accept a Codex
   finding as a verdict.
4. Dispatch the `independent-reviewer` subagent with: the diff, both hashes,
   the review-scope file list, and the CodexReview JSON verbatim as data (or the
   words "Codex unavailable"). Give it the diff only — never your reasoning or
   justifications (its independence is the point). Optionally fold in
   `invariants-auditor` and `red-team-code` outputs as additional input.
5. Pipe the returned ReviewVerdict JSON verbatim to
   `uv run python scripts/gate.py attest --kind review`.
6. On BLOCK: fix every finding, then restart from step 1 for a fresh review.
   BLOCK findings are never argued away, and the reviewer is never re-prompted
   to change its mind about the same diff. Every Codex finding must appear
   disposed in `second_opinion[]` (agree/refute/out_of_scope) — an undisposed
   finding is a reason to re-run, not to attest.
