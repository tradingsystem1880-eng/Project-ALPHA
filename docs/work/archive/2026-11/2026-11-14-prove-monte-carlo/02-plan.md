# Prove "Path-risk simulation (Monte Carlo)" end to end

**Delivery state:** Completed — built, reviewed and verified on branch `m8/prove-monte-carlo`; done when its pull request merges.
**Build class:** standard — four files; output and caveat changes in one alpha-cli command, tests and a smoke check; no quant-tier source.

Filed straight into the archive, as `2026-11-14-prove-crypto-data` was: the work-in-progress
ceiling admits no new live plan, and the work is finished in one sitting.

## For the owner

- A new automatic check runs the real `alpha` program to simulate a strategy's possible paths and
  recomputes every number with independent code. "Path-risk simulation" can now count as Working.
- The "regime" simulation now says how many days fell in its calm and volatile states and warns
  when one is nearly empty: on your Alpaca SPY data 97.5% of days were "volatile", so that
  simulation was in effect the same as the plain reshuffle.
- The command now prints the headline numbers (median outcome, bad-case drawdown, chance of loss
  and of ruin) instead of only a grade.
- Nothing for you to decide here. The Kronos-model simulation is not proven (no model files here).

```json
{
  "schema_version": 1,
  "title": "Prove Path-risk simulation (Monte Carlo) end to end",
  "context": "monte-carlo is Partial: only an in-process CliRunner test exists. Run through the installed alpha on a real validate run (Alpaca SPY 2016-2026, 2,205 OOS returns, 2,000 paths): every family's terminal-return q05/q50/q95, drawdown q50/q95, loss-streak q95, loss and ruin probabilities and their Wilson bounds matched an independent recomputation from paths.parquet to 9e-19; IID and regime draws are all from the observed OOS returns; reruns are deterministic (same run id). Findings: the regime boundary is frozen from the first training prefix (2016-2017, very calm), so state 0 held 55 of 2,205 OOS returns (2.5%) and the family is effectively IID while reporting 'estimable'; the command prints only status/grade per family; report.md does not show state populations.",
  "assumptions": [
    {"statement": "summarize_path_family accepts a caveats tuple that is stored in the family summary and so in the manifest's families list.", "verified_by": "packages/alpha-validation/src/alpha_validation/path_montecarlo.py summarize_path_family signature and return"},
    {"statement": "The run id comes from the identity payload (no summaries or caveats in it), so adding caveats and report lines changes the manifest and report.md but not the run id.", "verified_by": "monte_carlo_cmds.py classical: run_identity_for(payload, ...) with payload built before the summaries"},
    {"statement": "monte_carlo_cmds.py is not in DAILY_GUARD_FILES and not quant tier.", "verified_by": "apps/alpha-cli/src/alpha_cli/_native_rule_environment.py; docs/reference/invariants/engineering.md Quant tier"},
    {"statement": "On the smoke data (seed_store SPY 400 bars, smoke-v1 snapshot, the validation smoke gauntlet), classical Monte Carlo with --regime-window 10 --min-state-observations 10 --min-state-transitions 5 gives 240 OOS returns with states 97/143 in about 1 s.", "verified_by": "prototype run on the Dell, 2026-11-14, tmp/prove2/mcsyn"}
  ],
  "alternatives_considered": [
    "Re-fit the regime boundary per fold or on the OOS window: rejected, it changes a research design decision (ADR-0029, training-frozen causal boundary) and would read OOS data; disclosure is the honest change.",
    "Fail the regime family when one state holds under 10% of OOS returns: rejected, the support floors are already user options; a caveat keeps the declared floors and says what the number is based on.",
    "Change alpha_validation.summarize_path_family to add state shares: rejected, quant-tier bytes; the caller already passes caveats."
  ],
  "pre_mortem": [
    "The smoke check recomputes with the product's own helpers and proves nothing: it uses numpy cumprod/maximum.accumulate, a plain Python streak loop and the Wilson formula written out, never alpha_validation.",
    "Caveat text breaks an existing test that compares manifests: only test_monte_carlo_cli.py reads classical manifests and it does not compare caveats.",
    "The warning threshold misfires on balanced states: it applies only when the smaller state's share is below 0.10; the share is always reported."
  ],
  "slices": [
    {"title": "Regime state disclosure and readable output", "verify": "uv run pytest -q tests/integration/test_monte_carlo_cli.py", "expected": "all pass; the new tests fail on main", "rollback": "revert monte_carlo_cmds.py and the test", "status": "done"},
    {"title": "Monte Carlo smoke check through the installed alpha", "verify": "uv run python scripts/run_owned_test.py --timeout 900 -- uv run pytest -q -m smoke -n 0 tests/smoke/test_monte_carlo_smoke.py", "expected": "passed", "rollback": "delete tests/smoke/test_monte_carlo_smoke.py", "status": "done"}
  ],
  "tier_impact": ["none"],
  "docs_to_update": ["docs/roadmap/capabilities.toml", "STATUS.md", "docs/roadmap/README.md"],
  "out_of_scope": ["packages/alpha-validation/src", "packages/alpha-research/src", "apps/alpha-cli/src/alpha_cli/_artifacts.py", "apps/alpha-cli/src/alpha_cli/report_cmds.py"],
  "files": [
    "apps/alpha-cli/src/alpha_cli/monte_carlo_cmds.py",
    "tests/integration/test_monte_carlo_cli.py",
    "tests/smoke/test_monte_carlo_smoke.py"
  ]
}
```

## Read first

| Read | Section | When |
|---|---|---|
| [tests workspace](../../../../../tests/CONTEXT.md) | How to change it | always |
| [Monte Carlo command](../../../../../apps/alpha-cli/src/alpha_cli/monte_carlo_cmds.py) | `classical`, `_report_text` | always |
| [path statistics](../../../../../packages/alpha-validation/src/alpha_validation/path_montecarlo.py) | `summarize_path_family`, `path_metric_arrays` | always (read only) |
| [smoke harness](../../../../../tests/smoke/_harness.py) | — | slice 2 |
| [smoke homes](../../../../../tests/smoke/conftest.py) | — | slice 2 |
| [validation smoke](../../../../../tests/smoke/test_validation_smoke.py) | `_GAUNTLET` | slice 2 |

## Slices

### 1. Regime state disclosure and readable output

In `apps/alpha-cli/src/alpha_cli/monte_carlo_cmds.py`, `classical` only (leave `kronos` alone):

- Compute `state_observations` (calm, volatile counts) before the summaries (it is already
  computed later; move it up, same values). New module constant `MIN_STATE_SHARE = 0.10`.
- A helper `_regime_caveats(state_observations, horizon) -> tuple[str, ...]`: always
  `f"Causal states: calm {n0} of {h} OOS returns ({p0:.1%}), volatile {n1} ({p1:.1%}); the
  boundary is frozen from the first training prefix."`; plus, when the smaller share is below
  `MIN_STATE_SHARE`, `f"One state holds under {MIN_STATE_SHARE:.0%} of OOS returns, so this family
  is close to the IID empirical family; the frozen boundary may not describe the OOS period."`
- The regime family's summary gets these caveats: `summarize_path_family("regime_switching", ...,
  caveats=_regime_caveats(...))` when estimable; when not estimable, append them after the
  existing failure caveat. Other families unchanged.
- `regime_diagnostics` in the manifest gains `"state_shares": [p0, p1]` (floats).
- `_report_text` gains a `regime_caveats` argument and prints them as a line `Regime states: ...`
  after the table (both caveat sentences when present).
- The final echo becomes the existing first line unchanged, followed by one line per family:
  `f"  {family}: {status}/{grade} median terminal {q50:+.4f} (5%-95% {q05:+.4f} to {q95:+.4f}),
  drawdown median {dd50:.4f} 95th {dd95:.4f}, P(loss) {lp:.3f} [{lo:.3f}, {hi:.3f}], P(ruin, drawdown
  >= 50%) {rp:.3f} [{rlo:.3f}, {rhi:.3f}]"`; a not-estimable family prints `not estimable` and its
  first caveat instead of numbers. Then, when the warning caveat applies, a last line with it.

Tests first in `tests/integration/test_monte_carlo_cli.py` (must fail on main): in the existing
classical run, the regime family's `caveats` start with `Causal states: calm` and its counts equal
`regime_diagnostics.state_observations`; `state_shares` sums to 1; stdout has one line per family
starting with two spaces and the family name, containing `median terminal`, `P(ruin`. A second
test monkeypatches `alpha_cli.monte_carlo_cmds._causal_regime_states` to return states with 1 calm
observation out of the horizon (set `--min-state-observations 1 --min-state-transitions 1`) and
asserts the "close to the IID empirical family" caveat is in the manifest, report.md and stdout.

### 2. Monte Carlo smoke check through the installed alpha

`tests/smoke/test_monte_carlo_smoke.py` (new; `pytestmark = [pytest.mark.smoke,
pytest.mark.usefixtures("owned_test_process")]`). Uses `data_home`, `copy_home`, `SNAPSHOT`,
`STRATEGY` from `tests.smoke.conftest` and `_GAUNTLET` from `tests.smoke.test_validation_smoke`;
every step is `tests.smoke._harness.alpha` (a new process).

1. `test_classical_monte_carlo_is_published_and_recomputes_independently(data_home, tmp_path)`:
   - `alpha validate SPY *STRATEGY *_GAUNTLET --snapshot smoke-v1`; take the run id from
     `-> run <id>:`.
   - `alpha monte-carlo classical --from-run <id> --paths 400 --seed 19 --regime-window 10
     --min-state-observations 10 --min-state-transitions 5`; take the new run id from
     `-> run <id>:`; stdout has a line per family with `median terminal`.
   - The run folder has `manifest.json`, `paths.parquet`, `path_metrics.parquet`,
     `observed_oos.parquet`, `regime_diagnostics.parquet`, `regime_emissions.parquet`,
     `report.md`. Manifest: `command == "monte_carlo_classical"`, `source_run_id`, three families
     with `n_paths == 400` and `horizon` equal to the source equity curve length minus 1.
   - `observed_oos.parquet` equity equals the source run's `equity_curve.parquet` equity exactly.
   - Independent recomputation for every family (numpy and polars only; never `alpha_validation`
     or `alpha_cli`): from `paths.parquet` sorted by path and step, wealth `cumprod(1 + r)` with a
     leading 1, terminal return, maximum drawdown `max(1 - w / running max)`, longest run of
     negative returns by a plain loop, quantiles with `numpy.quantile` (default method) at 0.05,
     0.5, 0.95 for terminal, 0.5 and 0.95 for drawdown, 0.95 for streak; loss = terminal < 0, ruin =
     drawdown >= 0.5; Wilson interval written out with z from `statistics.NormalDist().inv_cdf(1 -
     (1 - confidence) / 2)`. Each equals the manifest family field within 1e-12, and the per-path
     `path_metrics.parquet` columns equal the recomputed arrays.
   - Every IID and regime path value is one of the source OOS account returns
     (`equity[1:] / equity[:-1] - 1`, the same float values).
   - `regime_emissions.parquet` state counts equal `regime_diagnostics.state_observations`, and
     each row of `transition_matrix` equals the transition counts from consecutive emission states
     divided by their row sum (1e-12).
   - `alpha report <mc id>` prints `family[iid_empirical]:` with `median_terminal=` equal to the
     manifest value at 4 decimals; `alpha figures render <mc id> --json` has `failed == []` and the
     four `monte_carlo_*` figure ids.
   - Determinism: the same `monte-carlo classical` command again prints the same run id and the
     `paths.parquet` bytes are unchanged; with `--seed 20` the run id differs.
2. `test_monte_carlo_refuses_a_backtest_source(backtest_home, tmp_path)`: on a copy of the
   backtest home, `alpha monte-carlo classical --from-run <backtest run id>` exits 2 with
   `must be a completed validate run` in the output, and no new run folder appears.

Do not change product code in this slice. If the installed program does not behave as listed,
stop and report the exact output instead of adjusting the expectation.

## Test plan

Slice 1's tests fail on main. Slice 2 starts the installed program; run it outside any sandbox if
a sandbox blocks subprocesses. Existing Monte Carlo tests must pass.

## Look-ahead, determinism and import impact

No read path changes; state labels are computed as before. Seeds unchanged; the run id does not
depend on the new caveat text. No import changes.
