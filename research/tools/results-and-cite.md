---
owner: research pipeline
sources:
  - apps/alpha-cli/src/alpha_cli/results_cmds.py
  - apps/alpha-cli/src/alpha_cli/spine/facts.py
verified: 4487a967b258939d
---
# Results and cite
**Reach for it when** quoting a run. **Commands** `alpha results show <run_id>`, `cite <run_id> <metric>`, `compare <a> <b>`, `check <file>`.
- `tradable_total_return`, `tradable_cagr`, `tradable_sharpe`, `tradable_max_drawdown`, `tradable_trades`, `tradable_benchmark_total_return`,
  `tradable_benchmark_cagr`, `tradable_benchmark_sharpe`, `tradable_benchmark_max_drawdown`, `scored_total_return`, `scored_cagr`, `scored_sharpe`,
  `scored_max_drawdown`, `scored_trades`, `scored_benchmark_total_return`, `scored_benchmark_cagr`, `scored_benchmark_sharpe`, `scored_benchmark_max_drawdown`,
  `data_period`, `traded_period`, `verdict`, `evidence`, `oos_sharpe`, `dsr`, `psr`, `full_sample_total_return`, `full_sample_cagr`, `full_sample_sharpe`,
  `full_sample_max_drawdown`, `benchmark_total_return`, `benchmark_cagr`, `benchmark_sharpe`, `benchmark_max_drawdown`, `resized_entries`, `trades`, `exposure`,
  `top_1_profit_share`, `top_3_profit_share`, `delay_base_sharpe`, `delayed_sharpe`, `total_trials`, `family_trials`, `trial_dsr`, `variants_evaluated`,
  `inverted_sharpe`, `inverted_sharpe_se`, `inverted_total_return`, `inverted_trades`, `inverted_label`, `wfe`, `wfe_fold_count`, `price_noise_median_sharpe`,
  `price_noise_p05_sharpe`, `price_noise_p95_sharpe`, `price_noise_sign_flip_share`, `price_noise_median_trades`, `robustness.start_end_dates.total_return_min`,
  `robustness.start_end_dates.total_return_max`, `robustness.start_end_dates.cagr_min`, `robustness.start_end_dates.cagr_max`,
  `robustness.start_end_dates.sharpe_min`, `robustness.start_end_dates.sharpe_max`, `robustness.start_end_dates.max_drawdown_min`,
  `robustness.start_end_dates.max_drawdown_max`, `robustness.start_end_dates.positive_share`, `robustness.start_end_dates.beat_hold_share`,
  `trades.dependence.runs`, `trades.dependence.expected`, `trades.dependence.z`, `trades.dependence.p_value`, `market.changepoints.count` (`changepoint_count`),
  `setup_trades`, `setup_trade_mean_net_return`, `setup_trade_hit_rate`, `setup_trade_mean_bars_held`, `setup_trade_excess_over_drift`,
  `setup_trade_random_date_p`, `setup_trade_mean_r`, `market.vol_regimes.turbulent_share_of_time` (`regime_turbulent_share_of_time`),
  `market.vol_regimes.turbulent_share_of_return` (`regime_turbulent_share_of_return`), `trades.side_contribution.sides`, `trades.side_contribution.long_count`,
  `trades.side_contribution.long_profit_share`, `trades.side_contribution.long_win_rate`, `trades.side_contribution.long_average_pnl`,
  `trades.side_contribution.short_count`, `trades.side_contribution.short_profit_share`, `trades.side_contribution.short_win_rate`,
  `trades.side_contribution.short_average_pnl`, `resampling.student_t_paths.low`, `resampling.student_t_paths.median`, `resampling.student_t_paths.high`,
  `resampling.student_t_paths.drop_q95`, `trades.concentration.without_best_1`, `trades.concentration.without_best_3`, `trades.concentration.without_best_5`,
  `trades.concentration.top_decile_share`, `market.attribution.beta` (`market_beta`), `market.attribution.alpha_annual` (`market_alpha_annual`),
  `market.attribution.alpha_p` (`market_alpha_p`), `market.attribution.r_squared` (`market_r_squared`), `overfit.deflated_sharpe.dsr`,
  `overfit.deflated_sharpe.trials`, `overfit.deflated_sharpe.benchmark`, `resampling.return_interval.point`, `resampling.return_interval.lower`,
  `resampling.return_interval.upper`, `costs.break_even.zero_multiple`, `costs.break_even.hold_multiple`, `costs.break_even.cost_share`,
  `costs.break_even.sentence`, `costs.break_even.result_after_borrow`, `costs.break_even.borrow_charge`, `costs.break_even.borrow_note`,
  `resampling.drawdown_distribution.observed`, `resampling.drawdown_distribution.median`, `resampling.drawdown_distribution.q95`,
  `performance.downside_ratios.sortino`, `performance.downside_ratios.calmar`, `performance.downside_ratios.omega`, `performance.downside_ratios.tail_ratio`,
  `performance.downside_ratios.sharpe`, `setup_occurrences`, `setup_mean_net_return`, `setup_median_net_return`, `setup_hit_rate`, `setup_excess_over_drift`,
  `setup_random_date_p`, `resampling.block_bootstrap_paths.low`, `resampling.block_bootstrap_paths.median`, `resampling.block_bootstrap_paths.high`,
  `resampling.block_bootstrap_paths.drop_q95`, `resampling.sharpe_interval.point`, `resampling.sharpe_interval.lower`, `resampling.sharpe_interval.upper`,
  `context.published_factors.explained_share`, `context.published_factors.sentence`. **What it cannot tell you** `cite` never computes (a gap is `null` +
  reason). **Next** No row: say "not tested"; offer a [test](rule-test.md).
