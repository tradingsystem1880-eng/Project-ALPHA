# ADR-0031: Provider readiness and paper acceptance V2

**Status:** Accepted
**Date:** 2026-08-13

## Decision

Provider availability has three independent dimensions: local configuration, the result and time
of the last explicit verification, and the capabilities granted by that verification. Package or
environment-variable presence is never labelled ready. Opening or refreshing the Workstation is a
read-only projection and never contacts a provider.

Explicit checks produce immutable, content-addressed `ProviderCheckReceiptV1` records. Receipts
contain no credential value, raw response, absolute path, token, or full broker account. Tiingo and
QuantPad REST are separate checks; Codex-managed QuantPad OAuth is descriptive discovery only and
does not prove REST access. Finnhub without a credential is `optional_disabled`. IBKR readiness is
a set of local diagnostic facts (Docker CLI, daemon, reviewed digest, masked DU account, loopback
paper endpoint, permissions, and market data), never a single inferred boolean. ALPHA never starts
or stops Docker.

macOS Keychain access belongs only to a narrow shell launcher. Python and the browser do not invoke
Keychain APIs. The launcher disables tracing, retrieves exactly one named item into an environment
variable, and `exec`s a closed ALPHA command without putting the secret in argv or a file.

Operational paper acceptance uses `PaperAcceptanceV2`. An immutable one-shot plan is frozen before
broker activity. Only closed typed callback facts may be recorded, chained by previous-fact hash
and bound to plan hash, session, correlation lineage, policy version, and implementation
fingerprint. Readiness is recomputed from raw fact fields; producer `passed` values are neither
accepted nor stored. Legacy paper journals remain monitoring history only and cannot earn credit.
There is no generic REST, MCP, or CLI fact-append route.

`IBKRWhatIfPlanV2` is separate from paper acceptance. It permits only a SPY one-share DAY limit
preview on a masked DU paper account at `127.0.0.1:4002`, with a reviewed image digest,
`whatIf=true`, the IBKR-required wire-level `transmit=true`, a fixed price collar, expiry, and a
one-shot plan hash. The contract separately records `broker_order_transmitted=false`: IBKR requires
the wire flag to process a what-if request, while `whatIf=true` prevents order placement. V1 plans
remain readable but cannot be executed. Creating a plan is offline. Executing the real preview
requires a separate current owner checkpoint and never creates an order, fill, cancellation,
position change, or paper-acceptance fact.

## Consequences

- Credential presence is honest local configuration, not verification.
- UI refresh is safe and side-effect free; only explicit test buttons perform bounded probes.
- Provider failures have stable actionable categories and redacted receipts.
- A forged journal event can never satisfy readiness.
- A successful what-if preview demonstrates bounded connectivity only; `paper_passed` remains
  false until separately authorized real paper scenarios are mechanically completed.
