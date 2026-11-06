# Integrated offline Bybit funding candidate

Status: bounded offline implementation; software qualification/publication receipts are
separate from live-provider/data admission, which is not established here.
Integration base: `7824bebf2e9d10077e8ffdb92b9b6871ea482287` (merged PR #116).
Original funding base: `5a0d64ae6e04dad1d7fb31cb02ee798a314c9bff`.

Delivery successor: the original 19-file tree
`6ddac25c6578bb4d3d59ae66c584cec260cdea35` and its receipts remain preserved separately.
Public component execution found a combined-manual size failure (6,226 bytes against
6,000) and four stale Atlas outputs. The successor condenses equivalent manual guidance
while retaining the delivery-plan link in AGENTS.md, and regenerates Atlas through its
supported generator. Funding implementation and tests are unchanged; inactive F5 stays
excluded. Final gates and native evidence must bind the successor, not the old receipts.

The owner subsequently approved the funding-specific absence-only decision: proceed
to GitHub with unavailable private engineering coverage marked UNVERIFIED, provided
the full public checks and genuine independent review pass. The approved funding
software tree is `d7ac9dbf22fab59a42d3442ffb8f62f6ad68b04d`, content SHA256
`3020451d00249e58385e5185440b9cf7fc687d7cc7073d64a61f8a7486df7ef1`.
This integration keeps every funding Python implementation/test file byte-identical,
retains merged main's assistant-cleanup changes and resolves only documentation and
generated-Atlas overlap. The exception covers this unchanged funding work and its
necessary integration, not F5, later features, actual failures or scientific holdouts.
The prior native BLOCK remains correct preserved history. Fresh native verdicts,
README evidence and public gates must bind the actual integrated tree.

This converges the existing funding implementation; it adds integration coverage and
delivery documentation, not another capability. Historical slice plans/results remain
historical. The final inventory, patch and verification receipt bind the integrated
candidate separately. No previous test counts or review receipts transfer as fresh passes.

## Working composed path

The internal Python entry point is `collect_retained_funding_pages`, supplied with a
`FundingResponseSupplier` constructed using a fake opener and injected monotonic clock.
The caller supplies a native Bybit funding dataset identity, aware acquisition cutoff,
inclusive millisecond range and finite call/accepted-byte limits.

1. The collector fixes identity, global bounds and budgets. Before every supplied page,
   the raw composition checks the existing store identity/reserve and freezes requested
   parameters. Production reserve defaults remain unchanged.
2. The response supplier constructs the existing closed funding request, passes a
   remaining-window-capped I/O timeout to the injected opener, checks response metadata,
   reads bounded chunks, checks its cooperative deadline and closes the response.
3. Only a complete eligible byte body reaches actual `CryptoBulkStore` staging,
   external-artifact-first/internal-manifest-last publication and hash verification.
   This occurs before funding JSON decoding. Empty or malformed complete bodies remain
   raw evidence even when subsequent decoding fails.
4. `parse_funding_page` reuses the legacy frame parser and validates every settlement's
   exact requested symbol/category, inclusive bounds and acquisition cutoff. Native
   signed rates and irregular intervals are preserved; no eight-hour assumption or
   publication timestamp is invented.
5. Each successful page decreases the inclusive upper boundary to its oldest settlement
   minus one millisecond. Repeated/conflicting or nonprogressing pages fail. Short pages
   continue; empty/lower-bound/call/byte stops return `coverage_complete=False`.

The returned frame contains observed candidate settlements, not a qualified complete
history. Returned raw manifests use existing schemas. There is no normalized publication,
quality acceptance, snapshot, ledger, durable resume or restore in this composed path.
On later failure, earlier committed raw evidence remains; no partial collection is returned.
An interrupted pre-manifest publication needs exact original replay inputs to recover full
request/receipt metadata. Filesystem tests do not prove power-loss durability/concurrency.

The existing funding acquisition plan uses the stricter page validator. **The composed
transport/retention/backward-pagination path is not registered with production CLI/API/MCP.**
The existing production full-page refusal remains; no live opener or provider call is enabled.

## Enforcement limits

Accepted body bytes are capped at the remaining allowance, up to 8 MiB per page; reads
request at most 64 KiB plus one overflow/EOF probe byte. A conforming response can return
at most allowance+1 bytes before overflow rejection. Library buffers/headers/RSS and a
misbehaving injected method's prior allocation are not bounded by these checks.

An I/O timeout argument is not proof of actual library enforcement. Shared monotonic
deadline checks occur around open/read/cleanup and across pages; arbitrary blocking code
cannot be preempted. This is not a hard storage/acquisition deadline. The future admitted
opener must configure I/O timeouts and refuse redirects before following; final URL checks
cannot undo a redirect performed inside arbitrary opener code.
The expected closed URL is frozen before passing a mutable Request to the opener;
mutating that Request cannot rebind the accepted response identity. Cross-layer review
identified and prompted this correction; the composed regression refuses it before
body reading or raw publication and still closes the response.

Overflow, truncation, transport/cancellation/cleanup failure and invalid response metadata
do not yield a complete eligible body or complete raw receipt. No partial-stream schema is
invented. Original exception text/chains are sanitized; fresh cancellation objects preserve
control semantics with only safe SystemExit codes. Deadline/callback counts and accepted
bytes are not durable quota, exposure or billing records.

## Fresh verification and preservation

The final receipt lists exact selected tests, commands, output and tool versions. Combined
focused checks run after final fixes; no aggregate coverage/full-gate pass is inferred.
Integration cases specifically exercise full-page-to-singleton success with raw-before-decode
ordering on every page, second-response failure propagation, storage failure after response
cleanup and finite budget stops at the opener boundary. Existing tests cover malformed raw
retention, EOF/length/encoding handling, deadlines, replay and sanitized cancellation.

The original checkout and all historical predecessors remain untouched. The exact transport
predecessor `11bd06fc3bb51ac1e0024e84c7ade68df1b6be31ff3e57bb2359f6938aff8ca6`
is preserved as an allowlisted source snapshot plus its existing inventory/review receipts.
Delivery artifacts are local only: `funding-delivery.patch`, `inventory.json`,
`verification.json`, `review.json` and a reproduction helper in the delivery directory.

README disposition: updated. Its data paragraph now explains the composed offline API and
production boundary, and records the owner exclusion of QuantPad while preserving historical
code/attribution/records. This is necessary reader-facing scope reconciliation, not a new
provider decision. Native tree-bound README attestation remains pending below.

## Release prerequisites still blocked

Owner authorization permits build/review/commit/push and standard locked setup; earlier
public-gate restrictions are lifted. Original-tree component results remain historical.
Final successor commands, results and bindings belong to its separate delivery receipts.
Private-suite coverage remains UNVERIFIED under the explicit funding-specific absence-only
decision above. All other failures still block. Separate standing direction authorizes
a qualified merge through normal protections; no provider, trading or deployment
permission follows from either decision.

| Required action | Current obstacle and treatment |
|---|---|
| `uv run python scripts/gate.py full` | Allowed; requires successful backend/frontend/literature/Qlib/Atlas/eval receipts for one final tree and genuine comparison base. No original-tree receipt supplies a successor pass. |
| In `tools/alpha-atlas`: `uv run python -m alpha_atlas.generate --check` | Use the supported generator after source/docs are final; freshness must pass without hand-editing generated files. |
| Native private-suite treatment | The suite is absent; coverage remains UNVERIFIED under the approved funding-only absence decision. Never read private source or infer a private-test pass. No actual failure is excused. |
| Stage the final allowlist; obtain native independent review and `uv run python scripts/gate.py attest --kind review < review.json` | Source review is advisory. Use genuine independent execution and the exact approved absence-only scope; retain the prior BLOCK and informational UNVERIFIED finding. Never convert author test results into native APPROVE. |
| Fetch real `origin/main`, review README, then `uv run python scripts/gate.py attest --kind readme < readme-review.json` | Rebind after final-tree or main changes. Original-tree README evidence does not cover this successor. |
| Install Git guards; guarded commit/push and draft PR | No bypass; verify exact remote commit and actual CI. Mark ready and merge only after normal protections/checks/review pass under standing direction. Deployment and live trading remain unauthorized. |

The earlier external Claude submission remains held and is not retried. It supplies no
native attestation; the repository's native independent review remains mandatory.

Only data parsing, collection, transport hygiene and filesystem composition change. No
statistical estimator/default, label/calendar or strategy semantics change, so no quant
formula approval is inferred or requested by this diff. Existing final gates decide actual
on-touch scope. Source review is advisory engineering evidence, not application authority.

## Live-provider/data admission is separate

After release qualification, any live use still requires explicit provider-call authorization,
current regional/access/rights evidence, named instruments/ranges, admitted retained storage,
an admitted no-redirect timeout-enforcing transport and durable acquisition budgets/recovery.
Partial-stream evidence, durable quota/resume and snapshot restore need separate contracts;
none is silently supplied here. Provider qualification, historical publication availability,
complete coverage, research admission and trading authority remain unproven. QuantPad remains
excluded. No production full-page refusal can be removed on these offline results alone.
