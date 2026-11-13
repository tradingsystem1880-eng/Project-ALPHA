---
owner: agentic benchmark
sources:
  - tools/alpha-eval/**
  - scripts/gate_components.py
verified: 0377681b
---

# Evaluation tool invariants

What must hold for `tools/alpha-eval`, the agentic research benchmark that measures the platform plus
its agent through deterministic platform probes and agent trajectory scenarios.

## Authority

- Scores are diagnostic engineering evidence, never authority to promote research, trade or use capital.
  `CLAUDE.md` lists the benchmark as advisory. [research integrity § Owner authority](research-integrity.md#owner-authority).
- A platform validation PASS in a trial is not proof that a planted positive control is commercially
  executable; inspect fills, concentration, sample size and costs.
- Do not fix platform defects to improve a campaign's scores; they are follow-up work.

## Project boundary

- A separate uv project with its own `uv.lock`, outside the root workspace. Gate:
  `uv run python scripts/gate.py component eval` (the CI `eval` job), which from `tools/alpha-eval/` runs
  `uv lock --check`, `uv sync --locked`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy`,
  `uv run pytest -q -m "not network"`.
- `worlds/build.py` and the measurement-worker scripts run in the platform environment (they import
  `alpha_data` and `alpha_validation`); the evaluator package itself imports no `alpha_*` code.

## Execution and models

- New trials and judges use Codex only; Claude execution is rejected (`runner.py::parse_sut`, `harness.py`,
  `judge.py` raise "Codex only"). Historical Claude trajectories, caches and scorecards stay readable and unchanged.
- A second-pass judge is a separate Codex session: same-model review, not cross-model validation.

## Evidence and reproducibility

- Raw streams, sandbox data and model outputs live outside Git under `$ALPHA_EVAL_HOME` (default
  `~/.alpha-bench`); `results/` holds summaries and the compressed historical hash inventory.
- Run manifests bind platform commit, expanded scenarios, world files, harness, model, effort and client
  version. Resume rejects incompatible or unmanifested runs.
- A trial collision fails; explicit retries allocate `attempts/0001` and onward, and originals are kept.
- Scoring writes a new `scoring/<revision>/`, never historical scorecards or judge files. A complete revision
  cannot be overwritten; partial cards are named `partial-scorecards*`; resume a revision only with identical
  inputs. `score --reuse-revision` reuses judgments only for identical prompt, schema, model, effort and
  trajectory keys.
- `investigate-demo` output is append-only; an existing destination is rejected.

## Isolation

- Each campaign exports a pinned platform commit, read-only, used by setup, CLI and MCP alike. Exports exclude
  evaluator code, audits, plans, answer keys, hidden or proposed holdouts, user configuration and owner data.
  [research integrity § Protected and hidden tests](research-integrity.md#protected-and-hidden-tests).
- Every trial first proves its permitted and denied reads and writes and its MCP tools; a startup failure
  blocks the trial. If preflight fails, never substitute `workspace-write` or unrestricted execution.
- In the investigation demo, a trusted controller alone dispatches actions; no action accepts model-provided
  paths, code, search parameters or commands.

## Reporting

- Missing judges and harness failures are excluded from rates and counted visibly; unknown token use or cost
  stays unknown.
- Never pool adaptive diagnostic follow-ups or versioned panels (for example `workflow_v2`) with fixed-cohort
  or historical rates. A changed suite, scorer or judge does not by itself show improvement.
  [research integrity § Statistical evidence](research-integrity.md#statistical-evidence).
