---
paths:
  - "packages/alpha-backtest/**"
---
# alpha_backtest rules

Verbatim relocation from the pre-v2 CLAUDE.md MODULE MAP (drift-tested against `tests/fixtures/claude_md_v1.md`). The core `CLAUDE.md` DAG paragraph and golden rules still apply here.

RISK TIER: every edit under `packages/alpha-backtest/src` requires an APPROVE `ReviewVerdict` (`/review-gate`) before commit.
### `alpha_backtest` (`packages/alpha-backtest/src/alpha_backtest/`) — nautilus run harness. core + data only.
| Module | Responsibility | Key public symbols |
|---|---|---|
| `feed.py` | Bar → nautilus feed (t+1-fill encoding) | `to_execution_feed(bars, bar_type, *, slippage_bps=...)`, `daily_bar_type(symbol, venue="SIM")` |
| `engine.py` | `BacktestEngine` harness (`bar_execution=False`; credits dividend cash at pay_date) | `run_backtest(instrument, data, strategy, *, starting_cash, account_type, leverage, fee_bps, dividends)` → `BacktestResult` |
| `instruments.py` | Per-asset instruments (slash pairs → 5-decimal crypto) | `instrument_for(symbol)`, `equity_instrument`, `crypto_instrument` |
| `frictions.py` | Per-notional fee model | `BpsFeeModel(fee_bps)` (slippage modeled separately in `feed`) |
| `results.py` | Canonical result + causal trace schema | `BacktestResult(orders, fills, trades, equity_curve, decision_trace, indicator_trace, chart_annotations, order_trace, fill_trace, portfolio_state_trace, benchmark_curve)`, `Trade`, `OrderTrace`, `FillTrace`, `PortfolioStateTrace` |
| `portfolio_replay.py` | Deterministic synchronized long-only target-weight replay with ONE cash ledger across symbols (the Nautilus harness is single-instrument; per-symbol engines cannot reconcile a rotating cross-sectional book) | `WeightTarget`, `ReplayPeriod`, `PortfolioReplayResult`, `run_weight_replay` |

