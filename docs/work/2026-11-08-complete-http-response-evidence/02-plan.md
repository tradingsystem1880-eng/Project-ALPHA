# Strict complete-response evidence before replay

**Delivery state:** Implemented – qualification pending — code only in uncommitted candidate a631e8e7; never merged or gated

Canonical v9 W05/W02 slice C requires persistent consumption across retry/resume,
no partial publication, and no history/exposure reset. Preserved predecessor is
5af99595d9f5977136625d5dac0438dfd2926c21; cumulative base remains3f7b2318.

This is the task's explicit minimum transport-evidence fallback, NOT completed replay.

```json
{
  "schema_version": 1,
  "title": "Strict complete-response evidence prerequisite for replay",
  "context": "Existing raw receipts and accounting do not bind HTTP completeness or ordered window replay. Implement only explicit supported framing evidence in actual acquired path, leaving replay refused.",
  "assumptions": [
    {
      "statement": "Strict response evidence only supports status200 body-free GET identity encoding with validated Content-Length and response EOF.",
      "verified_by": "Synthetic multi-chunk, short/extra body, invalid framing, close/read failures and exact hash/count tests."
    },
    {
      "statement": "Retained hash equality and read evidence do not alone authorize completed-window HTTP replay.",
      "verified_by": "Native acquisition success plus fresh connection/process counterproofs preserve replay refusal and exact nonrefunded debits."
    }
  ],
  "alternatives_considered": [
    "Relabel legacy read_operation_closed as complete response: rejected.",
    "Treat raw bytes/hash as HTTP framing or ordered accounting membership: rejected.",
    "Add an implicit reason-string ledger or retrofit legacy receipts: rejected.",
    "Implement the authorized minimum framing boundary and state the missing versioned associations: selected."
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
      "title": "Expose strict framing evidence through actual transport/acquisition",
      "verify": "Owned wrapper scoped unit tests and real synthetic native backfill; strict types/lint/imports",
      "expected": "Evidence only after declared exact bytes, EOF and context close, before accounting settles; observer failure stays uncertain",
      "rollback": "Stop supplying optional observer; preserve existing artifacts/schema and legacy behavior",
      "status": "done"
    },
    {
      "title": "Prove unsupported replay is refused without extra send/charge",
      "verify": "Fresh process429 replay counterproof, completed native window refusal, malformed/truncated/observerfailure tests and independent source review",
      "expected": "No cache/replay authority fabricated; consumed attempts remain charged; no partial progress on failure",
      "rollback": "Keep predecessor and all receipts; no refund, redispatch, reset or legacy metadata upgrade",
      "status": "done"
    }
  ],
  "tier_impact": [
    "determinism"
  ],
  "docs_to_update": [
    "docs/work/2026-11-08-complete-http-response-evidence/02-plan.md"
  ],
  "out_of_scope": [
    "Retained-response\u2194attempt and ordered-window binding protocol or migration",
    "Successful completed-window replay or legacy upgrade",
    "429 error body completeness/retention",
    "Provider policy, billing, socket bytes, sender fencing or retained-history authority",
    "Live stores/providers/credentials, protected/full gates, transfers/install/publication"
  ],
  "files": [
    "apps/alpha-cli/src/alpha_cli/_crypto_backfill.py",
    "apps/alpha-cli/src/alpha_cli/crypto_data_cmds.py",
    "packages/alpha-data/src/alpha_data/crypto/providers/_wire.py",
    "packages/alpha-data/src/alpha_data/crypto/providers/bybit.py",
    "tests/unit/test_crypto_http_response_evidence.py",
    "tests/integration/test_complete_http_accounting.py"
  ]
}
```

## Existing contract gap and bounded decision

CryptoRawReceiptV1 binds supplied body hash/bytes, dataset, request and pagination.
retain_provider_payload preserves those exact bytes, including malformed bodies, but
cannot establish HTTP framing or their accounting membership. _wire previously did one
capped read; HTTPError bodies are closed without retention. Normalized input_manifest_ids
cover parsed successful pages, not consumed429 attempts. The accounting event reducer
has exact schemas; outcome stores only state and a reason string. Ledger done state binds
manifest/quality/time, not an ordered request/attempt/response chain.

Therefore neither legacy hashes nor arbitrary strings prove completed-window replay.
Existing HTTP_COMPLETED_RESPONSE_BINDING_UNAVAILABLE stays intact. No byte replay or
automatic redispatch is enabled, even after complete-response evidence is observed.
A future NEW versioned binding must explicitly commit request identity + scope/policy +
reservation/attempt/retry ordinal → response manifest ID + status/framing/hash/bytes, and
ordered window attempts → normalized manifest/clock/parameters. It must handle all
consumed429 bodies and publication/settlement gaps; never retrofit legacy records.
These are engineering contract prerequisites, not a new provider policy or request for
Hunter to choose schema columns. Namespace/schema1 remains unchanged in this slice.

## Implemented strict evidence path

A caller may supply response_evidence to _wire.fetch_bounded. This enables the existing
no-redirect opener, host check and body-free GET restriction. Legacy no-observer behavior
and accounting policy remain unchanged. CompleteHttpResponse(schema_version1) is emitted
only after status200, bounded unambiguous headers, mandatory numeric Content-Length,
identity encoding/no Transfer-Encoding, bounded chunks, exact declared byte count,
response EOF probe and successful context close. Empty bytes may be complete transport
but invalid JSON. Headers are not copied into the evidence. Method/exact URL/hash are frozen before open and checked for identity drift and exact final
URL before emission; accounting and evidence use the same frozen hash. Request hash, status,
declared length, exact immutable bytes/hash and explicit framing basis are available to the trusted
observer; constructing this value alone authenticates nothing.

The observer runs after response cleanup and before HTTP accounting settlement, without
holding a SQLite transaction. It can fail; this produces existing unknown charged state,
not success/progress or a refund. It is NOT assumed durable: a callback, an in-memory list
or a file written by a test cannot certify an authoritative attempt binding.

The existing internal run_backfill now optionally forwards fixture_http_response_evidence
through the actual Bybit acquisition/pagination wrapper to the wire boundary. Supplying
it at this orchestration boundary requires existing explicit HTTP accounting. CLI options,
public defaults, provider retry behavior, reserve checks and persisted schemas are unchanged.
Accounting still says read_operation_closed; it does NOT persist/upgrade the new evidence.
Malformed/truncated reads, close failures and invalid framing emit no complete-response
value; existing accounting becomes unknown and progress remains absent. A later parser
failure does not negate a previously observed complete body; byte integrity and quality
remain separate. Complete raw publication requires actual storage evidence, not parsing.

## Limits and verification

Only the declared Content-Length/identity subset is supported; chunked, compressed,
missing/duplicate/invalid-length responses and non200 statuses get no complete evidence.
In particular consumed429 bodies remain unretained/unbound and ineligible for replay.
The existing library socket timeout applies; arbitrary injected open/read/observer work is
not forcibly preemptible. Header/chunk/application-body limits do not claim socket or RSS
bounds. EOF means urllib response-body EOF, not global TCP EOF or provider historical
coverage/publication availability. No power-loss, whole-store rollback or sender fencing
proof is added. Any future binding must use verified immutable manifest IDs, not merely
receipt IDs, and must survive the raw-publication/accounting/window crash boundaries.

Scoped tests use fake responses, temporary stores, declared fake capacity, owned-process
fixtures and the documented wrapper. A real native acquisition run emits strict evidence
before settlement and retains normal raw/normalized artifacts; reopen still refuses
HTTP-accounted completed-window replay without new opens or charges. A separate429 test
uses real wire retry code, then a fresh process confirms unbound replay refusal. Prior
process-kill/concurrency/accounting suites remain scoped regressions, not successful replay
qualification. Full/private/protected gates and successful replay scenarios are NOT RUN.

README/manual/shared-generated outputs are unchanged: no public setup/command is enabled;
this candidate-local plan documents the internal incomplete integration. No provider calls,
real stores, credentials, retained-host access, installation, transfer or publication.
