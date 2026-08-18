---
paths:
  - "packages/alpha-core/**"
---
# alpha_core rules

Verbatim relocation from the pre-v2 CLAUDE.md MODULE MAP (drift-tested against `tests/fixtures/claude_md_v1.md`). The core `CLAUDE.md` DAG paragraph and golden rules still apply here.
### `alpha_core` (`packages/alpha-core/src/alpha_core/`) — domain types, protocols, errors, config. Imports nothing internal.
| Module | Responsibility | Key public symbols |
|---|---|---|
| `types.py` | Frozen domain values | `Bar` (OHLCV), `ValidationOutcome`, causal `DecisionTrace`/`IndicatorTrace`, deterministic vector `ChartAnchor`/`ChartAnnotationTrace` |
| `errors.py` | Typed error hierarchy | `AlphaError` ← `DataError`, `LookAheadError` |
| `protocols.py` | Structural interfaces | `DataSource` (`available_symbols`, `as_of`), `Validator`, `ExecutionEventSink` (flat low-volume operational events only) |
| `config.py` | Typed settings (env `ALPHA_*`/`.env`) | `AlphaSettings(data_dir=Path("data"), random_seed=7, paper_enabled=False, ibkr_paper_enabled=False)`; `forecast_hub_cache`/`forecast_local_only` = machine-local HF weight cache + no-network loading (never in run ids/manifests; ADR-0010) |
| `corporate.py` | Corporate-action types (two-clock) | `ActionType` (SPLIT/DIVIDEND/REDENOMINATION/SYMBOL_MIGRATION), `CorporateAction` (`knowledge_time`, `knowledge_is_estimated`) |

