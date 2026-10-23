**Delivery state:** Local uncommitted candidate; exact-tree verification is recorded in task evidence

# Pinned Semgrep gate execution

```json
{
  "schema_version": 1,
  "title": "Pinned Semgrep gate execution",
  "context": "Both the repository Semgrep gate and its contract checker use unpinned uvx semgrep, so cached package metadata can change which version runs. Share one exact Semgrep 1.181.0 invocation and reject missing, failed, or mismatched tools without changing scan arguments or rules.",
  "assumptions": [
    {"statement": "The existing .semgrep/alpha.yml rules and caller argument lists remain unchanged.", "verified_by": "offline argument-preservation tests and the Semgrep gate"},
    {"statement": "A tool launch or version-check failure must fail the gate and leave no passing stamp.", "verified_by": "offline failure-path tests against the shared runner and gate stamp"}
  ],
  "alternatives_considered": ["Rejected adding Semgrep to application dependencies or changing root/worker lockfiles; keep this as isolated tooling.", "Rejected a new gate path; reuse gate.py semgrep and the existing contract checker through one shared runner."],
  "pre_mortem": ["A version mismatch might continue into scanning; stop before scan and return a nonzero result.", "A cold uvx bootstrap might mix install diagnostics into the version output; keep stdout and stderr separate and verify stdout exactly.", "A launcher failure might be treated as advisory; require both callers to fail and ensure the gate clears prior stamps.", "Refactoring argv could drop scan flags or findings; assert exact underlying argv in offline tests and run the public Semgrep gate."],
  "slices": [
    {"title": "1 Shared pinned runner and offline contract tests", "verify": "uv run pytest -q tests/unit/test_claude_harness_gate.py -k semgrep", "expected": "The shared runner pins and checks Semgrep 1.181.0, returns tool failures, preserves scan argv, and both callers route through it.", "rollback": "Remove the runner and restore each caller's prior direct invocation.", "status": "done"},
    {"title": "2 Fail-closed gate, docs, and review", "verify": "uv run ruff check scripts/semgrep_runner.py scripts/harness_quant.py scripts/check_semgrep_contracts.py tests/unit/test_claude_harness_gate.py; uv run mypy scripts/semgrep_runner.py scripts/harness_quant.py scripts/check_semgrep_contracts.py tests/unit/test_claude_harness_gate.py; independent review", "expected": "Tool failures and mismatches fail closed without a stamp; both caller argument sets and the existing rules remain unchanged.", "rollback": "Revert the gate adapter and docs while retaining the old scan rules.", "status": "done"}
  ],
  "tier_impact": ["protected", "determinism"],
  "docs_to_update": ["CLAUDE.md", "docs/BUILD-STATUS.md"],
  "out_of_scope": ["Application and worker dependency lockfiles", "Semgrep rules or scan scope", "New gate system", "Commits, pushes, merges, deployment, and private suites"],
  "files": ["scripts/semgrep_runner.py", "scripts/harness_quant.py", "scripts/check_semgrep_contracts.py", "tests/unit/test_claude_harness_gate.py", "CLAUDE.md", "docs/BUILD-STATUS.md", "docs/superpowers/plans/2026-10-22-pinned-semgrep-gate.md"]
}
```
