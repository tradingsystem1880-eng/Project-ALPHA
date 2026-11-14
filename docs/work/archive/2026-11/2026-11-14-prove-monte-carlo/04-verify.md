# Verification: "Path-risk simulation (Monte Carlo)" end to end

Run on the Dell on 2026-11-14 (UTC), branch `m8/prove-monte-carlo`.

## Offline, through the installed program (the smoke check)

`uv run python scripts/run_owned_test.py --timeout 900 -- uv run pytest -q -m smoke -n 0 tests/smoke/test_monte_carlo_smoke.py`:
2 passed, 18 s. On the smoke home (synthetic SPY, snapshot `smoke-v1`) the installed `alpha`
runs `validate`, then `monte-carlo classical` (400 paths), `report` and `figures render`. Every
family's terminal-return and drawdown quantiles, loss-streak quantile, loss and ruin
probabilities and Wilson bounds, and every per-path metric, are recomputed from `paths.parquet`
with numpy and a written-out Wilson formula (1e-12); IID and regime draws are all observed OOS
returns; regime counts and the transition matrix agree with the published emissions; the same
command gives the same run id and identical `paths.parquet` bytes, another seed a different id;
a backtest run as source exits 2 and publishes nothing.

New oracle `tests/oracles/test_known_answer_path_montecarlo.py`: hand-computed paths (terminal
return, drawdown including a first-day loss, streaks, the 50% ruin edge), a plain-Python
recomputation on random heavy-tailed paths with flat days, and path-order invariance.

## For real, on free data (not yet confirmed)

On a copy of the Alpaca folder under `tmp/prove2/mc/`:

```text
alpha validate SPY --snapshot alpaca-starter-2026-11-14 --tier1-paths 50 --tier2-paths 4 --tier3-paths 4 --n-resamples 200 --seed 7 --max-workers 4
  -> run 415f2b81ae0ec262: FAIL (Verdict B), OOS Sharpe 0.615, 2,205 OOS returns 2018-01-10..2026-10-20
alpha monte-carlo classical --from-run 415f2b81ae0ec262 --paths 2000 --seed 11      (3 s)
  iid_empirical    warning/D  median terminal +0.7777, drawdown 95th 0.3600, P(ruin) 0.003
  regime_switching warning/D  median terminal +0.7743, drawdown 95th 0.3566, P(ruin) 0.004
  student_t        warning/D  median terminal +0.7261, drawdown 95th 0.3537, P(ruin) 0.001
```

Independent check (`tmp/prove2/scripts/check_mc.py`): every summary field and per-path drawdown
agreed to 8.7e-19; IID and regime draws are all from the observed returns; the observed path
(terminal +0.744, drawdown 0.260) sits inside the simulated range. The same command twice gives
the same run id. `report`, `figures render` (4 figures) and a bad source id all behaved.

Finding, now disclosed: the regime boundary is the median trailing volatility of the first
training prefix (2016-2017, very calm: 0.49% a day), so only 55 of 2,205 OOS returns (2.5%) were
"calm" and the regime family was in effect the IID one while reporting "estimable". The family
now carries the state counts and a warning, also in `report.md` and the command output. The
run id changed with the code change (the identity binds the code), as for any code change.

Not changed, noted: the Student-t family draws continuous returns, so it has none of the 501 flat
(out-of-market) days and longer loss streaks (q95 13 vs 9); its sample kurtosis (5.2) is below the
observed 12.9, as expected for a t with about 4.5 degrees of freedom. `alpha monte-carlo kronos`
ran only with the stand-in model (`--model fake`, 8 paths); the Kronos model files are not on
the Dell, so that family is not proven.

## Checks

- New integration tests: 3 fail on `origin/main`; Monte Carlo unit, integration and oracle tests: 25 passed.
- `uv run python scripts/gate.py check --base origin/main`: passed (see the pull request).

## Review

Codex review through the bridge, one medium finding: the warning claimed a family with a state
under 10% "is close to the IID empirical family", which a share alone does not establish (a rare,
persistent state with extreme returns can still change drawdown and ruin). Fixed: the warning now
says the state's emissions and transitions rest on few observations and asks for a comparison
with the IID family. On the Alpaca run the two families did come out nearly equal (drawdown 95th
0.3566 vs 0.3600), which is an observation, not a rule.
