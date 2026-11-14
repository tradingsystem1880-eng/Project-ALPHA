---
owner: delivery pipeline
sources:
  - scripts/handoff.py
  - scripts/codex_bridge.py
  - .claude/agents/*.md
  - .codex/config.toml
  - AGENTS.md
verified: 0d2cc970448a
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
- `medium` for small tasks: both calibration tasks (below) came out correct and clean first time
  at `medium`; the earlier hand-run trial at `high` took 8 minutes for a task of similar size.
- `high` for standard and `gpt-6-astra` for hard: first measured 2026-11-14 (tasks F and G below),
  one build each, so still provisional.
- Lighter models (`gpt-6-luna`, "fast and affordable") are not used for building: a quiet quality
  loss costs more than the allowance saved. No evidence yet says otherwise.
- Higher efforts (`xhigh`, `max`, `ultra`) are not used by default: unmeasured, and they spend the
  weekly allowance fastest.

Calibration, 2026-11-14, both small route, `gpt-6.1-sol` `medium`, no fix round needed:

| Task | Wall time | Input tokens (cached) | Output | Result |
|---|---|---|---|---|
| A: redact paths in the rules-evaluate relay error (3 files) | 3m57s | 496,656 (468,736) | 3,749 | correct; one unrequested doc re-wrap, caused by the brief |
| B: aggregate the per-plan tests in `test_plan_schema.py` (1 file) | 2m57s | 188,778 (150,656) | 2,822 | correct, strictness kept; 314 cases to 6 |

Test clean-up stream, 2026-11-14, all small route, `gpt-6.1-sol` `medium`, no fix round needed,
reviewed by Claude (Opus) before merge:

| Task | Wall time | Input tokens (cached) | Output | Result |
|---|---|---|---|---|
| C: run the v2 Qlib-isolation test in a fresh process (1 file) | 5m03s | 156,373 (126,336) | 1,777 | correct, every assertion kept |
| D: aggregate the theme drift tests, drop a permanent skip (2 files) | 3m55s | 187,865 (164,864) | 3,199 | correct; 54 cases to 8 |
| E: barrier for the investigation watchdog deadline test (1 file) | 2m52s | 351,724 (314,112) | 2,161 | correct, test-only, assertions kept |

The mutation-gate change in the same stream touched guarded harness files (`scripts/gate*`,
`scripts/harness_*`), which a brief cannot declare, so Claude built it and Codex reviewed it
(`handoff.py review`: 0 findings) alongside an Opus reviewer (one medium finding, fixed).

First standard and hard builds, 2026-11-14, standard and hard briefs, triage clean-up, reviewed by Claude:

| Task | Class, model, effort | Wall time | Input tokens (cached) | Output | Fix rounds | Result |
|---|---|---|---|---|---|---|
| F: one copy of literature acquisition code (6 files) | standard, `gpt-6.1-sol`, `high` | 7m30s | 1,328,298 (1,244,160) | 19,234 | 2, empty | correct; note 1 |
| G: remove QuantPad code (28 files) | hard, `gpt-6-astra`, `high` | 20m51s | 2,796,814 (2,715,648) | 9,859 | 0 | correct; note 2 |

1. Task F's build round alone was 401,809 in and 6,010 out. Both fix rounds were spent on a brief
   check that also searched documents the builder was told not to touch (a brief error).
2. Task G was approved unchanged; the orchestrator rebuilt the SPA bundle, which needs the network.

RD-Agent model gateway, 2026-11-14, from a brief (three code files, raised to standard with
`--class standard`), reviewed by Claude (Opus):

| Task | Class, model, effort | Wall time | Input tokens (cached) | Output | Fix rounds | Result |
|---|---|---|---|---|---|---|
| H: RD-Agent model gateway and tests (3 files) | standard, `gpt-6.1-sol`, `high` | 19m27s | 3,228,369 (3,052,928) | 73,983 | 1 (gate) | correct; note 3 |

3. The first live Codex call found two things no offline test could: a setting 0.167.0 does not
   recognise and a CLI notice item mistaken for tool use. Claude fixed both by hand (small edits
   plus one test), reviewed by Codex. A long brief with exact flags was worth its context.

A fix round resumes the whole thread, so even an empty round costs about the full context again
(about 40k more input each in task F). A brief's checks must only cover files the builder may change.

Most of Codex's allowance goes on context: a turn's input count adds up what is sent with each
model call (inferred: 497k input for one turn of 32 commands, 94% cached), so every file read
early costs again on each later step; a short read list saves more than a lower effort. Re-calibrate
when a model is added, or when a class looks wrong in three builds running.

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
- A brief says what to change and where; a style remark about a whole file reads as an order to
  rewrite it (calibration task A re-wrapped a whole reference file that way).

## Records

`handoff.py` writes a JSON build record for every run under its home (default
`<parent of the main checkout>/tmp/handoff/records/`, or `ALPHA_HANDOFF_HOME`); for a task folder
it also writes `docs/work/<task>/03-build.json`, committed with the build. On the small route the
record stays outside the tree and its numbers go into the pull request under "Who built and who
reviewed". Worktrees are `<home>/wt/<name>` on branch `build/<name>`; `handoff.py status` lists
them and `handoff.py clean` removes merged ones (only those it created). A later run on the same
worktree (a fix by hand, or the Claude fallback through `handoff.py verify`) keeps the earlier
attempts under `previous_attempts`, so the fallback stays visible.
