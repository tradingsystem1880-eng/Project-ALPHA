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
