---
owner: delivery pipeline
sources:
  - scripts/handoff.py
  - scripts/codex_bridge.py
  - .claude/agents/*.md
  - .codex/config.toml
  - AGENTS.md
verified: c4a47968e14d
---

# Model routing: who builds, who reviews, what happens at a limit

Claude plans, decides and reviews; Codex implements. The owner chose this on 2026-11-14 ("Codex
usually has cleaner better code"; Claude is better at planning and decision making). Codex runs on
the ChatGPT Pro plan (generous, weekly limits); Claude runs on Max 5x, which is the one to ration.
Apply the tables below mechanically; `scripts/handoff.py` applies the build and review rows itself.

## Roles

- **Orchestrating Claude session** — decides; writes briefs and plans; runs `handoff.py`; reads its
  summary and the diff stat (never build logs); commits; opens pull requests and lands them as
  [stage 05](../../workflow/stages/05-land/CONTEXT.md) says. Writes no code a builder could write.
- **Claude Opus sub-agents** — investigation, design, research-integrity judgement, quant
  verification (`quant-verifier`), review of risk-tier diffs (`reviewer`).
- **Claude Sonnet sub-agents** — chores (merges, regeneration, re-stamping, summarising logs),
  finding things (`navigator`), first-pass review of an ordinary Codex-built diff (`reviewer`
  called with `model: sonnet`), fallback builder for a small task.
- **Codex as builder** (`handoff.py build`) — stage 03: code and tests from a written plan or brief,
  in its own worktree. Never commits, pushes, merges, uses the network or decides.
- **Codex as reviewer** (`scripts/codex_bridge.py`, via `handoff.py review` or `/codex-review`) —
  second opinion on Claude-written code, plans and documents. Grants no authority.

The writer is never the only reviewer: Codex-built work is reviewed by Claude, Claude-built work by
Codex (or, when Codex is out, by a different Claude agent than the writer). Machine checks and CI
run for everything and outrank every model.

## Task classes

The class is computed from the plan by `handoff.py` (`classify`); a plan's `**Build class:**` line
or `--class` may raise it, never lower it. The design is always already decided: an undecided task
goes back to stage 02.

| Class | Objective criteria | Codex model, effort | Time cap (fix round) | Claude fallback |
|---|---|---|---|---|
| `small` | ≤ 3 files in scope, no tier other than `none` | `gpt-6.1-sol`, `medium` | 15 min (10) | Sonnet |
| `standard` | 4–8 files, or tier `dag`, `bias` or `determinism` | `gpt-6.1-sol`, `high` | 30 min (15) | Opus |
| `hard` | > 8 files, or tier `quant`, `risk` or `protected`, or a guarded path in scope | `gpt-6-astra`, `high` | 60 min (20) | Opus |

Why, one line each:

- `gpt-6.1-sol` is the newest workhorse coding model on this login; `gpt-6-astra` is listed as the
  frontier model "for the most demanding work" (`~/.codex/models_cache.json`, 2026-11-14).
- `medium` for small tasks: calibration (below) showed `high` reading and re-checking far more than a
  one-module fix needs; quality stayed equal on both small tasks.
- Lighter models (`gpt-6-luna`, "fast and affordable") are not used for building: a quiet quality
  loss costs more than the allowance saved. No evidence yet says otherwise.
- Higher efforts (`xhigh`, `max`, `ultra`) are not used by default: unmeasured, and they spend the
  weekly allowance fastest.

Calibration, 2026-11-14 (two real small-route tasks, numbers in each task's build record):
see the commit messages of the two calibration commits on `m3/model-routing` and the report kept
with this change. Re-calibrate when a model is added or a class looks wrong in three builds running.

## What stays with Claude or the machine

- Anything needing the network: `uv sync`, GitHub, CI, web research for a decision.
  `handoff.py` runs `uv sync --locked` before Codex starts.
- Commits, pushes, pull requests, merges. Codex's sandbox cannot write the git directory, and
  `handoff.py` refuses a build whose HEAD moved.
- Checks Codex's sandbox cannot run (verified 2026-11-14 with `codex sandbox`): tests using FastAPI
  `TestClient` (they hang), anything binding or connecting a localhost TCP socket (`EPERM`),
  `tests/smoke/` (starts the installed programs and a web server), browser tests, `uv run` (the uv
  cache is outside the worktree), any network call. `handoff.py` runs all checks again outside.
- Decisions not written in the plan or brief; owner actions of any kind.
- Changes to the never paths (`tests/holdout/`, `scripts/codex_bridge.py`, `scripts/claude_hooks.py`,
  `.claude/settings*.json`, credential-shaped files) — refused whatever the plan says.
- Changes to guarded paths — hash-bound source bytes (`packages/alpha-research/src`,
  `packages/alpha-validation/src`, the four research CLI modules, `uv.lock`), quant-named modules,
  `tests/oracles/`, `tests/bias_guards/`, `tests/acceptance/`, and the protected harness files
  (`CLAUDE.md`, `AGENTS.md`, `.claude/`, `.codex/`, `.github/`, `.agents/`, `scripts/gate*`,
  `scripts/harness_*`, `scripts/handoff.py`, the harness and file-system contract tests) — unless
  the plan lists the path in `files` AND declares the matching tier (`quant`, `bias`, `protected`),
  and the owner approved the plan. The list lives in `handoff.py` (`NEVER_PATHS`, `GUARDED`).

## Review by risk tier

`handoff.py review --base <ref> [--task <folder>]` prints the route for the current diff. Tiers
come from the plan's `tier_impact` and from the paths changed (quant tier:
[engineering rules](invariants/engineering.md#quant-tier); protected and hash-bound: the list above).

| Diff | Built by Codex | Built by Claude |
|---|---|---|
| ordinary | machine checks + `reviewer` with `model: sonnet` | machine checks + Codex review through the bridge |
| `risk`, `protected` or `bias` | machine checks + `reviewer` (Opus) | machine checks + `reviewer` (Opus) + Codex review |
| `quant` | machine checks + `quant-verifier` (Opus) + `reviewer` (Opus) | the same + Codex review |

Review findings are advisory; each is disposed of (fix, or reject with a reason) in `04-verify.md`
or the pull request. A Codex review that comes back `available: false` is replaced by `reviewer`
(Opus), so the writer is still not the only reviewer.

## Limits and fallback

Signals, as `handoff.py build` reads them (exit status in brackets):

- Codex unavailable [10]: `codex` not on PATH, `codex login status` not "Logged in", the class's
  model missing from the models cache, or an auth error in the event stream.
- Codex usage limit [11]: an `error` or `turn.failed` event (or stderr) matching "usage limit",
  `usageLimitExceeded`, "rate limit", "429", "quota" or "purchase more credits". The exact wording
  was read from the 0.167.0 binary, not seen live: ASSUMED until a real limit is hit.
- Codex timeout [12]: the class's time cap passed; the process group is stopped.
- Codex failed [13]: any other non-zero exit or failed turn.

On 10–13 the record's `fallback` names the Claude builder for the class. The orchestrator gives the
same `prompt.md` (path in the summary) to a general-purpose sub-agent with that model, in the same
worktree, then runs `handoff.py verify --worktree <wt> --built-by claude:<model> --brief|--task ...`,
which applies the same policy and checks and writes the record with the Claude builder named. Do
not wait or ask the owner. A Codex-reviewed change whose reviewer is out goes to `reviewer` (Opus).

On a Claude limit: queue more work for Codex (several `handoff.py build` runs may go in parallel,
one per worktree), keep orchestrator turns to reading summaries and committing, and defer Opus
reviews that are not on the merge path. Every fallback is recorded: the build record's `built_by`
and `fallback`, and the pull request's "Who built and who reviewed".

## Economy rules for the Claude side

- Briefs point at routing files and sections (a Read first table); they never paste context.
- The orchestrator reads `handoff.py`'s summary (≤ 40 lines) and `git diff --stat`, not logs or
  event streams; it opens the diff only to review or when the summary says something failed.
- Fix rounds are driven by `handoff.py` (`codex exec resume` with the failing command and its
  output tail), never by a Claude turn. Budget: `--fix-rounds`, default 2.
- Sub-agent models are set in each agent's front matter (`model:`); override per call only as the
  review table says.
- One small route task per brief; batch unrelated small fixes into separate parallel builds.

## Records

`handoff.py` writes a JSON build record for every run under its home (default
`<parent of the main checkout>/tmp/handoff/records/`, or `ALPHA_HANDOFF_HOME`); for a task folder
it also writes `docs/work/<task>/03-build.json`, committed with the build. On the small route the
record stays outside the tree and its numbers go into the pull request under "Who built and who
reviewed". Worktrees are `<home>/wt/<name>` on branch `build/<name>`; `handoff.py status` lists
them and `handoff.py clean` removes merged ones (only those it created).
