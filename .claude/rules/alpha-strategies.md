---
paths:
  - "packages/alpha-strategies/**"
---
# alpha_strategies rules

Verbatim relocation from the pre-v2 CLAUDE.md MODULE MAP (drift-tested against `tests/fixtures/claude_md_v1.md`). The core `CLAUDE.md` DAG paragraph and golden rules still apply here.
### `alpha_strategies` (`packages/alpha-strategies/src/alpha_strategies/`) — nautilus Strategy + pure decision fns. core only.
| Module | Responsibility | Key public symbols |
|---|---|---|
| `signals.py` | Pure signals (all `{-1,0,1}`, trailing-window only) | `ts_momentum_signal`, `ma_crossover_signal(closes, fast, slow)`, `zscore_reversion_signal(closes, window, entry_z)`, `breakout_signal(highs, lows, closes, window)` |
| `sizing.py` | Pure vol-target sizing | `realized_volatility(closes, *, periods_per_year)`, `vol_target_size(signal, price, vol, *, target_vol, capital, max_leverage)` |
| `base.py` | Shared Nautilus lifecycle for vol-targeted signals (+ opt-in `size_on_equity`, `halt_drawdown`; paper-only priming, exact intent release, reconciliation/risk, venue normalization) | `VolTargetStrategy` (`prime_history`, `configure_paper_risk`, `release_paper_intent`; subclasses implement `_signal()`), `PaperRiskLimits`, `normalize_order_quantity` |
| `ts_momentum.py` | TS-momentum (a `VolTargetStrategy` subclass since the 2026-07 audit) | `TimeSeriesMomentum` |
| `signal_replay.py` | Replay a precomputed per-bar signal sequence (the kronos engine strategy; fail-loud on uncovered indices) | `SignalReplay(VolTargetStrategy)` |
| `ma_crossover.py` · `mean_reversion.py` · `breakout.py` | `VolTargetStrategy` subclasses | `MovingAverageCrossover`, `MeanReversion`, `DonchianBreakout` |
| `hedged_basis.py` | Pure sandbox model for the registered two-venue BTCUSDT basis candidate (ADR-0033): evaluates an already-materialized point-in-time crowding event stream; constructs no orders, connects to neither venue, and never reinterprets a leg as a universal crypto price | `HedgedBasisPlanV1`, `registered_hedged_basis_plan`, `HedgedBasisObservationV1`, `HedgedBasisTradeV1`, `HedgedBasisEvaluationV1`, `evaluate_hedged_basis` |

