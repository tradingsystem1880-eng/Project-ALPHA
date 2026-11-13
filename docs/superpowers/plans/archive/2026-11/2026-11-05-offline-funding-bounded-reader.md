# Offline funding bounded response reader

**Delivery state:** Completed — merged via PR #117

**Historical delivery state (as first recorded):** Focused offline implementation and source review complete; no live transport installed or production integration.

```json
{
  "schema_version": 1,
  "title": "Offline funding bounded response reader",
  "context": "Preserve raw-retention content 30a916523d4a6154ce57c452918399e5595cfc58798d3ebd04850ceaa71e8a87; add a mandatory-injected response reader on main 5a0d64ae6e04dad1d7fb31cb02ee798a314c9bff.",
  "assumptions": [
    {"statement": "Finite body reads and between-operation deadline checks improve the offline supplier without preempting arbitrary code.", "verified_by": "Injected response/clock tests, including blocking-operation overrun observed after return."},
    {"statement": "Complete eligible bodies still enter existing raw retention before JSON decoding.", "verified_by": "Temporary filesystem composition with fake opener."}
  ],
  "alternatives_considered": ["Reuse fetch_bounded unchanged: it installs live transport and lacks aggregate deadline/redaction behavior.", "Forcefully interrupt arbitrary callbacks: unsupported; enforce read contract and describe timeout assumptions."],
  "pre_mortem": ["Slow chunks evade an aggregate deadline.", "Oversized bodies or compressed data bypass accepted-byte limits.", "Exception chains leak request URLs or body text."],
  "slices": [
    {"title": "Injected bounded response supplier", "verify": "Explicit ordinary synthetic transport cases", "expected": "Bounded reads, cleanup, metadata checks, redacted failures and shared deadline", "rollback": "Remove unused supplier; predecessor composition unchanged", "status": "done"},
    {"title": "Raw composition and independent review", "verify": "Affected funding/raw/wire tests; lint/types/import/plan checks", "expected": "Fresh scoped evidence and exact limit classification", "rollback": "Preserve predecessor without activation", "status": "done"}
  ],
  "tier_impact": ["determinism"],
  "docs_to_update": ["CLAUDE.md", "docs/operations/research-platform-contracts.md", "docs/BUILD-STATUS.md"],
  "out_of_scope": ["Live opener/provider calls", "Credentials", "Dependencies", "Protected contents", "Full/Atlas/preflight gates", "Retries", "Partial-stream retention schema", "Durable accounting/resume", "Snapshot restore", "Publication"],
  "files": ["packages/alpha-data/src/alpha_data/crypto/providers/funding_transport.py", "tests/unit/test_funding_bounded_transport.py"]
}
```

README no_change: internal injected transport only, no new command/setup/readiness.

Workspace `/workspace/alpha-funding-transport`, main tree
`b795de4e9611035aa9c725a2604bf3bcf038f414`. All predecessors remain unchanged.
Reuse the current closed funding URL builder, urllib Request/read/close conventions,
Tiingo's sanitized failure pattern, and the existing raw-retaining collector. The
shared `_wire.fetch_bounded` and all production callers remain unchanged: they lack
this injected deadline contract and have different retry/error/EOF semantics.

| Limit | What is enforced | What is not established |
|---|---|---|
| Accepted body | At most supplied allowance, up to 8 MiB | Socket/header buffering or arbitrary callback allocation |
| Reads | Requested chunks at most 64 KiB; one overflow/EOF probe byte | A misbehaving response can allocate too much before rejection |
| Timeout | Remaining-window-capped I/O timeout argument reaches opener | Actual socket behavior without a qualified opener binding |
| Shared deadline | Monotonic checks around open/read/cleanup and across pages | Forced preemption or hard end-to-end storage/acquisition deadline |
| Cleanup | Close attempted on every returned response; HTTPError close path covered | Arbitrary close code cannot be forcibly terminated |
| Raw retention | Complete eligible bytes enter existing real store before decode | Partial/error stream retention, resume or power-loss durability |

The mandatory opener must refuse redirects before following and configure library
I/O timeouts. The adapter only rejects redirect statuses/changed final URLs after
open; it never follows Location itself. No such live opener is installed or qualified.
Inactivity timeouts do not cap an entire drip-fed read; between-operation deadline
checks detect an overrun only when control returns. Identity encoding is requested;
unsupported encoding and invalid status/MIME/length/duplicate headers fail closed.
No incomplete or overflow body receives a complete raw receipt.

Fresh evidence: 188 affected tests passed (39 new bounded-transport, 19 raw-retention,
38 pagination, 24 single-page and 68 wire/request-budget/Tiingo cases). After typed
HTTPError fixture headers were corrected, all 39 final transport tests passed again;
these are overlapping counts. Ruff check/format, strict mypy for two Python files,
13 import contracts and plan/diff checks passed. Initial red collection lacked the
module. Initial mypy found HTTPError fixture header-type errors (one, then two after
adding a second fixture), corrected using the standard Message class.

Independent source review required two cancellation corrections: original cancellation
objects leaked text/tracebacks, and cleanup could swallow/bypass cancellation. Fresh
sanitized cancellation objects, safe SystemExit codes and cancellation precedence now
cover read, HTTPError cleanup, ordinary cleanup and injected-clock paths. The reviewer
confirmed both findings corrected and no remaining required source findings. Final
content identity and final review are recorded under `/workspace/funding-evidence/`.

Tests use injected fake responses/clocks and real temporary raw storage, never network
or real datasets. Fake timeout observation proves the argument, not OS enforcement.
Prohibited full/Atlas/preflight gates, protected contents, providers, credentials,
dependencies/installations, commits and external publication were not used. Production
integration still requires an admitted no-redirect transport, actual I/O-timeout evidence,
current access/rights, retained-storage admission and durable acquisition safeguards.
Receipt/frame schemas, scientific defaults and production full-page refusal remain.
Providers stay unqualified; settlement/publication clocks differ; QuantPad is excluded.
