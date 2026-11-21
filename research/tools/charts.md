---
owner: research pipeline
sources:
  - apps/alpha-cli/src/alpha_cli/figures_cmds.py
  - apps/alpha-cli/src/alpha_cli/results_cmds.py
verified: d7965a396c852ce4
---

# Charts

**Reach for it when** an answer would be clearer with a picture, or the owner asks to see it. Name only
charts the run can render.

**Commands**
```text
uv run alpha results show <run_id> --json
uv run alpha figures list --run <run_id>
uv run alpha figures render <run_id> --figure equity_vs_passive --json
```

**How to read it**

- `charts` in `alpha results show` lists the figure ids available for that run. `alpha figures list --run`
  shows each id with `ok` or the reason it is unavailable.
- `alpha figures render` writes the file and, with `--json`, returns its `path`. Give the owner the path and
  one sentence on what to look at.
- Useful ids: `equity_vs_passive` (strategy against buy and hold), `equity_underwater` and
  `drawdown_episodes` (falls), `monthly_heatmap` (when the profit came), `trade_pnl` (each trade),
  `fold_sharpe` (walk-forward slices), `null_distribution` (random-price comparison),
  `confidence_intervals`, `exposure_turnover`, `return_distribution`.
- Every figure comes as a pair: `--variant plain` (the standard chart, the default) and `--variant annotated` (the same chart with callouts and a long reading). All figures are white. New rule tests save both Summary figures for each period in both variants.
- Every rule test also writes a tear sheet (`tearsheet.html`) in its run folder; `alpha report` prints the path.

**What it cannot tell you**

- A chart is the same numbers drawn, not extra evidence. Do not describe a chart you have not rendered, and
  do not read a number off a picture: cite it instead ([results and cite](results-and-cite.md)).
- [Setup sheets](setup-find.md) , [study figures](setup-study.md) and [trade figures](setup-trade.md) exist; regime shading and sensitivity bars do not.

**Next** Put the chart beside the cited numbers in the report, labels first.
