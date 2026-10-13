# Synthetic investigation development demo

Development controls only; no baseline comparison or general uplift claim.

| Designed case | Accounting | Final received (not graded) | Actions executed |
|---|---|---|---|
| conditional | True | completed | inspect_run, loss_episodes, historical_context, conditional_diagnostic |
| indicator_null | True | completed | inspect_run, loss_episodes, conditional_diagnostic, historical_context |
| accounting_defect | False | completed | inspect_run |

## conditional

The synthetic strategy fell 59.53% from June 29 to September 27, 2020, over 90 intervals, versus a 36.31% benchmark loss—23.22 percentage points worse. It recovered on May 12, 2021. Cash-plus-position accounting passed its synthetic identity check, but execution realism remains unverified. Broad market weakness accompanied the drawdown; leverage, concentration, liquidity exposure or trading costs could explain the additional loss, but the receipts cannot distinguish them. The frozen indicator provides a descriptive lead: mean next-interval returns were −1.0% for indicator 1 (90 observations) and +0.4% for indicator 0 (409), a −1.4 percentage-point difference. This establishes neither causation nor a validated predictive edge. The synthetic liquidity note became available June 30, after the peak, and cannot justify a signal at that peak. Drawdown size alone does not warrant rejection.

Proposed next tests: Obtain dated holdings, leverage, trades, costs and valuation records to attribute the excess loss and check execution realism.; Audit indicator construction and point-in-time availability; map its observations to the drawdown and benchmark returns to assess whether the association reflects market exposure or a single clustered episode.; If those checks support further research, specify a hypothesis and risk limits before testing on new data; do not treat this retrospective panel as confirmation.

## indicator_null

The strategy fell 59.5% from June 29 to September 27, 2020, versus the benchmark’s 36.3% loss—a 23.2 percentage-point gap—and recovered on May 12, 2021. Synthetic accounting identities pass, but this is limited validation. Broad market weakness is consistent with the losses; higher exposure, concentration, trading costs or liquidity sensitivity could explain the additional decline. The synthetic liquidity note suggests a hypothesis, not a demonstrated cause. The frozen indicator’s next-interval means are nearly identical, offering little descriptive separation while leaving tail risk unresolved. These exploratory results justify further attribution, not automatic rejection or deployment.

Proposed next tests: Request dated holdings, exposure, trades and cost data to attribute the drawdown and benchmark gap; check benchmark comparability.; If interval data become available, examine tail losses and exposure within the frozen indicator groups without tuning its parameters.; Assess the loss magnitude and recovery duration against predefined risk limits before deciding whether to retain or revise the strategy.

## accounting_defect

Performance interpretation is blocked: the synthetic accounting check failed, with maximum identity error 10.0 (attempt-1). The drawdown cannot yet be reliably attributed to strategy losses or used to reject the strategy. Accounting distortion, genuine losses, or both remain possible; the receipt does not identify affected rows, error units, or the impact on drawdown.

Proposed next tests: Obtain row-level cash, positions, prices, transactions, and the identity definition; reconcile the discrepancy and repeat the integrity check in a corrected run.; After integrity passes, measure loss episodes and benchmark-relative losses to assess what drove the drawdown.
