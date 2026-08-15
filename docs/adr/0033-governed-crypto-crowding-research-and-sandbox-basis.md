# ADR-0033: Govern crypto crowding research separately from sandbox basis development

**Status:** Accepted
**Date:** 2026-08-15
**Deciders:** Project ALPHA owner and AI build agents

## Context

ADR-0032 established provider-native crypto data authority but deliberately granted no empirical
operator or strategy authority. A qualified snapshot can therefore be registered as research data
without making any proposal executable. The next program needs one narrow real-data research
question and one deterministic development fixture without turning funding, open interest, basis,
or venue prices into a universal signal.

The research question is whether unusually positive Bybit BTCUSDT linear-perpetual crowding is
followed by mark-price underperformance relative to the index through the next provider-declared
funding timestamp. The later development candidate is a separately qualified, two-leg Bybit
perpetual/Binance spot hedge. These are different authority stages: evidence about a phenomenon is
not a validated strategy, and a sandbox fixture is not paper or execution evidence.

## Decision

### Registered research operator

Register exactly one answer bundle, `bybit_btcusdt_crowding_reversal_v1`. It accepts only one
compatible, qualified `CryptoSnapshotV1` whose provider-native members contain:

- Bybit linear `BTCUSDT` with quote asset exactly `USDT`;
- funding, hourly open interest, premium, mark, index, derivative bars, and the applicable
  instrument catalog;
- the registered long/short-ratio confounder when the protocol evaluates that diagnostic; and
- the frozen asset-master and qualification method versions named by the proposal.

The primary event requires funding at or above the point-in-time 95th percentile of the preceding
365 completed funding observations, positive 24-hour open-interest change, and positive premium.
The 90th and 97.5th percentile sensitivities form one frozen Holm family. Every observation must
have `available_at` no later than event admission; measurement starts at the first complete hourly
bar afterward. The primary outcome is mark return minus index return through the next
provider-declared funding timestamp, with at least 5 basis points of underperformance as the
practical hurdle.

Events are non-overlapping. Admission needs at least 50 effective events overall and at least 10
sealed D2 events; otherwise the scientific classification is `INCONCLUSIVE`. Controls match UTC
funding slot, recent trend, and volatility. Uncertainty clusters by UTC week. Shifted-date
placebos, long/short ratio, and regime diagnostics are preregistered. D0 includes planted, null,
confounded, future-poisoned, missing, corrected, and insufficient-sample fixtures.

The existing chronological, group-atomic 60/20/20 D1/D2/D3 topology remains unchanged. D2 remains
one-shot and owner-authorized; D3 remains prohibited to research. A mixed quote, venue,
instrument, family, unit, timestamp convention, stale qualification, future observation,
correction without lineage, substituted member, or changed operator fingerprint fails before an
attempt or evidence record exists.

Pure, versioned plan and observation contracts live in `alpha_research`. `alpha_cli` re-verifies
and composes exact `CryptoSnapshotV1` members from `alpha_data`; no lower layer imports the CLI and
TypeScript gains no analytical authority. Proposal preflight offers the bundle only when exactly
compatible registered data exists. Submission revalidates bundle, snapshot, asset master,
qualification versions, source pack, case revision, and operator fingerprint.

### Sandbox-only hedged basis candidate

`hedged_basis_crowding_v1` is a development candidate only after a supported owner research
disposition. It shorts the exact Bybit linear BTCUSDT perpetual and holds a delta-matched Binance
BTCUSDT spot hedge. Both legs use separately qualified hourly datasets with identical BTC/USDT
identity while retaining venue, leg, funding cash flow, and availability lineage. Entry follows
the registered crowding event; exit is the next declared funding boundary. The deterministic
fixture uses a conservative 40-basis-point total round-trip cost and 365-day, continuous-crypto
annualization.

The candidate is permanently sandbox-only. It receives no exchange credential, order, paper-entry,
or broker authority. Its paper preflight must return `UNSUPPORTED_MULTI_VENUE_PAPER` and create no
paper-readiness credit, order, fill, position, or broker event.

## Consequences

- Qualified crypto data becomes executable only for one declared scientific question rather than
  acting as implicit permission for arbitrary research.
- Real-data results may honestly be `SUPPORTED`, `CONTRADICTED`, `INCONCLUSIVE`, or `INVALID`;
  profitability and promotion are never acceptance requirements.
- The deterministic strategy fixture can exercise the full pre-paper development lifecycle while
  remaining visibly non-authorizing.
- Adding another instrument, quote asset, venue, event definition, outcome, sensitivity family,
  strategy leg, or execution path requires a new registered generation and governance review.

## Implementation anchors

- `packages/alpha-research/src/alpha_research/crypto_crowding.py`
- `apps/alpha-cli/src/alpha_cli/research_intake.py`
- `apps/alpha-cli/src/alpha_cli/research_runtime.py`
- `apps/alpha-cli/src/alpha_cli/research_d1.py`
- `apps/alpha-cli/src/alpha_cli/research_d2.py`
- `packages/alpha-data/src/alpha_data/crypto/research.py`
- `packages/alpha-strategies/src/alpha_strategies/`

