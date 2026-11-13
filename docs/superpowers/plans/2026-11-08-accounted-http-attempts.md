# Opt-in synthetic per-HTTP accounting integration

**Delivery state:** Implemented – qualification pending — code only in uncommitted candidate a631e8e7; never merged or gated

Canonical requirement: v9 W05/W02 market-data slice C, persisted budget use across
retry/resume without exposure reset. This is an inactive disposable-store engineering
subset, not operational provider quota or provider qualification.

```json
{
  "schema_version": 1,
  "title": "Opt-in synthetic per-HTTP attempt accounting",
  "context": "Real Bybit/backfill orchestration connects to per-explicit-open accounting; no live activation, policy selection or schema migration.",
  "assumptions": [
    {
      "statement": "Each explicit opener invocation is one accounted transport attempt, including retries; caller declares charges and scope.",
      "verified_by": "Synthetic real wire retry/pagination/native pipeline tests compare committed intents with open calls."
    },
    {
      "statement": "Returned read operation is not proof of complete HTTP body or dataset coverage.",
      "verified_by": "Receipt uses read_operation_closed; existing parser/quality/retention remains separate; EOF and Content-Length not asserted."
    }
  ],
  "alternatives_considered": [
    "Relabel opaque window counts as requests: rejected.",
    "New accounting ledger: rejected; existing md_acquisition schema1 and caller-supplied connection reused.",
    "Automatically resend completed/uncertain requests or refund cancellation: rejected; no response replay authority."
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
      "title": "Connect per-attempt wire hook and Bybit orchestration",
      "verify": "Focused synthetic real adapter, retry and pagination/native backfill integration cases; mypy, ruff and imports",
      "expected": "Every explicit send follows committed intent and a caller-declared debit, including retries; defaults unchanged",
      "rollback": "Disable optional inputs and retain existing account records; no refund/reset or live schema change",
      "status": "done"
    },
    {
      "title": "Verify uncertainty, ownership and guarded progress",
      "verify": "Owned-process contention/kill/reopen, lost acknowledgment, external cancellation/history changes, exact-tree independent review",
      "expected": "No participating duplicate send on replay, no refunded consumption, no progress on uncertainty/missing history",
      "rollback": "Retain preserved239a candidate and event readers; do not erase debits or infer absent history",
      "status": "done"
    }
  ],
  "tier_impact": [
    "determinism"
  ],
  "docs_to_update": [
    "docs/superpowers/plans/2026-11-08-accounted-http-attempts.md"
  ],
  "out_of_scope": [
    "Live admission, real store migration, provider/account/IP/period policy",
    "Sender fencing, legacy binary cutover, response replay and full restore",
    "Private/full gates, providers/credentials/live data, installs, transfers or publication"
  ],
  "files": [
    "apps/alpha-cli/src/alpha_cli/_crypto_backfill.py",
    "apps/alpha-cli/src/alpha_cli/_crypto_backfill_accounting.py",
    "apps/alpha-cli/src/alpha_cli/_crypto_http_accounting.py",
    "apps/alpha-cli/src/alpha_cli/crypto_data_cmds.py",
    "packages/alpha-data/src/alpha_data/crypto/providers/_wire.py",
    "packages/alpha-data/src/alpha_data/crypto/providers/bybit.py",
    "tests/integration/test_accounted_http.py",
    "tests/integration/test_accounted_http_process.py"
  ]
}
```

## Slice 1: transport boundary

DONE: `_wire.fetch_bounded` accepts a trusted optional `HttpAttemptHook`. One hook
invocation surrounds each explicit open/read/close, including existing 429 retries.
Method and exact URL hash distinguish pages; no URL/header/body is persisted by accounting.
Opted-in mode uses the existing no-redirect opener and host check. Operation is single-use.
Default no-hook semantics and retry policy stay unchanged. Bybit forwards the optional
hook; the separate `FundingResponseSupplier` and other unmodified transports do not.

## Slice 2: accounting and actual acquisition composition

DONE: `FixtureHttpAccounting` borrows the existing supplied SQLite connection and schema1
namespace. It inherits connection/transaction/ownership checks, not new persistence.
Explicit `synthetic_http_send` basis, full policy/charges/scope/caller label/clock/cancel
inputs are required. HTTP and window attempt prefixes cannot share a scope. Charges are
caller declarations, not inferred weights, measured wire bytes, or provider billing.

Ledger ownership precedes short BEGIN IMMEDIATE. Reserve + intent commits before open;
no SQL transaction spans HTTP/artifact I/O. Each request retry gets a distinct stable
attempt ID. Only an exact recorded previous 429 permits the next ordinal; all existing
attempt replays, pending scope owners and unknown/history states refuse dispatch. No
refund, timeout-based release or sender-lease steal exists. Durable intent/cancel/history
is rechecked immediately before opening, then ownership/cancel/history/result identity
is rechecked after the acquisition callback before Ledger publication. These checks are
not an atomic fence: concurrent changes can still race after each check. Known HTTP errors settle
consumed failure before normal wire retry/error handling. Open/read/close/overflow or
commit uncertainty conservatively blocks; exact read-operation success settles before
parsing/retention and is NOT data quality, raw-retention or historical-completeness proof.
The legacy bounded single read does not verify EOF or Content-Length; unlike the separate
FundingResponseSupplier it does not prove full response-body integrity. Its outcome
reason is read_operation_closed, not complete-body or complete-raw-receipt approval.

Actual `run_backfill` optionally supplies the hook through `_backfill_acquire` →
`_acquire_result` → `_fetch_bybit_pages` → `fetch_bybit_public` → `_wire`. Only Bybit is
supported in this opted-in internal orchestration mode. The CLI exposes no activation
option. Window + HTTP adapters are mutually exclusive here; no window is double-counted.
Missing scope/history or a callback that ignores the hook cannot publish completed progress.
Fatal accounting errors survive the CLI's ordinary DataError translation unchanged.

An existing completed window still lacks immutable HTTP/page-accounting binding. Therefore
opted-in completed-window resume refuses rather than inventing zero usage or re-fetching.
A consumed success without retained body also refuses replay; this does not implement
response cache replay, durable page resume, or a new receipt schema. The production funding
full-page refusal remains. No new historical coverage or publication-time claim follows.

## Verification and boundaries

Use `scripts/run_owned_test.py` and owned process fixture for focused public synthetic
transport, native acquisition, pagination, retry, process kill/contention and replay tests.
Run affected types/lint/imports and independent exact-tree review. Full/private/protected
qualification is NOT RUN. README/manual/shared-generated outputs are unchanged: this
inactive internal fixture-only hook changes no setup or public command. Delivery still
needs repository-native full qualification and honest documentation integration.

No opener/database lifecycle/migration/provider policy or live authority is added. Shared
scope concurrency is cooperative with current writers, not legacy/live sender fencing.
There is no TTL, authoritative period rollover, restore/rollback detection, no-send proof,
power-loss guarantee or cross-store atomicity. A process killed before committed intent
has no durable debit; after committed intent it remains consumed unresolved even if the
open never occurred. Callback/OS work cannot be forcibly bounded by these transactions.

Operational use requires admitted store/history/host/account/IP/period policy, writer
cutover/fencing and transport coverage/admission. No providers, credentials, live data,
installations, transfers or publication are authorized or performed by this slice.
