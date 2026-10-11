# Synthetic investigation efficiency report

Nine frozen development trials; one run per mode and case. These are designed synthetic controls, not trading evidence or a general reliability estimate.

| Mode | Finals | Model calls | Measurements | Input tokens | Cached subset | Output tokens | Wall seconds |
|---|---:|---:|---:|---:|---:|---:|---:|
| legacy | 3/3 | 12 | 9 | 127,832 | 28,032 | 2,011 | 170.7 |
| prechecked | 3/3 | 7 | 7 | 74,126 | 18,688 | 1,462 | 106.0 |
| fixed | 3/3 | 3 | 9 | 32,425 | 18,688 | 911 | 61.3 |

Prechecked used 42.0% fewer total input tokens and 41.7% fewer model calls than legacy. Fixed-evidence synthesis used 74.6% fewer total input tokens and 75.0% fewer model calls. Cached input is already included in input tokens. Uncached input totals were 99,800 / 55,438 / 13,737 respectively; these are not dollar costs.

Wall time includes provider setup, worker measurements and model calls; excludes shared calibration/preflight. Nine calibration measurements are additional to the 25 trial measurements. All calls have usage receipts. Mode acquisition order rotates across cases; cache reuse and one sample per cell limit timing/cost generalization.

## What the comparison tests

Legacy asks the model to request inspection. Prechecked executes and debits inspection before reasoning, uses lossless compact JSON, and leaves optional work to the model. Fixed collects all four registered measurements on valid data, then requests one synthesis. It stops collection after failed integrity. All modes share the same question, model/effort, exported hashes, tools and isolation. Fixed is a synthetic all-evidence advisory comparator, not a benchmark of production `diagnostic suggest`.

Automatic integrity enforcement and fixed collection are controller behavior, not model initiative. Both prechecked valid-data trials explicitly skipped historical_context after judging attribution and timing evidence more valuable; they did not claim to have inspected omitted notes.

Independent [evidence review](independent-review.md) recomputed the measurements and checked all 22 usage records against raw events. It found no critical factual, causal or integrity regression in the nine outputs. This is qualitative review, not a general reliability score.

## Decision and next experiment

The prechecked version meets the preregistered 15% input-token target on this panel. However, the much simpler fixed-evidence baseline is cheaper and covers every available measurement. This narrow task does not justify a larger agent team. Keep existing defaults unchanged and retain both experimental policies for comparison.

Next: freeze a richer development panel where measurement choice matters—costly or unavailable optional data, relevant versus misleading dated context, hindsight-only regime signals, and provider failures. Define case-specific required evidence and acceptable skips before acquisition; repeat paired trials and review failed as well as successful answers. Real-data use still requires independently reviewed export and execution reconciliation. Runtime or specialist changes should be separate ablations.

## Trial results

| Case | Mode | Calls | Measurements | Input tokens | Status |
|---|---|---:|---:|---:|---|
| conditional | legacy | 5 | 4 | 53,609 | completed |
| conditional | prechecked | 3 | 3 | 31,890 | completed |
| conditional | fixed | 1 | 4 | 11,026 | completed |
| indicator_null | prechecked | 3 | 3 | 31,873 | completed |
| indicator_null | fixed | 1 | 4 | 11,039 | completed |
| indicator_null | legacy | 5 | 4 | 53,612 | completed |
| accounting_defect | fixed | 1 | 1 | 10,360 | completed |
| accounting_defect | legacy | 2 | 1 | 20,611 | completed |
| accounting_defect | prechecked | 1 | 1 | 10,363 | completed |

## Recorded answers

### conditional / legacy

The synthetic strategy fell 59.5% from June 29 to September 27, 2020, over 90 intervals, versus a 36.3% benchmark loss—a 23.2 percentage-point gap—and recovered on May 12, 2021 (attempt-2). Cash-plus-position accounting passed, but only the synthetic identity check; broader integrity remains unverified (attempt-1).

Broad market exposure could explain part of the loss. Greater exposure, concentrated holdings, or liquidity and trading costs could explain the additional damage; the receipts cannot distinguish these. Indicator-1 intervals averaged −1.0% next-interval returns (90 observations), versus +0.4% for indicator 0 (409). This association could reflect temporal clustering or market exposure; it does not validate a trading rule (attempt-3). A synthetic note reports changed liquidity conditions, but supplies no causal proof and became available June 30, after the June 29 peak (attempt-4).

The drawdown merits investigation, not automatic rejection. These retrospective, advisory measurements establish neither statistical significance nor deployment readiness.

Decision rationale: All four available actions are exhausted. Attribution and indicator timing are the useful next investigations; parameter search or an indicator-based rule is unsupported by these receipts.

Suggested tests: If further data become available, prioritize dated holdings, exposure, leverage, turnover and execution costs to attribute the benchmark loss gap.; Check indicator availability at each decision time and its overlap with the loss episode; compare conditional benchmark returns to assess whether the association merely reflects market conditions.; Before changing the strategy, define acceptable drawdown and recovery limits and evaluate any fixed proposal on genuinely untouched data.

### conditional / prechecked

The synthetic strategy lost 59.5% over 90 intervals from June 29 to September 27, 2020, versus the benchmark’s 36.3% loss—a 23.2 percentage-point shortfall—and recovered by May 12, 2021. Cash-plus-position accounting passes, but only within the synthetic identity check (attempt-1, attempt-2). Broad market weakness plausibly contributed; exposure differences, costs, or condition-dependent weakness could explain the additional loss. Across the panel, mean next-interval returns were −1.0% for indicator 1 (90 observations) and +0.4% for indicator 0 (409 observations). This association warrants investigation, but matching observation counts do not establish overlap with the drawdown (attempt-3). These exploratory results establish neither cause nor a validated edge. The loss alone does not justify rejection or deployment.

Decision rationale: Skip historical_context: dated synthetic notes would offer narrative context but would not resolve the central missing evidence—episode alignment, exposure and cost attribution, and uncertainty. The supplied measurements support a bounded diagnosis without another action.

Suggested tests: If additional receipts become available, align indicator states with the drawdown and compare strategy and benchmark returns within each state.; Obtain exposure, leverage, holdings, turnover and cost attribution to distinguish market sensitivity from strategy-specific losses.; Check indicator availability at decision time and dependence among observations; any rule change would need separate prospective evaluation.

### conditional / fixed

Synthetic accounting identities passed with zero error, permitting limited interpretation—not validation of execution or data quality [attempt-1]. The strategy fell 59.53% over 90 intervals from June 29 to September 27, 2020, versus the benchmark’s 36.31% loss: 23.22 percentage points worse. It recovered on May 12, 2021 [attempt-2]. Broad market losses plausibly contributed; leverage, concentration, trading costs or strategy-specific exposure could explain the additional loss, but these receipts cannot distinguish them. The synthetic liquidity note supplies a hypothesis, not causal evidence; it became available June 30, after the peak [attempt-3]. The frozen indicator’s flagged intervals averaged −1.0% next-interval returns (90 observations), versus +0.4% otherwise (409), a −1.4 percentage-point difference. This is descriptive association without uncertainty estimates or validated edge [attempt-4]. The drawdown alone does not justify rejection or an indicator-based change.

Decision rationale: All four permitted actions are complete. Further collection and fitting are unavailable; skip parameter tuning and deployment recommendations because the receipts support only synthetic retrospective diagnosis.

Suggested tests: If position, exposure and cost records become available, attribute the peak-to-trough loss to market exposure, leverage, concentration and execution costs.; Verify indicator availability at each decision time and its overlap with the loss episode; examine benchmark-relative conditional returns and dependence-aware uncertainty to distinguish broad stress from strategy-specific weakness.; Before changing the strategy, freeze the proposed rule and evaluate it on genuinely untouched data with realistic costs; assess the drawdown against a predefined risk tolerance.

### indicator_null / prechecked

The synthetic strategy fell 59.5% from June 29 to September 27, 2020, versus a 36.3% benchmark loss—a 23.2 percentage-point shortfall—and recovered its prior peak on May 12, 2021. Broad market weakness is consistent with part of the loss; leverage, portfolio composition, trading timing, and costs remain possible explanations for the additional decline. The drawdown alone does not justify rejection. Synthetic accounting identities passed, but that check does not validate the strategy or its inputs. The frozen indicator barely separates average next-interval returns: 0.1480% versus 0.1470%. This provides little descriptive support for an indicator-based filter, while leaving differences in tail losses and exposure unresolved. All findings are retrospective and exploratory.

Decision rationale: Stop here and skip historical_context: dated synthetic notes could suggest narratives, but cannot replace the missing exposure and loss-attribution measurements. No causal claim, statistical significance, validated edge, or deployment recommendation is supported.

Suggested tests: Obtain dated holdings, leverage, trades, costs, and benchmark construction to attribute the drawdown and assess whether the benchmark reflects comparable exposure.; Examine loss tails and drawdown-period exposure by the frozen indicator; similar full-panel means can conceal concentrated losses. Any resulting rule would need separate prospective evaluation.

### indicator_null / fixed

The synthetic strategy lost 59.53% over 90 intervals from 2020-06-29 to 2020-09-27, versus a benchmark loss of 36.31%—23.22 percentage points worse—and recovered on 2021-05-12 (attempt-2). Cash-plus-position identities passed, but that check establishes only synthetic accounting consistency (attempt-1). Broad market weakness plausibly contributed; exposure, leverage, concentration, trading costs or strategy-specific losses could explain the additional decline, but these receipts cannot distinguish them. The synthetic liquidity note is a hypothesis, not causal evidence, and was available only after the peak (attempt-3). The frozen indicator barely separates average next-interval returns: 0.1480% versus 0.1470%, with no uncertainty estimate or tail-loss comparison; it supplies no validated basis for a risk filter (attempt-4). The drawdown warrants investigation, not automatic rejection. All findings are exploratory and advisory.

Decision rationale: All four permitted actions are complete. Skip indicator tuning and causal conclusions: the supplied evidence lacks loss attribution, uncertainty estimates and independent confirmation.

Suggested tests: If further receipts become available, attribute episode losses using dated positions, leverage, exposures, trades, financing and execution costs, with a comparable benchmark.; Examine return dispersion, tail losses and indicator timing around the episode; nearly equal conditional means can conceal differences in downside risk.; Assess the drawdown and recovery against predefined risk limits before proposing changes; evaluate any later change on genuinely untouched data.

### indicator_null / legacy

The synthetic strategy fell 59.53% from June 29 to September 27, 2020, across 90 intervals, versus a 36.31% benchmark loss—23.22 percentage points worse—and recovered its peak on May 12, 2021 [attempt-2]. Synthetic accounting identities passed with zero error, permitting limited interpretation; this does not validate execution or data quality more broadly [attempt-1]. Shared market weakness is plausible, while greater exposure, concentration, trading costs or strategy-specific losses could explain the additional decline. The synthetic liquidity note supplies context, not causal proof [attempt-4]. The frozen indicator barely separated average next-interval returns: 0.1480% versus 0.1470%, with 250 and 249 observations. These means cannot rule out differences in tail losses or loss clustering [attempt-3]. The drawdown warrants investigation, not automatic rejection; these retrospective measurements establish neither significance nor a validated edge.

Decision rationale: All four available actions are exhausted. Exposure, execution-cost attribution and conditional tail behavior remain missing, so neither a causal diagnosis nor an indicator-based strategy change is justified. Further parameter search or deployment is unsupported.

Suggested tests: If additional receipts become available, attribute peak-to-trough losses to positions, exposure/leverage, turnover and costs; compare against a benchmark matched for exposure.; Examine downside tails and loss clustering by the existing frozen indicator, including its state during the drawdown, without tuning thresholds.

### accounting_defect / fixed

Performance interpretation is blocked: the synthetic accounting integrity check failed, with a maximum identity error of 10.0 (receipt attempt-1). The reported drawdown cannot yet support accepting or rejecting the strategy.

Decision rationale: An accounting defect could distort the reported loss; genuine economic losses could also coexist with it. The receipt provides no failing rows, error units, transaction records, or valuation details, so the defect's source and effect on drawdown remain unknown. Skip loss, historical, and conditional diagnostics until integrity is restored; they cannot resolve this prerequisite failure.

Suggested tests: Locate the rows that violate the cash-plus-position accounting identity and reconcile them against the underlying synthetic records.; After correcting and rechecking accounting, measure loss episodes and benchmark returns to distinguish broad market losses from strategy-specific underperformance.

### accounting_defect / legacy

The accounting check failed: the maximum synthetic cash-plus-position identity error was 10.0. This blocks performance interpretation, so the reported drawdown cannot yet support rejecting or endorsing the strategy. The receipt does not establish whether genuine trading losses, accounting errors, or both contributed.

Decision rationale: Skip the remaining diagnostics for now: loss comparisons, historical narratives, and conditional returns cannot resolve the integrity defect. Even after repair, this synthetic retrospective analysis would remain exploratory.

Suggested tests: Locate the failing rows and reconcile cash, positions, valuation prices, and transaction records; these details are missing from the supplied receipt.; Correct the discrepancy and rerun the identity check before measuring loss episodes and benchmark-relative performance.

### accounting_defect / prechecked

The accounting check failed: synthetic cash-plus-position identity error reached 10.0. This blocks interpretation of the reported drawdown; it does not establish that the strategy should be rejected.

Decision rationale: The receipt cannot distinguish genuine market losses from accounting distortion, or a combination. Row-level discrepancies, transaction records, and the error's scale relative to equity are missing. Skip further performance and contextual diagnostics until integrity is restored; they would not resolve this blocker.

Suggested tests: Locate the rows with identity failures and reconcile cash, positions, valuation marks, and transaction records.; After correcting and revalidating accounting, measure loss episodes and compare them with the benchmark.
