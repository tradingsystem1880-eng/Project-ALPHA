---
owner: command line paper and providers
sources:
  - apps/alpha-cli/src/alpha_cli/paper_*.py
  - apps/alpha-cli/src/alpha_cli/_paper.py
  - apps/alpha-cli/src/alpha_cli/*ibkr*.py
  - apps/alpha-cli/src/alpha_cli/daily_scheduler.py
  - apps/alpha-cli/src/alpha_cli/provider*.py
  - apps/alpha-cli/src/alpha_cli/system_status.py
  - tests/unit/test_paper_*.py
  - tests/unit/test_daily_scheduler.py
  - tests/integration/test_paper.py
  - tests/integration/test_provider_cli.py
verified: 1724a5befe5d
---

# Command line paper invariants

What must not break when changing operational paper trading (`alpha paper ...`: Binance sandbox, native IBKR Paper,
the daily scheduler, readiness) and provider status. Project-wide rule:
[research integrity § No live capital](research-integrity.md#no-live-capital).

## Sessions are not research runs

- Paper sessions use UUIDs, clocks, heartbeats and an event journal under `data_dir/paper/<uuid>/`. Never put that
  state into `RUN_DIRS`, `RunSpec`, run hashing or validation evidence.
  [ADR-0012](../../adr/0012-operational-paper-sessions.md)
- Paper shares strategy code with research but never research identity; a paper result is never strategy evidence.
- The journal (`paper_store.py`) is schema v2 (`local_sandbox`, `ibkr_paper`) and must keep reading schema-v1 Binance
  sessions; event records publish atomically and are immutable, and readers recover an event published just before a crash.

## Crypto sandbox

- `alpha paper run` needs `ALPHA_PAPER_ENABLED=true`, `--provider binance`, and a verified, fresh, same-symbol
  `ccxt:binance` warm-up snapshot (`_paper.load_paper_warmup`).
- Only strategies flagged `supports_live_paper` may run (today `ts_momentum`, `ma_crossover`, `mean_reversion`,
  `breakout`); `rules` and `kronos` are refused (`_strategies.py`).
- Binance supplies public data only; execution is the local Nautilus sandbox. Never construct Binance execution or
  accept real-order credentials (the data config sets `api_key=None`, `api_secret=None`).

- `alpha paper preflight` and `alpha paper ibkr-preflight` build their configuration offline; they never connect or
  place an order.

## IBKR Paper boundary

- `IBKRPaperBoundary.create` (`_ibkr_paper.py`) requires an allow-listed `DU…` paper account, a digest-pinned gateway
  image, loopback `127.0.0.1`, paper port 4002, an approved client-id range and a non-empty instrument allowlist.
  Live and desktop ports are denied.
- Order authority needs both `ALPHA_PAPER_ENABLED` and `ALPHA_IBKR_PAPER_ENABLED`.
- Strategy-generated futures orders are disabled; futures are explicit dated micro-contract connectivity probes only.
- Release consumes one exact scheduler-issued intent after broker and journal reconciliation, with a quote no older than
  5 seconds. [ADR-0017](../../adr/0017-authoritative-daily-data-and-broker-paper-boundary.md)
- An intent is one-shot across restarts: `claim_order_intent_release` creates the claim directory exclusively, and a
  second claim fails with "reconcile instead of retrying".
- Reconciled overnight units seed the target delta; never assume a flat account.

## Stop, readiness and previews

- Safe stop cancels ALPHA DAY orders and never flattens positions (`flatten_positions: False` in `paper_store.py`).
- `PaperAcceptanceV2` readiness is mechanically re-verified; elapsed time and legacy producer flags never pass it.
  [ADR-0031](../../adr/0031-provider-readiness-and-paper-acceptance-v2.md)
- The IBKR what-if preview is one-shot from a frozen plan, uses IBKR's required `transmit=true` wire flag with
  `whatIf=true`, must show no broker order, fill or position change, and earns no readiness credit (`ibkr_what_if.py`).
- The daily scheduler is wake-safe; crash-marker repair needs an explicit `--acknowledge`.

## Provider status

- `alpha info providers` and `alpha info system` are redacted and local-only; they never probe the network.
- `alpha provider check` is the only explicit, bounded verification path and writes a `ProviderCheckReceiptV1`.
