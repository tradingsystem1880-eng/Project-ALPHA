---
description: Optional second-opinion review via the Codex CLI (graceful skip if unavailable)
argument-hint: [diff scope, defaults to git diff HEAD]
---

OPTIONAL extra check — the mandatory pipeline (/gate, /review-gate,
/verify-quant) never depends on this.

1. Check availability: `command -v codex`. If absent (or it errors on
   invocation, e.g. no quota), reply with one line — "codex unavailable —
   skipping second opinion" — and stop. Do not treat this as a failure.
2. If available, run a READ-ONLY second opinion on $ARGUMENTS (default:
   `git diff HEAD`), e.g.
   `codex exec --sandbox read-only "Review this diff for correctness, look-ahead bias, and statistical-convention errors: ..."`.
3. Relay its findings clearly labeled as a second opinion; fold any real
   findings into the normal fix→gate→review loop.
