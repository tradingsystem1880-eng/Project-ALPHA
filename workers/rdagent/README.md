# Pinned native loop development probe

This isolated Python 3.12 project exercises RD-Agent commit
`484776c211e4fbbeef03e0ec00d6bbee7362a4f4` with fixed synthetic inputs. It has no application
dispatch route. No ALPHA package imports this worker. `NativeFixtureLoop` explicitly uses
upstream `LoopMeta` and inherits upstream `run`, `_run_step`, `dump` and `load` without overrides.
That original fixture never imports or instantiates stock `RDLoop`; the separate
stock continuation diagnostic below does.

## Reproduce

Obtain upstream commit `484776c211e4fbbeef03e0ec00d6bbee7362a4f4` as a pristine checkout, either
from `https://github.com/microsoft/RD-Agent/archive/484776c211e4fbbeef03e0ec00d6bbee7362a4f4.tar.gz`
(expected archive SHA-256 `4c5d1c792b133d7148bb4d59aea09b8accf4d14deb4a10ffed276ce178dd855c`) or by
fetching that exact commit with git and checking `git rev-parse HEAD`. Keep it unmodified.
Its root contains a top-level `test/` package, which the shadow check below always rejects because
`test` is a standard-library name. Point `ALPHA_RDAGENT_SOURCE` at a separate derived root holding a
byte-identical copy of `rdagent/` plus upstream `LICENSE` (and optionally `pyproject.toml`); nothing
outside `rdagent/` is imported. Record the pristine origin, HEAD and every excluded entry.

The probe verifies all 694 files under `rdagent/` (except bytecode) against the aggregate digest
in `source_pin.py` before any upstream import, rejects symlinks/drift and records each imported
source file's hash. That tree digest is the only measured source identity: results report
`source_pin.verified.source_tree_sha256`, while the commit and archive checksum appear only under
`source_pin.expected` and are listed in `source_pin.not_verified`. Verify the archive checksum
yourself when you download it. Source remains external; no upstream scheduler is vendored here.
The external source root is never placed on `sys.path`: a narrow finder resolves only `rdagent`
within the verified directory and binds each worker helper to its reviewed source file. Importable
source-root shadows of worker, standard-library or installed dependency modules are rejected.
The fresh bytecode cache is selected before importing even the local source verifier. Every
successful probe validates both upstream and worker helper origin hashes.

From the repository root, using the normal ALPHA test environment:

```sh
uv sync --locked --project workers/rdagent
ALPHA_RDAGENT_SOURCE=/absolute/path/to/derived-rdagent-484776-root \
  uv run --no-sync pytest -q tests/unit/test_native_loop_conformance.py
```

Optionally set `ALPHA_RDAGENT_RECEIPTS` to a disposable evidence directory. Each probe writes a
unique JSON receipt there, preserving failures across reruns. Without an explicit source path,
the public tests skip and confer no native qualification. The isolated `uv.lock` is a focused
import dependency subset, **not** upstream's full application dependency environment. Root
dependencies and lock are unchanged.

## Install on a development machine

`bash scripts/setup_rdagent.sh` (idempotent; about 1.1 GB, under a minute with a warm uv cache)
fetches the pinned commit into `.alpha/state/runtime/rdagent-pristine` when absent, derives
`.alpha/state/runtime/rdagent-source`, verifies the source-tree digest, syncs `.venv` and builds
and validates `.venv-rule-qualified` and `.venv-economics-qualified`. It is the RD-Agent part of
`ALPHA_CLOUD_FOUNDATION=1 ALPHA_CLOUD_RDAGENT=1 scripts/cloud_setup.sh` without Git hooks, npm,
browser download or fontconfig. All of it is gitignored (`.alpha/state/`, `.venv-*/`). It prints
`export ALPHA_RDAGENT_SOURCE=…`, which runs the conformance, W04 and rule tests. Two optional
flags add the rest (both idempotent, both off by default so the default install stays small):

- `--with-daily-container` pulls exactly one image, `python@sha256:aa943ce4…d159`
  (`python:3.12-slim`, about 120 MB), checks that it is image
  `sha256:ae4e8b7c575fabea88a029b6cae757f342ca2525e07f7c22272d5105c346b35e`, and runs
  `qualify_daily_container.py` (an offline import smoke under the daily security policy; no
  derived image is built), which writes `.alpha/state/runtime/daily-container.json`. Without it the
  13 daily-study tests that need the image are skipped with that reason.
- `--with-stock-runtime` builds the stock `RDLoop` runtime bundle
  `.alpha/state/runtime/rdagent-stock-py311/` (`venv/`, `dependencies.lock.txt`,
  `stock-profile.json`; about 230 MB) on CPython 3.11 from
  [`stock-requirements.lock`](stock-requirements.lock) with `--require-hashes --no-deps`, then
  `install_stock_profile.py` proves the installed distributions are exactly the 60 locked ones and
  records an inventory digest (`--verify` rechecks it on every run). It prints
  `export ALPHA_STOCK_PYTHON=…/venv/bin/python` and a fresh `ALPHA_STOCK_RECEIPTS` directory.

**Why Python 3.11 for the stock runtime:** upstream RD-Agent at the pin declares and tests only
3.10 and 3.11 (`pyproject.toml` classifiers; `constraints/3.10.txt`, `constraints/3.11.txt`), and
the earlier hand-built stock runtime was 3.11. The stock bundle imports no ALPHA package, so the
project's 3.12 requirement does not apply to it. The lock is the minimum closure for this fixture
path (`stock_fixture_entry.py` → `rdagent.core.conf`, `rdagent.components.workflow.rd_loop` and the
core records): `docker`, `rich`, `numpy`, `openai`, `tiktoken`, `litellm` plus the conformance
imports and their declared dependencies; pandas and scikit-learn are not imported and not
installed. It was resolved against upstream `constraints/3.11.txt` (so `dill==0.3.9` and
`psutil==6.1.0`, not the conformance environment's newer pins) with package dates up to the pin's
commit date. `litellm` is pinned to 1.97.0, the version upstream's own `constraints/3.10.txt`
names; it is also the library a future model connection would go through, which this runtime does
not make (the fixture clears all model settings and blocks the network).

Smoke check: `uv run python scripts/run_owned_test.py -- uv run pytest -m smoke
tests/smoke/test_rdagent_smoke.py`.

## Contracts exercised

- `direct_exp_gen` returns native `Hypothesis` and `Experiment` under `propose`/`exp_gen`.
  Coding is a noop, running attaches only fixed metrics, feedback is a native
  `HypothesisFeedback` subclass, and record uses native `Trace.sync_dag_parent_and_hist`.
- SUPPORTED, CONTRADICTED, INCONCLUSIVE and INVALID are **supplied synthetic labels**, not
  classifications produced by ALPHA's scientific acceptance logic. Labels and metric names,
  values and units survive recording and signed checkpoint loading. Native `decision` and
  `acceptable` remain false for every fixture; truth conversion raises instead of collapsing
  a label into generic success. No label grants evidence or approval authority.
- Native `run(step_n=0)` executes one stage; `step_n=1` executes two. These post-effect stop
  knobs are not admission budgets. A separate ephemeral fixture allowance checks each stage
  before its fixed operator, and remains outside the pickle. It tests only the fixture guard,
  **not ControlStore reservation, settlement, exposure or economics integration**.
- One live fixture owner guards the entire run/load/resume operation. Native tasks are drained
  before unlocking. Duplicate start, stale/foreign checkpoint and concurrent continuation are
  rejected. Successful checkpoints resume once under that same owner. Cancellation closes the
  owner and retains the fixture charge for interrupted work.
- Upstream advances its in-memory cursor in `finally` even when a stage is cancelled, but writes
  no checkpoint for that incomplete stage. Tests load the actual last successful checkpoint
  and reject further execution through the cancelled owner. No durable consumption ledger or
  cross-owner recovery is added.

## Scope and limits

Every test launches a new sanitized subprocess in an empty temporary directory. Environment,
HOME, log path, signing-key path and bytecode cache are fixture-local. The key is generated by
the existing upstream signed-pickle implementation. An import allowlist excludes backends and
stock loops; Python audit tripwires reject network connection/DNS and subprocess effects. These
checks contain trusted fixture mistakes; they are not hostile-code or same-UID security isolation.

No real provider, LLM, generated code, market data, holdout, broker, live database, migration or
real owner-approval action executes. ALPHA retains admission/budget/exposure/execution/economics/
evidence/approval responsibility. Owner-death recovery, physical containment, production
activation and scientific artifact admission remain unqualified. Public focused checks are not a
full gate or release approval.

## Bounded W04 admission fixture

`test_native_w04_admission.py` composes this actual child with the existing synthetic process
owner and scratch-created ControlStore. It approves measured worker/code/lock/interpreter/config
fingerprints through existing synthetic test helpers, reserves the full remaining D1 envelope,
requires one reserved variant and positive CPU allocation, and commits a single trusted owner
claim before child effects.
The closed `native_loop` launcher accepts only fixed fixture modes; there is no caller command,
dynamic operator, provider, model or production route. Interpreter/config and lock identity are
measured; they do not qualify the installed dependency environment or enforce CPU/token usage.

The child receives a reference-only JSON admission identity, never a ControlStore handle or owner
lock. Its existing ephemeral stage guard derives `loop_steps` from the actual reservation. The
signed native pickle includes a digest of job/reservation/spec/manifest/owner/mode/allowance.
Resume is allowed only in the same live child; path, byte digest and admission binding are checked
before continuing. The reserve is charged once and never restored from checkpoint state.

The supervisor retains the actual native child handle and applies the existing independent lease
and process-group cleanup. After cleanup, exact feedback labels and metric names/values/units are
validated against the admitted fixed mode. Every successful result remains process-only and
`pending_scientific_admission` / `not_admitted`. No scientific run ID or completed D1 attempt is
invented. Failure/cancellation reconciles through existing failed-attempt/link/status records;
unknown cleanup or result/journal publication retains capacity and the complete charge.

The W04 process-only lifecycle event schema and fields are unchanged. The later closed rule
workflow adds the narrowly validated `rule_result` binding described below; old readers must not
write/read those new outcomes in a mixed deployment. Study `ExplorationMandateV1`
references grant no launch authority; this fixture is not a new registration in the closed
scientific operator registry. It exercises existing reservation exposure, not generic study/trial
admission or scientific acceptance. Full resource metering, durable scientific artifact admission,
cross-owner recovery and production activation remain W08 gaps. See
[`2026-10-26-native-w04-admission.md`](https://github.com/tradingsystem1880-eng/Project-ALPHA/blob/pre-thin-2026-11-14/docs/work/archive/2026-10/2026-10-26-native-w04-admission.md).

## Closed frozen-rule authority profiles (2026-10-26)

See the [current handoff plan](https://github.com/tradingsystem1880-eng/Project-ALPHA/blob/pre-thin-2026-11-14/docs/work/archive/2026-10/2026-10-26-native-rule-authority.md).
The old `.venv` and `uv.lock` above remain the W04 conformance environment. Two **fresh-only**
environments add closed position and costed synthetic profiles, with hash-pinned requirements
reusing already approved root/worker versions. Root `uv.lock` is unchanged. The economics profile
uses root-pinned Nautilus 1.228.0, pytz 2026.2 and tqdm 4.68.2; it does not overwrite the old profile.

On a fresh checkout with the normal locked root environment and complete pinned upstream available:

```sh
uv venv --python 3.12 workers/rdagent/.venv-rule-qualified
uv pip install --python workers/rdagent/.venv-rule-qualified/bin/python --require-hashes --no-deps -r workers/rdagent/rule-requirements.lock
.venv/bin/python -B workers/rdagent/install_rule_profile.py
uv venv --python 3.12 workers/rdagent/.venv-economics-qualified
uv pip install --python workers/rdagent/.venv-economics-qualified/bin/python --require-hashes --no-deps -r workers/rdagent/economics-requirements.lock
.venv/bin/python -B workers/rdagent/install_rule_profile.py --economics
```

`.gitignore` now covers both through its `.venv-*/` entry (checked 2026-11-14 with
`git check-ignore`); `cloud_setup.sh` still also lists `/workers/rdagent/.venv-rule-qualified/` and
`/workers/rdagent/.venv-economics-qualified/` in the clone-local `.git/info/exclude`. Unignored, the
generated environments would be hashed into the gate tree and scanned by ruff and semgrep as source.
These are generated-environment excludes, not test or coverage exclusions.

Do not run these commands over preserved environments. The installer copies complete noncache
source/resources, compares original distribution metadata to pyproject, preserves Requires-Dist,
and writes honest source-install provenance and RECORD. It invokes no build backend and installs
no editable hooks. It rejects symlinks, duplicate metadata and unexpected site hooks. Profile
inventories bind every installed dependency/source byte, source pyprojects and root/profile locks;
pre-effect admission and result checks compare them to the owner-approved fingerprints. Runtime
imports record actual package and metadata origins. Fresh bytecode is selected before imports.

The positions profile omits Nautilus, so alpha-strategies has an explicitly unsatisfied declared
dependency. Economics includes Nautilus and its required closure; alpha-data still has unqualified
provider dependencies, listed precisely in its installed PROFILE.json. Full package API qualification
is false for every local distribution. No fallback root sys.path or merged package environment is
used. These are local fixture source installations, not built wheels or upstream full applications.

V1 evaluates the original visible bars through actual rule_signal. V2 owns a separate seven-row
synthetic dataset (one warmup and six execution bars); it runs actual run_backtest/RuleStrategy
sequentially for the baseline and flat control before Feedback. The unchanged audit hook was
exercised by the real compiled engine. Only serializable canonical results enter checkpoints;
Nautilus resources are disposed by the canonical engine. Synchronous execution relies on the
external supervisor deadline; no immediate cooperative cancellation or hard real-time claim is made.

An exact approved contract and consumed real local-confirmation receipt are required before the
existing reservation/claim. Two outcome exposures share one trial. D0 uses the existing three-variant
engineering allowance; the caller must explicitly approve a sufficient budget. No repair/default
budget is invented. Signed checkpoint continuation and publication recovery do not create another
trial or refund charges. Scientific acceptance and empirical W08 remain blocked.

### Observed result byte binding

For closed rule success only, the trusted supervisor validates one bounded receipt read after
cleanup and records `rule_result` with nested schema `SyntheticNativeRuleObservationV1` and the
SHA256 of those same bytes. The existing100000-byte fixed receipt cap is enforced during that read.
This field is accepted only for the registered native rule reservation and clean successful
outcome; original process-only V1 fields stay unchanged. The issuer detaches and freezes the
closed nested string mapping; journal serialization copies it without exposing mutable owner
evidence. The hash alone proves no execution.
Completion compares the captured bytes to the trusted observation, publishes those exact bytes,
and pins `native_receipt_ref` in existing immutable attempt details. The verified completed-attempt
reader rechecks it before accepting derived numerical artifacts; general case summaries return
metadata and do not revalidate D1 artifacts. Self-consistent rehashing
of receipt/economics/projections cannot replace the recorded result. No SQL schema or ledger is
added. Unbound historical rule outcomes/artifacts cannot be upgraded into completion; retained
charge/capacity and investigation are required. Older writers/readers do not understand the new
rule binding; deployment cutover remains unqualified. Generic standalone UI/report readers keep
their existing integrity/unknown-state behavior and are not newly qualified by this boundary.

### Storage and history preflight

Linux execution may use the existing `cloud_root_identity` backend with control, manifests,
runs and bulk on one explicitly retained mount/device/owner. A study with a temporary duration
still needs retained storage: `/tmp`, tmpfs and overlay roots remain rejected, and the reserve
is the larger of 15% and 100 GB unless the owner has set an attributed value of at least 10 GB
for that root ([ADR-0043](../../docs/adr/0043-storage-reserve-is-owner-set.md),
[storage settings](../../docs/operations/storage-settings.md)). Verify underlying capacity and retention too; free space
reported by a thin virtual disk is not proof of available backing-disk space or a backup.

This option does not change the native `macos_volume_uuid` backend. Keep existing Mac profiles,
archives and authoritative history intact. A separate Linux root must not evade the existing
database-wide one-trial reservation guard. No new Mac/Linux UUID bridge is implemented.

Before designating an execution root, run the explicit-root metadata reader against existing
authority, using the installed project environment:

```sh
uv run python scripts/inspect_daily_rule_history.py --data-dir /absolute/existing/data
```

It opens one read-only schema-7 snapshot, selects closed routing metadata rather than project
prose or full contracts, and counts daily deep reservations across all projects. Counts cover
the entire selected store even when the contract list is paged. Event-study job counts also
cover unlinked jobs and other research routes; they do not prove process liveness. Malformed,
oversized, missing or older-schema history is unknown, never an empty installation. SQLite may
use WAL/SHM sidecars; this path does not write database records or change journal settings.

The report always grants no authority to initialize, migrate or switch roots. Reconcile prior
and unknown records first; do not import artificial ledgers, copy stale authority over later
state, or reset consumption. Actual activation still requires qualified Linux process/container
boundaries, retained storage, real input bindings and exact local owner confirmation. See the
[implementation record](https://github.com/tradingsystem1880-eng/Project-ALPHA/blob/pre-thin-2026-11-14/docs/work/archive/2026-10/2026-10-31-linux-storage-history.md).

## Stock RDLoop continuation diagnostic

The additive `stock_fixture_entry.py` now executes the actual pinned
`rdagent.components.workflow.rd_loop.RDLoop`. Its constructor loads fixed native
Scenario, HypothesisGen, Hypothesis2Experiment, Developer (coder/runner) and
Experiment2Feedback implementations from `stock_fixture.py`. All five stock stage
methods and upstream run/dump/load remain unchanged; the trace guard delegates
recording to native `Trace.sync_dag_parent_and_hist`. This uses an isolated pinned
source loader, not the stock CLI or a financial scenario.

The public `test_native_stock_fixture.py` obtains a reference through
`alpha_cli.native_stock_fixture.request_from_owner`, checking the existing exact
synthetic owner, canonical running reservation, cancellation, code/evaluator
fingerprint and minimum reserved envelope. It runs only with explicitly supplied
`ALPHA_RDAGENT_SOURCE`, `ALPHA_STOCK_PYTHON` and `ALPHA_STOCK_RECEIPTS` paths.
Root test dependencies and the full native application environment are separate;
no installation or dependency change is part of this slice.

The child rejects malformed/oversized requests before native imports, rechecks
worker/source identity, clears inherited environment, uses public synthetic
signing material and rejects network, provider, shell and credential-file effects.
Only the existing read-only `uname -p` and `ldconfig -p` dependency import probes
are allowed. No generated code or real tool executes.

Native `step_n=1` completes proposal AND coding before stopping. The last successful
signed checkpoint is hash-checked and loaded into a fresh checkout directory;
remaining running/feedback/record stages complete without repeating earlier
attempts. Pre-effect counters stay in the live fixture guard outside the pickle.
Tests also inject actual `asyncio.CancelledError` before the runner body, exhaust
fake model allowance before feedback and tamper checkpoint bytes before load.
The cancelled guard cannot continue, and the last successful checkpoint survives.
Cross-owner/process restart recovery remains unqualified.

`validate_stock_artifacts` reads bounded JSON and checkpoint bytes only, never
unpickles worker artifacts. It checks exact request/hash bindings, native class,
stage order, trace history/parent/loop identities, fixed synthetic observations
and unaccepted feedback. Canonical JSON comparison rejects boolean/numeric type
substitutions independently of hashes. Successful diagnostic output remains
`synthetic_only`, `not_admitted` and `production_dispatch=false`.

These references and counters are NOT durable consumption or a new ledger.
Repeated reference creation does not prevent another process from reusing one;
the whole existing reservation remains unchanged. CPU allocation is checked but
not enforced as a CPU cap; tests apply their own 40-second child timeout and reap
it. This does not qualify provider/subscription limits, dollar caps, installed
dependency integrity, hostile-code containment or production process ownership.
The standalone diagnostic adds no launch authority; the retained-owner successor
below extends only internal synthetic dispatch, using the existing accounting store.
Production registration, durable execution ownership, scientific admission,
protected-suite/full-gate qualification and independent release review remain gates.

## Retained-owner stock dispatch successor

`StockFixtureLaunch` is a second exact, closed launch identity accepted by the
existing internal synthetic owner. It inherits the non-scientific NativeLaunch
shape but rejects every study/authority and arbitrary mode. The runtime selector
names an existing bundle containing `venv/bin/python`, `venv/pyvenv.cfg` and
`dependencies.lock.txt`. Code/source/worker/interpreter/config/lock identity is
bound into the canonical approved invocation. This measures a runtime; it does
not install or qualify its dependencies, grant inference or bypass storage rules.
No public research command or production activation is added.

The existing `start_synthetic_owner` reconstructs that exact identity in its
retained owner process. `_Owner.spawn`, its `Popen`, immediate safety lease,
process-group cleanup and existing immutable observations remain the launch path.
The child receives only a fixed bounded reference, neither owner lock nor store.
The supervised workspace requires the existing synthetic marker and exact job
path. Its own environment is cleared before native settings import.

A stock claim carries its full launch-profile hash. Immediately before spawn,
`consume_before_spawn` uses the existing ControlStore write transaction to validate
the live owner/claim, active reservation, unchanged profile, stop/deadline state
and the fixed reserved envelope. One protected `native_invocation` event in
existing `job_events` records five stages/two fake-model/two fake-tool attempts;
commit precedes `Popen`. It is whole-invocation consumption, not measured API
usage or another ledger. No reservation/balance row is rewritten or refunded.

Rollback prevents spawn. A committed consumption followed by cancellation,
process-creation failure or lost availability cannot be reminted. Existing durable
claims prohibit relaunch after owner exit/reopen; start requires prior stock
consumption. Generic journal append cannot write the private event. Legacy
histories without stock markers remain readable; malformed stock events on
legacy claims are rejected. Readers/writers must deploy coherently: older readers
cannot validate the new scoped claim/event; no history migration is performed.
The earlier synthetic-model-allowance prototype has a different fixed profile
and grants no authority for this route; it is not copied as a second ledger.

A successful retained stock child must pass the same strict artifact validator.
The returned bounded receipt bytes are rechecked against the validated hash,
preventing replacement between validation and publication. Every result remains
synthetic/process-only and `not_admitted`, with no scientific run/D1 completion
invented. Internal dispatch now executes this fixture; production registration,
actual provider/subscription/token/USD enforcement, CPU caps, full installed
runtime integrity, arbitrary-descendant containment and full project qualification
remain separate gates. No live inference or other-host work is part of this slice.

## Typed stock-worker boundary successor

[Worker hardening](../../docs/operations/native-worker-hardening.md) records targeted
Python3.11 stock-runtime typing separately from the lighter conformance environment.
Its closed request/audit/context/result checks keep the exact native RDLoop and the
existing three-file worker manifest. Changed bytes require freshly derived profiles;
old approvals/history are not rewritten. Synthetic execution remains unqualified for
live inference, scientific admission or hard budget enforcement.

## Model gateway (2026-11-14)

`model_gateway.py` is the one way RD-Agent reaches an AI model
([ADR-0044](../../docs/adr/0044-rdagent-model-gateway.md)). It is a stdlib-only program, run with
any Python 3.11 or 3.12, that listens on `127.0.0.1` only and speaks the OpenAI chat-completions
and embeddings formats; it imports neither ALPHA nor RD-Agent. Chat goes to the signed-in Codex
CLI (`codex exec`, confined: read-only, ephemeral, no user configuration, no tools, no web search,
RD-Agent's system message in place of Codex's built-in instructions), embeddings to local Ollama
`nomic-embed-text`, and an optional paid route to an OpenAI-compatible provider whose key the
owner sets in the environment. The fixture loops above still clear every model setting; nothing
here changes them.

```sh
python3 workers/rdagent/model_gateway.py serve --data-dir /absolute/data/dir --run-id <id> \
  --accept-unhonoured temperature          # writes model-gateway/session.json; logs to stderr
python3 workers/rdagent/model_gateway.py status --data-dir /absolute/data/dir
```

RD-Agent is pointed at it with `CHAT_MODEL=lm_studio/alpha-chat`,
`EMBEDDING_MODEL=lm_studio/alpha-embed`, `LM_STUDIO_API_BASE=<base_url>/v1`,
`LM_STUDIO_API_KEY=<token>` (both from `session.json`, a per-start local token, mode 0600) and
`LITELLM_LOCAL_MODEL_COST_MAP=True` (otherwise LiteLLM downloads its price list at import). The
`lm_studio/` prefix is LiteLLM's generic OpenAI-compatible provider: unlike `openai/<unknown
name>` it forwards `response_format`, so the gateway can enforce RD-Agent's JSON mode.

- **Fidelity:** each request parameter is honoured, enforced another way (JSON checked and retried;
  a JSON schema passed as `--output-schema`; streaming replayed after the whole reply), waived only
  if listed in `--accept-unhonoured` (and then recorded on every call), or refused with an
  OpenAI-shaped 400 naming it. On the Codex route `temperature`, `top_p`, `seed`, penalties and
  `max_tokens` cannot be honoured; RD-Agent always sends `temperature` 0.5, so its launch accepts
  losing that one. Tools, `stop`, `n`>1, images and unknown keys are always refused.
- **Budget:** `--run-max-calls` (60), `--month-max-calls` (3000), `--run-max-usd` (10) and
  `--month-max-usd` (50, the owner's ceiling, cannot be raised) are checked under a file lock before
  every model attempt and fail closed. State: `<data-dir>/model-gateway/budget.json`; the data
  directory may not be inside a git tree; unreadable state refuses every call.
- **Records:** `<data-dir>/model-gateway/calls.jsonl`, one line per request (route, real model,
  effort, honoured/enforced/waived/refused, attempts, JSON validity, tokens, dollars, time, status,
  prompt and reply hashes). No prompt or reply text unless `--log-content`.
- **No silent switch:** a Codex usage limit returns `codex_usage_limit` (429); the paid route is
  used only when the gateway is started with `--chat-route api` and the owner's
  `ALPHA_GATEWAY_API_BASE`/`ALPHA_GATEWAY_API_KEY` plus `--api-model` and both prices.

Checks: `uv run pytest -q tests/unit/test_rdagent_model_gateway.py` (no sockets, fake `codex`) and
`uv run python scripts/run_owned_test.py -- uv run pytest -q -m smoke -n 0
tests/smoke/test_rdagent_model_gateway_smoke.py` (loopback only; with `ALPHA_RDAGENT_SOURCE` and
`ALPHA_STOCK_PYTHON` set it also drives RD-Agent's own `APIBackend` through LiteLLM against the
fake route). Measurements: [the task's verification](https://github.com/tradingsystem1880-eng/Project-ALPHA/blob/pre-thin-2026-11-14/docs/work/archive/2026-11/2026-11-14-rdagent-model-gateway/04-verify.md).
It is not part of `scripts/setup.sh` or `gate.py doctor`: it needs no install, and whether Codex is
signed in is already what `codex login status` reports.

## ALPHA-judged factor loop (2026-11-14)

RD-Agent's own factor loop (`rdagent.app.qlib_rd_loop.factor`, unmodified) with ALPHA as the
judge ([ADR-0049](../../docs/adr/0049-alpha-judges-rdagent-factors.md)). RD-Agent proposes and
codes factors; its settings `QLIB_FACTOR_SCEN`, `QLIB_FACTOR_HYPOTHESIS_GEN`, `QLIB_FACTOR_RUNNER`
and `QLIB_FACTOR_SUMMARIZER` name four classes in `alpha_factor_judge.py`; the runner sends the
factor values to `alpha_cli.rdagent_factor_eval` in ALPHA's environment, which screens each new
factor (rank IC against the next-open-to-next-open return, autocorrelation-adjusted inference,
BH over the cross-run trial ledger) and replays only those that pass through ALPHA's canonical
synchronized engine with crypto costs. RD-Agent never sees 2024 or later; no Qlib model, Docker
image, MLflow or conda is involved.

```sh
bash scripts/setup_rdagent.sh --with-factor-runtime      # once; hash-pinned Python 3.11 runtime
export ALPHA_RDAGENT_SOURCE=... ALPHA_FACTOR_PYTHON=...   # as printed by the setup script
.venv/bin/python workers/rdagent/factor_loop_launch.py run \
  --data-dir /abs/alpha/data --run-dir /abs/runs/<date>-<slug> \
  --gateway-data-dir /abs/runs/model-gateway-state \
  --trial-ledger /abs/runs/rdagent-trial-ledger/rdagent-factor-trials.jsonl \
  --run-id <id> --loop-n 2      # at most 3 loops and 60 model calls; Codex and Ollama routes
```

- `factor-requirements.lock`: 79 hash-pinned packages (the stock runtime's plus pandas 2.2.3,
  tables, pyarrow, pandarallel, fire, scipy); recorded by
  `install_stock_profile.py --profile factor`. `gate.py doctor` names it when missing.
- `factor_loop_entry.py`: verifies the source pin, imports RD-Agent through a meta-path finder
  (the source root is never on `sys.path`) and runs the loop.
- `alpha_factor_data.py`: writes RD-Agent's `daily_pv.h5` folders and the truncated copies the
  prefix-invariance (look-ahead) check uses.
- The run folder holds `panel/` (frozen panel and receipt), `factor_data/`, `work/` (RD-Agent's
  own log and workspaces), `evaluations/` and `evaluations.jsonl` (one ALPHA record per
  iteration), `feedback.jsonl` (the model's suggestion beside ALPHA's decision), `launch.jsonl`,
  `logs/` and `receipt.json`. The trial ledger is shared by all runs and append-only.
- Generated factor code runs with the gateway's address and token removed from its environment.

### Evidence recorded per trial

All files below live under the run directory, outside git; they remain exploratory, not admitted.

- `evaluations/iter-<n>/series/<code_sha256>.screen.parquet`: daily rank IC and finite-name counts.
- `evaluations/iter-<n>/series/<code_sha256>.buckets.parquet`: direction-adjusted tercile outcomes and observation counts.
- `evaluations/iter-<n>/series/<code_sha256>.buckets_daily.parquet`: outcomes per day and tercile (bucket 3 is the replay's top third).
- `evaluations/iter-<n>/series/<code_sha256>.replay.parquet`: canonical period returns, turnover, fees and slippage.
- `evaluations/iter-<n>/series/<code_sha256>.holdings.parquet`: decision-day instruments, target weights and scores.
- `evaluations/iter-<n>/series/series.json`: factor hashes and file hashes, bound into evaluation inputs and trial-ledger evidence references; unavailable series carry `series_note`.
- `code/<code_sha256>.py`: the exact factor code, written once and checked on reuse.
- `rounds.jsonl`: RD-Agent's hypothesis, tasks and feedback words linked to factor hashes and both decisions; `feedback.jsonl` stays unchanged.
- `steps.jsonl`: UTC start/end records for each loop step, including error types.
- `calls-labelled.jsonl`: this run's gateway calls labelled by loop and step; `launch.jsonl` also records launcher step starts.
- New trial-ledger rows carry a deterministic plain-English `plain_name` beside the original name.

### Exposure log and imported trials

```sh
.venv/bin/python -m alpha_cli.rdagent_exposure add \
  --ledger /abs/runs/rdagent-trial-ledger/rdagent-factor-trials.jsonl --file /abs/exposures.json
.venv/bin/python -m alpha_cli.rdagent_exposure list \
  --ledger /abs/runs/rdagent-trial-ledger/rdagent-factor-trials.jsonl --json
.venv/bin/python -m alpha_cli.rdagent_factor_eval import-historical \
  --ledger /abs/runs/rdagent-trial-ledger/rdagent-factor-trials.jsonl --file /abs/historical-trials.json
```

`add` appends validated disclosures to `rdagent-exposure-log.jsonl` beside the trial ledger,
outside git; its input is a JSON list without `schema`, `entry_index` or `label`, and duplicate
content refuses the whole call. `list` writes nothing and shows the entries and each trial's
current exposure label (`--json` for canonical JSON, omit it for plain text). `import-historical`
appends V2 `IMPORTED` trials with hashes of the supplied absolute `code_path` files and their
original windows and provenance; they count in the distinct-code family with p = 1, are never
evaluated or replayed, and later identical code is a `REPEAT`.

An exposure matches when its end date reaches the trial's reserved start, its case-insensitive
Python regex matches the factor name, and its matching instruments overlap the trial's
instruments (or are `["*"]`); legacy trials use the 15-coin loop universe. Matching `known` or
`suspected` exposures mark the protected window previously exposed and unable to give fresh
confirmation; `unknown` stays disclosed, and a missing log leaves exposure unknown.

Choosing the model route (owner decision 2026-11-14: DeepSeek through OpenRouter is allowed for
RD-Agent, with temperature control; caps unchanged at 60 calls and 10 USD a run, 50 USD a month):

- **Codex (default, no cost):** as above. `temperature` is waived and recorded on every call.
- **DeepSeek through OpenRouter (paid, honours temperature):** model
  `deepseek/deepseek-v4.1-flash-1017` (DeepSeek V4.1 Flash, 17 October 2026 snapshot served by
  DeepSeek; 1,048,576-token context; OpenRouter lists `response_format`, `structured_outputs`,
  `temperature` and optional `reasoning` for it), USD 0.038 per million input and 0.50 per
  million output tokens (cache reads 0.01), read from https://openrouter.ai/api/v1/models on
  2026-11-14 12:35 UTC. Chosen over the undated `deepseek/deepseek-v4.1-flash` (0.0507 / 0.2028)
  because a dated snapshot cannot change under a run; re-read the prices before each use.
  `--api-openrouter` makes OpenRouter route only to providers that honour every parameter sent
  (`provider.require_parameters`) and settles the budget with the cost OpenRouter reports
  (`usage.cost`, recorded beside the gateway's own estimate as `estimated_usd`). The key reaches
  only the gateway process: load the owner's file inside the same command, never print it.

```sh
bash -c 'set -a; . ~/.config/alpha/openrouter.env; set +a; exec .venv/bin/python \
  workers/rdagent/factor_loop_launch.py run --chat-route api --api-openrouter \
  --api-model deepseek/deepseek-v4.1-flash-1017 \
  --api-price-in-per-mtok 0.038 --api-price-out-per-mtok 0.5 \
  --data-dir ... --run-dir ... --gateway-data-dir ... --trial-ledger ... --run-id ... --loop-n 2'
```

  First run 2026-11-14 13:04-13:13 UTC (run `rdloop-deepseek-20261114-1`, 3 iterations): 54
  calls of 60, USD 0.044 as reported by OpenRouter (gateway estimate 0.039), every reply valid
  on the first attempt, temperature honoured. Nine factors entered the ledger (trials 6-14),
  mostly short-term reversal: five failed the screen, one failed to run, three passed the screen
  and failed the replay after costs (daily turnover 0.52-0.79). No candidate. One run per route
  is not a quality comparison.
- Embeddings stay on local Ollama on both routes.
- Not yet: supervision by `alpha`'s native job supervisor
  ([backlog](../../docs/roadmap/backlog/rdagent-factor-loop-supervision.md)); a Nautilus replay;
  the candidate-to-research-case hand-off
  ([backlog](../../docs/roadmap/backlog/rdagent-candidate-to-research-case.md)).
