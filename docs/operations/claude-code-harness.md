# Claude Code Harness (agent operating system, harness v1)

Installed 2026-08-18. The repo previously relied on prose (CLAUDE.md) that agents had to
voluntarily obey; this harness makes the load-bearing rules mechanical, structured as
SR 11-7's three lines of defense: development standards (tiered gate, TDD pipeline,
per-edit lint), independent validation with effective challenge (fresh-context reviewers,
schema-validated verdicts, academic cross-referencing for statistical code), and
governance (append-only audit, authority denials, a self-protecting control plane).

## Components

| Piece | Path | Role |
|---|---|---|
| Gate runner | `scripts/gate.py` | `fast\|full\|check\|attest\|override\|ack\|doctor`; tree hash; stamps; audit journal |
| Artifact schemas | `scripts/harness_models.py` | Pydantic v2 strict models validated at every write |
| Hooks | `scripts/claude_hooks.py` | Seven stdlib-only hook entrypoints (argv dispatch) |
| Wiring | `.claude/settings.json` | Permissions allow/deny, hook registration, statusline (committed) |
| Statusline | `.claude/statusline.py` | branch · dirty count · stamp state · pending obligations |
| Skill stubs | `.claude/skills/*/SKILL.md` | Auto-discovery stubs → canonical `.agents/skills/` (drift-guarded by test) |
| Subagents | `.claude/agents/*.md` | navigator, test-architect, quant-verifier, invariants-auditor, independent-reviewer, adversarial-reviewer |
| Commands | `.claude/commands/*.md` | plan-feature, implement, gate, gate-fast, verify-quant, review-gate, adversarial-review, harness-doctor, codex-review, retrospective |
| Awareness (v2) | `gate.py brief` / `gate.py index` / `.claude/rules/*.md` | Generated session brief (SessionStart/PostCompact), `.claude/state/repo-index.json`, path-scoped rules holding the relocated MODULE MAP (drift-tested by `tests/unit/test_claude_md_relocation.py` and `test_repo_awareness_drift.py`) |
| Reasoning (v2) | `gate.py plan-check` / `harness_models.FeaturePlan` | Plan docs open with a ```json front block (assumptions with `verified_by`, ≥1 alternative, ≥2 pre-mortem, slices with verify/expected/rollback, tier impact, out-of-scope); `/implement` refuses to start without a passing check; edits outside the open plan's declared `files[]` are warn-only `over_eager_edit` audit events surfaced in the Stop/PostCompact brief; `/retrospective` writes `docs/operations/retrospectives/YYYY-MM-DD-<slug>.md` whose `## Watch-outs` feed the next session brief |
| Tests | `tests/unit/test_claude_harness_{gate,hooks,skills}.py` | TDD coverage of every decision function |

## Tree-hash stamp protocol

`gate.compute_tree_hash()` stages the entire working tree (tracked + untracked,
gitignore-respected) into a THROWAWAY git index and hashes the resulting tree object id.
It is a pure content hash: any byte change anywhere invalidates it; a pure `git commit`
(no bytes change) does not — so an atomic commit sequence needs exactly one full gate run.
`.claude/state/` is gitignored, so harness bookkeeping never perturbs the hash.

- `gate.py fast` — ruff check, ruff format --check, lint-imports, mypy (repo + harness).
- `gate.py full` — uv lock --check, uv sync --locked, fast steps, pytest -m "not network"
  --cov, OpenAPI freshness, uv build --all-packages, 13-wheel import smoke (byte-mirrors
  `.github/workflows/ci.yml`).
- The stamp is deleted at gate start and written only on full success; `check --tier
  fast|full` exits 0 iff a stamp of at least that tier matches the current tree (`full`
  satisfies `fast`, never the reverse).

## Hooks (all in `scripts/claude_hooks.py`, wired in `.claude/settings.json`)

| Hook | Event | Blocks when | Cleared by |
|---|---|---|---|
| `post-edit` | PostToolUse Edit\|Write | edited `*.py` fails per-file ruff (frontend: eslint when node_modules present) | fixing the lint finding |
| `pre-edit-guard` | PreToolUse Edit\|Write | target is protected control plane | `gate.py ack --reason` (one-shot) |
| `pre-bash-guard` | PreToolUse Bash | `git commit` without a full stamp (docs-only waived); non-conventional message; >1000 non-docs lines; risk-tier staged without APPROVE verdict | `/gate`, message fix, split, `/review-gate`; or `gate.py override --reason` (one-shot) |
| `stop-guard` | Stop | source edits without fast stamp; quant edits without PASS attestation (max 3 blocks/session, then allow with warning) | `/gate-fast`, `/verify-quant` |
| `session-start` | SessionStart | never (injects the working contract + doctor warnings) | — |
| `prompt-context` | UserPromptSubmit | never (3-line situational brief) | — |
| `pre-compact` | PreCompact | never (compaction guidance) | — |

Hook root resolution derives from the payload cwd via `git rev-parse --show-toplevel`
(worktree-correct); `$CLAUDE_PROJECT_DIR` resolves to the main checkout in worktrees, so
the wiring falls back to the relative path and exits 0 when the script is absent. A
crashing hook fails open — a broken harness must never brick the session.

## Path tiers

- **Quant** (`gate.matches_quant`): `packages/alpha-validation/src/**`,
  `packages/alpha-research/src/**`, plus any module named
  `dsr|psr|pbo|deflated|bootstrap|reality_check|spa|montecarlo|walkforward|cpcv|multiple_testing|overfitting`
  under `packages/*/src`. Requires a PASS `QuantVerificationReport` bound to the
  quant-scope diff hash (out-of-scope edits do not invalidate it).
- **Risk** (`gate.matches_risk`): quant + `packages/alpha-backtest/src/**` + the seven
  `alpha_cli` modules `_gauntlet/_optim/_seeds/_identity/_surrogate/_synth/_runner`.
  Requires an APPROVE `ReviewVerdict` bound to the exact current tree hash.
- **Protected control plane** (`gate.protected_reason`): the three harness scripts,
  `.claude/settings.json`, `.claude/skills/**`, `tests/bias_guards/**`,
  `.github/workflows/ci.yml`, `CLAUDE.md`, and `pyproject.toml` edits whose content
  touches `[tool.importlinter]` / `fail_under` / `strict`. Requires a one-shot ack.

## Artifacts and audit

Every persisted artifact is validated by `scripts/harness_models.py` at write time;
malformed input is rejected loudly and nothing is written. A `QuantVerificationReport`
with `overall: PASS` cannot contain non-VERIFIED claims or missing citations (model
validator). Every stamp write, attestation, block, override, and ack appends an
`AuditEvent` (timestamp, session, event, detail, tree hash) to
`.claude/state/harness-audit.jsonl` — append-only, per-machine, gitignored.

One-shot tokens: `override` (bypasses the commit gate once), `ack` (permits one
control-plane edit). Both are consumed on use and audited at write and consume.

## Operations

- `python3 scripts/gate.py doctor` — verifies settings parse, all seven hooks wired,
  scripts present, statusline present, state dir writable, stub↔canonical sync.
  SessionStart runs it automatically and warns loudly.
- Statusline shows `branch · ±dirty · gate:tier✓/stale/none · needs:…` every prompt.
- **Emergency recovery**: delete `.claude/state/` (stamps/tokens/session state; the
  audit journal goes with it), or set `ALPHA_HARNESS_DISABLE=1` to bypass all hooks.
  The main checkout's `.git/info/exclude` blanket-ignores `.claude/`, so NEW files
  under `.claude/` need `git add -f` once; tracked ones behave normally.
- Write paths (`attest`/`override`/`ack`) need pydantic and re-exec themselves under
  `.venv/bin/python` when invoked as plain `python3`.

## Known limitations (process controls, not cryptography)

- Attestations prove that a validated artifact was written for a given tree/diff hash,
  not who wrote it; the audit journal preserves what was attested and when.
- Bash-mediated file writes bypass the edit guards (they are caught at commit time by
  the stamp, which any content change invalidates). Batch control-plane writes should
  append an explicit `control_plane_batch_write` audit event.
- The Stop guard sees files edited via Edit/Write tools; Bash-only edit sessions are
  caught at commit, not at Stop.
- `/codex-review` is optional and gracefully skips when the `codex` binary is absent or
  quota-less; nothing mandatory depends on it.

## Deferred (needs runtime changes; own ADR-governed efforts)

1. Cross-session trial ledger feeding family-wise trial counts into single-run DSR
   (López de Prado complete trial accounting).
2. Standing backtest-vs-paper divergence monitor (SR 11-7 outcomes analysis).
3. Named multi-agent Workflow scripts under `.claude/workflows/` for review sweeps.
