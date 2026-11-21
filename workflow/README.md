---
owner: delivery pipeline
sources:
  - scripts/handoff.py
  - scripts/roadmap_index.py
  - tests/unit/test_filesystem_contract.py
verified: bb945d1901fa6d5f
---

# Delivery pipeline: from an idea to a merged change

The path of a change in one place, the task folders it leaves, and how a stage file is shaped. The routing page is [CONTEXT.md](CONTEXT.md).

## Which stage am I in?

Which stage am I in? No task folder yet: 01. A brief but no plan: 02. A plan whose slices are not
all `done`: 03. Slices done but no `04-verify.md`: 04. Otherwise: 05.

## From an idea to a merged change

The whole path in one place. Other pages link here and do not repeat it.

1. **Who builds.** Claude plans, decides, reviews, commits and opens the pull request. Claude Sonnet builds from a precise brief; Opus reviews
   honesty and quant work ([model routing](../docs/reference/model-routing.md); owner decision of
   [2026-11-19](../docs/reference/project/owner-decisions-5.md#2026-11-19-claude-agents-build-until-the-codex-subscription-returns-the-file-system-comes-first)).
   The Codex hand-off tool (`scripts/handoff.py`) is paused until the owner turns Codex back on.
2. **The brief.** Write it outside the repository, in the shape of the [brief template](../docs/reference/model-routing.md#brief-template), and give
   it to the builder. Headings: Task, Workspace, Decision, Change, Do not touch, Done when, Tier, Builder, Do NOT load, Report. A planned task uses its `docs/work/<task>/` folder instead. Then you review (stage 04).
3. **Where the files land.** `brief.md` and the builder's `report.md` go to `docs/work/<yyyy-mm-dd>-<slug>/`, merge with the work and are linked from the pull
   request. The JSON build record stays outside the repository, in the handoff folder ([task folders](../docs/work/CONTEXT.md)).
4. **Checks.** Locally: `uv run python scripts/gate.py check`. On the pull request the one required check is `ci-ok`. Open the pull request as a draft while you build: a draft runs only the quick
   `static` job, and its `ci-ok` fails on purpose. When the work is done, mark it ready (`gh pr ready <number>`): that starts the full run.
5. **Who merges.** The orchestrating session merges once `ci-ok` is green and the branch is current: `gh pr merge <n> --merge` (a merge commit). The
owner keeps
   branch-protection changes ([stage 05](stages/05-land/CONTEXT.md)).
6. **Marking a document re-read.** When your change makes a document's TEXT wrong, fix the text in the same pull request. Do NOT run
   `fs.py verify` in a feature pull request: re-stamping made every open pull request conflict with every other one. A stale document is
   listed by `uv run python scripts/fs.py stale` and by the gate, and it does not block (broken front matter and a missing source still do).
   One sweep pull request re-reads the stale documents and stamps them (`fs.py verify <doc>`, or `--reason "<why still correct>"`, kept in
   `docs/verified-reasons.txt`); `fs.py owners <path>` names the documents that describe a file.

## Task folders

- A build from a brief leaves `brief.md` and `report.md` in `docs/work/<yyyy-mm-dd>-<slug>/` (step 3 above). Read a stage file's other `docs/work/<task>/`
  paths as the optional route.
- The optional route: one folder per planned task, on its branch while the pull request is open (stage 05 removes it), holding `01-brief.md`, `02-plan.md`,
  `03-build.json`, `04-verify.md` and `05-handoff.md`; one is committed only with a `02-plan.md`. The owner may edit any stage file between stages.
- The small route skips the folder: a fix in one module with an obvious test, or a documentation-only change. It runs stages 03 to 05 on a branch from a
  short brief and the area's `CONTEXT.md`; 04's results go under `## Checks run` in the pull request; 05 fills the template directly.

One folder per build, `docs/work/<yyyy-mm-dd>-<slug>/`, on the build's branch and merged with the work
(the paused Codex hand-off tool wrote it; today the orchestrator saves it). These are outputs (the paper's Layer 4), not reference
documents: they carry no front matter, no line limit and are never re-verified.

- `brief.md`: what was asked and what was already decided, as the builder received it. Edit it
  before a relaunch; the next build reads the edited file.
- `report.md`: the builder's final report: what it changed, which checks it ran, what is
  unverified, deviations and open questions. Home paths and model names are removed.
- A planned task (`02-plan.md`, the [delivery pipeline](CONTEXT.md)) keeps its stage
  files here too; the build adds its `report.md` beside them.

The pull-request description links both files.

## Changing a stage file

- A rule a stage needs belongs in a reference file (`docs/reference/`); the stage links it.
- Agents (`.claude/agents/`) and commands (`.claude/commands/`) are entry points into these
  stages and hold no rules of their own.

- Each stage file follows the shape checked by `tests/unit/test_filesystem_contract.py`:
  Purpose, Inputs, Read first, Process, Outputs, Checkpoint; at most 60 lines.
