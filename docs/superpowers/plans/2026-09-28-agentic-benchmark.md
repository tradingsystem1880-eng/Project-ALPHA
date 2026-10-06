**Delivery state:** Completed (2026-09-29; baseline complete; see docs/audit/2026-09-28-agentic-benchmark-baseline.md). Second scenario set: docs/superpowers/plans/2026-09-29-realistic-research-scenarios.md.

# Agentic research benchmark (`tools/alpha-eval`)

```json
{
  "schema_version": 1,
  "title": "Agentic research benchmark (alpha-eval)",
  "context": "Owner requested a reusable benchmark that measures PROJECT-ALPHA as an agentic quant-research system and exposes weaknesses in separating real from false edge. Approved 2026-09-28: SUT Sonnet 5 (~40 scenarios x 3 trials), judge Opus 5.5, Codex as second judge and as SUT on a ~10-scenario subset, protected edits (gate component, codex_bridge judge kind) under independent review.",
  "assumptions": [
    {"statement": "The benchmark drives the platform only through the public alpha CLI and MCP subprocess seams and never imports alpha_* except in the world builder, which uses public alpha_data store APIs.", "verified_by": "tools/alpha-eval has its own pyproject without alpha_* deps; grep for 'import alpha_' limited to worlds/build.py"},
    {"statement": "Every trial is isolated from owner state by ALPHA_DATA_DIR/ALPHA_BULK_DATA_DIR, a cwd outside the repo, --strict-mcp-config and an answer-key-free workspace (git archive of HEAD minus tools/alpha-eval, no .git/.env/data).", "verified_by": "per-trial before/after hash of data/control and git status recorded in each trial summary; canary tests"},
    {"statement": "Runtime behaviour, authority and numerical results of the platform are unchanged.", "verified_by": "no edits under packages/ or apps/; gate.py full"}
  ],
  "alternatives_considered": [
    "Pure LLM-judge benchmark without deterministic probes: rejected, Layer A gives cheap non-LLM truth on the platform's own gates.",
    "Separate external blinded runner service (Codex's recommendation): adopted in spirit via separate world/SUT/adjudication boundaries inside one tool rather than a new service.",
    "An in-repo MCP tool-call ledger: rejected for this change (frozen MCP surface); trajectories are captured client-side from stream-json."
  ],
  "pre_mortem": [
    "SUT reads answer keys from tools/alpha-eval or git history: SUT workspace is a git archive without tools/alpha-eval or .git, Bash(git:*) and Read of the repo are denied, and a canary string in truth blocks flags contamination. allowedTools is not an OS boundary; this residual risk is documented in tools/alpha-eval/README.md.",
    "SUT mutates owner data/control via an unscoped CLI call: ALPHA_* env is set on the claude process and the MCP config; integrity hashes before/after each trial fail the trial loudly.",
    "LLM judge rewards verbosity or keyword stuffing: known-bad synthetic trajectories must fail; uncited scores become grading_failure, not dropped.",
    "Planted 'real edge' too weak to detect so a correct rejection is scored as a miss: every world declares analytic power and allowed verdicts are power-aware."
  ],
  "slices": [
    {"title": "1 Package scaffold, models, stats, deterministic checks, known-bad scorer tests", "verify": "cd tools/alpha-eval && uv run pytest -q", "expected": "Known-bad trajectories fail for the intended reasons", "rollback": "Delete tools/alpha-eval", "status": "done"},
    {"title": "2 World builder and Layer A platform probes", "verify": "cd tools/alpha-eval && uv run alpha-eval probe --seeds 40 --out <dir>", "expected": "Probe results classified with Wilson CIs; no writes outside the sandbox", "rollback": "Remove probes module", "status": "done"},
    {"title": "3 Sandbox, Claude/Codex SUT harness, trajectory normalisation", "verify": "smoke scenarios A04/A09/ADV12 on Claude and A04 on Codex; owner_state_unchanged and canary_leaked recorded per trial", "expected": "Canary and integrity checks pass; trajectory.jsonl produced", "rollback": "Remove harness module", "status": "done"},
    {"title": "4 Judges (Claude, Codex bridge judge kind) and reports/compare", "verify": "golden-trajectory judge tests; /review-gate for scripts/codex_bridge.py", "expected": "Schema-valid, evidence-cited scores; grading failures visible", "rollback": "Revert bridge judge kind", "status": "done"},
    {"title": "5 Scenario catalog, baseline run, analysis, regression cases, gate component", "verify": "uv run python scripts/gate.py full", "expected": "Baseline summary committed; eval component green", "rollback": "Remove component registration", "status": "done"}
  ],
  "tier_impact": ["protected"],
  "docs_to_update": ["docs/BUILD-STATUS.md", "docs/audit/2026-09-28-agentic-benchmark-baseline.md", "tools/alpha-eval/README.md"],
  "out_of_scope": ["Changing platform runtime behaviour to improve scores", "New MCP/REST/UI surfaces", "Owner approvals, D2, promotion or paper actions", "Editing tests/holdout"],
  "files": ["tools/alpha-eval/", "scripts/gate.py", "scripts/gate_components.py", "tests/unit/test_gate_components.py", "tests/unit/test_claude_harness_codex_bridge.py", "tests/holdout_seed/test_holdout_benchmark_defects.py", "scripts/codex_bridge.py", "scripts/schemas/", ".github/workflows/ci.yml", "docs/"]
}
```

Approved design: see the session plan (two layers — deterministic platform probes on planted-truth
worlds, and headless agent trajectory evals — scored by deterministic checks, critical-failure classes,
and evidence-cited rubric dimensions; results fingerprinted for version comparison).
