# Harness, permission, CLI-availability and gate verification — 2026-08-19/20

Evidence record for the branch-cleanup PR (plan
`docs/superpowers/plans/2026-08-19-branch-cleanup-simplify-merge.md`, Tasks 12–14). Every row is an
observed result; nothing below is inferred. Commands were run from the branch worktree at HEAD
`252c4c2` unless a row says otherwise.

## A — Harness measures

### A.0 Which settings govern this session (Task 12 Step 1)

| check | observed |
|---|---|
| `/Users/hunternovotny/Desktop/Project-ALPHA/.claude/settings.json` (checkout A, branch `codex/full-repair-program`) | **does not exist** (only `launch.json`, `settings.local.json` with no hooks/permissions) |
| `~/.claude/settings.json` | exists; 0 hooks, 0 allow, 0 deny |
| session project dir (`.claude/worktrees/infallible-kalam-2f15ea`, on `main`) | no `.claude/settings.json`, no `scripts/claude_hooks.py` |
| `CLAUDE_PROJECT_DIR` | unset |
| audit journal `.claude/state/harness-audit.jsonl` since 2026-08-19T09:00Z (this session's work) | 78 `ack_written`, **0 `ack_consumed`**, 16 `stamp_written`; the only `blocked_*` events are the Step-3 probes below |

**Finding:** the branch's hooks and permission rules were **not loaded** by this autonomous session —
the harness files live on the branch and the session's project root (a `main`-rooted worktree) and
checkout A have none. Every commit guard, ack and stamp in this session was honoured *procedurally*
by the agents (one ack per write, full stamp before every commit, `check --tier full` before every
commit and push). The guard logic itself is verified below by driving the real hook scripts with
the same payload shape CI's block-smoke uses, plus the 385-test harness suite. Once this PR merges,
checkout A on `main` carries `.claude/settings.json` + `scripts/claude_hooks.py`, and sessions rooted
there load the hooks live. Until then, the two implementer observations "ack not consumed after a
heredoc write" were this — not a write-classification gap — though the separately ledgered
`bash_write_targets` heredoc gap remains a real follow-up.

### A.1 Mechanical checks (Task 12 Step 2)

| # | measure | command | observed | result |
|---|---|---|---|---|
| 1 | doctor | `gate.py doctor` | every row `ok`; `owner token configured — WARN: not configured` (owner decision 2026-08-19); `gate stamp — 0.3h old, stale` (docs commit 252c4c2 after the last stamp; docs-only is waived) | PASS |
| 2 | weakening scanner | `gate.py lint-harness` | `ok — no guardrail regressions vs baseline` | PASS |
| 3 | stamp check | `gate.py check --tier full` | `no valid full stamp for current tree` — expected after the docs-only commit; Task 14 re-stamps | PASS (honest stale) |
| 4 | audit chain | `gate.py audit --verify` | `902 events, chain intact, 1 concurrent-append fork(s) tolerated` | PASS |
| 5 | digest | `gate.py audit --digest` | self-authorized escapes listed per path (ack_written 375, 366 agent self-serve) | PASS |
| 6 | brief | `gate.py brief` | branch, 0 dirty, `gate stamp none/stale`, recent commits incl. 252c4c2, open plan = this plan | PASS |
| 7 | statusline | `python3 .claude/statusline.py < /dev/null` | `claude/blissful-edison-00b74b · ±0 · gate:full-stale · needs:owner-token-unset` exit 0 | PASS |
| 8 | harness tests | 8 harness test files | `385 passed in 85.85s` | PASS |
| 9 | codex probe | `scripts/codex_bridge.py probe` | `available: true`, model `gpt-5.3-codex-spark`, logged in via ChatGPT | PASS |

### A.2 Guardrails that must BLOCK (Task 12 Step 3 — real hook scripts, CI payload shape)

| # | probe | hook | observed | result |
|---|---|---|---|---|
| P1 | Read `tests/holdout/README.md` | `pre-read-guard` | exit 2 `BLOCKED: tests/holdout/README.md is a HIDDEN HOLDOUT test …` | BLOCKS |
| P2 | Edit `.claude/settings.json` without ack | `pre-edit-guard` | exit 2 `BLOCKED: .claude/settings.json is harness/governance control plane … one-shot governance ack` | BLOCKS |
| P3 | `git commit -m "feat: probe"` with a staged `probe_t12.py` and no stamp | `pre-bash-guard` | exit 2 `BLOCKED: no full-tier gate stamp for the current tree` (probe file then unstaged + removed) | BLOCKS |
| P4 | `rm -rf /tmp/never-exists-alpha-probe` | `pre-bash-guard` | exit 0 — **allowed by design**: `/tmp/` is in `_SCRATCH_PREFIXES`; the plan's probe path was miscalibrated | n/a |
| P4b | `rm -rf /Users/hunternovotny/never-exists-alpha-probe` | `pre-bash-guard` | exit 2 `BLOCKED: recursive rm outside the scratchpad` | BLOCKS |
| P4c | `rm -rf data` (repo-relative) | `pre-bash-guard` | exit 2 `BLOCKED: recursive rm outside the scratchpad (data)` | BLOCKS |
| P5 | `uv run alpha research approve nonexistent` | `pre-bash-guard` | exit 0 — the hook does not gate it; the **permission deny list** does (`Bash(uv run alpha research approve*)` + `alpha …` + `.venv/bin/alpha …` forms present in `.claude/settings.json`). Not run live (owner-authority verb; session rule) | DENY-LISTED |
| P6 | `security find-generic-password -w -s project-alpha-tiingo` | `pre-bash-guard` | exit 0 — gated by the deny rule `Bash(security find-generic-password *-w*)`. Never run live (would print a secret) | DENY-LISTED |
| P7 | `git push --force origin …` | `pre-bash-guard` | exit 2 `BLOCKED: force push` (also deny-listed `git push --force*`, `git push -f*`) | BLOCKS |
| P8 | `git commit --amend --no-edit` | `pre-bash-guard` | exit 2 `BLOCKED: git commit --amend rewrites history` (also deny-listed) | BLOCKS |
| P9 | `git push -u origin …` without a stamp | `pre-bash-guard` | exit 2 `BLOCKED: git push requires a full-tier gate stamp` | BLOCKS |
| S3 | CI block-smoke #3 `{"verdict":"MAYBE"}` → `gate.py attest --kind review` | — | pydantic `Field required … missing`, non-zero | REJECTS |

Deny-list coverage confirmed in `.claude/settings.json` for: research approve/reject/decide,
`find-generic-password *-w*`, `push --force`/`-f`, `commit --amend`/`--no-verify`, `reset --hard`,
`clean -f`, `stash drop`, `Read(.env)`/`Read(.env.*)`, `paper ibkr-run`, `owner-auth enroll`,
`project override-research-gate`/`reveal-holdout` (each in `uv run alpha`, `alpha`, `.venv/bin/alpha`
forms). `ALPHA_HARNESS_DISABLE` has no deny rule — it is the documented, loudly-audited owner bypass.

### A.3 Positive checks (Task 12 Step 5)

| check | observed | result |
|---|---|---|
| `ack --reason … --path .claude/rules/docs.md` then `ack --clear` | journal: `ack_written` then `ack_disarmed` for that path (`authorized_by: agent (owner token not configured)`); the digest counts it under `ack_written` (it lists escapes, not disarms) | PASS |
| `gate.py brief` after the latest commit | `recent commits: 252c4c2 …` (brief keyed on git position) | PASS |
| `gate.py check` (default tier) | `no valid fast stamp for current tree — run gate.py fast` (honest; tier word `fast`) | PASS |
| `main`-rooted worktree `infallible-kalam-2f15ea` | `.claude/settings.json` and `scripts/claude_hooks.py` **absent** — harness travels with the branch until merge | PASS (as designed) |

## B — Permission matrix (Task 12 Step 4)

Autonomous session: permission prompts cannot be observed, and per A.0 the branch allow/deny lists
were not loaded for this session. Recorded as "ran / exit" only — **no claim that the allowlist
suppressed a prompt is made.**

| command | observed |
|---|---|
| `git status --short` | ran, clean tree |
| `git log -1 --oneline` | ran, `252c4c2 docs: …` |
| `git diff --stat` | ran, empty |
| `find . -maxdepth 1 -name '*.md'` | ran, `./CLAUDE.md` … |
| `du -sh .` | ran, `2.3G` |
| `security find-generic-password -s project-alpha-tiingo` (metadata only, no `-w`) | ran, keychain item metadata printed (no secret) |
| `uv run python scripts/gate.py doctor` | ran, all ok |
| `uv run alpha info` | ran, resolved settings printed |

Live-prompt verification of the allow/deny matrix is an **owner action after merge** from a
`main`-rooted interactive session: run the eight allow commands (expect no prompt) and one deny
probe such as `git commit --amend --no-edit` (expect refusal).
## C — CLI availability

Verified on worktree `claude-quantitative-finance-improvements-fa7386`, HEAD `252c4c23a5f3f9f7e9d3d2e222ce9e9a9a5ba111`. Read-only sweep; no repo edits, no commits.

### Step 1 — sub-app and leaf command `--help` sweep

**24 sub-apps / root commands** (`data crypto-data backtest forecast optim paper propfirm provider quantpad-data info options owner-auth risk screener research figures project evidence ml monte-carlo suite strategy-candidate validate report`): all 24 answered `--help` with exit 0. Zero FAIL.

**172 leaf command ids** (from `alpha info commands --json`): all 172 answered `--help` with exit 0. Zero FAIL. Full log at `cli-help-sweep.txt` (172 `OK` lines, 0 `FAIL` lines).

| command | exit | note |
|---|---|---|
| all 24 sub-apps listed above | 0 | OK — `--help` succeeded for every one |
| all 172 leaf command ids (`alpha info commands --json`) | 0 | OK — `--help` succeeded for every one; see `cli-help-sweep.txt` |

**Baseline comparison** (`$SCRATCH/baseline.json` vs current `alpha info commands --json` / sub-app sweep):
- `command_ids`: current set has 172 ids, baseline has 172 ids — **identical sets, zero diff** (no ids missing from current, no ids added).
- `subapps`: baseline holds the 23 first tokens of `command_ids` (no `figures`, which `info commands` excludes by design); the 24-name `--help` sweep list is exactly those 23 plus `figures` — **identical** on the comparable set.
- Verdict: **identical** — no drift between baseline and current CLI surface.

### Step 2 — Projections

| command | exit | note |
|---|---|---|
| `alpha info` | 0 | OK — printed `alpha-core 1.0.0`, `data_dir=data`, `random_seed=7`, `forecast_model=NeoQuasar/Kronos-small` |
| `alpha info strategies --json` | 0 | OK — 5 strategies (`breakout`, `kronos`, `ma_crossover`, `mean_reversion`, `ts_momentum`) |
| `alpha info providers --json` | 0 | OK — 12 providers, as expected |
| `alpha info system --json` | 0 | OK |
| `alpha data symbols --json` | 0 | OK |
| `alpha data snapshots --json` | 0 | OK |
| `alpha paper readiness --json` | 0 | OK — `paper_passed: false`; 22 requirements, all `passed: false` (all unevidenced) — matches the expected honest state |
| `lsof -iTCP -sTCP:LISTEN -nP \| grep ':4002'` | — | no listener found on 4002 |
| `alpha paper ibkr-preflight SPY.ARCA --asset-class etf` | — | **gateway down, preflight skipped** (per brief: port 4002 not listening) |

### Step 3 — Provider checks through the canonical launcher

| command | exit | note |
|---|---|---|
| `scripts/alpha-with-keychain-provider tiingo check` | 0 | OK — `tiingo: verified (...); No action required.` |
| `scripts/alpha-with-keychain-provider quantpad check` | 0 | OK — `quantpad: verified (...); No action required.` |
| `scripts/alpha-with-keychain-provider coingecko check` | 0 | OK — `coingecko: verified (...); No action required.` |
| `scripts/alpha-with-keychain-provider finnhub quote` | 0 | OK — returned a bounded live SPY quote JSON |
| `scripts/alpha-with-keychain-provider finnhub check` | 64 | Refused by design — launcher output: "Finnhub has no receipted readiness check; use 'finnhub quote' for a bounded live probe" (recorded as expected, not a defect) |
| `alpha provider check ibkr --json` (owner env recipe with `security find-generic-password -w ...`) | — | **DENIED by session policy (recipe uses `-w`); skipped** — not run per this session's hard rules |

### Step 4 — MCP + web

| command | exit | note |
|---|---|---|
| `grep -c "@mcp.tool" apps/alpha-mcp/src/alpha_mcp/server.py` | 0 | **62** — matches the pinned MCP tool count |
| `uv run pytest tests/integration/test_research_mcp.py -q -k "tool"` | 0 | OK — `3 passed, 4 deselected in 19.78s` |
| `uv run pytest tests/integration -q -k "healthz or web_app"` | 0 | OK — `1 passed, 598 deselected in 2.82s` |

### Summary

- 172/172 leaf commands OK (0 FAIL); 24/24 sub-apps OK (0 FAIL).
- Baseline comparison: **identical** — `command_ids` and `subapps` sets match `$SCRATCH/baseline.json` exactly, no diff.
- No FAIL, MISSING, or unexpected DENIED rows. The two intentionally-skipped items (`ibkr-preflight` — gateway down; `provider check ibkr` — session policy forbids the `-w` recipe) and the by-design `finnhub check` refusal are recorded as such, not failures.

## D — Gates (Task 14)

All runs from the branch worktree; Python gates at HEAD `252c4c2` and again at `ea54427` (after the
semgrep-gate fix below); frontend gate at `ea54427`.

| gate | command | duration | result |
|---|---|---|---|
| Python full gate (13 steps: lock, sync, ruff check/format, import contracts, mypy, mypy harness, harness lint, semgrep (changed scope), pytest+coverage (floor 93 %), OpenAPI freshness, wheel build, wheel smoke) | `gate.py full` | 516 s @252c4c2 · 507 s @ea54427 | **PASS — stamp written** (both) |
| import contracts | `uv run lint-imports` | — | 14 kept, 0 broken |
| bias guards | `uv run pytest -m bias_guard -q` | 7 s | 147 passed (35 guard files; `harness-baseline.json` re-pinned 32 → 35 after the final review — see D.2) |
| CLI smoke | `uv run alpha info` | — | OK |
| frontend gate | `npm ci && lint --deny-warnings && test:coverage && generate:api && playwright install chromium && test:e2e` | 179 s | **PASS** — 31 vitest files / 166 tests; 83 Playwright e2e passed; `git status --porcelain` on `static/app` + `generated.ts` **empty** |
| literature worker | `uv lock --check && uv sync --locked && ruff check && ruff format --check && mypy && pytest -m "not network"` | 6 s | PASS — 29 passed |
| qlib worker | same + `pytest -q` | 112 s | PASS — 14 passed |
| determinism double-run | `gate.py determinism` | — | ok, 2 passes green over 4 files under perturbed env |
| semgrep, whole repo | `gate.py semgrep` | 4 s | see D.1 — **honestly RED: 2 pre-existing findings** (was falsely green) |
| doctor | `gate.py doctor` | — | 65 ok rows |
| harness lint | `gate.py lint-harness` | — | ok, no regressions vs baseline |
| audit chain | `gate.py audit --verify` | — | 914 events, chain intact |

### D.1 Defect found and fixed by this verification: the semgrep step could not fail

`harness_quant.semgrep()` classified a run as "unavailable" (advisory, exit 0) whenever the output
contained `command not found`, `No such file` **or `OSError`** — and a real finding whose matched
source line read `except OSError:` contained that token. Whole-repo `gate.py semgrep` therefore
reported `[semgrep] unavailable` while **three Blocking findings** existed. Fixed in `ea54427`
(`fix(gate): …`): unavailability is now decided from the scanner's own launch failure (runner
exception or a missing `uvx`, first output line only) with a four-case regression test. The commit
gate's `semgrep --changed` step was unaffected (clean tree ⇒ nothing to scan); the nightly whole-repo
sweep was the blind spot.

Of the three findings: `provider_readiness.py:340` `except OSError: pass` (silent empty except in
the IBKR gateway reachability probe) is fixed in the same commit (`reachable = False`, recorded
state). The remaining two — `packages/alpha-research/src/alpha_research/crypto_crowding.py:112/123`,
`alpha-float-literal-equality` on `self.primary_percentile != 0.95` / `self.practical_hurdle_return
!= -0.0005` — are exact frozen-contract identity checks (a tolerance would admit a non-identical
registered plan), i.e. a rule false positive. A `# nosemgrep` suppression with rationale was
review-gate **APPROVED** (independent reviewer, attested) but the edit trips the on-touch mutation
gate: the Codex-added quant module has **no mutation baseline**, so the 0.90 floor applies and the
measured kill rate is 0.647 (915 mutants, 268 timed out inside the 600 s budget). The edit was
**reverted** rather than baselining the module unilaterally. **FOLLOW-UP (owner decision):** either
strengthen `crypto_crowding` tests / record a mutation baseline and then suppress with rationale, or
scope the float-equality rule to exclude frozen-contract `__post_init__` identity checks. Until then
whole-repo semgrep (nightly) is red on those two lines — visibly, not silently.

### D.2 Baseline diff (`$SCRATCH/final.json` vs `baseline.json`; Task 1 → HEAD `ea54427`)

| metric | baseline | final | cause |
|---|---|---|---|
| `subapps` (first tokens of launchable ids) | 23 | 23, identical | — |
| `command_ids` | 172 | 172, identical set | — (`crypto-data feature-create` gained `--available-at`; ids unchanged) |
| `mcp_tools` | 62 | 62 | pinned |
| `deny` rules | 57 | 57 | pinned |
| `allow` globs | 100 | 87 | 13 subsumed globs removed (Task 5) |
| hook events | 12 | 11 | `InstructionsLoaded` retired (write-only; Task 5) |
| hook names | — | `instructions-loaded` removed | same |
| `scripts/gate.py` lines | 2066 | 1429 | dead code + leaf extraction (Tasks 4–6) |
| `scripts/harness_quant.py` / `harness_awareness.py` | — | 354 / 329 | extracted leaves (Task 6) |
| `scripts/claude_hooks.py` | 1210 | 1167 | telemetry/dead hook removal (Task 5) |
| `scripts/harness_models.py` | 249 | 239 | `DriftFinding(s)` removed (Task 7) |
| `.claude/settings.json` | 362 | 338 | allow prune + hook block (Task 5) |
| harness tests collected | 380 | 389 | +9 net (new stamp/parser/JSON/semgrep tests; dead-code tests removed) |
| `.claude/agents` / `.claude/commands` | 11 / 12 | 9 / 10 | Task 7 |
| `bias_guard_tests` baseline pin | 32 | 35 | three crypto future-poison guard files added in Task 9 (batches 1–2); re-pinned after the final whole-branch review flagged the stale count |
| stamp tier | full | full | — |

### D.3 Worktree note

`tests/holdout/` does not exist in this worktree (only `tests/holdout_seed/`); the pre-read guard
still blocks the path (A.2 P1), and the independent reviewer ran `tests/holdout_seed` (14 passed) in
its place.
