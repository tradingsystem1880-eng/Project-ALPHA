# neurotrader888 Technique Provenance

- **Reviewed:** 2026-09-12
- **Scope:** every public repository of GitHub user `neurotrader888` and how each technique is
  carried into Project ALPHA under the port plan
  `docs/superpowers/plans/2026-09-12-neurotrader888-port.md`
- **Status:** engineering inventory; not legal advice

## Licence and permission

Thirteen of the fourteen repositories carry the MIT licence (copyright neurotrader888). The owner
additionally holds the author's personal approval, recorded on 2026-09-12, for full use of the
licensed repositories inside this private, single-owner project. `IntramarketDifference` carries no
licence file and is **not covered** by either grant: its technique (CMMA, close minus moving average
normalised by ATR) is re-implemented from the published formula and Masters (2020) only, with no
upstream code, fixtures, or data copied.

ALPHA never vendors these scripts. Each technique is ported into the layer the architecture DAG
assigns, rewritten for numpy/Polars, `mypy --strict`, fail-loud errors, and knowable-at timing, and
each ported function carries a docstring line
`Provenance: github.com/neurotrader888/<repo>/<file>@<sha> (MIT); adapted: <what changed and why>`.
Upstream BTCUSDT CSV fixtures are not copied; parity fixtures are generated once from the pinned
upstream code in a scratch environment and stored as small JSON arrays with named tolerances under
`tests/fixtures/neurotrader/`.

## Mapping (upstream file → ALPHA module)

| Repo @ head | Upstream file | ALPHA destination | Deviations (stream A delivered 2026-09-12) |
|---|---|---|---|
| TechnicalAnalysisAutomation @ da99c20 | `rolling_window.py` | **not ported** — `alpha_patterns.swings.find_swings` + `swings_known_by` | upstream tie rule is strict on both sides; ALPHA is strict-left/non-strict-right; equivalence test pins the rest |
| | `directional_change.py` | `alpha_patterns/directional_change.py` | extremes carry `confirmed_index`; DataFrame wrapper and plotting dropped; exact parity |
| | `perceptually_important.py` | `alpha_patterns/pips.py` | adds `pip_windows` (z-scored, `end_index`); a fully collinear window still selects a bar (upstream inserts index -1); exact parity otherwise |
| | `head_shoulders.py` | **not ported** — `alpha_patterns.head_shoulders.detect_head_shoulders`; `HSEvent.neckline_r2` added | `HSEvent.pattern_r2` added (R² of the LS→N1→head→N2→RS close polyline; upstream `compute_pattern_r2` runs start→break); forward-return helper not ported |
| | `flags_pennants.py` | `alpha_patterns/flags.py` | upstream rolling-window top/bottom test kept as a private helper for exact confirmation timing; exact parity for both variants |
| | `harmonic_patterns.py` | `alpha_patterns/harmonics.py` | `confirmed_index == d`; a zero-height leg is skipped instead of raising from `log`; exact parity on 93 patterns |
| | `retracement_ratios.py` | `alpha_research/retracements.py` | scipy KDE, peak list returned instead of a plot |
| | `mp_support_resist.py` | `alpha_patterns/market_profile.py` + `_kde.py` | numpy weighted KDE and prominence peaks with SciPy's conventions (differential-tested); causal simple-mean `log_atr` instead of pandas_ta Wilder ATR; as upstream, the signal at i tests against the levels of bar i; exact parity with the ATR supplied |
| | `trendline_automation.py` | `alpha_patterns/trendline_fit.py` | pure numpy, unchanged algorithm; exact parity |
| | `pip_pattern_miner.py`, `wf_pip_miner.py` | `alpha_research/pip_miner.py` | numpy k-means++/silhouette replaces pyclustering; labels crossing `train_end` rejected; explicit seed |
| TrendLineAutomation @ 63b1429 | `trendline_automation.py` | `alpha_patterns/trendline_fit.py` | same module as above |
| TrendlineBreakoutMetaLabel @ 874d938 | `trendline_breakout.py`, `trendline_break_dataset.py` | `alpha_patterns/trendline_fit.py` (`trendline_breakout`, `breakout_features`) | breakout series exact parity; `breakout_features` uses causal simple-mean log ATR and `directional_index` ADX instead of pandas_ta, and never returns an open trade |
| mcpt @ 2c0d70c | `bar_permute.py` | `alpha_validation/bar_permutation.py` | `numpy.random.Generator` instead of global seed |
| | `insample_*_mcpt.py`, `walkforward_donchian_mcpt.py` | `alpha_validation/mcpt.py`, `alpha_cli/_mcpt.py`, gauntlet tier | p-value `(1+c)/(1+N)` (Davison & Hinkley) instead of `c/N` |
| | `donchian.py`, `moving_average.py` | **not ported** — `alpha_strategies` `breakout` / `ma_crossover` | optimisation via `alpha optim grid` |
| | `tree_strat.py` | **excluded** | author-disowned; sklearn not a root dependency |
| market-structure @ 36a7d89 | `local_extreme.py`, `atr_directional_change.py`, `hierarchical_extremes.py` | `alpha_patterns/market_structure.py` | frozen `LocalExtreme` keyed by bar index; `DataError` instead of `assert`; `update` returns the confirmed extreme; `get_level_*` return `None`; exact parity at every level |
| VolatilityHawkes @ 51c8557 | `hawkes.py` | `alpha_patterns/hawkes.py` | bar-0 negative-index artefact replaced by skipping bar 0; quantile windows containing NaN stay NaN; trade extraction helper not ported; exact parity |
| VSAIndicator @ a95bf30 | `vsa.py` | `alpha_patterns/vsa.py` | generic `rolling_ols_residual` extracted (reused by the TVL feature); causal simple-mean `atr` and `rolling_median` instead of pandas_ta/pandas; the gate uses Pearson r as upstream (not r²); exact parity on stored inputs |
| RSI-PCA @ f3b9735 | `rsi_behavior.py`, `pca.py` | `alpha_patterns.indicators.rsi_matrix` (delivered), `alpha_research/rolling_pca.py` (stream B) | feature block computed with ALPHA's `rsi`; rolling fit only; eigenvector sign fixed by largest loading |
| IntramarketDifference (no licence) | — | `alpha_patterns/cmma.py` | re-implemented from Masters' formula with a NaN warm-up; threshold-entry / zero-cross-exit rule stated in the module; no upstream code or fixture |
| TradeDependenceRunsTest @ 5f63804 | `runs_test.py`, `runs_indicator.py` | `alpha_patterns/runs.py`, `alpha_validation/trade_dependence.py` | `runs_z` is NaN when all signs agree (upstream divides by zero); zeros break runs as upstream; exact parity |
| TimeSeriesReversibility @ 3d76b9e | `reversibility.py` | `alpha_patterns/reversibility.py` | HVG from `alpha_patterns.visibility` (the author's `ts_to_vg` rule) instead of ts2vg; KL in numpy; embedding dimension parameterised; default-argsort tie order kept; exact parity on sine / logistic / price windows |
| TimeSeriesVisibilityGraphs @ d646293 | `ts_to_vg.py`, `network_indicators.py` | `alpha_patterns/visibility.py` | boolean adjacency; BFS average shortest path (networkx convention) instead of networkx/ts2vg; `lookback ≤ 500`; exact parity incl. the author's worked example |
| PermutationEntropy @ 890da37 | `perm_entropy.py` | `alpha_patterns/entropy.py` | unchanged algorithm; NaN head; exact parity for two embeddings |
| TVLIndicator @ 00745d0 | `tvl_indicator.py` | `alpha_data/crypto/providers/defillama.py`, `crypto/features.py::defi_tvl_residual` (ADR-0036) | governed family with receipts and `available_at`; endpoint shape UNVERIFIED in the build sandbox |

## Primary sources cited by the ported statistics

Arthur & Vassilvitskii 2007 (k-means++); Rousseeuw 1987 (silhouette); Martin & McCann 1989 (Ulcer
index / Martin ratio); Scott 1992 (KDE bandwidth); Chung, Fu, Luk & Ng 2001 (perceptually important
points); Bandt & Pompe 2002 (permutation entropy); Zanin et al. 2018 and Yang & Shang 2018
(reversibility); Lacasa et al. 2008 (visibility graphs); Wald & Wolfowitz 1940 (runs test); Masters
2018 (permutation tests for trading systems) and Masters 2020 (CMMA); Davison & Hinkley 1997
(permutation p-value convention); Jolliffe 2002 (PCA).

## Review on change

Re-verify the upstream head SHA before regenerating any parity fixture; a changed upstream file is
a new provenance row, never a silent fixture update. Reopen this document if the owner's scope ever
changes from private local use (see the dependency/license matrix).
