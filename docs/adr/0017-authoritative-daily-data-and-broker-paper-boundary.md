# ADR-0017: Qualify authoritative daily data before releasing broker-paper intents

**Status:** Accepted
**Date:** 2026-08-03
**Deciders:** Owner-approved daily-data and paper-trading hardening plan and AI build agents

## Context

ALPHA already has a canonical Nautilus research engine, a React/FastAPI Workstation, and a local
Binance-data sandbox path. Adding a second engine or chart stack would create conflicting research
and execution authorities. Moving stocks and ETFs to broker paper trading also requires stronger
data identity, correction handling, idempotency, reconciliation, and secret boundaries than a
direct vendor-to-chart or strategy-to-broker connection can provide.

## Decision

Keep NautilusTrader as the only simulation/execution engine and `alpha_cli` as the only composer.
Keep the existing React/FastAPI and direct Lightweight Charts frontend. Adopt Tiingo EOD as the
authoritative stock/ETF daily source; Yahoo Finance and Stooq are comparison-only and cannot replace
qualified Tiingo history. CCXT remains the authoritative crypto-history seam.

Every receipt-backed daily pull follows:

`provider → immutable receipt → provider candidate → quality gate → canonical Parquet → immutable snapshot`

Version-2 provenance embeds a `DatasetIdentity` and `FetchReceipt`; legacy provenance and snapshots
remain readable. A candidate is quarantined on duplicate/invalid bars, calendar gaps, missing
existing sessions, action conflicts, non-authoritative source, or unexplained cross-source price
differences above one percent. Corrections retain the old/new row hashes. Promotion uses immutable
pre-promotion backups and a fail-closed marker; in-process failure restores automatically and a
process interruption requires an explicit rollback command.

Receipt and intent readers reject type coercion, repair promotion re-verifies the stored raw response
hash and candidate identity, and an explicitly approved quarantine remains idempotent on retry.

The daily scheduler runs one wake-safe, exchange-calendar-derived tick. It qualifies Tiingo data,
freezes a snapshot, runs the registered deterministic strategy through Nautilus, and writes a
content-addressed `OrderIntent`. The intent binds the strategy fingerprint and parameters, NAV,
snapshot identifier/hash, instrument, target, next session, cutoff, knowledge time, and fixed risk
profile. A repaired process resumes from an already-published exact snapshot rather than refetching
or silently rebinding the decision to a later receipt.

IBKR Paper is a broker-paper boundary, not a second engine. Native pinned Nautilus IB clients may be
constructed only for loopback port 4002, a `DU…` account, an approved client-ID range, an explicit
instrument allowlist, and a reviewed digest-pinned gateway image. Order authority requires both
`ALPHA_PAPER_ENABLED=true` and `ALPHA_IBKR_PAPER_ENABLED=true`. `ibkr-run` consumes the exact
scheduler intent, reconciles the journal expectation with the broker account before release, and
uses the intent hash as the broker client-order reference. A stale quote/cutoff, mismatch, duplicate,
journal failure, rejection, or disconnect blocks new orders. Safe stop cancels ALPHA-owned DAY
orders and does not flatten positions. An atomic, permanent release claim makes every intent
one-shot across process restarts; reconciled overnight units initialize the next order delta.

Futures remain connectivity probes using explicit dated micro contracts; strategy-generated
futures orders, continuous symbols, automatic rolls, and futures research claims are prohibited.
Live-capital routing is absent.

## Implementation anchors

- `packages/alpha-data/src/alpha_data/adapters/base.py` and `tiingo_adapter.py`
- `packages/alpha-data/src/alpha_data/pipeline.py`, `store.py`, and `snapshot.py`
- `apps/alpha-cli/src/alpha_cli/daily_scheduler.py`, `_ibkr_paper.py`, `paper_cmds.py`,
  `paper_store.py`, and `paper_readiness.py`
- `packages/alpha-strategies/src/alpha_strategies/base.py`
- `apps/alpha-web/src/alpha_web/api/candles.py` and `api/paper.py`
- `tests/unit/test_tiingo_adapter.py`, `test_ingest_pipeline.py`, `test_daily_scheduler.py`,
  `test_ibkr_paper.py`, `test_paper_strategy.py`, and `test_paper_readiness.py`

## Options considered

- Streamlit or a second chart layer: rejected because the current React/Lightweight Charts surface
  already satisfies the visual boundary.
- LEAN/QuantConnect or MetaTrader as another engine: rejected because this duplicates or weakens
  the canonical Nautilus/CLI authority.
- Massive or Databento in this milestone: deferred until the universe, intraday requirements, or
  funded futures research justify their cost and a new evidence review.
- Direct browser/strategy vendor or broker calls: rejected because they bypass receipts, PIT,
  qualification, intent, and reconciliation controls.

## Consequences

- Easier: one engine, auditable source corrections, replayable snapshots, deterministic intent
  creation, and a narrow broker boundary.
- Harder: qualification is fail-closed; vendor/broker outages and mismatches require operator
  review rather than fallback.
- Operational status: offline implementation is testable without secrets. “Paper passed” remains
  pending until the machine-readable Binance and real IBKR Paper evidence requirements all pass.
- As amended on 2026-08-12, legacy journal scenario labels and producer `passed` booleans are not
  machine evidence. The aggregate remains pending until the versioned acceptance runner and
  mechanical verifier bind causal facts to an immutable one-shot plan. A non-transmitting IBKR
  what-if preview is connectivity evidence only and earns no paper-readiness credit.
- Revisit live capital only through a separate ADR, threat model, cost model, kill-switch drill, and
  explicit owner approval.
