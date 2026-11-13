# Development loop

**CI on the pull request is the merge gate** ([ADR-0039](../adr/0039-ci-is-the-merge-gate.md)).
Nothing local has to pass before a commit except the commit-message format.

```text
edit → gate.py check → commit → push → draft pull request → CI → owner merges
```

1. Work on a branch, never on `main`. Commit as often as is useful; partial staging and
   work-in-progress commits are fine. The one local hook refuses a subject that is not
   `type(scope): summary` (install it once with `uv run python scripts/git_guard.py install`).
2. Run the fast local check while you work:

   ```sh
   uv run python scripts/gate.py check            # under a minute for a typical change
   uv run python scripts/gate.py check --all      # the whole fast test tier, about 2–3 minutes
   uv run python scripts/gate.py check --base main
   ```

   It runs `ruff check`, `ruff format --check`, `lint-imports`, one strict `mypy` over
   `packages apps tests` and the harness scripts, then pytest on: the bias guards, the quick
   oracles, `tests/acceptance`, tests mapped from the files changed since the merge base with
   `origin/main`, and last run's failures. It writes nothing except pytest and tool caches.
3. Push and open a **draft** pull request. CI runs every component. Mark it ready when CI is
   green; the owner merges. Model review is advisory and belongs on the pull request.

## What CI checks

The `ci-ok` job passes only when every job below succeeded; branch protection requires it.

| Job | Checks |
| --- | --- |
| `check` | Locked install, ruff, import contracts, strict mypy, harness lint, Semgrep, **every** pytest test (not `network`/`slow_oracle`) with coverage, OpenAPI freshness and authority, wheel build and smoke; slow oracles and mutation when quant source changed. |
| `harness` | Harness doctor, weakening scanner, strict mypy of the harness scripts, hook and selector tests. |
| `frontend` | npm lint, build and types, unit coverage, API freshness, browser lanes, SPA freshness. |
| `qlib-worker`, `literature-worker` | Each worker's own lock, lint, format, types and tests. |
| `eval` | The benchmark tool's own lock, lint, format, types and tests. |

Nightly runs Semgrep on the whole tree, determinism and raise coverage; a weekly job runs the
full mutation sweep.

## Running one CI job locally

```sh
uv run python scripts/gate.py component backend   # also: frontend, literature, qlib, eval
```

It runs exactly the steps CI runs for that job and stops at the first failure. `backend` takes
about 13 minutes here. `python3 scripts/gate.py preflight [--json]` reports, without changing
anything, whether this machine has what the components need.

## Fast tier and focused tests

`tests/_tiers.py` decides which tests are in the fast tier: real-process and lifecycle families
(native fixtures, daily rules, leases, supervisors), harness tests and files of about ten seconds
or more are left to CI and to `check`'s change mapping. CI runs them all regardless.

| Change | Start here |
| --- | --- |
| Python behaviour | `uv run pytest -q tests/unit/test_<feature>.py` and its integration tests |
| Imports | `uv run lint-imports` |
| Frontend model | In `apps/alpha-web/frontend`: `npm test -- src/path/model.test.ts` |
| Browser behaviour | The focused Playwright workflow below |

Linux tests that rely on orphan reaping must run under the process owner; `gate.py` does this
for you, and by hand:

```sh
uv run python scripts/run_owned_test.py -- uv run pytest -q tests/unit/test_durable_job_lease.py
```

The `owned_test_process` fixture fails before such a test starts without that owner.

## Browser lanes

The frontend component builds once (`npm run build`, including TypeScript) and then runs
`test:e2e:built` through `scripts/run_frontend_browser_lanes.py`: default → risk-basis →
risk-live → native, fail-fast, with no test selection. The native lane needs
`ALPHA_RDAGENT_SOURCE` and `ALPHA_STOCK_PYTHON`; when neither is set (hosted CI) it prints
`native lane skipped: ALPHA_RDAGENT_SOURCE/ALPHA_STOCK_PYTHON not provisioned` and the other three
lanes still run. Setting only one, or an invalid one, fails. Nothing is installed or downloaded;
`PLAYWRIGHT_BROWSERS_PATH` is honoured. Each run keeps its reports and logs in a fresh
`alpha-browser-lanes-*` temporary directory (`--output-parent` chooses its parent).

For one focused browser test, `scripts/playwright_evidence.py prepare --output-parent DIR
--project NAME --file e2e/x.spec.ts --grep TITLE --expect-id ID` allocates fresh output paths and
prints the owner-wrapped command to run; `export` copies one stopped run's files with hashes.
A focused result never replaces the lane sequence in CI.

## Prove a workflow end to end

`tests/smoke/` runs each user workflow (data, backtest, validation, research case, web app)
through the installed `alpha` and `alpha-web` programs in a fresh temporary home, offline, in
about two minutes. CI's `check` job runs them; the fast local tier leaves them out.

```sh
uv run python scripts/run_owned_test.py --timeout 900 -- uv run pytest -q -m smoke -n 0
```

## Process environment facts

- Web→CLI forwards `UV_CACHE_DIR` and `MPLCONFIGDIR` only when set, verbatim; it invents no
  default and does not sandbox the home, fonts or other caches. Use a fresh empty directory, not
  the owner's configuration, when verifying rendering.
- Workstation cancellation is reported only after its journal write succeeds; an uncertain
  terminal write is recovered with `project job-show --event-limit 1 --event-tail --json`.
- Retained browser fixtures use `ALPHA_TEST_PYTHON`, else the checkout's `.venv/bin/python`.

## Where code goes

Pure Python behaviour lives in the owning `packages/alpha-*` package. CLI commands live in
`apps/alpha-cli/src/alpha_cli/*_cmds.py`; web and MCP relay CLI seams; frontend models render
results Python computed. Follow the import contracts before adding a dependency. Read the
[research-integrity rules](../reference/invariants/research-integrity.md) for the invariants, the
[architecture](../ARCHITECTURE.md) for ownership and data flow, and the [ADRs](../adr/README.md) for
decisions. When behaviour changes, update the one document that owns the fact (see the table in
[CONTEXT.md](../../CONTEXT.md)); never copy a fact into a second file.

## Evidence and recovery

- Before a retry, copy the failing run's output (command, exit code, logs) somewhere private and
  new; never overwrite it. Allocate fresh output for the retry.
- After an ambiguous or unknown result, read back the real state before repeating a create, run
  or merge. A cancellation or denial ends that action; do not route around it.
- Fix from the retained evidence, keep assertions and thresholds unchanged, and say plainly which
  checks ran and which did not. A listing, a startup check or a review request is not a pass.
- Credentials, private traces and raw task conversations never go into documentation.

The [cleanup retrospective](retrospectives/2026-10-17-cleanup-execution.md) keeps dated incidents.
