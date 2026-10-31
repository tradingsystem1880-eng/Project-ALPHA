# Packet 3 daily rule implementation

**Delivery state:** In progress. The native implementation has artificial engineering proof;
the approved real-market demonstration has not begun. No market conclusion or W01–W19 completion
is claimed. The existing [Packet 3](../../context/feature-readiness-checklist-2026-10-27.md#packet-3-complete-one-real-native-rule-and-control-study)
remains the scope owner; the full roadmap is preserved there.

```json
{
  "schema_version": 1,
  "title": "Packet 3 daily rule implementation",
  "context": "Implement existing Packet 3 as one registered native daily rule/control route through existing authority, reservations, RD-Agent ownership, canonical engine, immutable evidence and V1 reports. Actual market demonstration remains blocked on legitimate durable hosting.",
  "assumptions": [
    {
      "statement": "Hunter approved the Binance BTC/USDT daily 2020\u20132022 discovery scope, frozen momentum20/control economics and bounded resources, plus an absence-only private-suite exception for this Packet3 task through delivery.",
      "verified_by": "Parent-forwarded owner approvals 2026-10-31, including Sentinel_d3b1f354a4cc8191b4b3d0752090af05; local consumed exact-contract confirmation remains mandatory before execution."
    }
  ],
  "alternatives_considered": [
    "Use existing ts_momentum instead of an exact RuleSpec source lag; the latter keeps the existing rule explanation and canonical execution seam."
  ],
  "pre_mortem": [
    "A full-day candle stamped at 23h could leak its final hour.",
    "A reconstructed captured price series could be mistaken for historical publication/revision evidence.",
    "A typed draft could be mistaken for consumed owner authority or native route qualification."
  ],
  "slices": [
    {
      "title": "Exact momentum and daily clock",
      "verify": "uv run pytest -q tests/unit/test_rules_source_lag.py tests/unit/test_utc_day_execution_feed.py",
      "expected": "Hand-specified chronology and accounting pass with legacy defaults unchanged.",
      "rollback": "Remove additive lag/timing options; retain old readers and artifacts.",
      "status": "done"
    },
    {
      "title": "Bounded verified price query and frozen identity",
      "verify": "uv run pytest -q tests/unit/test_crypto_price_snapshot_query.py tests/unit/test_native_daily_rule_study.py",
      "expected": "Full requested coverage, exact source bindings, independent restore and inert typed study identity.",
      "rollback": "Remove new internal modules; retain immutable underlying manifests.",
      "status": "done"
    },
    {
      "title": "Real native admission, worker, completion and report",
      "verify": "Actual approved route lifecycle and independent numerical fixtures, then canonical full gate",
      "expected": "Existing ControlStore and pinned RD-Agent owner execute one admitted pair and reopen identical artifacts without resetting exposure.",
      "rollback": "Keep real route closed and preserve historical reservations and artifacts.",
      "status": "in_progress"
    }
  ],
  "tier_impact": [
    "risk",
    "protected",
    "bias",
    "determinism"
  ],
  "docs_to_update": [
    "CLAUDE.md",
    "README.md",
    "docs/BUILD-STATUS.md",
    "docs/context/feature-readiness-checklist-2026-10-27.md"
  ],
  "out_of_scope": [
    "New roadmap or coordinator",
    "Private-suite exception inference",
    "Holdout inspection",
    "Tuning",
    "Paid data",
    "Paper/live trading"
  ],
  "files": [
    "packages/alpha-strategies/src/alpha_strategies/rules.py",
    "packages/alpha-backtest/src/alpha_backtest/feed.py",
    "apps/alpha-cli/src/alpha_cli/crypto_price_snapshot_query.py",
    "apps/alpha-cli/src/alpha_cli/_native_daily_rule_study.py",
    "apps/alpha-cli/src/alpha_cli/_native_daily_rule_protocol.py",
    "apps/alpha-cli/src/alpha_cli/_native_daily_rule_container.py",
    "apps/alpha-cli/src/alpha_cli/_native_daily_rule_artifacts.py",
    "apps/alpha-cli/src/alpha_cli/_native_daily_rule_projection.py",
    "apps/alpha-cli/src/alpha_cli/_native_daily_rule_restore.py",
    "apps/alpha-cli/src/alpha_cli/daily_native_cmds.py",
    "apps/alpha-cli/src/alpha_cli/daily_rule_report.py",
    "apps/alpha-cli/src/alpha_cli/crypto_bulk_store.py",
    "workers/rdagent/daily_container_entry.py",
    "workers/rdagent/qualify_daily_container.py"
  ]
}
```

## Implemented route and limits

A separately registered daily operator binds the full immutable query, source/snapshot identity,
qualified installed packages, pinned container image, critical execution guards, economics and
resources before effects. It reuses ControlStore confirmation, D0, pre-effect reservations,
attempt/exposure accounting, retained native ownership, cancellation and uncertain recovery.
The old synthetic protocols keep their exact validators and fingerprints.

All 1,096 declared days are discovery. D2/D3 are unavailable and receive no samples or confirmation
authority. The D0 mechanics fixture stays artificial. Source lag expresses exact `close[t] >
close[t−20]`, with equality/negative return flat; the Strategy Builder preserves lag on save.

The actual pinned RD-Agent LoopBase/LoopMeta running stage executes both roles through the canonical
engine. Fixed-unit strategies, fractional BTC spot CASH settlement, signals, orders, fills,
observed commissions, cash, units, trades and equity are recorded. No resize while long, shorting,
leverage, generated shell, fitting, tuning or live order route is added. Rejected orders produce
`accounting_rejection_inconclusive`, distinct from a valid zero-trade or loss/null observation.

Canonical report projections keep CryptoSnapshotV1 and the separately derived chart Parquet
snapshot distinct, with exact conversion/query/source lineage. Existing CLI/API/UI readers show
linked price/trades, equity/benchmark, drawdown, exposure, comparison and paged accounting/evidence.
They reject rehashed sidecar/query/lineage tampering and unsupported authority relabeling. The
visible PnL-before-commissions measure retains modeled spread/slippage; no cost-free replay is implied.

Missing-only evidence restore verifies an independent reference against the current trusted native
receipt and approved contract. It never imports an older database or replaces conflicting files,
so later authoritative reservations/history remain. It is not a stale database rollback facility.

## Approved study and exact execution interpretation

- Binance BTC/USDT spot, exactly 2020-01-01 through 2022-12-31, designated discovery.
- Two separate 10,000 USDT CASH accounts. Momentum targets 0.05 BTC when close[t] exceeds close[t−20],
  otherwise zero; a held positive quantity is unchanged. Control attempts 0.05 BTC at the first
  eligible next open, then holds actual units. An unaffordable control entry does not retry later.
- First20 days within the approved range warm history; first decision uses January21 close,
  available January22. No 2019 warmup or 2023 opening price is acquired or used.
- Commission10 bps per side; full spread2 bps plus slippage5 bps per side. Modeled bid/ask is
  open±6 bps before price rounding. Quantity precision6/increment0.000001 BTC; price precision2.
  These are declared simulation approximations, not verified historical exchange filters.
- Completed UTC-day knowledge occurs at next midnight; the next-open price event is ordered1µs
  later. This is a simulation ordering convention, not measured publication latency or proof of
  an executable price. Both roles use the same convention.
- No forced liquidation. Canonical valuation ends at the last admitted opening quote, December31
  +1µs. The last daily close produces an unfilled terminal decision; no January1 open is invented.
- Unaffordable buys reject without resizing. Baseline fresh daily decisions may attempt the frozen
  quantity again; any execution rejection makes the comparison inconclusive rather than a valid
  null market conclusion. Fees, cash and units remain inspectable.
- One comparison; two outcome exposures plus the existing three-exposure D0. Zero repairs,
  model calls or worker tool calls. Source intake≤four HTTP attempts/one MiB response bodies.
- Maximum60 seconds total approved wall allowance, one CPU,1 GiB physical memory. The existing
  D0 charge leaves59 seconds for the native job; no retry/restore replenishes it. Hard container
  memory/swap and CPU limits apply before worker execution; an independent watchdog preserves the
  original monotonic deadline even if the host owner dies.
- Per-file FSize is32 MiB. The entire closed output set and published evidence must pass a32 MiB
  aggregate admission bound. This is not a hard total temporary-disk-write quota; hosting must
  accommodate bounded scratch files and the existing free-space reserve.

Owner approvals were forwarded on2026-10-31. The bounded private-suite absence-only exception
extends through this task's delivery; private coverage remains UNVERIFIED. It excuses no public
failure, coverage reduction, authority bypass or broader scope. No private test contents were read.

## Runtime and storage setup

Use the existing clean RD-Agent bootstrap in [README](../../../README.md) first. Daily execution
also requires a local immutable Docker image and explicit qualification; execution never pulls an
image or creates credentials. The managed local daemon is selected explicitly. In this executor,
import-only and actual artificial native execution succeeded with image
`sha256:ae4e8b7c575fabea88a029b6cae757f342ca2525e07f7c22272d5105c346b35e`, obtained from
`python:3.12-slim@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159`.

```sh
uv run python workers/rdagent/qualify_daily_container.py --image-id sha256:ae4e8b7c575fabea88a029b6cae757f342ca2525e07f7c22272d5105c346b35e
```

The helper verifies fixed imports, hard policy and exact cleanup, then atomically creates the
ignored `.alpha/state/runtime/daily-container.json`; it refuses a different existing profile.
Runtime has no network, daemon socket, inherited credentials or writable source/packages. Only
its exact workspace is writable. Container identity is bound before start; trusted completion
requires verified container cleanup and retained POSIX cleanup. Unknown cleanup retains capacity
and full charges. The older synthetic probes keep their existing process boundary.

Cloud data use requires an operator-approved durable POSIX mount. No such root is configured here.
This first portable backend requires both bulk data and control/manifests/runs to share the same
approved mount/device/owner; it rejects symlinks, temporary roots and disposable filesystems.
The Mac UUID backend remains the default and is unchanged. No disk identity was mocked in production.

The operator supplies `<data_dir>/crypto/storage-config.json`:

```json
{
  "schema": "CryptoBulkStorageConfigV1",
  "backend": "cloud_root_identity",
  "bulk_root": "<absolute durable bulk directory>",
  "control_root": "<exact canonical durable data_dir>",
  "mount_point": "<observed approved mount>",
  "device_id": 0,
  "owner_uid": 0,
  "filesystem_type": "<observed non-disposable filesystem>",
  "mount_source": "<observed mount source>",
  "durable_hosting_reference": "<operator hosting/retention decision reference>"
}
```

The zero values above are placeholders, not observations. Configuration records a hosting decision;
identity checks do not certify a provider SLA. Preserve the existing free-space reserve. No paid
storage or configuration/security change is authorized implicitly by this example.

After legitimate bounded acquisition and qualification, public CLI entry points are:

```sh
alpha research draft-daily PROJECT --source-pack-id PACK --snapshot-id SNAPSHOT --normalized-manifest-id MANIFEST --json
alpha research approve PROJECT --help
alpha research run pilot PROJECT --json
alpha research run deep PROJECT --json
alpha research status PROJECT --json
alpha research cancel PROJECT --reason "Stop this study" --json
alpha report RUN_ID --json
```

`approve` uses the existing exact local confirmation ceremony. Deep reconnects an existing job or
completed attempt; it does not create another comparison. Pre-dispatch interruption reports the
original job UUID and known reservation state for explicit reconciliation, never a replacement.
Missing-only restore is the bounded `restore_daily_rule_evidence` seam in the existing native route.

## Verification and remaining acceptance

Focused artificial checks cover independent one-bar chronology/cash, fractional settlement and
observed fees, frozen input/operator/origin/image/code guards, typed storage/coverage/revision
limits, UI roundtrips, report semantics, tampering and bounded evidence. Actual pinned native runs
under hard1 GiB completed five stages, exercised interrupted publication and idempotent completion,
restored missing evidence while preserving a later reservation, and tested cancellation/lost-owner
quarantine. A separately killed host owner left the container bounded by its original deadline;
uncertainty was retained instead of fabricating clean evidence. Exact final-tree gate/review results
are recorded in the task handoff; preliminary/prerequisite stamps confer no final acceptance.

The initial full gate was explicitly interrupted when review found UI lag loss and provider
substitution. A later prerequisite gate was safely stopped through its owned test supervisor when
implementation continued. Those logs remain failures/interruption history, not passing evidence.
A1 GiB address-space experiment failed from mapped library footprint; replacing it with a hard
1 GiB physical container limit preserved the approved budget rather than raising it.

**Real demonstration blocker:** no approved durable bulk/control root is available. `/workspace`
is an observed overlay; platform retention is not established. The conservative mounted-root
adapter currently refuses it, but overlay alone is not proof of disposability. No real dataset was acquired, no numerical
market study began and no real-study allowance was consumed. Provider acquisition was not attempted
without storage; no provider access denial or uncertain download is claimed. Selecting legitimate
hosting and verifying its identity/retention remain necessary before real intake and the exact
owner-frozen market study. Full Packet3 market acceptance remains open.

## Storage contract reconciliation and existing artifact retention

At delivered main `ab0f6b75`, CryptoBulkStore requires a configured Mac volume UUID, mounted
directory, capacity reserve, immutable raw/normalized lineage and completion manifests. Its reserve
is max(15% total capacity,100 GB). W19 requires coherent catalog-plus-referenced-artifact restore
without erasing later reservations/exposure. Neither source requires a blanket overlay ban or
control/bulk placement on one mount. Those are conservative choices in this first mounted-root
adapter, not universal requirements or evidence that managed cloud compute can never retain data.
Environment metadata establishes no stop/rebuild/backup guarantee for this workspace.

Existing Library tools support persistent versioned files and guarded replacement without a new
account or credentials. A230-byte artificial probe was saved successfully as
`libfile_dd82d207c124819180913034ccb28e62`, file version0. Exact-version materialization into an
independent directory failed with `download failed`; no restored file exists. The returned host
`sdmntprcentralus.oaiusercontent.com` is absent from the current enforced egress allowlist, which is
consistent with the transport failure; no HTTP status was exposed, so its cause is not proven. No
permission change or automatic retry occurred. This proves write availability, not restore acceptance.

Library can retain coherent immutable checkpoint bundles; it is not a live SQLite/WAL filesystem.
A host-side bridge must first commit the existing reservation, export a consistent catalog plus all
referenced input/evidence artifacts, retain a complete version and independently acknowledge its
bytes, then permit effects. Subsequent completion retention and latest-authoritative-history
reconciliation are needed. CAS alone is not proof of complete attempt history. This bridge is not
implemented or silently substituted for the mounted-store contract. Local scratch may remain
ephemeral only when retention barriers prevent loss of charged allowance.

Minimum decision: either supply platform-backed retention/recovery facts for an existing compute
root, select an existing verified durable mount with the identity facts above, or adopt the existing
Library checkpoint path after restoring exact-byte download and implementing its retention barrier.
No infrastructure, credentials, paid service or broader egress permission was provisioned.

Size evidence from the artificial1096-day source fixture: raw104110 bytes, Parquet17336 bytes, query
JSON336083 bytes, snapshot774 bytes and source manifests4657 bytes. A completed native workspace
measured9389056 bytes across19 files. Tens of MiB is a planning estimate for one study, not an actual
Binance measurement; admitted publication remains bounded at32 MiB and scratchIO is distinct.

## Portable contract coverage after PR105

The first hosted check on `344b7334` passed 7,108 tests and skipped74 runtime-dependent cases,
but failed the unchanged93% coverage floor at92.38%. The local qualified-runtime aggregate had
passed at93.0732%. These are different execution environments; neither result replaces the other.
The hosted gaps included all123 restoration statements,66 completion statements and70 daily
dispatch statements. The private-suite absence exception does not excuse this public failure.

Additional portable public tests exercise the actual contracts through artificial observed-input
fixtures: consumed owner confirmation, existing reservations, canonical-engine accounting,
receipt/code/query/container bindings, fail-closed interrupted dispatch, missing-only recovery,
all-conflicts preflight and preservation of later authoritative reservations. Only external
runtime measurements and worker transport are fixture ports; these tests confer no native
process, physical-resource or market acceptance. Runtime-only tests and their skip conditions
remain unchanged. No source files, coverage exclusions or thresholds are relaxed.

Final qualification uses the CI runtime selection with the qualified-source environment unset,
alongside separate focused native-runtime evidence. Measured coverage and hosted delivery results
belong in the handoff/PR evidence after the coherent tree is checked. Real acquisition and study
execution remain blocked on admitted retained storage, with no real-study allowance consumed.

## Shared daily root review correction

Review of the published portable-coverage repair found that `DailyRuleWorkspaceV1` wrongly made
the shared root exclusive to its first project. New `DailyRuleWorkspaceV2` records only canonical
root identity. Strict legacyV1 markers remain accepted as historical root metadata without byte
rewrites. Each launch still requires its independently consumed exact owner authority; the
retained claim binds root/project/contract/job/reservation, and the same-study exposure-reset
guard remains unchanged. Eligible new launches validate the workspace before queue/job/reservation
effects, then the retained owner rechecks before dispatch. This prevents known invalid markers
from consuming a native allowance; uncertainty after committed dispatch preparation stays charged.
Portable regressions exercise two approved projects sharing inputs and root, a single authorized
native reservation, rejection of a second same-study launch, legacy-marker preservation and invalid
root/authority rejection. These tests establish contracts, not native-process or market acceptance.
