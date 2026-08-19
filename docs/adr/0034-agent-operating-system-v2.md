# ADR-0034: Agent operating system v2 — owner-token authorization, oracle test tiers, second-model review seam

**Status:** Accepted
**Date:** 2026-08-19
**Deciders:** Project ALPHA owner and AI build agents

## Context

Harness v1 (2026-08-18) made the load-bearing CLAUDE.md rules mechanical: a tree-hash gate
stamp, commit/stop guards, schema-validated attestations, a protected control plane, six
subagents. A repo gap audit (45 findings), the agentic-coding reliability literature and the
quant model-risk literature (SR 11-7 three lines of defense, mutation testing, metamorphic
relations, known-truth calibration, hash-chained audit) showed the remaining holes shared three
roots: (a) the agent could authorize its own escape hatches, (b) statistical code was tested
against goldens it could have frozen wrong, and (c) every check ran inside one model's context,
so a plausible-but-wrong claim had no independent challenger.

The owner's decisions for v2: harness + test layer only (no runtime behavior change, no DAG
contract change); owner-token authorization for escapes; CLAUDE.md restructured into a < 200-line
core plus path-scoped rules with zero-loss drift tests; slow oracles nightly and on-touch; the
Karpathy guidelines always on mechanically; and Codex — via the ChatGPT-authenticated CLI, model
`gpt-5.3-codex-spark` — as an optional second model for review and research.

## Decision

1. **Owner-token authorization.** `gate.py override|ack|baseline` require `ALPHA_OWNER_TOKEN`
   when the owner token is configured; unset (the owner's 2026-08-19 decision), every escape is
   agent self-serve and audited — the logbook `gate.py audit --digest` is the control. When
   configured, its sha256 matches `.claude/settings.local.json:ownerTokenHash` (`gate.py owner-init`,
   interactive, once). *(Correction, 2026-08-19: the implementation stores the hash in
   `.claude/owner.local.json`, not in `settings.local.json`. `gate.py:OWNER_FILE` is
   authoritative; see `docs/operations/claude-code-harness.md`.)*
   Until the owner configures it, escapes are agent self-serve but audited
   as `authorized_by: agent (owner token not configured)` and flagged in the statusline, brief
   and doctor. With the token configured, agents may still ack ≤ 3 low-risk text edits per
   session (`.claude/agents|commands|rules`), nothing else. Attestations bind to the scoped
   diff hash of their tier (`QuantAttestation.bound_quant_diff_hash`,
   `ReviewVerdict.reviewed_diff_hash`) and to the file list, not only to the tree.
2. **Oracle test tiers for statistical code.** Every public statistical primitive must be
   wrong-detectable by at least one of: metamorphic relations (`tests/oracles/test_metamorphic_*`),
   known-truth calibration with Wilson/binomial tolerances (`slow_oracle`), or a differential
   oracle against a test-only reference transcription (`tests/oracles/_reference/`). The engine
   has an independent P&L re-derivation; bias guards carry must-fail leaky twins; a hidden
   holdout suite (`tests/holdout/`, author-agent unreadable) runs in the full gate; the mutation
   gate (`gate.py mutate`, kill-rate ≥ 0.90 or the module's recorded baseline floor) and
   `.semgrep/alpha.yml` run on-touch, with the whole sweep plus determinism double-run and
   raise-site coverage nightly. `/verify-quant` now executes oracles and numeric spot checks
   rather than reading only.
3. **Second-model review seam (optional, graceful).** `scripts/codex_bridge.py` runs
   `codex exec` read-only, ephemeral, output-schema-bound and wall-clock capped; results are
   `CodexReview`/`CodexResearch` JSON with instruction-shaped text stripped; every failure mode
   is `available: false` + `unavailable:<reason>` and exit 0. Only the `codex-liaison` agent may
   call it; the `independent-reviewer` disposes of each Codex finding
   (`agree|refute|out_of_scope`) in `ReviewVerdict.second_opinion[]`; Codex never attests,
   writes, or approves. `.mcp.json` registers `codex mcp-server` (Spark, read-only) for
   interactive use. Every mandatory gate must pass with Codex absent.
4. **Awareness and reasoning as generated artifacts.** Session brief and repo index are derived
   from the tree; MODULE MAP and CLI surface live in `.claude/rules/*.md` (relocation proven
   byte-for-byte by `tests/unit/test_claude_md_relocation.py`); plans carry a `FeaturePlan`
   JSON block (assumptions, alternatives, pre-mortem, per-slice verify/rollback, out-of-scope);
   `/retrospective` closes the loop into rules. Karpathy guidelines are injected at
   SessionStart/PostCompact and preloaded into every subagent; sandboxed subagents' Bash is
   allow-listed (`claude_hooks.AGENT_BASH_ALLOW`); JSON-only agents are schema-checked at
   SubagentStop.

## Consequences

- Author ≠ approver by construction: owner token, fresh-context reviewers, a different model
  family where available, and holdout tests the author never reads.
- Statistical goldens can no longer freeze a wrong answer silently: a sign, threshold or
  annualization bug now fails a metamorphic relation or a calibration bound, and a test that
  cannot kill a mutant is visible in the mutation report.
- Cost: `gate.py full` runs slow oracles and the mutation gate only when a quant source module
  changed; the nightly job (`.github/workflows/nightly.yml`, up to 6 h) carries the sweep.
  Renderer-heavy modules carry low but honest mutation floors (`timeout`/`no_tests` mutants are
  never credited as kills).
- Codex adds review breadth without authority; when quota, login, or the model cache is missing
  the pipeline is unchanged and the skip is audited.
- Known limitations are process controls, not cryptography: attestations prove an artifact was
  written for a hash, Haiku prompt hooks are advisory, the audit journal is per-machine, and
  `raise-cov` stays report-only until its 177/576 backlog is paid down. Runtime-side follow-ups
  (trial ledger, backtest-vs-paper divergence monitor, PROV lineage) are deferred to their own
  ADRs.

## Evidence anchors

- `docs/operations/claude-code-harness.md` (v2 sections), `scripts/{gate,claude_hooks,
  harness_models,codex_bridge}.py`, `.claude/settings.json`, `.claude/rules/*.md`,
  `.claude/agents/*.md`, `.mcp.json`, `.semgrep/alpha.yml`, `.claude/mutation-baseline.json`.
- Tests: `tests/unit/test_claude_harness_{gate,hooks,hooks_subprocess,settings,skills,
  codex_bridge}.py`, `tests/unit/test_claude_md_relocation.py`,
  `tests/unit/test_repo_awareness_drift.py`, `tests/oracles/**`, `tests/holdout_seed/**`,
  `tests/bias_guards/test_poison_variants.py`.
- CI: `.github/workflows/ci.yml` (`harness` job), `.github/workflows/nightly.yml`.
