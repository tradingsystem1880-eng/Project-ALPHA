# Clean RD-Agent cloud bootstrap

**Delivery state:** Completed implementation and clean-bootstrap qualification. Repository delivery still requires the normal full gate, independent review and hosted checks on the published candidate.

```json
{
  "schema_version": 1,
  "title": "Qualify clean RD-Agent cloud bootstrap",
  "context": "Close the existing foundation backlog's clean environment and pinned-source acquisition gaps while preserving optional root/browser provisioning.",
  "assumptions": [
    {"statement": "The exact public RD-Agent Git commit is reachable through the supported transport.", "verified_by": "Fresh scratch fetch of 484776c211e4fbbeef03e0ec00d6bbee7362a4f4 and source digest verification on 2026-10-31."},
    {"statement": "Native fixture launch requires the isolated worker interpreter as well as the two qualified profiles.", "verified_by": "_native_loop_admission.command and existing profile/source measurement code."}
  ],
  "alternatives_considered": ["Treat root/browser readiness as worker readiness; rejected because these are distinct scopes.", "Reuse existing environments or pristine source; rejected because that cannot prove clean bootstrap."],
  "pre_mortem": ["Source fetch failure could discard evidence; retain partial directories and never reset existing source.", "Existing profiles could be silently overwritten; preserve current identity validation and interrupted-build retirement rules.", "Provisioning could be confused with execution authority or private coverage; retain explicit limitations."],
  "slices": [
    {"title": "Add explicit pinned-source and isolated launcher provisioning", "verify": "Focused cloud setup regressions including default mode, exact pin acquisition, failure preservation and re-entry", "expected": "Minimal mode stays non-fetching; explicit RD-Agent mode creates and validates its required environments.", "rollback": "Revert only new opt-in logic and tests; retain scratch evidence.", "status": "done"},
    {"title": "Qualify a clean container and preserve exact evidence", "verify": "Fresh host checkout with empty caches; fresh container checkout and virtualenv paths using locked download caches; source/profile measurement, native-loop conformance and idempotent re-entry", "expected": "Measured bootstrap receipts replace the specific unverified backlog entry without claiming all workers, Mac or private coverage complete.", "rollback": "Preserve failed container/workspace evidence and leave acceptance open.", "status": "done"}
  ],
  "tier_impact": ["protected"],
  "docs_to_update": ["docs/superpowers/plans/2026-10-26-native-rule-authority.md", "docs/BUILD-STATUS.md", "docs/superpowers/plans/2026-10-31-clean-rdagent-bootstrap.md"],
  "out_of_scope": ["README owned by another task", "Trading or provider calls", "Private test contents", "Mac readiness", "Other worker capability qualification", "Credential or network-policy changes"],
  "files": ["scripts/cloud_setup.sh", "tests/unit/test_cloud_setup.py", "docs/superpowers/plans/2026-10-26-native-rule-authority.md", "docs/BUILD-STATUS.md", "docs/superpowers/plans/2026-10-31-clean-rdagent-bootstrap.md"]
}
```

Use `ALPHA_CLOUD_FOUNDATION=1 ALPHA_CLOUD_RDAGENT=1 bash scripts/cloud_setup.sh` for
explicit RD-Agent provisioning. With no supplied pristine/source paths it acquires the fixed
Git commit into `.alpha/state/runtime/rdagent-pristine` and creates the verified derived source
at `.alpha/state/runtime/rdagent-source`. Existing source must remain pinned and clean; failed
partial acquisitions are preserved. Foundation alone retains its non-fetching behavior.

The two closed profiles and isolated RD-Agent launcher are provisioning scope only. The script
prints the derived source export for later shells; this grants no execution authority, whole-package
upstream qualification, full-suite acceptance or private-suite coverage. Git source identity does
not verify archive bytes. README instructions are coordinated separately with its current owner.

## Executed qualification — 2026-10-31

Fresh public ALPHA fetch: `2a8aa50b5669f6645ecfb5c0e0e23fb8f932bf82`, plus this setup-script delta.
The host run started without project/worker virtualenvs, pristine/derived source or task caches.
It installed the locked root/frontend dependencies, acquired RD-Agent, created its isolated
launcher and both closed profiles, passed the browser smoke, then passed 20 native-loop
conformance tests. Re-entry retained both measured profile identities without fetching or
creating environments again. Focused orchestration tests passed 26 cases with one host-specific
fontconfig skip; shell syntax, Ruff and plan validation passed.

A separate fresh container repeated these checks from a fresh network checkout and without
preexisting project virtualenvs or RD-Agent source. It reused only downloaded package/browser
caches through hardlinks to fit the bounded disk; dependency locks and source pins remained
enforced. The container's 20 conformance tests passed in 18.31 seconds, re-entry retained both
profile identities without refetch/recreation, and it exited 0 at 02:11:42 UTC.

- Python image: `python@sha256:392307d22300de8b5986851a12d9176dfc0fc073e65bf6523ebd7dcbeb23564e`
  (Python 3.12.14); uv 0.12.23 installed from PyPI.
- Node 24.19.0/npm runtime copied from
  `node@sha256:a9f5f7c91a432850b2a8a7797adf5eadb6c733ceed61167806cee7ea7fbc29df`.
- RD-Agent Git commit: `484776c211e4fbbeef03e0ec00d6bbee7362a4f4`; verified source digest
  `0266b2d63328f88fcaf6f239bf6d67f29c896b8161566f794ef69465b7788707`.
- Root lock: `f88c1b2f556a0d228cd6826cad4cf6c4ef16514f5bf0f57e36e1729a83254bcd`;
  worker lock: `ed5adbce78d487cce3987d8d6ac7abdbbc7c67b4392723e4e18f663351563a5a`.
- Rule lock: `ee43c576ba73fbde7669f2eff20a2bbc71ada5ddf5ddcd582297933006629fcc`;
  economics lock: `57ce3fda0c8a13c68a0656df1473b1aecd0b1daf5f1800b0d329fc501c0b32be`.
- Container rule identity: `c19dac116600c61206ce2732ad2476be1acd255a12443e5f94abddf4b603e12b`;
  economics identity: `20e2b084bbcdf551795d01c50f87db4b277fbaa0fc693b05fb3c854c22101293`.

The initial Dockerfile build never executed: its client tried to create read-only
`/home/agent/.docker/buildx`. It was not retried or given different authentication. The successful
qualification ran the already-pulled pinned Python image directly, mounted the combined CA bundle
read-only and retained the configured proxy; Docker/auth/network protection settings were not
changed. Task-owned host dependencies were subsequently relinked to identical locked cache bytes
using `uv sync --locked --reinstall` with `UV_LINK_MODE=hardlink` to recover disk capacity.
Original source/profile evidence and prior gate receipts remain preserved. Archive bytes,
upstream's whole application dependency environment, private suites and Mac readiness remain
UNVERIFIED. This is provisioning and bounded synthetic conformance, not execution authority.

## Coordinated foundation integration — 2026-10-31

The final candidate combines bootstrap `8051ac33bc80ccd5ccf3b335d5659ec873960087`,
checkpoint retention `c260c5136ef956139eaca649e228fd859d17ab70` and native README review
`3db13037ed2445206b3c386556a38d1721c4653c` against main `2a8aa50b`. The complete README
branch delta is retained, including its reader guide and removal of the superseded API route.
Both gate command registries/handlers coexist; README review evidence is retained by the
checkpoint allowlist. A real archive round-trip regression verifies that the receipt survives
byte-for-byte without being restored or accepted as a current review.

Shared build histories retain all three source records. README adds the explicit bootstrap
opt-in and dry-run/verified-archive commands; its native session decision must bind this final
tree and fetched main. Atlas is regenerated from all combined sources. Original source heads
are preserved by normal ancestry merges; attaching remaining ancestry may reuse acceptance
only when the exact source tree, comparisons, README scope and all component definitions stay
unchanged and normal guards pass. The combined candidate requires its own full gate and
independent review; no individual source receipt accepts this assembly. Private coverage remains
UNVERIFIED and broader product/Mac scope is unchanged.


## Supplied-input validation follow-up — 2026-11-01

Base: main `fcec79b91c18467ff818c1f7d03684a9908ac9de`. This bounded correction moves the
existing dependency-free required-derived-path, pristine HEAD-pin and cleanliness checks before
cache setup, dependency installs and Git guards. Explicit full bootstrap still supplies its existing
default paths and acquires an absent pristine checkout at the exact pin. The same validation runs
after acquisition before derived copying. Locked installs, source digest verification, rule/economics
profiles, failed-partial retention and interrupted-venv preservation keep their existing semantics.

Implementation sequence: first require zero provisioning/timeouts, guard/exclude changes, runtime
creation or acquisition for invalid supplied inputs; then move the checks and exercise the existing
valid-source/default/foundation/acquisition/re-entry cases plus invalid fetched bytes. The seven new
invalid-input expectations failed against the original script before implementation. Focused shell
fixtures use local Git repositories and stub external tools; they perform no live downloads. This
slice changes no import DAG, look-ahead, determinism, admission or execution-authority behavior.
README and the operating manual describe early refusal. Relative source paths still resolve from
the checkout; relative cache paths retain their original invocation-directory semantics. No separate command or documentation tree
is introduced. Final independent review, whole-tree gate and hosted delivery evidence remain required;
focused results alone do not establish aggregate acceptance. Private coverage remains UNVERIFIED.

Focused verification: `uv run pytest -q tests/unit/test_cloud_setup.py` passed 39 tests with one
host-specific fontconfig skip; Ruff check/format and `bash -n scripts/cloud_setup.sh` passed.
The initial seven failures remain retained as red-phase evidence. These offline fixtures do not
repeat clean-container qualification or establish private coverage.

Independent review of the first frozen candidate blocked a checkout-relative existence predicate
that was still evaluated from the invocation directory in full mode. Three added relative-path
invalid-input cases reproduced the bypass before correction. Both the predicate and validation
now run from the checkout without changing cache-path resolution. That candidate's full gate was
stopped during typing (exit130); its patch, partial receipts and logs are retained separately and
are not a pass. Fresh corrected-tree qualification/review are required. The reviewer also could
not establish that any recorded bounded absence-only approval covers this follow-up; no existing
exception is expanded here, and guarded delivery remains blocked unless applicability is proven.


## Bounded public-fixture repair checkpoint — 2026-11-01

The corrected setup tree's canonical full gate ended in backend at 93.10% public coverage:
7,246 passed, five failed, 74 skipped and one setup error. Remaining components did not run;
no aggregate acceptance stamp exists. Exact logs, receipts and coverage bytes are retained.
The six-case smaller selection passed with five workers; a controlled CPU-load comparison
reproduced startup-margin and CLI-timeout failures. This is resource-sensitivity evidence,
not proof of full-load concurrency correctness or a waiver of any failing check.

The public closure-kill test's cleanup had a demonstrated late-barrier race. Its existing
safe barrier can appear after the first check while the retained owner is paused. The minimal
seven-line repair rechecks that same barrier in `finally` and reaps only its retained `Popen`.
The original assertion, owner deadline, wait allowances and cleanup expectations remain intact.
The applied repair's focused negative control still fails its injected assertion but emits no
leaked-child/unraisable warning. This is a fixture repair, not a production lifecycle refactor.
All three diagnostic test paths were checked against `gate.protected_reason` and are editable
public tests. Protected test contents were neither read nor edited.

The existing native no-start diagnostic now also records `unclaimed` wait failures; the web
capacity test appends bounded terminal-error/line-tail context to its unchanged cancellation
assertions. The consolidated focused selection reported 44 passed, one skipped and one failure.
That remaining web failure now names an unchanged five-second heartbeat CLI timeout. Its relation
to the original aggregate failure and the original TMPDIR startup phase are not established.
The controller-death margin remains at least 1.0 s; no assertion, deadline, coverage floor,
exclusion, production source or runtime profile was weakened. Targeted Ruff and typing pass.

This is an uncommitted consolidation checkpoint on `fcec79b9`, awaiting reader-first delivery,
actual-main reconciliation, pending bounded private-suite authorization and fresh independent
review/whole-tree qualification. No aggregate rerun is started on this obsolete base. Private
coverage stays UNVERIFIED; no real study, allowance use, Mac access or trading occurred.


## Lazy intake startup correction checkpoint — 2026-11-01

A bounded heartbeat profile isolated ordinary subprocess startup from journal work on independent
public synthetic stores. An idle profiled heartbeat used 2.253 s total, including 1.562 s importing
research intake/runtime before the journal; append and cancellation read used 4.85 ms and 2.11 ms.
Under five concurrent calls plus four bounded CPU workers on a four-core quota, three of five
baseline calls timed out at the unchanged five-second limit before entering the journal. A scratch
lazy-import overlay completed all five in 1.71–1.90 s; idle time was 0.478 s. These are retained
experimental measurements, not universal latency or whole-suite concurrency guarantees.

The implementation moves only `draft_exploration_contract`'s import to its sole `project create`
caller. Public arguments/results, create validation/projection errors and all journal/lease/accounting
logic remain unchanged. Clean-process import-presence regressions for heartbeat, job status and
job show failed before the move. They now pass without any wall-clock assertion. Additional
clean-process create cases prove the dependency is loaded on execution and invalid ideas retain
exit2; existing project-create workspace and post-commit projection-error cases remain covered.

Focused five-worker verification covering bootstrap, entry/create/validation and the six reported
lifecycle cases passed 62 tests with one host-specific fontconfig skip in 30.43 s. The earlier
44-pass/one-failure checkpoint remains failure history. Its heartbeat timeout now has a measured
startup inefficiency and narrow repair; this does not prove the original full-gate web cause or
TMPDIR startup phase, nor resolve the supervisor startup and controller-margin acceptance under
full load. Deadlines, the 1.0 s margin, assertions, coverage floor/exclusions and runtime profiles
are unchanged. Fresh independent review covers the complete consolidated bootstrap, fixture and
lazy-import candidate. Reader-first reconciliation, pending private-suite approval and an actual
final-tree aggregate remain required; no new aggregate or publication is attempted here.


## Reader-main reconciliation and bounded approval — 2026-11-01

Fetched main `4e3ca30d49b6c403bc70c59bbad14f33b5bad720` contains reader commit
`ab70633fbddb4f355ea64e7c7c496536ce71653e` from PR108. The prior consolidated Git tree
`f4e3ecf54b9ccbe6ccf293de3ad62ad483a19c2c` and its byte-identical patch remain preserved;
Git stash `b00845201a794f17988889ba5bf7f960d1e6450b` retains the preintegration candidate.
The shared manual keeps both cloud/history guidance, both appended build histories remain intact,
and Atlas is regenerated from the actual combined tree. Reader production bytes are unchanged.

The owner explicitly approved the bounded cloud-setup correction proceeding without the absent
private engineering suite, including necessary corrections through delivery. Consent provenance
is retained privately. This is an absence-only task exception: private coverage remains
UNVERIFIED, never PASS. It excuses no public failure, missing component, failed startup-margin
receipt or other finding. The unchanged 93% floor, exclusions, deadlines, assertions, independent
review, README evidence and normal Git/hosted checks remain mandatory. It grants no protected-test
content access, self-approval, bypass, force publication or unrelated standing exception.

An environment restart removed the earlier `/tmp` raw logs and timing traces. Those losses are
explicitly recorded; historical summaries come from the retained tool transcript and are not
reconstructed as raw execution logs. Workspace-resident failed backend/README receipts, coverage
bytes, Git checkpoints and the exact consolidated source patch survived and were copied into the
ignored task evidence directory. Fresh final-tree evidence is saved there rather than `/tmp`.
Earlier failed and focused results retain their original scope and do not qualify this assembly.

Hosted backend selection supplies no external RD-Agent source/profile and runs the same shared
component command. Final qualification uses the matching default unconfigured-native selection;
optional native skips confer no native qualification. Actual platform/runtime observations and
all final commands/results are retained in the ignored task evidence. No gate policy, coverage
standard, admission rule or runtime profile is changed to conduct this delivery.
