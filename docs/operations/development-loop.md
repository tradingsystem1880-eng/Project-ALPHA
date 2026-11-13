# Development loop

Use a focused check while editing, then run final acceptance on the finished tree.
Complete code, documentation, generated contracts and assets before the full gate;
changing them afterward invalidates its evidence.

The implementing owner carries the authorized task through necessary fixes, covering QA,
independent review findings, documentation/context upkeep and authorized delivery. Use existing
development roles and context maps. Related slices can share one coherent commit; focused
feedback is required during editing, and the unchanged full gate and required independent
review apply before every actual commit. A line-count target does not force a commit or another
aggregate run. Missing publication authority is resolved against a concrete qualified payload.

On Linux, orphan-dependent lifecycle tests require the existing process owner:

```sh
uv run python scripts/run_owned_test.py -- uv run pytest -q tests/unit/test_durable_job_lease.py
```

The scoped `owned_test_process` fixture fails before those test bodies run when owner identity
is missing, stale or not a live ancestor running the wrapper. Identity includes Linux process
birth ticks and survives pytest workers. The wrapper publishes it after enabling subreaping;
the child cannot independently inspect that ancestor's subreaper flag. This is an execution
precondition, not a security or application-authority boundary. Ordinary focused tests remain
runnable with plain pytest, and non-Linux execution keeps its existing behavior.
The guarded cases cover durable leases, interrupted research execution, suite cancellation
and workstation job cancellation/startup failure. Mere subprocess use does not establish this
dependency: a parent that waits for its own children supplies its own reaping, and pidfd exit
readiness or stopped-execution checks do not assert zombie disappearance.

The web-to-CLI process environment preserves a configured `UV_CACHE_DIR` so isolated workers
can use the runtime's writable cache when the default home cache is read-only. It does not invent
a cache path when none is configured. HOME and credential filtering, worker exit/schema
validation and installed-versus-missing readiness behavior retain their existing boundaries.

The same web-to-CLI filter now forwards `MPLCONFIGDIR` only when present in the server's
process environment, verbatim, for Matplotlib configuration and cache placement. It adds no
default, validation, normalization or directory creation. Unset stays absent; empty, relative
or unusable values are forwarded too and may leave Matplotlib using a fallback. This is
trusted operator configuration, including inherited shell state, not a request environment
map. Other allowlists, HOME/XDG/credential filtering and separate worker/model filters are
unchanged. Existing renderer Agg selection and rcParams-default initialization remain intact.

For bounded verification, clear unrelated inherited state before starting the server and
supply a new empty owned writable absolute directory. Do not copy owner configuration:
`MPLCONFIGDIR` can contain `matplotlibrc`, so it is not merely output storage. Also verify
an owned working directory without `matplotlibrc`, which can take precedence. Keep the
directory through the run and retain required evidence before cleanup. Passing a path does
not prove the directory Matplotlib actually used; verify that separately when rendering.
This first-hop contract does not isolate the whole home, Python bytecode, font discovery,
other library/descendant caches or networking, and is not a sandbox.

| Change | Start here |
| --- | --- |
| Python behavior | `uv run pytest -q tests/unit/test_<feature>.py` and its covering integration tests |
| Python imports | `uv run lint-imports` |
| Frontend model | In `apps/alpha-web/frontend`: `npm test -- src/path/model.test.ts` |
| Browser behavior | Use the focused Playwright evidence workflow below with the intended existing config |
| Component readiness | `uv run python scripts/gate.py component NAME` |
| Candidate qualification | `python3 scripts/gate.py preflight [--json]` |
| Final acceptance | `uv run python scripts/gate.py full` |

The read-only qualification preflight reports the candidate ref and available resources, checks
allowlisted public tracked prerequisites and Git object alternates, reuses the manual-size and
harness-lint checks, checks the candidate-local environment and mypy executable, confirms Node and
npm are available, checks that the canonical full-gate mypy command includes `tests`, and runs Atlas
freshness only with an already available Python 3.12 interpreter. The mypy scope entry is labeled
`scope_only`; a separate `not_run` entry makes clear that preflight did not execute mypy. JSON and
human output label checks as metadata, scope-only, executed, or not run. Preflight never installs
dependencies or repairs outputs; blockers return a nonzero status. Preflight success is a readiness
report; final acceptance still requires the full gate.

The JSON result also reports `mutation_selection`: the effective `ALPHA_GATE_BASE` ref (explicit
environment value or the canonical `origin/main` default), whether the ref and merge base resolved,
whether target selection was an exact diff or the gate's conservative all-quant fallback, and the
selected target count. An exact diff that selects every quant module is labeled as an exact
all-module selection; an unavailable base is a warning that names the fallback cause and returns a
nonzero preflight result. Preflight never chooses or repairs the base.

`freshness_index_alignment` checks only the paths used by both canonical frontend API and SPA
freshness commands. It blocks if either step is missing or any tracked target is absent from the
checkout, including a sparse `skip-worktree` omission. Those commands compare the working tree with
the Git index. If candidate output is unstaged or untracked, preflight reports an actionable
`index_setup` warning and identifies the path; this does not establish that generated output is
stale. The Atlas generator's `--check` remains a separate executed check and reports actual
`generated_drift`. Neither check stages files or regenerates outputs.

The frontend component runs `npm run build` once, including TypeScript, before
`test:e2e:built`. The standalone `test:e2e` still builds first; use the built-only
command only after a fresh build. API and SPA freshness remain required.
Both npm entry points route through `scripts/run_frontend_browser_lanes.py`, a fixed,
fail-fast default → risk-basis → risk-live → native sequence. It has no test-selection
pass-through. For a deliberately focused ordinary check, use the existing evidence
workflow below; dedicated fixtures require their own config/driver, not a default
file filter. A focused result never substitutes for the mandatory sequence.

All lanes require installed Node/Playwright/Chromium, Vite and the controller Python
with `uv`, `alpha` and dependencies. The native lane additionally requires explicit
`ALPHA_RDAGENT_SOURCE` and `ALPHA_STOCK_PYTHON` (the installed runtime's lexical
`venv/bin/python` path), with its lock/config files. The existing native validator
checks the pinned source and measures the runtime; presence checks alone are not
runtime qualification. An explicit installed `PLAYWRIGHT_BROWSERS_PATH` survives
native's fresh HOME; otherwise the current Linux cache is made explicit. No install,
resolution or browser download is performed. The npm uv launcher uses
`--offline --no-python-downloads --no-sync`; child uv calls inherit equivalent
controls. Missing inputs fail before any lane. When neither native selector is set
(e.g. hosted CI), the other three lanes still run and the runner prints
`native lane skipped: ALPHA_RDAGENT_SOURCE/ALPHA_STOCK_PYTHON not provisioned`;
setting only one selector, or an invalid one, still fails.

Fresh selection reports come from the original Playwright configs and retain every
configured project repetition and existing performance opt-in. Execution must return
exactly those `(projectName, spec.id, file)` identities. Existing retry and skip
policies remain unchanged. The native driver is selected by one exact pytest node;
its fresh JUnit must contain exactly one matching executed testcase with no
skip/error/failure. Pytest exit zero alone is insufficient.

The adapter prints a retained `alpha-browser-lanes-*` temporary directory outside
source, with separate selection reports, execution reports, logs and artifacts.
`--output-parent /existing/private/parent` chooses another existing parent. Every
invocation allocates a new directory. On failure, prior completed lanes and the
error are recorded, later lanes remain unrun, and all outputs are kept. Native
allocates its own new `native/evidence` child. Historical receipts are never inputs.
Risk-live builds directly with Vite into its fresh `risk-live/spa`; it must not use
`normalize-build.mjs` or a copied production bundle. Ordinary/native lanes still
require the normal production build. See the [routing scope](../superpowers/plans/2026-11-10-browser-lane-routing.md)
for bounded checks and still-pending full acceptance.

The hosted backend job starts the stdlib-only runner with
`uv run --no-project --python 3.12 python scripts/gate.py component backend`.
Its unchanged first steps, `uv lock --check` and `uv sync --locked`, own root
dependency setup, including cold starts and repair of missing packages. The job
does not first run a separate root sync or an implicit project sync. Other jobs
retain their setup: workers use isolated projects, and frontend browser provisioning
requires installed, locked Playwright dependencies. No gate step is skipped.

For a focused browser invocation, `scripts/playwright_evidence.py prepare` allocates
fresh absolute output paths and checks a listing through the existing process owner:

```sh
.venv/bin/python scripts/playwright_evidence.py prepare --output-parent /ABS/private-existing-parent \
  --project chromium-minimum --file e2e/feature.spec.ts --grep 'intended title' --expect-id REVIEWED_NATIVE_ID
```

Use a reviewed native ID from the intended public listing. After a fresh build,
use the returned `cwd`, owner-wrapped `test_argv` and log paths; prepare again for
each invocation. The helper does not run that test command or prevent later reuse.
Optional `export --run-dir /ABS/run --destination /ABS/new-copy --test-exit 1 --stopped`
copies enumerated files from one stopped run and verifies sizes/hashes. Originals
and partial copies remain on failure. Listing/copy success is not test acceptance;
the supplied test status and stopped-writer declaration remain caller-reported.

`NAME` is `backend`, `frontend`, `literature`, `qlib`, `atlas` or `eval`.
Focused checks give feedback; they do not confer aggregate acceptance. The `fast`
backend lane excludes platform tests, so control-plane and web changes need their
covering tests explicitly. Keep browser tests serial while their shared store
requires it. Run timing budgets on an idle reference machine under the existing
opt-in policy; functional browser coverage remains required.

Place pure Python behavior in the existing `packages/alpha-*` owner. CLI command
registration belongs in `apps/alpha-cli/src/alpha_cli/*_cmds.py`; reusable application
composition stays in that package. Web/MCP relay supported CLI seams, and frontend
models render Python-authoritative results. Follow the enforced import contracts
before adding a dependency or extracting a module.

Within the CLI, `_crypto_persistence.py` owns exact-byte immutable crypto JSON
writes; typed command wrappers keep document identity and directory selection.
`_control_json.py` owns pure JSON encoding/validation/decoding. `control_store.py`
retains its existing facade names, database transactions, migrations and authority.
Source relocation changes new execution fingerprints intentionally; it never
rewrites historical research evidence or changes document content identities.

Read [the operating manual](../../CLAUDE.md) for mandatory invariants,
[architecture](../ARCHITECTURE.md) for ownership and data flow,
[ADRs](../adr/README.md) for decisions, and [build history](../BUILD-STATUS.md)
for recorded delivery evidence. Plans describe scope; they are not proof of a pass.

## Evidence and recovery

Before a run or retry:

1. Record the base, exact candidate paths, command, tool versions, configured caches
   and available disk. Check prerequisites before starting; report missing runtime
   evidence and obtain the required authorization before provisioning it. Define an
   explicit permitted path list before searching or reading; protected links permit
   metadata checks only. Stop content access when protection is unclear.
2. For a focused browser run, check the locked Playwright listing with the intended
   config, project and filter. Use `prepare` above and review
   its intended cases separately from additional projects. Require nonempty intended
   selection and every requested native ID; this is not a complete expected-case-set
   check. A bad config, zero intended cases or missing requested ID blocks execution.
   Use the existing process owner and avoid concurrent duplicate runs.
3. Before any retry, preserve the current failure's permitted
   artifacts in a new absolute private task directory. Retain the original command,
   error and exit code, plus copied relative paths, byte counts and SHA256 values.
   `export` above verifies enumerated files from one stopped
   run; account for required evidence separately rather than claiming a complete or
   atomic snapshot. Reject links, traversal, special files and overwrites. If copying
   or verification fails, stop the retry and leave source and partial evidence intact.
   Allocate fresh output for the retry; run `prepare` again.
4. For an ambiguous or `UNKNOWN` action result, read back authoritative state before
   repeating a create, run or merge. Cancellation or denial ends the relevant write
   action; do not switch tools, routes or flags to carry it through. Resume only after
   fresh explicit authorization. Preserve bounded status/error metadata without
   guessing service-internal causes or widening permissions, credentials or scope.
5. Only with explicit task authorization, a failed CLI read returning 401 permits
   one bounded recovery: preserve the failed read, perform one supported sanitized
   auth-status check without printing or retaining raw account/credential output,
   and, only if status succeeds, retry the identical read once with the same CLI,
   account and configuration. Stop if either check or retry fails. Do not change
   credentials, scopes, security settings or configuration. This grants no write
   retry permission and does not apply to the separate pending-upload CONNECT 403
   support case.
6. Diagnose from the retained evidence before changing code. Keep any fix separately
   identified, preserve assertions and thresholds, and validate the final frozen
   candidate through independent review and the required gate. Record failed attempts
   separately. Distinguish an observed pass from a startup check, selection listing,
   review request or unavailable coverage; never infer acceptance from those alone.

Private traces, credentials, support identifiers and raw task conversations stay
outside public documentation and publication payloads. See the
[cleanup execution retrospective](retrospectives/2026-10-17-cleanup-execution.md) for dated observations and
their evidence limits; keep incident history there rather than duplicating it here.

Workstation cancellation distinguishes verified process-group cleanup from durable terminal
publication. The lease reports cancellation only after its journal callback succeeds. Publication
errors take precedence over a local cancellation request in UI/SSE status. An uncertain terminal
write uses `project job-show --event-limit 1 --event-tail --json` within the original CLI deadline;
matching job/status recovers a lost response. There is no second terminal write. Unresolved state
remains reserved until authoritative reconciliation; process cleanup alone does not release it.

The self-owned retained browser fixtures keep their original interpreter selection:
`ALPHA_TEST_PYTHON` when set, otherwise the candidate's `.venv/bin/python`. The
adapter checks executable presence without replacing that selector. This and the
other prerequisite diagnostics are not exhaustive runtime qualification; actual
fixture/browser execution is still required.
