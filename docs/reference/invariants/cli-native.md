---
owner: command line native upstream loops
sources:
  - apps/alpha-cli/src/alpha_cli/_native_*.py
  - apps/alpha-cli/src/alpha_cli/native_*.py
  - apps/alpha-cli/src/alpha_cli/daily_native_cmds.py
  - apps/alpha-cli/src/alpha_cli/daily_rule_report.py
  - apps/alpha-cli/src/alpha_cli/rdagent_cmds.py
  - apps/alpha-cli/src/alpha_cli/rdagent_run_*.py
  - tests/unit/test_rdagent_run_command.py
  - tests/unit/test_native_*.py
  - tests/unit/test_daily_rule_*.py
  - tests/unit/test_daily_native_*.py
verified: 802c31b3ac77f10b
---

# Command line native invariants

What must not break when changing the native upstream lanes: the synthetic native fixture supervisor, the pinned
RD-Agent loop child (`workers/rdagent`), synthetic and costed rule studies, the registered daily rule route, the stock
RDLoop diagnostics and the synthetic Qlib-to-Nautilus pipeline. Every rule here is taken from the code, and the
project-wide rule is [research integrity § Models and isolated workers](research-integrity.md#models-and-isolated-workers).

## Starting a factor loop

- `alpha rdagent run` only builds the argument list `factor_loop_launch.py` already accepts and starts that launcher as a
  child. It sets no prompt, memory, threshold, cap or rule, and no retry. Each launcher option has one config key of
  the same name; a key left out puts nothing on the line, so the launcher's default applies.
  `tests/unit/test_rdagent_run_command.py` checks every launcher option has a key, rebuilds the owner's launch element
  by element, and parses the list with the launcher's own parser.
- The dry run prints a limit only when the config passes it on; otherwise it says the launcher or gateway sets it.
- The config holds only the key file's path. The path goes to the child in an environment variable, never in the command
  text; the command never reads, prints or stores the file. `alpha rdagent status` only reads the run folder.

## Synthetic only

- Native fixture jobs run only in a disposable workspace that carries the `synthetic-only` marker, with a canonical
  UUID job id (`native_supervisor.py`). The one exception is a daily workspace, which needs the exact approved daily
  authority and a canonical persistent store.
- There is no production activation and no caller-supplied command: fixtures are the closed set `success`, `failure`,
  `wait`, `descendant`, `escape`, `native_loop`.
- Engineering approval of a synthetic rule never establishes market evidence (`_native_rule_protocol.py`). Real
  discovery through this lane is blocked before any data is read.
- Synthetic position artifacts (`_native_rule_artifacts.py`) are distinct from statistical research evidence.
- `ml_native_plan.py` and `ml_refit.py` produce inert diagnostics or metadata with no
  admission, registration or fit authority.
- A stock RDLoop invocation is consumed once, atomically, in the control store before spawn
  (`_native_stock_launch.consume_before_spawn`); there is no refund or usage ledger, and a stopped, cancelled or
  re-measured owner cannot consume.

## Launch identity

- `NativeLaunch` refuses a study without its typed `RuleAuthority`, a study that differs from the exact owner-approved
  request, an unknown mode, or a symlinked or unresolved source (`_native_loop_admission.py`).
- A launch measures its source and mode into a fingerprint; a child command needs a reservation and unchanged launch
  bytes. Enforced by `tests/unit/test_native_launch_fingerprint_contracts.py` and
  `tests/unit/test_native_public_contracts.py`.
- A daily launch must equal `study_from_contract(approved)` and its measured implementation fingerprints must equal the
  approved `hashes`; inputs are reopened and re-checked before launch.
- Daily rule contracts require exactly five variant exposures (three D0, two execution), five loop steps, and zero model
  calls, tokens and tool calls (`_native_daily_rule_protocol.validate_daily_contract`).

## Approval fingerprints

- Rule approvals bind `rule_implementation_fingerprints` (`_native_rule_environment.py`): worker files, the worker
  requirements lock, the measured isolated runtime, the probe evaluator, and the data or query hash. The `code` and
  `evaluator` hashes bind code structure, not bytes ([ADR-0045](../../adr/0045-approvals-bind-code-structure.md),
  `_structural_digest.py`); locks, the measured runtime and non-Python files stay bound by bytes.
- For daily studies the `code` hash also covers `DAILY_GUARD_FILES`: every `_native_daily_rule_*` guard,
  `_native_loop_admission.py`, `_native_rule_*` modules, `_native_fixture_store.py`, `native_supervisor.py`,
  `control_store.py`, `_control_json.py`, `owner_auth.py`, `_artifacts.py`, `artifact_contract.py`, `durable_lease.py`,
  `research_analysis_plan.py`, `crypto_price_snapshot_query.py`, `crypto_bulk_store.py`, `daily_native_cmds.py`,
  `_control_schema.py`, `_native_daily_rule_history.py`, `_ml_observation_store.py`, `job_capacity.py`,
  `paper_resources.py`, `run_store.py`, `run_context.py`, `_native_tearsheet.py`, `research_readiness.py`,
  `research_runtime.py`, `_native_stock_launch.py`, `native_stock_fixture.py`, the package `__init__.py`, and the
  worker `daily_container_entry.py` ([ADR-0048](../../adr/0048-daily-rule-lane-binding-and-named-months.md)).
- Every `alpha_cli` import in a bound file, at module level or inside a function, must reach a bound file or a reviewed
  exemption whose import never executes on a daily path (`tests/unit/test_daily_guard_boundary.py::REVIEWED_OUTSIDE`);
  a new import of an unbound module fails that test. `alpha_research`, `alpha_validation` and `research_cmds.py` are not
  bound by daily approvals (open owner decision).
- A comment, formatting or unread-docstring edit to those files keeps an approval valid; any change to what they do
  invalidates every existing daily rule approval, so say so in the change description. Rule approvals made before
  ADR-0045 no longer verify and must be re-drafted and re-approved by the owner. See also
  [engineering § Hash-bound source bytes](engineering.md#hash-bound-source-bytes).
- A rule contract (daily or synthetic) runs only with the owner's review plus one consumed local-confirmation receipt
  for that exact contract and actor (`_native_rule_protocol.require_rule_confirmation`). Only the Workstation's local
  confirmation creates that receipt, so a bare `alpha research approve exploration` of a rule contract is refused
  before any review or phase change (`ControlStore.review_research_contract`); the owner approves it in the Workstation.
- Symlinked guard files, runtime roots, metadata or packages, and stray bytecode in the runtime, fail closed.
- The measured runtime also pins the root `uv.lock` and the source bytes of the packages in its profile; changing
  either fails the measurement.

## Process ownership

- The supervisor supports only the `linux-posix-v1` profile, requires the default SIGCHLD disposition and records the
  host boot and PID namespace identity.
- The child never receives the control-store path or the owner lock descriptor. Process-group cleanup is not a sandbox
  against hostile same-user Python.
- Only the live issuing process with the retained owner lock may act as owner; a different process fails.
- Stale-heartbeat reconciliation skips jobs with a native claim: lease age proves no process ended, so capacity and the
  reservation stay held until the owner records cleanup.
- The daily rule container (`_native_daily_rule_container.py`) gets no Docker socket, credentials, shell, checkout parent
  or mutable package path, and needs supported Linux resource enforcement.
- Per-job `payload-<job_id>` directories sit directly under the control-store data root.

## Results and inspection

- Results are validated from the same bounded receipt bytes observed after child cleanup (`NativeLaunch.verify_result`),
  capped at `MAX_NATIVE_RECEIPT_BYTES`.
- `_native_daily_rule_restore.py` restores only missing immutable daily evidence and keeps current authority and
  reservations.
- `native_stock_inspect.py` opens the store read-only and always reports `resume_allowed: false` and
  `resume_authority: none`. It never dispatches, deserialises a checkpoint or authorises a resume.
- Never start a replacement job, borrow a reservation or reset counters from inspection output; reconcile through the
  original owner process. Cross-owner restart continuation does not exist.
- Keep `native_supervisor` start-up free of the native-loop admission stack, `alpha_research` and scipy. Enforced by
  `tests/unit/test_native_supervisor_import_boundary.py`.
