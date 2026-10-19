# Development loop

Use a focused check while editing, then run final acceptance on the finished tree.
Complete code, documentation, generated contracts and assets before the full gate;
changing them afterward invalidates its evidence.

| Change | Start here |
| --- | --- |
| Python behavior | `uv run pytest -q tests/unit/test_<feature>.py` and its covering integration tests |
| Python imports | `uv run lint-imports` |
| Frontend model | In `apps/alpha-web/frontend`: `npm test -- src/path/model.test.ts` |
| Browser behavior | In that directory: `npm run test:e2e -- e2e/feature.spec.ts` |
| Component readiness | `uv run python scripts/gate.py component NAME` |
| Final acceptance | `uv run python scripts/gate.py full` |

The frontend component runs `npm run build` once, including TypeScript, before
`test:e2e:built`. The standalone `test:e2e` still builds first; use the built-only
command only after a fresh build. API and SPA freshness remain required.

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
