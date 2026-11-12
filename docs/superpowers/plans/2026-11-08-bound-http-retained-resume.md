# Versioned accounted retained completed-window resume

**Delivery state:** Implemented – qualification pending — code only in uncommitted candidate a631e8e7; never merged or gated

Canonical v9 W05/W02 market-data slice C requires bounded acquire/resume, consumption
persisting across retry/restart, reverified completed hashes and no partial publication or
history/exposure reset. Thus successful completed-window reuse is required, not an optional
new inspector. This successor completes that bounded path. Preserve predecessor97c1665265717af982cb87d6995aa68cb4356f93 and every earlier export; cumulative base3f7b2318.

```json
{
  "schema_version": 1,
  "title": "Accounted retained completed-window resume",
  "context": "Canonical v9 W05/W02 slice C requires successful resume with persistent consumption and verified completed hashes. An inactive explicit-policy synthetic mode uses existing raw/derived artifacts and an append-only final HTTP outcome to bind ordered attempts and normalized output.",
  "assumptions": [
    {
      "statement": "A committed final w200 outcome is the authoritative completed window root; loose files or mutable Ledger metadata are not.",
      "verified_by": "Before/after raw/window publication process kills, lost commit acknowledgments, forged root and missing Ledger recovery cases."
    },
    {
      "statement": "Every complete response including consumed429 is retained and bound to full policy/charge replay and exact ordered native requests.",
      "verified_by": "Actual native two-page open_interest429+200+200 sequence then fresh-process skip with exact unchanged events/debits/artifact identities."
    },
    {
      "statement": "No new provider quota/host/history/operational authority is granted by a synthetic fixture.",
      "verified_by": "synthetic_only existing namespace; explicit caller policy, dataset/root/clock/limits; default inactive, no CLI option or migration."
    }
  ],
  "alternatives_considered": [
    "More prerequisite-only hooks: rejected; successful retained completed-window resume is needed by slice C.",
    "Mutable Ledger-only window reference: rejected; durable w200 anchors normalized+ordered response manifests.",
    "Refund/release orphan reservations or reuse legacy unbound bytes: rejected.",
    "New physical accounting ledger or W09 table: rejected; existing namespace and store publication reused.",
    "First settle final200 then rewrite terminal outcome: rejected; retain intent until one atomic final success/w200."
  ],
  "pre_mortem": [
    "An accounting refusal enters ordinary DataError splitting/continuation.",
    "Two progress files dispatch the same reserved request.",
    "Success commits but missing progress allows retry under a new label.",
    "Mutable callback configuration redirects settlement to another scope.",
    "An external cancellation/history marker arrives during callback and is ignored.",
    "Forced-process test cleanup touches a poisoned multiprocessing Event lock."
  ],
  "slices": [
    {
      "title": "Retain complete per-attempt responses and advance atomically",
      "verify": "Real synthetic native Bybit pagination with429, exact body/request manifests, no SQL around I/O, exhaustion and cancellation tests",
      "expected": "Every attempt charged once; prior deferred200 settlement and next reservation/intent atomic; unsupported framing or uncertain publication cannot become complete",
      "rollback": "Disable optional new adapter; preserve existing events/artifacts; no refunds/resets or legacy upgrades",
      "status": "done"
    },
    {
      "title": "Anchor complete windows and verify retained resume",
      "verify": "Derived Parquet root+final w200 commit, old-reader fail-closed, exact full policy/debits/request/order/root validation and fresh-process zero-open/zero-charge resume",
      "expected": "Only a valid DB-anchored root authorizes completed reuse or missing-progress reconstruction; no automatic adoption of uncommitted loose roots",
      "rollback": "Retain new binding readers for published synthetic artifacts; ordinary default commands unchanged",
      "status": "done"
    },
    {
      "title": "Exercise crashes, concurrency and adversarial evidence",
      "verify": "Owned-process raw/final commit termination, lost ack before/after commit, conflicting Ledger, legacy/tamper/reorder/partial, compressed decode and prior-body revalidation regressions; scoped types/imports/lint and independent exact-tree review",
      "expected": "No redispatch on unknown or omitted history, no extra spend during cooperative contention, no source/study/admission qualification implied",
      "rollback": "Preserve all predecessors and failed receipts; never mutate authoritative later history",
      "status": "done"
    }
  ],
  "tier_impact": [
    "determinism"
  ],
  "docs_to_update": [
    "docs/superpowers/plans/2026-11-08-bound-http-retained-resume.md"
  ],
  "out_of_scope": [
    "Live provider/acquisition/study/trading or qualification",
    "Real ControlStore migration, host/account/IP/period/rights selection",
    "Legacy unbound receipt/attempt reinterpretation or missing history as zero",
    "Unknown/incomplete-window automatic reconstruction or no-send/refund/lease-expiry policy",
    "Legacy sender fencing, power-loss guarantees or whole-store rollback detection",
    "CLI activation, other-owner paths, protected/full gates, installs/transfers/publication"
  ],
  "files": [
    "apps/alpha-cli/src/alpha_cli/_crypto_http_replay.py",
    "apps/alpha-cli/src/alpha_cli/_crypto_http_accounting.py",
    "apps/alpha-cli/src/alpha_cli/_crypto_backfill.py",
    "apps/alpha-cli/src/alpha_cli/crypto_data_cmds.py",
    "packages/alpha-data/src/alpha_data/crypto/providers/_wire.py",
    "packages/alpha-data/src/alpha_data/crypto/providers/bybit.py",
    "tests/integration/test_bound_http_replay.py",
    "tests/integration/test_bound_http_replay_process.py"
  ]
}
```

## Actual native path and explicit inputs

run_backfill accepts the new exact FixtureBoundHttpAccounting type only through the
existing inactive internal HTTP-accounting slot. It composes _backfill_acquire →
_acquire_result → _fetch_bybit_pages → fetch_bybit_public → existing wire open/retry code.
No CLI option or default changes. The caller supplies the existing disposable connection,
full policy/charges/scope/stable label/clock/cancellation/busy timeout plus CryptoBulkStore,
exact native dataset, pinned capture time, explicit retry429 boolean and verification caps.
No database opener/DDL/migration/ControlStore wiring or second physical ledger is added.

The supported new binding path is native Bybit funding/open_interest with the existing
framing subset and bounded upstream pagination. Actual multi-page+429 proof uses the
native open_interest cursor lane: existing requested bounds stay fixed while cursor varies.
The production funding full-page refusal remains unchanged; no funding historical coverage
or interval guarantee follows. Funding parsing/rates and all scientific defaults remain.
Retry429 is an explicit internal opt-in using existing wire max4/backoff policy, not a new
vendor guarantee; every send consumes the caller's declared charge vector. These remain
application opener attempts, separate from socket bytes and provider billing.

## Versioned response and window bindings

CompleteHttpResponse now supports a separately opted-in complete429 error observer. Error
responses require exact frozen URL/method, status429, bounded identity Content-Length body,
EOF and successful cleanup, just as200 responses do. Missing/encoded/chunked/ambiguous
framing or another HTTP status is unsupported in this new bound mode: charged uncertainty,
no complete binding or retry. Legacy response-observer and no-observer modes are unchanged.

Before parsing or terminal settlement, retain_provider_payload publishes the exact body
through real existing staging/raw-manifest verification. New receipts are tagged
alpha-http-response-binding-v1. Their hash-bound metadata includes scope, full policy digest,
request hash, exact attempt ID, retry ordinal, window digest, sequence/page position, observed
status, framing basis and byte length. The raw MANIFEST ID binds all receipt metadata, unlike
receipt ID alone. Legacy unbound artifacts are never assigned those semantics retroactively.

Known429 outcomes commit once as failure/b429_<raw-manifest-id>. A200 response remains in
intent while the callback parses/retains/normalizes it. Before the next send, its retained
body is reverified outside SQL; prior success/b200_<raw-manifest-id> and the next complete
reservation/intent then commit in ONE BEGIN IMMEDIATE transaction. Exhaustion or conflicts
roll back both transitions, leaving the prior charged intent blocking. Retry eligibility
also reopens its429 evidence before reserving. No network/artifact I/O runs inside SQL.

The final200 stays genuinely pending. After the callback returns the normalized manifest,
the adapter publishes a real one-row Parquet derived artifact via existing publish_derived.
Kind http_window_binding_v1 contains canonical version1 data: pinned window/dataset/clocks,
full policy digest/label, ordered attempts and raw response manifest IDs, normalized output
manifest/quality and explicit last_complete_200 anchor role. Normalized input IDs remain
the existing derived input contract; the new reader explicitly verifies all additional raw
response references. It never assumes ordinary derived verification traverses metadata refs.
Only after full verification does ONE append-only success outcome commit as
w200_<derived-window-manifest-id>. The payload does not hash-reference itself. This durable
DB reference binds the normalized output and ordered chain independently of mutable Ledger.
Ledger's new optional http_replay_manifest_id is written last; older fields/version remain.

## Verified completed resume and uncertainty

Every use rechecks caller ownership/configuration, namespace/history, full immutable policy
and exact debit replay. All scope rows must have interpretable memberships; unknown legacy
terminal rows cannot silently disappear. Response metadata supplies order, not sorted attempt
IDs. Page/retry positions are consecutive;429 predecessors/request identities and successful
page request hashes/order/body hashes must match normalized raw inputs. Existing
verify_completed_window still checks dataset, requested bounds, raw hashes and quality.
No cached byte equality substitutes another venue/feed/instrument/clock.

A completed Ledger reference is accepted only when a unique matching durable w200 exists,
all manifests are active/readable/hash-correct, exact chain membership/order holds and its
normalized output matches Ledger. A fresh process can then skip with ZERO new opens,
reservations, outcomes or debits. If Ledger publication was lost after w200, the same fully
verified DB root may reconstruct missing progress without calling acquisition. Conflicting
progress or an unbound legacy completion is refused rather than overwritten.

After raw/derived publication but before final commit, loose files cannot authorize reuse:
pending/unknown work remains charged and blocks. Final commit acknowledgment loss fails the
current invocation WITHOUT blindly marking an already-terminal root unavailable. A fresh
reader must observe either actual committed valid w200 (reusable) or retained intent (blocked).
Existing unavailable-history events are NEVER cleared by a valid root or owner acknowledgment.
There are no refunds, wall-time releases, inferred no-send proof or cancellation quiescence.
Incomplete windows without a committed root do not gain automatic page-resume authority.

Ledger exclusion is cooperative current-code resource ownership. The429 backoff interval
may allow another Ledger owner to claim the scope; every atomic next reservation checks
pending attempts. This prevents participating overspend, not an uninterrupted window lease
or legacy/live sender fencing. External artifact mutations may still race after verification;
immutable-store assumptions and final rechecks remain explicit. No power-loss/directory-fsync,
coordinated all-history tamper or whole-store rollback claim is made.

## Resource and verification boundaries

Response bodies retain the existing8MiB limit. Window chains cap at400 attempts and100pages;
canonical JSON caps256KiB and actual Parquet1MiB. Writer uses uncompressed data with no
statistics. Reader checks bounded Thrift footer metadata, one row/column/group, BYTE_ARRAY,
UNCOMPRESSED codec and declared uncompressed totals <=320KiB BEFORE Polars decoding.
PyArrow24 is already locked/installed via required Nautilus; no dependency/install change.
These are decoder-work estimates/format bounds, not a hard total RSS or process-preemption
guarantee. Root materialization adds <=1MiB beyond existing hash-budget reads. Caller hash/
metadata limits bound individual verification passes; repeated passes are not provider quota.
Underlying socket timeout and trusted callback cooperation remain, not forced wall-time caps.

Ordinary synthetic tests exercise actual native429+two-page normalized publication, exact
fresh-process resume, raw/root tamper/reorder/omission/legacy states, publication gaps,
SIGTERM after raw/before/after anchor, commit acknowledgment ambiguity, simultaneous owners,
atomic cap exhaustion, cancellation and unavailable-history refusal. Owned wrapper/process
fixture preflight is used. Scoped regression/type/lint/import/plan checks and independent
source review bind the candidate; full/private/protected/release qualification is NOT RUN.

README/manual/shared-generated outputs have no changes: this is an internal inactive
fixture-only adapter with no setup/public-command activation. This dated plan records actual
behavior and limits; integrated delivery still needs its genuine repository requirements.
No real stores/providers/data/credentials, admission/security changes, installations,
transfers, commits or publication were used. QuantPad stays excluded.
