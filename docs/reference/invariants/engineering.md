---
owner: engineering standards
sources:
  - pyproject.toml
  - .semgrep/alpha.yml
  - scripts/gate.py
  - scripts/gate_components.py
  - apps/alpha-cli/src/alpha_cli/research_cmds.py
verified: 1ac86fc02443
---

# Engineering rules

Project-wide coding rules. Area files add their own detail and link here. The research rules
(point-in-time, fills, immutability, owner authority) are in
[research integrity](research-integrity.md).

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
- Workers (`workers/*`) and `tools/alpha-eval` are separate uv projects; no root package imports them.

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
- A test that cannot run is reported as not verified, with the reason; failing output is quoted
  exactly, never paraphrased into a pass.

## Hash-bound source bytes

- The bytes of every `.py` file in `packages/alpha-research/src` feed the research implementation
  hash, together with four CLI modules (`research_intake.py`, `research_runtime.py`,
  `research_crypto_data.py`, `research_crypto_runtime.py`) and the root `uv.lock`. The hash is
  computed by `apps/alpha-cli/src/alpha_cli/research_cmds.py::_implementation_hashes` and checked
  against owner-approved research contracts.
- So even a cosmetic edit there (a comment, formatting, a rename) invalidates existing owner
  approvals. Make no cosmetic edits in those files; change them only when the behaviour must change,
  and say in the pull request that approvals will need renewing.
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
- `/verify-quant` and `/review-gate` reports are advisory on the pull request.

## Reproducible code

- No wall-clock reads in `packages/` (semgrep rule `alpha-wall-clock-in-packages`); network
  adapters stamp fetch receipts by design. Timestamps belong to the CLI and control plane.
- No unseeded random number generators (`alpha-unseeded-rng`) and no negative `shift` in packages
  (`alpha-negative-shift`, it reads the future).
- Semgrep runs fail-closed at a pinned version: `uv run python scripts/gate.py semgrep`.

## Working style

- Think before coding: state assumptions, surface trade-offs, ask when unclear.
- Simplicity first: the minimum code that solves the problem; nothing speculative.
- Surgical changes: touch only what the task needs; do not reformat or "improve" nearby code.
- Goal-driven: define how success is checked (usually a failing test first), then make it pass.
- Long form: `.claude/rules/00-karpathy.md`.

## Checks and commits

- Loop: edit, then `uv run python scripts/gate.py check` (ruff, import contracts, mypy, and the
  tests mapped from changed files), then commit, push, open a draft pull request.
- CI on the pull request is the merge gate; the owner merges. A commit needs only a
  `type(scope): summary` message. Model review is advisory.
  [ADR-0039](../../adr/0039-ci-is-the-merge-gate.md)
- One CI job locally: `uv run python scripts/gate.py component NAME` (`backend`, `frontend`,
  `literature`, `qlib`, `eval`).
