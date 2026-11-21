---
owner: research pipeline
sources:
  - apps/alpha-cli/src/alpha_cli/spine/*.py
  - apps/alpha-cli/src/alpha_cli/optim_cmds.py
verified: eaa3634693206571
---

# Sensitivity: costs, delay and nearby settings

**Reach for it when** a result may depend on cheap trading, on catching the exact bar, or on one lucky
setting. Every rule test already made the cheap re-runs.

**Commands**

```text
uv run alpha diagnose <run_id> --json
uv run alpha results cite <run_id> delayed_sharpe
uv run alpha test --rule ma_cross --param fast=50 --param slow=200 --asset SPY --fee-bps 5 --slippage-bps 10 --json
```

**How to read it**

- `sensitivity.variants` holds full re-runs: `costs_x2` (fee and slippage doubled) and each rule number moved
  down and up by a fifth (`kind` is `costs` or `parameter`), each with its own Sharpe, return and drawdown.
- `delay` compares `base_sharpe` with `delayed_sharpe` (every position taken one bar later). It is a
  returns-level approximation, not a full re-run: compare the two with each other, not with `oos_sharpe`.
- Flags: `fragile-to-costs`, `fragile-to-parameters`, `fragile-to-delay` fire when a variant's Sharpe is at or
  below zero, or under half the base.
- For other cost levels, run the rule test again with `--fee-bps` and `--slippage-bps`. Each is a counted
  trial; say you changed the costs and why.

**What it cannot tell you**

- For the scored break-even cost, use the [run-level check](run-level-checks.md). Costs here are flat and do not model trade capacity.
- Wider parameter ranges: the re-runs are one step each side only. A sweep is
  [deflated Sharpe and trials](deflated-sharpe-and-trials.md), and it must be reported as a search.

**Next** Fragile to costs: state the holding period and trade count beside it. Fragile to delay: treat the
result as depending on the exact bar and check `fills-after-decisions` in the audit.
