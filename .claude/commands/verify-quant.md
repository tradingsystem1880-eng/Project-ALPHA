---
description: Verify the quant-scope diff against primary academic sources (executed oracles + numeric spot checks) and attest
---

1. Compute the quant-scope diff: `git diff HEAD` restricted to
   `gate.matches_quant` scope. If the diff is empty, say so and STOP — never
   attest an empty scope. List the quant-tier files:
   `uv run python -c "import sys; sys.path.insert(0,'scripts'); import gate; print(sorted(gate.scoped_changed_paths(gate.repo_root(), gate.matches_quant)))"`.
2. Dispatch the `quant-verifier` subagent with the diff and that file list. It
   follows `.agents/skills/quant-source-verification/SKILL.md`, EXECUTES the
   relevant `tests/oracles/` suites and numeric spot checks in its sandbox
   (Bash is limited to `uv run pytest tests/oracles …`, `python -c`, and
   `codex_bridge.py research`), and returns a QuantVerificationReport JSON
   with `files_reviewed`, `oracles_present`, `numeric_spot_checks`.
3. Pipe the JSON verbatim to
   `uv run python scripts/gate.py attest --kind quant`.
4. If the report is FAIL (any DISCREPANCY/UNVERIFIABLE claim, missing
   docstring citation, `oracles_present: false`, or a failed spot check):
   report each finding, fix the code / citation / add the oracle, and restart
   from step 1. Never edit the report to pass, never attest around a FAIL.
