# Daily Data and IBKR Paper Hardening — Implemented Current-State Specification

**Date:** 2026-08-03
**State:** Offline implementation complete; external qualification and broker evidence pending
**Authority:** `CLAUDE.md`, ADR-0017, and the provider-control design

## Scope and authority

This change extends ALPHA's existing provider and operational-paper planes. It does not add
Streamlit, LEAN, MetaTrader, Massive, Databento, a second execution engine, or live-capital routing.
The browser remains a typed React/Lightweight Charts client of FastAPI. NautilusTrader remains the
sole simulator/executor, and only `alpha_cli` constructs provider, scheduler, strategy, or broker
objects.

Tiingo is the only source eligible for automatic stock/ETF daily promotion. Yahoo Finance and Stooq
remain explicit comparison pulls and may not silently replace Tiingo canonical bytes. CCXT remains
the crypto data path; Binance public data plus local Nautilus Sandbox remains crypto paper.

## Daily data contract

`DatasetIdentity` records canonical/provider symbols, provider, venue, asset class, `1D`, exchange
calendar, currency, and raw basis. `FetchReceipt` binds the requested range, UTC retrieval time,
adapter/parser versions, response SHA-256/size, row/action counts, and redacted request metadata.
Version-2 provenance embeds both; v1 stores and snapshots retain read compatibility.

Receipt-backed layouts below `data_dir/store/` are additive:

- `receipts/<provider>/<receipt-id>/` — immutable response bytes and receipt;
- `candidates/<provider>/<receipt-id>/` — passing merged candidate and quality report;
- `quarantine/<provider>/<receipt-id>/` — failed candidate, previous canonical untouched;
- `promotion-backups/<provider>/<receipt-id>/` — exact pre-promotion bytes; and
- `promotions/<symbol>.json` — fail-closed interruption marker.

The gate checks duplicate timestamps, OHLC/volume validity, exchange-calendar completeness, missing
canonical sessions in the requested range, conflicting actions, source authority, and cross-source
close differences above 1% on non-action dates. Identical rows are idempotent; corrections record
timestamp and old/new SHA-256; absent incoming rows never delete history. In-process promotion
failure restores the exact backup. A killed process leaves reads blocked until
`alpha data rollback-promotion SYMBOL --acknowledge` restores it.

## Decision and release contract

`launchd` invokes `alpha paper scheduler-tick` every five minutes. A tick derives the latest eligible
session from the configured exchange calendar, UTC close, and correction delay, so sleep/wake and
DST do not create missed wall-clock jobs. It performs Tiingo receipt ingestion, qualification,
snapshotting, and a real Nautilus simulation before publishing one immutable intent. An interrupted
cycle keeps a `.running` marker and requires exact-symbol/session repair. If the atomic snapshot was
already published before the interruption, the repaired cycle resumes from that exact verified
snapshot and its embedded receipt without contacting the vendor again.

The IBKR release path accepts only that persisted intent. It verifies its content hash and matches
the current strategy fingerprint/parameters, configured NAV, snapshot ID/hash, instrument, next
session, risk profile, and cutoff. The intent ID is journaled before submission and becomes the
Nautilus/IB client order ID. Before node construction, an atomic one-shot release claim permanently
consumes that intent hash; a process restart cannot resubmit it. It cannot be regenerated from a
later quote.

## Broker-paper threat model

Protected assets are the paper account state, approved intent, canonical dataset/snapshot, journal,
and secrets. Threats include live-port/account confusion, mutable images, unapproved instruments,
duplicate/ambiguous submission, stale data/quotes, missed cutoffs, journal loss, reconnect drift,
client-ID collision, hostile vendor text, and accidental frontend exposure.

Controls are:

- paper port 4002 and IPv4 loopback only; live/desktop ports rejected;
- `DU…` account and client IDs 20–28 only;
- dependency-reviewed gateway image pinned by SHA-256 digest;
- full account identifier remains inside the CLI/broker boundary; journal/API receive a masked alias;
- two independent execution flags and a nonempty exact instrument allowlist;
- native Nautilus reconciliation before strategy start plus journal-expected position matching;
- no open orders, no unexpected instruments, and exact expected units at admission; reconciled
  overnight units seed the target-to-order delta instead of assuming a flat book;
- latest completed Tiingo bar, verified snapshot, five-second quote freshness, healthy process
  heartbeat, and unexpired next-session cutoff;
- long-only equities, 5% NAV/order, 10% NAV/position, 50% gross, 1% daily-loss halt, and five open
  orders; all broker orders are DAY;
- durable one-shot release claim, intent-before-submit journal, and content-derived idempotent
  client order ID;
- cooperative safe stop cancels ALPHA orders and never auto-flattens; and
- AI has no secret, enable-flag, promotion, strategy-registration, or order-construction authority.

Futures validation is intentionally unsupported. Only explicitly dated MES/MNQ/M2K/MCL/MGC paper
contracts may be used by an owner-directed connectivity probe; one contract/open futures position,
DAY orders, no rolls, and no strategy generation are the v1 ceiling.

## Acceptance state

**2026-08-12 correction:** the original scenario-field reader is not an acceptance authority. A
generic journal event can carry arbitrary payload keys, and no shipped runtime path produces the
complete required scenario set. Legacy events therefore remain monitoring history only and the
aggregate readiness projection is forced pending. The replacement must freeze an immutable
one-shot plan, admit closed typed facts only from the dedicated runner, hash-chain them to exact
session heads, and mechanically recompute every predicate while ignoring producer pass flags.

Offline unit/integration, schema, frontend, and deterministic gates validate the code boundary.
Operational acceptance is separate. The readiness report can pass only from matching journal event
types/scenario identifiers and fails in the presence of rejection, reconciliation warning, or failed
risk checks. The standalone Binance public-quote smoke passed locally on 2026-08-04; the report still
requires durable Binance network-smoke and UTC-rollover events, then contract/permission,
cancellation, entry/exit, overnight restart, duplicate/position/fill/live-port/secret checks for
IBKR equity and the single micro-futures probe. Elapsed time and an operator assertion cannot pass it.

Until those external scenarios are executed with owner-provided accounts, permissions, reviewed
image digest, and subscriptions, readiness remains `pending`, futures research remains `false`, and
live-capital routing remains `absent`.
