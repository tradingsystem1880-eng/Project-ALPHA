---
description: Verify the quant-scope diff against primary academic sources and attest
---

1. Compute the quant-scope diff: `git diff HEAD` restricted to
   `packages/alpha-validation/src`, `packages/alpha-research/src`, and any
   quant-named module (dsr/psr/pbo/deflated/bootstrap/reality_check/spa/
   montecarlo/walkforward/cpcv/multiple_testing/overfitting) under
   `packages/*/src`. If the diff is empty, say so and STOP — never attest an
   empty scope.
2. Dispatch the `quant-verifier` subagent with the diff. It follows
   `.agents/skills/quant-source-verification/SKILL.md` and returns a
   QuantVerificationReport JSON.
3. Pipe the JSON verbatim to
   `uv run python scripts/gate.py attest --kind quant`.
4. If the report is FAIL (any DISCREPANCY/UNVERIFIABLE claim or missing
   docstring citation): report each finding, fix the code or citation, and
   restart from step 1. Never edit the report to pass, never attest around a
   FAIL.
