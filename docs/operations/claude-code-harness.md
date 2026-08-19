# Claude Code Harness (agent operating system, harness v2)

v1 installed 2026-08-18; v2 ("10x") landed 2026-08-19 (ADR-0034). The repo previously
relied on prose (CLAUDE.md) that agents had to voluntarily obey; the harness makes the
load-bearing rules mechanical, structured as SR 11-7's three lines of defense: development
standards (tiered gate, TDD pipeline, per-edit lint, plan schema), independent validation
with effective challenge (fresh-context reviewers, schema-validated verdicts, academic
cross-referencing and executed oracles for statistical code, an optional second model),
and governance (owner-token escapes, hash-chained audit, authority denials, a
self-protecting and self-testing control plane).

v2 principles: verify **state, never claims** (every "done" is a re-executed check on the
tree); independence by construction (author ≠ approver: owner token, fresh-context
reviewers, a second model family where available, hidden holdout tests the author never
sees); the harness tests itself in CI; awareness is generated from the tree, not remembered;
reasoning is a required artifact (plan schema, retrospectives); statistical code has
oracles, not just tests; Karpathy guidelines are always on, mechanically.

## Components

| Piece | Path | Role |
|---|---|---|
| Gate runner | `scripts/gate.py` | `fast\|full\|check\|attest\|override\|ack\|owner-init\|lint-harness\|baseline\|audit\|brief\|index\|plan-check\|doctor\|selftest\|mutate\|semgrep\|determinism\|raise-cov`; tree hash; stamps; hash-chained audit journal |
| Artifact schemas | `scripts/harness_models.py` | Pydantic v2 strict models validated at every write: `QuantVerificationReport`, `ReviewVerdict`, `InvariantFindings`, `DriftFindings`, `Counterexamples`, `CodexReview`, `CodexResearch`, `FeaturePlan` |
| Hooks | `scripts/claude_hooks.py` | Seventeen stdlib-only hook entrypoints (argv dispatch) + one advisory `prompt` hook |
| Wiring | `.claude/settings.json` | Permissions allow/deny (24 deny rules), hook registration, statusline (committed) |
| Statusline | `.claude/statusline.py` | branch · dirty count · stamp state · pending obligations · owner-token / stop-budget flags |
| Skill stubs | `.claude/skills/*/SKILL.md` | Auto-discovery stubs → canonical `.agents/skills/` (drift-guarded by test; `karpathy-guidelines` byte-synced with the plugin copy) |
| Rules | `.claude/rules/*.md` | `00-karpathy.md` (unscoped, always loaded) + path-scoped `alpha-*.md`, `quant.md`, `tests.md`, `docs.md` holding the relocated MODULE MAP / CLI surface / tier duties (`tests/unit/test_claude_md_relocation.py` proves zero loss vs `tests/fixtures/claude_md_v1.md`) |
| Subagents | `.claude/agents/*.md` | navigator (memory: project), test-architect, quant-verifier (sandboxed Bash: oracle suites, `python -c` spot checks, `codex_bridge.py research`), numerical-verifier, invariants-auditor, independent-reviewer (runs tests + hidden holdout, disposes Codex findings), red-team-code, docs-drift-checker, adversarial-reviewer, retrospective (memory: project), codex-liaison (the only Codex caller). JSON-only agents are schema-checked at SubagentStop; sandboxed agents' Bash is allow-listed per `claude_hooks.AGENT_BASH_ALLOW` |
| Commands | `.claude/commands/*.md` | plan-feature, implement, gate, gate-fast, verify-quant, review-gate, adversarial-review, harness-doctor, codex-review, codex-research, second-opinion, retrospective |
| Awareness (v2) | `gate.py brief` / `gate.py index` / `.claude/rules/*.md` | Generated session brief (SessionStart/PostCompact), `.claude/state/repo-index.json`, path-scoped rules holding the relocated MODULE MAP (drift-tested by `tests/unit/test_claude_md_relocation.py` and `test_repo_awareness_drift.py`) |
| Reasoning (v2) | `gate.py plan-check` / `harness_models.FeaturePlan` | Plan docs open with a ```json front block (assumptions with `verified_by`, ≥1 alternative, ≥2 pre-mortem, slices with verify/expected/rollback, tier impact, out-of-scope); `/implement` refuses to start without a passing check; edits outside the open plan's declared `files[]` are warn-only `over_eager_edit` audit events surfaced in the Stop/PostCompact brief; `/retrospective` writes `docs/operations/retrospectives/YYYY-MM-DD-<slug>.md` whose `## Watch-outs` feed the next session brief |
| Codex seam (v2) | `scripts/codex_bridge.py`, `scripts/schemas/codex_*.json`, `.mcp.json` `codex` server | Optional second model (`gpt-5.3-codex-spark` via the ChatGPT-authenticated Codex CLI); read-only, ephemeral, schema-bound, audited, graceful skip |
| Quant-rigor tests (v2) | `tests/oracles/**`, `tests/holdout/**`, `tests/bias_guards/**`, `.semgrep/alpha.yml`, `.claude/mutation-baseline.json` | Metamorphic / calibration / differential oracles, P&L re-derivation, hardened poison guards with leaky twins, hidden holdout, mutation + semgrep + determinism + raise-site sweeps |
| Tests | `tests/unit/test_claude_harness_{gate,hooks,hooks_subprocess,settings,skills,codex_bridge}.py` | TDD coverage of every decision function; the subprocess suite drives the real hook script; CI `harness` job runs doctor + block-smoke + `mypy scripts` + `--cov=scripts` |

## Tree-hash stamp protocol

`gate.compute_tree_hash()` stages the entire working tree (tracked + untracked,
gitignore-respected) into a THROWAWAY git index and hashes the resulting tree object id.
It is a pure content hash: any byte change anywhere invalidates it; a pure `git commit`
(no bytes change) does not — so an atomic commit sequence needs exactly one full gate run.
`.claude/state/` is gitignored, so harness bookkeeping never perturbs the hash.

- `gate.py fast` — ruff check, ruff format --check, lint-imports, mypy (repo + harness),
  `lint-harness`, semgrep on changed files.
- `gate.py full` — uv lock --check, uv sync --locked, fast steps, pytest -m "not network"
  --cov (holdout included), OpenAPI freshness, uv build --all-packages, 13-wheel import smoke
  (byte-mirrors `.github/workflows/ci.yml`); when a quant SOURCE module changed it also
  runs the `slow_oracle` suites and the mutation gate for those modules.
- The stamp is deleted at gate start and written only on full success; `check --tier
  fast|full` exits 0 iff a stamp of at least that tier matches the current tree (`full`
  satisfies `fast`, never the reverse).

## Hooks (all in `scripts/claude_hooks.py`, wired in `.claude/settings.json`)

| Hook | Event (matcher) | Blocks when | Cleared by |
|---|---|---|---|
| `pre-edit-guard` | PreToolUse Edit\|Write\|MultiEdit | target is protected control plane, or hidden holdout | `gate.py ack --reason --path` (one-shot; owner token or bounded agent self-ack) |
| `pre-read-guard` | PreToolUse Read | target is under `tests/holdout/` (author never sees it) | owner reads by hand |
| `pre-bash-guard` | PreToolUse Bash | `git commit` without a full stamp (docs-only waived); non-conventional message; >1000 non-docs lines; risk-tier staged without APPROVE verdict bound to the tree + scoped diff; git verbs that would render hidden-holdout content (`show/diff/log -p/blame/grep/cat-file`); destructive verbs (`commit --amend/--no-verify`, `reset --hard`, `checkout -- .`, `clean -f`, `stash drop`, `rm -rf` outside scratchpad); shell writes (`>`, `sed -i`, `tee`, heredoc `open(...,'w')`) to protected/holdout paths without ack; sandboxed subagent outside its `AGENT_BASH_ALLOW` prefixes | `/gate`, message fix, split, `/review-gate`; or `gate.py override --reason` (one-shot, owner-authorized) |
| `pre-mcp-guard` | PreToolUse `mcp__alpha__.*\|mcp__codex__.*` | owner-authority MCP verbs (approve/reject/decide/override-research-gate/reveal-holdout); Codex calls are logged | — |
| `post-edit` | PostToolUse Edit\|Write\|MultiEdit | edited `*.py` fails per-file ruff (frontend: eslint when node_modules present); every tracked edit is recorded in the session state file | fixing the lint finding |
| `post-bash` | PostToolUse Bash | never; records shell writes as edits, tracks obligations | — |
| `tool-log` | PostToolUse Agent\|Skill | never; audits subagent/skill dispatch | — |
| `post-tool-failure` | PostToolUseFailure Bash\|Edit\|Write\|MultiEdit | never; records the session state's `failures[]` (Stop brief lists unresolved; retrospective ingests) | — |
| `subagent-stop` | SubagentStop | a JSON-only agent's last message fails its schema (`JSON_AGENT_SCHEMAS`; `codex-liaison` = `CodexReview\|CodexResearch`) | re-run the agent |
| `task-completed` | TaskCompleted | a task marked complete while its named test file/command fails | make it pass |
| `config-change` | ConfigChange | settings/skills/agents/mcp changed without ack or owner token; audited | `gate.py ack` |
| `instructions-loaded` | InstructionsLoaded | never; records which CLAUDE.md/rules loaded (awareness telemetry) | — |
| `stop-guard` | Stop | source edits without fast stamp; quant edits without PASS attestation bound to the quant diff hash (3 blocks/session, then allow with `stop_budget_exhausted` audit + red statusline flag until the next passing gate) | `/gate-fast`, `/verify-quant` |
| `stop` prompt hook | Stop (`type: prompt`, Haiku, advisory) | transcript claims "should work / probably" about tests or skipped Karpathy §1–§3 — blocks once with the reason (shares the Stop budget) | state assumptions / run the check |
| `session-start` | SessionStart | never (working contract + owner-token warning + Karpathy block + generated repo brief + doctor warnings) | — |
| `prompt-context` | UserPromptSubmit | never (situational brief incl. `karpathy: think→simplify→surgical→goal-verify`) | — |
| `pre-compact` | PreCompact | never (compaction guidance) | — |
| `post-compact` | PostCompact | never (re-injects brief, Karpathy block, plan slice status, unattested obligations) | — |

Hook root resolution derives from the payload cwd via `git rev-parse --show-toplevel`
(worktree-correct); `$CLAUDE_PROJECT_DIR` resolves to the main checkout in worktrees, so
the wiring falls back to the relative path and exits 0 when the script is absent. A
crashing hook fails open — a broken harness must never brick the session.

## Owner-token authorization

`override`, `ack`, and `baseline` require `ALPHA_OWNER_TOKEN` in the environment whose sha256
matches the hash stored in `.claude/owner.local.json` (gitignored). Setup, once, interactively:

```bash
uv run python scripts/gate.py owner-init
```

then `export ALPHA_OWNER_TOKEN=<token>` in the owner's own shell — never in the shell that
launches Claude Code, since hooks inherit that environment and would grant the agent full owner
authority.

Until then every escape is agent self-serve, audited as
`authorized_by: agent (owner token not configured)` and flagged in the statusline, session
brief and doctor. With the token configured, an agent may still
ack ≤ 3 low-risk text edits per session (`.claude/agents|commands|rules`) — nothing else.

## Path tiers

- **Quant** (`gate.matches_quant`): `packages/alpha-validation/src/**`,
  `packages/alpha-research/src/**`, plus any module named
  `dsr|psr|pbo|deflated|bootstrap|reality_check|spa|montecarlo|walkforward|cpcv|multiple_testing|overfitting`
  under `packages/*/src`. Requires a PASS `QuantVerificationReport` bound to the
  quant-scope diff hash and naming every changed quant file (out-of-scope edits do not
  invalidate it; a post-attest change to any quant file does).
- **Risk** (`gate.matches_risk`): quant + `packages/alpha-backtest/src/**` + the seven
  `alpha_cli` modules `_gauntlet/_optim/_seeds/_identity/_surrogate/_synth/_runner`.
  Requires an APPROVE `ReviewVerdict` bound to the exact current tree hash AND the
  risk-scope diff hash.
- **Protected control plane** (`gate.protected_reason`): the four harness scripts
  (`gate`, `claude_hooks`, `harness_models`, `codex_bridge`), `.claude/settings.json`,
  `.claude/statusline.py`, `.claude/{harness,mutation}-baseline.json`, `.mcp.json`,
  `.semgrep/alpha.yml`, `CLAUDE.md`, `AGENTS.md`, `.claude/{skills,agents,commands,rules}/**`,
  `.codex/**`, `.github/workflows/**`, `tests/bias_guards/**`, `tests/holdout/**`,
  `tests/oracles/**`, `tests/unit/test_claude_harness_*`, the relocation/awareness drift
  tests, and `pyproject.toml` edits whose content touches `[tool.importlinter]` /
  `fail_under` / `strict`. Requires a one-shot ack. `gate.py lint-harness` (fast gate +
  PreToolUse) fails on any weakening vs `.claude/harness-baseline.json` (removed deny rules
  or hook wiring, lowered `fail_under`, deleted import-linter contracts or bias guards,
  disabled `--strict-markers`, `noqa`/`type: ignore` growth in quant modules).
- **Hidden holdout** (`tests/holdout/`): agents never read, edit or shell-write it (Read/Edit/
  Bash guards; git may stage/move it but never render its bytes); CI and the full gate run
  it, so a failure blocks the stamp and therefore every commit. Proposals go to
  `tests/holdout_seed/` and the owner `git mv`s them in.
- **Docs waiver** (commit gate only): `docs/**`, `*.md`, `.agents/skills/**/*.md`;
  `.claude/**` and `.codex/**` are never waived.

## Quant-rigor test layer (no runtime change)

Markers (`--strict-markers`): `bias_guard`, `network`, `oracle`, `slow_oracle`, `holdout`.
- **Metamorphic** (`tests/oracles/test_metamorphic_*.py`, `oracle`): SR scale/sign/√P
  relations; DSR(N=1)=PSR and monotonicity; PBO permutation invariance ≈0.5 on noise; bootstrap
  identities and seed determinism; split tiling/embargo; engine zero-signal / price-scaling /
  dividend-at-`pay_date`.
- **Known-truth calibration** (`test_calibration_*.py`, `slow_oracle`): analytic answers with
  Wilson/binomial tolerances (α documented per test); statistical goldens carry tolerances,
  never float `==`.
- **Differential** (`test_differential_*.py`, `slow_oracle`): test-only reference
  transcriptions under `tests/oracles/_reference/` (PSR/DSR closed forms, PBO, stationary
  bootstrap, BCa); no new runtime deps.
- **P&L re-derivation** (`test_pnl_rederivation.py`) from fills + fees + dividends against the
  golden equity curve.
- **Hardened poison guards** (`tests/bias_guards/test_poison_variants.py`): NaN/inf/outlier/
  time-reversed poison; every guard has a must-fail leaky twin.
- **Sweeps** (`gate.py`): `mutate` (mutmut per module in a staged tree; kill-rate ≥ 0.90 or the
  module's recorded baseline floor, whichever is lower; `timeout`/`no_tests` mutants never count
  as kills), `semgrep` (`.semgrep/alpha.yml`: `except: pass`, negative `.shift(-`,
  wall-clock time in packages, pandas outside the three sanctioned edges, float `==`, unseeded
  RNG, bare `type: ignore`, reasonless skips), `determinism` (goldens/identity tests twice under
  perturbed `PYTHONHASHSEED`/`TZ`), `raise-cov` (unreached `raise` sites in quant modules).
- **Scheduling:** fast gate = semgrep on changed files; full gate = holdout + (`slow_oracle` +
  mutation only when a quant SOURCE module changed); CI's `check` job runs every non-network
  test incl. `slow_oracle` on each push; `.github/workflows/nightly.yml` = mutation
  `--all --timeout 5400`, determinism, `raise-cov` (report-only), semgrep.
- `/verify-quant` requires `oracles_present` for every new public stat function, executes the
  oracle suites and numeric spot checks (quant-verifier sandbox; optional numerical-verifier),
  and primary-source citations per `.agents/skills/quant-source-verification/`.

## Subagents: sandbox, memory, schemas

- Every agent preloads `karpathy-guidelines`; reviewers/verifiers run at `effort: high` with
  explicit `disallowedTools` (never Edit/Write/NotebookEdit) and `maxTurns`.
- `AGENT_BASH_ALLOW` (in `claude_hooks.py`) is a per-`agent_type` tuple of command prefixes;
  redirections and command substitution are refused for sandboxed agents. Groups: git read-only,
  read-only tools (`grep/rg/ls/cat/head/tail/wc/find`, `uv run pytest`, `python -c`,
  `gate.py audit|check|brief|index|semgrep|raise-cov`), numeric tools (`uv run pytest
  tests/oracles`, `python -c`), and the Codex bridge. Main-session Bash is unaffected.
- `navigator` and `retrospective` carry `memory: project` (`.claude/agent-memory/`, gitignored);
  `/retrospective` summarises durable learnings into `.claude/rules`.
- JSON-only agents (`JSON_AGENT_SCHEMAS`) are validated at SubagentStop; malformed output is
  refused before it can be attested.

## Codex second-model seam (optional, graceful)

Verified locally on 2026-08-19: `codex-cli 0.146.0`, `codex login status` = "Logged in using
ChatGPT", `gpt-5.3-codex-spark` present in `~/.codex/models_cache.json` (efforts low→xhigh).
Using the ChatGPT-authenticated Codex CLI itself is the supported path (proxying that auth into
third-party clients remains rejected).

- `scripts/codex_bridge.py probe|review|research` runs `codex exec --skip-git-repo-check
  --ephemeral -s read-only -C <root> -m <model> -c model_reasoning_effort=… -c
  approval_policy="never" [-c web_search="live"] --output-schema scripts/schemas/codex_*.json -o …
  --color never -` with the prompt on stdin. Model resolution: `--model` > `ALPHA_CODEX_MODEL` >
  `gpt-5.3-codex-spark`; models absent from the cache are refused. Effort default `xhigh`;
  review cap 900 s, research 600 s; diffs > 200 kB truncated. Instruction-shaped text in Codex
  output is replaced by `[stripped: instruction-shaped text]`. Every call appends a `codex_call`
  audit event; every failure (no binary, logged out, quota, garbage output, wall-clock cap) is
  `available: false` + `unavailable:<reason>`, exit 0.
- `.mcp.json` registers `codex mcp-server` (Spark, read-only, `approval_policy=never`) for
  interactive use; the PreToolUse `mcp__codex__.*` guard logs each call. `.codex/config.toml`
  documents that the bridge uses explicit `-c` overrides (no `-p` profile: in 0.146 `-p` layers
  `$CODEX_HOME/<name>.config.toml`, not a repo table).
- Where it plugs in: `/codex-review` (findings labeled *second opinion (Codex, untrusted)*),
  `/codex-research` (cited claims labeled *unverified* — every claim is a source candidate for
  the quant-source-verification skill), `/second-opinion <file|diff>` (quick pass); `/review-gate`
  may call it first and the `independent-reviewer` disposes each finding
  (`agree|refute|out_of_scope`) in `ReviewVerdict.second_opinion[]` (or sets `codex_unavailable`);
  `/verify-quant` may use `research` for citation cross-checks. Only the `codex-liaison` agent
  invokes the bridge. **Codex never attests, writes, or approves**; every mandatory gate passes
  with Codex absent.

## Artifacts and audit

Every persisted artifact is validated by `scripts/harness_models.py` at write time;
malformed input is rejected loudly and nothing is written. A `QuantVerificationReport`
with `overall: PASS` cannot contain non-VERIFIED claims or missing citations (model
validator). Every stamp write, attestation, block, override, ack, Codex call, config
change, over-eager edit and stop-budget exhaustion appends an audit event (timestamp,
session, event, detail, tree hash, `prev_hash`) to `.claude/state/harness-audit.jsonl` —
append-only, hash-chained (`gate.py audit --verify` detects truncation/rewrite), per-machine,
gitignored. `gate.py audit [--json --since --kind]` is the reader; `/retrospective` consumes it.

One-shot tokens: `override` (bypasses the commit gate once), `ack` (permits one
control-plane edit; acks do NOT stack — arm one immediately before each write). Both are
consumed on use and audited at write and consume with `authorized_by`.

## Operations

- `python3 scripts/gate.py doctor [--json]` — settings parse, all hooks wired both ways,
  scripts present/executable, statusline, state dir, stub↔canonical sync, rules and agent
  frontmatter validity, stale stamp age, orphan tokens, owner-token presence, Codex
  availability probe (never calls the model). SessionStart runs it and warns loudly.
- `python3 scripts/gate.py selftest` — replays the harness test-suite (`/harness-doctor`).
- Statusline shows `branch · ±dirty · gate:tier✓/stale/none · needs:… · owner-token/budget flags`.
- **Emergency recovery**: delete `.claude/state/` (stamps/tokens/session state; the
  audit journal goes with it), or set `ALPHA_HARNESS_DISABLE=1` to bypass all hooks
  (audited emergency only). The main checkout's `.git/info/exclude` blanket-ignores
  `.claude/`, so NEW files under `.claude/` need `git add -f <file>` (never a directory —
  it pulls in `__pycache__`); tracked ones behave normally.
- Write paths (`attest`/`override`/`ack`/`baseline`) need pydantic and re-exec themselves
  under `.venv/bin/python` when invoked as plain `python3`.

## v2 rationale (evidence base)

1. Repo gap audit of v1 (45 findings: enforcement holes A1–A15, awareness B1–B9,
   reasoning C1–C9, subagents D1–D9, self-verification E1–E8, audit F1–F5) — each closed
   item maps to a hook row, gate subcommand or test above.
2. Agentic-coding reliability literature: verify state not claims (self-assessed
   trajectories over-report success); slice tasks; explicit scope/consent; hidden holdout +
   mutation gates defeat test-gaming; fresh-context external review beats intrinsic
   self-correction; LLM judges emit findings, deterministic code decides; instruction files
   keep only non-inferable rules; tool output is data, never instructions.
3. Quant/scientific rigor: SR 11-7 (conceptual soundness · ongoing monitoring · outcomes
   analysis), IIA three lines (author ≠ approver), mutation testing on statistical modules,
   metamorphic relations, known-truth calibration, differential oracles, independent P&L
   re-derivation, poison guards with discriminating power, banned-construct linting,
   cross-process determinism, hash-chained journals (17a-4 spirit).

## Known limitations (process controls, not cryptography)

- Attestations prove a validated artifact was written for a given tree/diff hash, not who
  wrote it; the audit journal preserves what was attested and when. The journal is
  per-machine and not rotated.
- Owner token is not yet configured on this machine: escapes are agent self-serve (audited,
  flagged) until `owner-init` runs.
- Bash-write detection covers `>`, `sed -i`, `tee` and heredoc `open(...,'w')` on tracked
  paths; more indirect shell writes are caught at commit time by the stamp.
- The agent Bash sandbox relies on `agent_type` being present in hook payloads (it is inside
  subagents; the main session is unsandboxed by design). Per-agent `hooks:` frontmatter is
  deliberately not used — the settings-level SubagentStop hook covers all agents.
- Haiku prompt hooks (Stop honesty/Karpathy judge, goal contract) are advisory and share the
  Stop budget; the deterministic Stop guard rules.
- Mutation floors: `timeout`/`no_tests` mutants are not credited, so renderer-heavy modules
  carry low but honest recorded floors (`figures/catalog` 0.0, `theme` 0.027, `render` 0.33 —
  `render.py` needs `--timeout 5400`); the nightly mutation report is report-only.
- `raise-cov` is report-only (177/576 unreached at baseline); `--cov-branch` is not in the
  gate; `.semgrepignore` is not a protected path; `[tool.mutmut]` is generated into the staged
  tree, not committed.
- The Bash guard's holdout-rendering check is token-based, so a `git commit -m` whose message
  contains the hidden-holdout directory literal is refused; write "the holdout suite" instead.
- `/codex-review`, `/codex-research`, `/second-opinion` are optional and gracefully skip when
  the `codex` binary is absent, logged out, or quota-less; nothing mandatory depends on them.
  ChatGPT-side quota resets are outside the harness's control.

## Deferred (needs runtime changes; own ADR-governed efforts)

1. Cross-session trial ledger feeding family-wise trial counts into single-run DSR
   (López de Prado complete trial accounting).
2. Standing backtest-vs-paper divergence monitor (SR 11-7 outcomes analysis).
3. PROV lineage in manifests; icontract/deal postconditions on stat outputs.
4. Named multi-agent Workflow scripts under `.claude/workflows/` for review sweeps.
