---
owner: research pipeline
sources:
  - apps/alpha-cli/src/alpha_cli/spine/*.py
  - apps/alpha-cli/src/alpha_cli/optim_cmds.py
verified: eaa3634693206571
---

# Deflated Sharpe and trial counting

**Reach for it when** several settings, assets or ideas were tried and one looks good. More tries, luckier best.

**Commands**
```text
uv run alpha results --symbol <SYMBOL> --json
uv run alpha results cite <run_id> trial_dsr
uv run alpha results cite <run_id> family_trials
uv run alpha optim grid <SYMBOL> --strategy ma_crossover --grid fast=20,50 --grid slow=100,200
```

**How to read it**
- `trial_dsr` and the verdict's `dsr` use the same inputs (equal after a rule test): spread from the idea
  family's distinct same-bar-size Sharpes and this run, N from the family count; its `trial_basis` names the
  family, repeats not counted and a floored spread (under 5 comparable trials), or says no family was found.
  Pass line 0.95. Variants count in N but stay out of the spread: full-sample, neighbouring, correlated.
- Cite `family_trials` for the count at the run: prior family trials, this run, scored variants and unknown
  rows, never below the distinct same-asset tests. `alpha results show` adds live family counts.
- A test is spec hash, asset, data window, bar size, store and data content, never the code version: the
  same test after a code change is a `repeat` (`repeat_of`: first run), counted nowhere; newer bars are a new test.
  The label is in the ledger row only. `same_asset_tests`, `same_asset_repeats`: "N distinct tests on this asset; R repeats not counted".
- `total_trials`: ledger row number, an audit sequence, not ideas tried (say "ledger entry N"). `variants_evaluated`: sensitivity re-runs only.
- `alpha optim grid` sweeps declared settings and prints the best one with its deflated Sharpe, `PBO` (the
  probability that the in-sample winner is below the middle out of sample; high is bad), and the `SPA` and
  `RC` p-values (is the best better than no skill, allowing for the search).
- Under 30 closed OOS trades: `too-few-trades` shows and the reading says `too little to read`. Noise copies are no trial.
**What it cannot tell you**
- Trials nobody recorded (`alpha validate`, `alpha optim`, `alpha backtest` runs): count by hand; the true number is higher.
- `alpha ledger summary` and `families` count every recorded try read-only; effective tests are not shown. Family counting feeds the verdict.
**Next** A setting that survives: check it against [the random-price null](random-price-null.md) and the
benchmark. A setting that does not: report it as best-of-many and stop tuning.
