---
owner: research pipeline
sources:
  - apps/alpha-cli/src/alpha_cli/spine/*.py
  - apps/alpha-cli/src/alpha_cli/test_cmds.py
  - apps/alpha-cli/src/alpha_cli/_context_plan.py
verified: a91b14f6153dbbae
---

# Rule test

**Reach for it when** the owner states a price rule or asks "does X work": the one route for a new idea.
**Command**
```text
uv run alpha test <spec.toml> --json
uv run alpha test --rule ma_cross --param fast=50 --param slow=200 --asset SPY --idea "<owner's words>" --json
uv run alpha test <spec.toml> --recheck --json   # system check, not a trial; exit 4 if the result differs
```
A spec file holds `name`, `idea`, `assets`, a `[rule]` table (`kind` plus its numbers) and an optional `[costs]` table
(`fee_bps`, `slippage_bps`). Rule kinds: `ma_cross` (`fast`, `slow`), `breakout` (`window`), `tsmom` (`lookback`, `skip`).
An asset is a symbol, or symbol@store. A file and rule flags cannot be mixed. `--quick` runs a small gauntlet, labelled `quick`.
An optional `idea_card` links an [idea card](idea-card.md). `[context]` and `when` (see `research/examples/rule-context.example.toml`): `--plan` only.
**How to read it**
- Each asset carries its own [data health verdict](data-health.md). Use `--check-data` to check missing or changed inputs before testing.
- The headline starts at the first open after warm-up; tiles, Sharpe and charts share each row’s dates (walk-forward only).
  Both lines use split-adjusted opens and one dividend basis. Missing period facts read “not recorded”.
- Each asset has `run_id`, `reading`, `oos_sharpe`, `benchmark_sharpe`, `labels`, `flags`, `error`, `resized_entries`, `executed`.
  `trials_total` counts ledger trials; `test_id` names the test.
- Quote the `reading`, never a grade: `clear of chance`, `some evidence`, `not clear of chance` or `too little to read`,
  and above, below or within the uncertainty of buy-and-hold. `Fault:` means no reading. `verdict` is the old letter.
- A failed asset keeps its row with `error` set and counts as a trial. If all fail, read `known` and `next` in `error`.
- Bars per year follow each market's calendar. Bars from 2024-01-01 on are held back (`reserved-period-held-back`).
- `--recheck`: the test computed again and compared with the stored result; no ledger row, no file
  ([rule](../../docs/reference/invariants/cli-rule-readings.md#recheck)). `executed` is `true` if the engine ran; `repeat` is not that.
**What it cannot tell you**
- Today's limits, planned to be lifted ([checklist](../../docs/roadmap/production-scope.md#4-backtest)): three rule kinds,
  daily bars, long only, all-in sizing. Say so and offer the nearest kind, or `alpha backtest run <SYMBOL> --timeframe 1h`
  (intraday, or a saved rule with `--strategy rules`): a plain backtest, no diagnostics, not in the ledger. Label it so.
- Whether the result is real. Read [diagnose and audit](diagnose-and-audit.md) first.
**Next** `uv run alpha diagnose <run_id> --json`, then the card that matches the first flag.
