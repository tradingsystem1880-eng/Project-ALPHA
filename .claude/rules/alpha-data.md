---
paths:
  - "packages/alpha-data/**"
---
# alpha_data rules

Verbatim relocation from the pre-v2 CLAUDE.md MODULE MAP (drift-tested against `tests/fixtures/claude_md_v1.md`). The core `CLAUDE.md` DAG paragraph and golden rules still apply here.
### `alpha_data` (`packages/alpha-data/src/alpha_data/`) — ingestion, PIT storage, snapshots.
| Module | Responsibility | Key public symbols |
|---|---|---|
| `store.py` | Raw unadjusted Parquet store + fail-closed promotion markers and v1/v2 per-symbol provenance | `ParquetStore(root)`: bars/actions methods + provenance/promotion methods |
| `pit.py` | **Look-ahead firewall** (frame-level) | `PointInTimeReader.as_of` (split-adjusted, future-excluded), `.dividends_as_of` |
| `source.py` | Typed PIT `DataSource` seam | `PointInTimeSource.as_of` → `list[Bar]`, `.dividends_as_of` |
| `corporate.py` | Two-clock split/div math | `known_actions`, `cash_dividends`, `split_factor` |
| `snapshot.py` | Immutable hashed snapshots + manifest; copies/hashes legacy or v2 provenance sidecars and rejects source relabelling | `create_snapshot`, `verify_snapshot` |
| `ingest.py` | Persist a `FetchResult` | `store_fetch_result` |
| `adapters/base.py` | Adapter seam + versioned source identity/receipt | `DatasetIdentity`, `FetchReceipt`, `FetchResult`, `DataAdapter` protocol |
| `adapters/tiingo_adapter.py` | Authoritative stock/ETF EOD: raw OHLCV, explicit split/dividend actions, adjusted-field consistency check, redacted receipt | `TiingoAdapter`, `parse_tiingo_eod` (pure) |
| `pipeline.py` | Immutable receipt/candidate/quarantine, calendar/correction/cross-source quality gate, merged promotion backup/recovery | `stage_and_promote`, `promote_quarantined`, `rollback_interrupted_promotion` |
| `adapters/yfinance_adapter.py` | Equities (splits+divs); reconstructs RAW prices from Yahoo's split-adjusted series, fail-loud discontinuity check | `YFinanceAdapter`, `parse_yfinance_history` (pure) |
| `adapters/ccxt_adapter.py` | Crypto daily OHLCV (UTC; validated `coinbase|binance`; **paginated** past per-call caps; venue-qualified provenance) | `SUPPORTED_CCXT_EXCHANGES`, `CCXTAdapter`, `parse_ccxt_ohlcv` (pure) |
| `adapters/stooq_adapter.py` | Comparison-only EOD OHLCV (FX/commodity/index/ETF; provider-adjusted, no actions). **Anti-bot gated:** browser-UA + SHA-256 PoW solve, then **fails loud** (`_csv_or_raise`) on Stooq's per-IP "Access denied"; never replaces authoritative Tiingo stock/ETF history | `StooqAdapter`, `parse_stooq_csv` (pure) |
| `adapters/quantpad_adapter.py` | **Research-only** daily bulk sub-slice (ADR-0018/0023): official `api.quantpad.ai` REST only, pinned wire schema that fails loud on drift, content-bound receipts, receipted scratch persistence for `rd_` dataset registration. Never in `data pull`/`_ADAPTERS`; provider capability `research_bars`, `research_authority: false` | `QuantPadAdapter`, `parse_quantpad_bars` (pure), `persist_research_fetch` |

