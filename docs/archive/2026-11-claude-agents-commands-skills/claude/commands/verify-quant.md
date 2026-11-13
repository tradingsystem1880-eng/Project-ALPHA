---
description: Verify the quant-scope diff against primary academic sources (executed oracles + numeric spot checks); the report goes on the pull request
---

1. Compute the quant-scope diff: `git diff $(git merge-base origin/main HEAD)` restricted to
   `gate.matches_quant` scope. If the diff is empty, say so and STOP. List the quant-tier files:
   `uv run python -c "import sys; sys.path.insert(0,'scripts'); import gate; print(sorted(gate.scoped_changed_paths(gate.repo_root(), gate.matches_quant)))"`
   (uncommitted changes; add the branch's committed quant files from the diff above).
2. Dispatch the `quant-verifier` subagent with the diff and that file list. It
   follows `.agents/skills/quant-source-verification/SKILL.md`, EXECUTES the
   relevant `tests/oracles/` suites and numeric spot checks in its sandbox
   (Bash is limited to `uv run pytest tests/oracles …`, `python -c`, and
   `codex_bridge.py research`), and returns a QuantVerificationReport JSON
   with `files_reviewed`, `oracles_present`, `numeric_spot_checks`.
3. Report the JSON verbatim and post it on the pull request. Nothing is attested
   locally; CI separately runs the slow oracles and mutation on touched quant modules.
4. If the report is FAIL (any DISCREPANCY/UNVERIFIABLE claim, missing
   docstring citation, `oracles_present: false`, or a failed spot check):
   report each finding, fix the code / citation / add the oracle, and restart
   from step 1. Never edit the report to pass.
