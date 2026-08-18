---
paths:
  - "packages/alpha-validation/**"
---
# alpha_validation rules

Verbatim relocation from the pre-v2 CLAUDE.md MODULE MAP (drift-tested against `tests/fixtures/claude_md_v1.md`). The core `CLAUDE.md` DAG paragraph and golden rules still apply here.

QUANT TIER: edits here require a PASS `QuantVerificationReport` (`/verify-quant`) before Stop and an APPROVE `ReviewVerdict` before commit. See also `quant.md`.
### `alpha_validation` (`packages/alpha-validation/src/alpha_validation/`) — engine-agnostic stats primitives + tear sheet. core only (+ numpy/scipy; pandas/quantstats at the tearsheet edge).
| Module | Responsibility | Key public symbols |
|---|---|---|
| `metrics.py` | Pure numpy return/risk metrics | `to_returns`, `sharpe_ratio`, `annualized_volatility`, `cagr`, `max_drawdown`, `FloatArray`/`FloatSeq` |
| `walkforward.py` | Causal purged/embargoed splitter | `walk_forward_splits(n, *, train_size, test_size, embargo, anchored) -> list[Split]` |
| `cpcv.py` | Combinatorial purged cross-validation | `combinatorial_purged_splits(n, *, n_groups, n_test_groups, embargo)`, `CPCVSplit`, `n_cpcv_splits` |
| `bootstrap.py` | Stationary-bootstrap BCa CIs | `stationary_bootstrap_indices`, `block_bootstrap_ci`, `ConfidenceInterval`, `Statistic` |
| `montecarlo.py` | Randomized-price null + fat-tailed generators | `randomized_price_null`, `parametric_price_null`, `student_t_paths`, `garch_paths`, `NullResult`, `StrategyFn` |
| `path_montecarlo.py` | Scenario/path-risk simulation over canonical OOS account returns | `empirical_return_paths`, `regime_switching_return_paths`, `student_t_return_paths`, `summarize_path_family`, `MonteCarloFamilySummaryV1`, `MonteCarloReviewV1` |
| `dsr.py` | Probabilistic + Deflated Sharpe (Bailey–LdP) | `probabilistic_sharpe_ratio`, `deflated_sharpe`, `expected_max_sharpe`, `DeflatedSharpeResult` |
| `overfitting.py` | PBO via CSCV (Bailey et al.) | `probability_of_backtest_overfitting`, `PBOResult` |
| `propfirm.py` | Prop-firm Monte Carlo (return-scaled, multi-phase eval→funded→payout; reuses `stationary_bootstrap_indices`) | `PropFirmRules`, `PropFirmResult`, `simulate_propfirm`, `FIRM_PRESETS` |
| `scenario.py` | Stress/what-if over a return stream (mean-preserving vol scaling + tail shocks; reuses `metrics`) | `scenario_metrics(returns, *, periods_per_year, confidence)`, `ScenarioSummary`, `scale_volatility`, `append_shock` |
| `verdict.py` | A–F grade over the computed gates (pure, threshold-banded) | `VerdictSummary`, `grade_verdict` |
| `reality_check.py` | White's Reality Check + Hansen's SPA | `reality_check`, `spa_test`, `DataSnoopingResult` |
| `tearsheet.py` | Report schema + render (pandas/quantstats edge) | `GauntletReport`, `RunMetadata`, `FoldSummary`, `NullSummary`, `CISummary`, `DSRSummary`, `CPCVSummary`, `build_outcomes`, `report_to_manifest`, `render_tearsheet_html` |
| `barrier.py` · `proportion.py` | Triple-barrier outcome labeling (target-vs-stop race within a horizon) + excursion statistics; proportion intervals (Wilson, Newcombe difference), Benjamini–Hochberg multiplicity, overlap/autocorrelation effective-sample corrections | `BarrierResult`, `BarrierCounts`, `barrier_outcome`, `aggregate_outcomes`, `excursion_quantiles`; `ProportionInterval`, `MultipleTestResult`, `wilson_interval`, `newcombe_diff_interval`, `benjamini_hochberg`, `effective_sample_size`, `overlap_factor`, `autocorrelation_effective_size` |
| `forecast_eval.py` · `forecast_calibration.py` | Forecast-skill primitives in horizon end-return space (sample CRPS, pinball, central coverage vs RW-drift + stationary-bootstrap baselines from the SAME context window) and fold-local convex blending + rolling-origin conformal calibration / frozen `kronos_calibrated` candidate assessment (ADR-0028) | `crps_sample`, `pinball_loss`, `central_coverage`, `rw_drift_end_returns`, `bootstrap_end_returns`, `OriginScore`, `score_origin`, `ForecastEvalSummary`, `summarize_scores`; `ForecastCalibrationContractV1`, `fit_rolling_conformal_blend`, `KronosCalibratedAssessmentV1`, `assess_kronos_calibrated_candidate`, `evaluate_frozen_calibration` |
| `native_tearsheet.py` | Python-authoritative dark-report metrics/series (no frontend calculation) | `NativeTearSheet`, `build_native_tearsheet`; calendar, distribution/Q-Q, rolling, benchmark, exposure/turnover, and trade-stat records |

