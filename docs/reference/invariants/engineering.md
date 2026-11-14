---
owner: engineering standards
sources:
  - pyproject.toml
  - .semgrep/alpha.yml
  - scripts/gate.py
  - scripts/gate_components.py
  - apps/alpha-cli/src/alpha_cli/research_cmds.py
  - apps/alpha-cli/src/alpha_cli/_structural_digest.py
verified: 3a0098cd96e3
---

# Engineering rules

Project-wide coding rules. Area files add their own detail and link here. The research rules
(point-in-time, fills, immutability, owner authority) are in
[research integrity](research-integrity.md).

## Project scope

- ALPHA is private, single-owner research software: Python 3.12, managed with uv (`uv sync --locked`). It is
  never hosted or distributed; the web app binds loopback only. Running it: [README](../../../README.md).

## Import layers

- The packages form a layered import graph (a DAG): a package may import only the layers below it.
  The picture and the rule are in [ARCHITECTURE § 2](../../ARCHITECTURE.md#2-the-layered-dag).
  [ADR-0001](../../adr/0001-strict-layered-dag.md)
- `alpha_core` imports nothing internal. `alpha_data` and `alpha_patterns` import only core.
  `alpha_strategies` imports core and patterns. `alpha_validation`, `alpha_research` and
  `alpha_forecast` import only core. `alpha_backtest` imports core and data. `alpha_study` imports
  core, data, patterns and research. `alpha_cli` may import all of them.
- `alpha_web` and `alpha_mcp` sit on top; nothing imports them, and they import only `alpha_core`
  and public `alpha_cli` seams. Only `alpha_cli` may import `alpha_forecast`.
- The contracts are the `[tool.importlinter]` section of `pyproject.toml`; check with
  `uv run lint-imports`. Never add an `ignore_imports` exception without an ADR (the one existing
  exception, the owner-auth seam, is ADR-0030).
- Workers (`workers/*`) are separate uv projects; no root package imports them.

## Subprocess boundary

- `alpha_cli` is the only place that composes the engine, the validation gauntlet, Nautilus, Qlib
  and Kronos. The web app and MCP server run the `alpha` command as a subprocess for actions and
  engine-backed projections; they never run that machinery in-process.
  [ADR-0002](../../adr/0002-cli-sole-composer-subprocess-surfaces.md)
- Engine imports inside `alpha_cli` are lazy, so light commands stay light.

## Strict typing

- `mypy --strict` covers `packages`, `apps`, `tests` and the harness scripts. Only the overrides in
  `pyproject.toml` (Nautilus, scipy, quantstats, vendored Kronos) are exempt.
- A `type: ignore` must name its error code (semgrep rule `alpha-type-ignore-without-code`).

## Polars by default

- Polars is the dataframe library. pandas is allowed only at three edges: the yfinance adapter,
  the tear-sheet renderer and the Kronos facade (semgrep rule
  `alpha-pandas-outside-sanctioned-edges`).
- numpy and scipy are sanctioned in the validation and research numeric code; deterministic
  Matplotlib rendering is sanctioned in `alpha_research`.

## Errors

- No bare `except`, no `except: pass`, no swallowed errors (semgrep rule `alpha-except-pass`).
  Raise or propagate typed `AlphaError` subclasses with context.
- A test that cannot run is reported `UNVERIFIED:` with the reason; failing output is quoted
  exactly, never paraphrased into a pass.
- Retry only inside a budget that already exists, then fail loud. Example: control-store WAL negotiation
  retries `SQLITE_BUSY` only within the connection's `busy_timeout` (`control_store.py::_enable_wal`).
  Never add a retry loop that hides a failure or extends a budget.

## Hash-bound source bytes

- Every file in `packages/alpha-research/src`, four CLI modules (`research_intake.py`,
  `research_runtime.py`, `research_crypto_data.py`, `research_crypto_runtime.py`) and the root
  `uv.lock` feed the research implementation hash, computed by
  `apps/alpha-cli/src/alpha_cli/research_cmds.py::_implementation_hashes` and checked against
  owner-approved research contracts. The fixed and daily rule lanes bind the rdagent worker files
  and `DAILY_GUARD_FILES` the same way (`_native_rule_environment.py::rule_implementation_fingerprints`);
  which files the daily lane must bind is tested ([ADR-0048](../../adr/0048-daily-rule-lane-binding-and-named-months.md)).
- Approvals bind code structure ([ADR-0045](../../adr/0045-approvals-bind-code-structure.md),
  `apps/alpha-cli/src/alpha_cli/_structural_digest.py`): an approval made since ADR-0045 (scheme 2)
  survives comments, blank lines, formatting and unread docstrings, and is invalidated by any change
  to what the code does. Lock files and non-Python files stay bound by bytes, as does a Python file
  that reads source, line numbers or frames.
- An approval made before ADR-0045 (scheme 1) stays bound to exact bytes until the owner re-approves.
  So while such an approval may be live, make no cosmetic edits in those files; change them only when
  the behaviour must change, and say in the pull request that approvals will need renewing. Never
  edit `_structural_digest.py` casually: any edit to it invalidates every scheme-2 approval, so a
  builder may change it only under a plan that declares the quant tier (`handoff.py` `GUARDED`).
- Run identity also fingerprints source bytes (`apps/alpha-cli/src/alpha_cli/_identity.py`), so
  edits to engine, strategy and CLI code change run ids. Details: `cli-runs.md` and `cli-native.md`
  in this folder.

## Quant tier

- `packages/alpha-validation/src` and `packages/alpha-research/src` are the quant tier, plus any
  `packages/*/src` file whose name matches a statistic (`dsr`, `pbo`, `bootstrap`, `cpcv`, ...;
  `scripts/gate.py::matches_quant`).
- A pull request that changes a quant source module makes CI also run the slow oracles and the
  mutation gate on the touched modules: each needs a mutation kill-rate of at least 0.90, or its
  recorded floor in `.claude/mutation-baseline.json`.
- Growth of `# noqa` or `type: ignore` in quant modules is blocked by `gate.py lint-harness`
  against `.claude/harness-baseline.json`.
- Float-literal equality is banned in quant code (semgrep rule `alpha-float-literal-equality`).
- The `quant-verifier` and `reviewer` agents report on the pull request and are advisory
  ([stage 04](../../../workflow/stages/04-verify/CONTEXT.md)).

## Reproducible code

- No wall-clock reads in `packages/` (semgrep rule `alpha-wall-clock-in-packages`); network
  adapters stamp fetch receipts by design. Timestamps belong to the CLI and control plane.
- No unseeded random number generators (`alpha-unseeded-rng`) and no negative `shift` in packages
  (`alpha-negative-shift`, it reads the future).
- Semgrep runs fail-closed at a pinned version: `uv run python scripts/gate.py semgrep`.

## Code size

- No product source file (`packages`, `apps`, `workers`, `tools`, `scripts`; tests are not
  measured) over 1,500 lines, and no function over 150 lines (`def` line to last line), so an
  agent can hold any file or function in its head.
- The offenders of 2026-11-14 (10 files, 98 functions; 8 files and 90 functions after the suite and research command splits) are capped at their size then in
  `.claude/code-size-baseline.json`. The baseline only shrinks: an entry that is higher than
  needed, gone or no longer over the limit fails until it is lowered or removed, and an entry
  added or raised since `origin/main` fails; split the code instead. Same-name definitions
  (a property setter) are measured separately as `name#2`. Enforced by `tests/unit/test_code_size.py`.

## Working style

- Think before coding: state assumptions, surface trade-offs and competing readings, push back when a
  simpler way exists, and stop to ask when unclear.
- Simplicity first: the minimum code that solves the problem; no unrequested features, configurability,
  single-use abstractions or handling for impossible cases.
- Surgical changes: touch only what the task needs; match the existing style; do not reformat or "improve"
  nearby code. Remove only the orphans your change created; mention other dead code, do not delete it.
- Goal-driven: define how success is checked (usually a failing test first), then make it pass. For
  multi-step work state a short plan with a check per step.
- One agent mutates the working tree per slice; others read or review.
- Evidence before claims: say a check passes only after running it on this tree and reading its result;
  an agent's report of success is checked against the diff before it is repeated.
- How a change is shaped, planned, built, verified and landed: the [delivery pipeline](../../../workflow/CONTEXT.md).

## Checks and commits

- Loop: edit, then `uv run python scripts/gate.py check` (ruff, import contracts, mypy, and the
  tests mapped from changed files), then commit, push, open a draft pull request.
- CI on the pull request is the merge gate; the orchestrating session merges on green
  (merge commits only; owner's delegation, 2026-11-14). A commit needs only a
  `type(scope): summary` message. Model review is advisory.
  [ADR-0039](../../adr/0039-ci-is-the-merge-gate.md)
- One CI job locally: `uv run python scripts/gate.py component NAME` (`backend` is the whole
  backend; CI runs it as `backend-static`, `backend-tests --shard I/4` and `backend-quant`;
  also `frontend`, `frontend-full`, `literature`, `qlib`). Every check: [checks](../checks.md).
- Step by step, with focused checks and owned test processes: [development loop](../../operations/development-loop.md).
- CI passing changes no application authority: owner actions, approvals and promotion are unchanged by it.
- A check result holds only for the exact tree and environment it ran on, with its command, exit and scope.
  A linked test, a result from another tree or one reported by someone else is not a pass here.
- Retire local code that duplicates an upstream capability only after a recorded value-level comparison,
  dependency and licence review, and a tested migration and backout; until then keep the old route.
