# ADR-0018: Split QuantPad discovery from bulk research-data access

**Status:** Accepted
**Date:** 2026-08-04
**Deciders:** Project ALPHA owner and AI build agents

## Context

The owner has an active QuantPad subscription whose external-data interfaces expose broad
historical futures, US-equity, equity-option, and futures-option coverage. QuantPad exposes two
different interfaces: an OAuth-authenticated MCP server for symbol discovery, coverage/schema
inspection, usage reporting, and small bar previews; and an API-key-authenticated REST/Python SDK
for bulk bars, trades, quotes, and supported 10-level market-by-price depth.

Those interfaces can materially improve research coverage, but neither should bypass ALPHA's
point-in-time, receipt, quality, snapshot, and execution boundaries. QuantPad is historical rather
than a live execution feed; its advertised L2 lookback is currently 30 days, full order-level L3/MBO
is not exposed, and advertised continuous futures require separate dated-contract verification.

## Decision

Adopt QuantPad as an **external research-data source**, not as canonical daily authority or an
execution feed.

- Use `https://quantpad.ai/api/mcp` from Codex for symbol search/resolution, coverage and schema
  discovery, usage inspection, and small OHLCV previews only. MCP responses are bounded discovery
  material and are never assembled into a dataset by repeated preview calls.
- Use the official `quantpad-data` Python SDK or `https://api.quantpad.ai` REST API for bulk bars,
  trades, L1, and `mbp-10` L2 payloads. Do not scrape the website or call nonpublic endpoints.
- Keep the QuantPad API key in the macOS keychain service `project-alpha-quantpad`; expose it only as
  process-local `QUANTPAD_API_KEY`. The OAuth MCP connection does not use this key.
- Keep Tiingo as the authoritative daily stock/ETF source, CCXT as the crypto source, and IBKR Paper
  as the stock/ETF paper connectivity/execution boundary. QuantPad data cannot create or release an
  order intent.
- Until a receipt-backed QuantPad adapter and qualification tests are implemented, downloaded data
  is research scratch input only. It cannot enter the canonical store, an immutable validation
  snapshot, a strategy evidence claim, or paper readiness.
- A later adapter must preserve QuantPad symbol/schema identity, UTC event time and knowledge time,
  contract identity, request/response hashes, coverage, corrections, and rate-limit metadata, then
  pass the existing candidate/quality/quarantine path before promotion.
- Local use remains private and single-operator. Do not redistribute, rehost, publicly display, or
  use the data to train a model. Permanent bulk retention, retention after subscription lapse, and
  any commercial or public use require explicit written QuantPad permission because the public
  product guide and license language are not sufficiently aligned on those cases.

## Implementation anchors

- Project Codex MCP registration: `.codex/config.toml`
- Operator routing and keychain procedure: `docs/operations/README.md`
- Canonical ingestion boundary: `packages/alpha-data/src/alpha_data/pipeline.py`
- Existing provider authority: `apps/alpha-cli/src/alpha_cli/providers.py`

## Consequences

- Codex can immediately inspect QuantPad symbols, schemas, coverage, and small samples after the
  owner completes OAuth sign-in in a new session.
- Bulk research can use the supported Arrow/CSV streaming API without abusing MCP preview limits or
  scraping browser pages.
- QuantPad expands research coverage without weakening Tiingo, CCXT, Nautilus, IBKR Paper, or the
  CLI composition boundary.
- Canonical QuantPad ingestion remains unimplemented and fail-closed until a separate tested adapter
  slice and license/retention evidence are approved.
