---
owner: research pipeline
sources:
  - apps/alpha-cli/src/alpha_cli/results_cmds.py
  - apps/alpha-cli/src/alpha_cli/spine/*.py
verified: ff8acf6e5b75ea90
---

# Diagnose and audit

**Reach for it when** a rule test finishes, and before any result is reported: it is the review step.

**Command** `uv run alpha diagnose <run_id> --json` (reads the pass stored with the run; costs nothing).

**How to read it**
- `flags`: observations, each with a `detail` sentence: `below-benchmark`, `drawdown-with-market`,
  `concentrated-profit`, `fragile-to-costs`, `fragile-to-parameters`, `fragile-to-delay`, `fragile-to-price-noise`, `implausibly-good`.
- `audit`: each line has `check`, `status` (`PASS`, `FLAG` or `NOT-CHECKED`) and `detail`.

| Check | A `FLAG` means |
|---|---|
| `fills-after-decisions` | a fill is not later than its decision: possible look-ahead; treat as fatal |
| `fills-inside-bar-range` | a fill is outside its bar's low to high, allowing the recorded slippage: unrealistic fill or mismatched data |
| `costs-charged` | fee or slippage is zero |
| `enough-trades` | fewer than 30 closed walk-forward trades |
| `benchmark-present` | a buy-and-hold figure is missing |
| `history-length` | under three years of bars |
| `artifacts-intact` | the stored files failed verification |
| `quick-run` | the run carries the `quick` label (`variants-counted` never flags: it counts the re-runs) |

- Other blocks: `full_sample`, `benchmark`, `drawdowns`, `by_year`, `concentration`, `sensitivity`, `delay`,
  `price_noise`, `inverted_signal`, `walk_forward_efficiency`, `trials`, and `macro_window` (stored macro series around
  the worst drawdown, or `available: false` and a `reason`).
- `implausibly-good`: at least 30 OOS trades and net Sharpe above 3, hit rate above 80%, or mean net
  daily-trade return above 5%. Check data and look-ahead; this observation blocks the word `clear of chance`.
- `too-few-trades`: fewer than 30 closed OOS trades. The reading says `too little to read`; the numbers stay.
**What it cannot tell you**
- A grade or pass mark: there is none. `alpha diagnose` prints the reading first. No flag is not proof of an edge.
- Volume against trade size, beta, regimes, or cherry-picking beyond the recorded variants. `--no-diagnose` runs return `NO_DIAGNOSTICS`.
**Next** Take the first `FLAG` to [the symptom index](README.md) and pick the cheapest test.
