---
owner: research pipeline
sources:
  - apps/alpha-cli/src/alpha_cli/spine/setup_costs.py
  - apps/alpha-cli/src/alpha_cli/spine/setup_trade_figure.py
  - apps/alpha-cli/src/alpha_cli/spine/setup_study.py
  - apps/alpha-cli/src/alpha_cli/spine/setup_controls.py
  - apps/alpha-cli/src/alpha_cli/spine/event_study_figure.py
  - apps/alpha-cli/src/alpha_cli/setup_cmds.py
verified: 3bdc969274d42c70
---
# Setup study

**Reach for it when** a recorded setup find has the intended matches and you want what followed each separate occurrence measured against ordinary dates.
**Commands**
```text
uv run alpha setup study <find_id> --json
uv run alpha setup study <find_id> --recheck --json   # no write; exit 4 if it differs
uv run alpha results cite <study_id> setup_mean_net_return --json
```
**See stored results:** Workstation → Research → Setup Lab.
**How to read it**
- Include `[study]` horizons and primary in the spec before finding. Only the pooled primary
  horizon is tested; others say "also looked at, not tested" and carry `not-primary`.
- Lead with complete separate occurrences beside matching days. Entry is the recorded next open;
  each horizon ends at its bar close, with [per-asset costs](setup-trade.md) on both sides.
  Old studies read with `older-cost-rule`; re-studying one is `remeasured-new-cost-rule`: one more look.
- Compare mean net return with drift and 2,000 spaced random-date samples (figure: grey band, dashed drift).
- Under 30 complete occurrences the word is `too little to read`. Overlapping outcomes and disagreeing halves are labels,
  not evidence to omit. Never say `clear of chance`: the p-value is not corrected for the setup variants tried.
- Quote the evidence word, "Setup study K of N" and the adjusted random-date figure; other idea texts are not counted.
  `alpha setup show <study_id> [<id> ...] --json` reads them again, for studies or trades, with no write.
- Each study counts one trial; a repeat is labelled `repeat`. A held-back find passes its label on; a find that used reserved bars is refused.

The study checks the inputs again before measuring returns. A failed report requires a reason on this invocation. [Data health](data-health.md)
**What it cannot tell you** Exits, sizing, portfolios, dividends or reserved-data confirmation.
Setups cluster in market states (a double bottom follows a decline): beating random dates says
the dates were unusual, not that the setup can be traded.

**Next** Cite stored facts and limitations; use [setup trade](setup-trade.md) to test declared exits.
