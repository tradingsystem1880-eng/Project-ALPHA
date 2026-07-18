// The metric glossary: every statistic the workstation shows, defined once.
// `short` feeds hover tooltips; `long` feeds the Glossary panel. Content is deterministic and
// offline — written for an expert who wants precision, not a textbook.

export interface GlossaryEntry {
  name: string
  short: string
  long: string
}

export const GLOSSARY: Record<string, GlossaryEntry> = {
  sharpe: {
    name: 'Sharpe ratio',
    short: 'Annualized mean excess return per unit of return volatility.',
    long: 'Mean daily return divided by daily return standard deviation, scaled by √periods-per-year. The workstation always quotes OOS (out-of-sample) Sharpe from concatenated walk-forward test windows — in-sample Sharpe is never shown. Rule of thumb on daily data: > 1 is strong, > 1.5 exceptional; anything measured on < 500 observations has wide error bars (see PSR).',
  },
  cagr: {
    name: 'CAGR',
    short: 'Compound annual growth rate of the equity curve.',
    long: 'The constant annual rate that compounds the starting equity into the final equity over the elapsed time. Sensitive to the sample window; always read it against max drawdown and volatility, never alone.',
  },
  annualized_vol: {
    name: 'Annualized volatility',
    short: 'Return standard deviation scaled to a yearly horizon.',
    long: 'Daily return standard deviation × √252. Strategies here are vol-targeted, so realized vol near the target (default 15%) means the sizing layer is doing its job; realized vol far above target signals leverage or gap risk the sizer could not contain.',
  },
  max_drawdown: {
    name: 'Max drawdown',
    short: 'Deepest peak-to-trough equity loss over the sample.',
    long: 'The worst percentage decline from a running equity peak. The verdict risk grade bands it at 10/20/35/50%: beyond 50% is an F — recovering from a 50% loss requires a +100% gain, and most allocators (and prop firms) are gone long before that.',
  },
  total_return: {
    name: 'Total return',
    short: 'Cumulative OOS return over the whole test span.',
    long: 'Product of (1 + r) over every out-of-sample day, minus one. Spans multiple walk-forward folds stitched in time order, so it is the return a single continuously-run account would have seen.',
  },
  value_at_risk: {
    name: 'VaR (95%)',
    short: '95th-percentile one-day loss.',
    long: 'The daily loss exceeded on only 5% of days, read from the empirical OOS return distribution. A VaR of 1% means one day in twenty loses more than 1%. Says nothing about HOW MUCH worse those days get — that is expected shortfall.',
  },
  expected_shortfall: {
    name: 'Expected shortfall (95%)',
    short: 'Average loss on the worst 5% of days.',
    long: 'The mean loss conditional on being beyond the 95% VaR — the honest tail number. ES materially above VaR means the loss tail is heavy: the bad days are not just frequent-adjacent, they are deep.',
  },
  risk_of_ruin: {
    name: 'Risk of ruin',
    short: 'Probability of a 50% peak-to-trough loss, from bootstrapped paths.',
    long: 'The fraction of 1,000 stationary-bootstrap resamples of the OOS daily returns whose equity path ever loses half its peak. Unlike max drawdown (one realized path), this asks how often catastrophe happens across plausible re-orderings of the same return stream.',
  },
  psr: {
    name: 'PSR',
    short: 'Probabilistic Sharpe: P(true Sharpe > 0) given the sample.',
    long: 'Bailey & López de Prado. The probability that the TRUE Sharpe exceeds zero, given the observed Sharpe, sample length, skew, and kurtosis. It answers "is this Sharpe statistically real?" — a 1.0 Sharpe on 60 days can carry a lower PSR than a 0.5 Sharpe on 2,000 days.',
  },
  dsr: {
    name: 'Deflated Sharpe (DSR)',
    short: 'PSR after penalizing for how many strategies were tried.',
    long: 'PSR computed against an elevated benchmark: the Sharpe you would expect the BEST of N random trials to show by luck alone (grows with N and with trial-Sharpe variance). On a single run n_trials = 1 and DSR = PSR; in an optimization sweep the deflation is the whole point — the best of 64 configs must clear the luck-of-64 bar.',
  },
  expected_max_sharpe: {
    name: 'E[max Sharpe]',
    short: 'Sharpe the best of N random trials would show by luck.',
    long: 'The expected maximum Sharpe among N zero-skill strategies, from extreme-value theory. This is the deflation benchmark inside DSR: a sweep\'s best Sharpe below E[max SR] is indistinguishable from selection luck.',
  },
  bca_ci: {
    name: 'BCa bootstrap CI',
    short: 'Bias-corrected block-bootstrap confidence interval.',
    long: 'A stationary block bootstrap (preserving autocorrelation) resamples the OOS returns 2,000 times; BCa correction adjusts the percentile interval for bias and skew. The gate requires the Sharpe interval\'s LOWER bound > 0 — i.e. even the pessimistic edge of the estimate shows positive risk-adjusted return.',
  },
  null_test: {
    name: 'Randomized-price null',
    short: 'Does the strategy beat luck on synthetic no-edge prices?',
    long: 'The headline gate, in two tiers. Tier 1 (returns-level): a fast surrogate of the strategy scored on 1,000 resampled return paths. Tier 2 (full-engine): the REAL engine run on 64 level-continuous synthetic OHLCV paths. The observed stat must beat the 95th percentile of the null in BOTH tiers — if random prices "earn" as much as the strategy, the edge is indistinguishable from luck.',
  },
  p_value: {
    name: 'p-value',
    short: 'P(null ≥ observed): chance luck matches the result.',
    long: 'Computed as (1 + #{null ≥ observed}) / (1 + n_paths) — the add-one keeps it honest at the extremes. Small p means few random paths matched the strategy; p around 0.5 means the strategy performed like the middle of the luck distribution.',
  },
  convention_divergence: {
    name: 'Convention divergence',
    short: 'Tier-1 fidelity check: close-fill vs t+1-open-fill Sharpe gap.',
    long: 'The Tier-1 surrogate fills at the close; the real engine fills at next open. This measures |Sharpe(close-fill) − Sharpe(open-fill)| of the same surrogate weights. When it exceeds the tolerance (default 0.25) AND Tier 2 passed, a Tier-1 fail is demoted to advisory ("flagged low fidelity") — the surrogate\'s crediting bias, not the strategy, likely caused the fail. A Tier-2 fail is never rescued.',
  },
  cpcv: {
    name: 'CPCV',
    short: 'Combinatorial purged CV: OOS Sharpe across many fold combinations.',
    long: 'Bailey et al. Instead of one walk-forward path, the OOS stream is split into groups and every combination of test-groups forms a fold (15 folds at 6-choose-2), with purging and embargo against leakage. A strategy that only works in one specific period shows a wide, sign-flipping fold distribution; the gate wants the MEAN fold Sharpe > 0.',
  },
  pbo: {
    name: 'PBO',
    short: 'Probability the sweep\'s in-sample winner underperforms OOS.',
    long: 'Probability of Backtest Overfitting via CSCV: split the trial-returns matrix into blocks, pick the in-sample best config in each split, and ask how often it falls below the OOS median. PBO near 0.5 means picking the backtest winner is a coin flip out of sample — the sweep selected noise. Gate threshold: < 0.2.',
  },
  reality_check: {
    name: "White's Reality Check",
    short: 'P(best-of-family performance is luck), by bootstrap.',
    long: 'Bootstraps the full trial-returns matrix to ask: what is the chance the BEST of these N configs performs this well when none has real edge? Small p rejects "the family is all noise". Hansen\'s SPA refines it to be less sensitive to deliberately bad configs padding the family.',
  },
  spa: {
    name: "Hansen's SPA",
    short: 'Studentized, less-gameable version of the Reality Check.',
    long: 'Superior Predictive Ability test: same question as the Reality Check (is the best config\'s edge luck given the whole family?), but studentized and robust to including poor strategies in the comparison set. The optim verdict uses SPA as its data-snooping gate.',
  },
  walk_forward: {
    name: 'Walk-forward OOS',
    short: 'Contiguous test windows after a training warmup, stitched in time.',
    long: 'The series is split into rolling train/test windows with an embargo gap; the strategy (fixed params — training windows are warmup only, nothing refits) trades each test window and the test segments concatenate into ONE out-of-sample stream. Every headline metric derives from that stream; in-sample numbers appear nowhere.',
  },
  embargo: {
    name: 'Embargo / purging',
    short: 'Gap between train and test windows against leakage.',
    long: 'A buffer of sessions dropped between a training window and its test window so serially-correlated information (and any lookback overlap) cannot leak across the boundary. CPCV additionally purges observations whose lookback windows straddle a fold edge.',
  },
  stationary_bootstrap: {
    name: 'Stationary bootstrap',
    short: 'Resampling in random-length blocks to keep autocorrelation.',
    long: 'Resamples a return series in geometric-length blocks (mean ~5 days here) instead of single draws, preserving short-range dependence. Used by the CIs, the Tier-1 null, risk-of-ruin, and the prop-firm Monte Carlo.',
  },
  coverage: {
    name: 'Interval coverage',
    short: 'How often the realized value lands inside a forecast band.',
    long: 'For a forecast\'s central X% band, coverage is the fraction of evaluation origins where the realized outcome fell inside. Well-calibrated 80% bands cover ~80% of the time: materially less = overconfident (bands too tight); materially more = underconfident.',
  },
  crps: {
    name: 'CRPS',
    short: 'Distance between a forecast distribution and the realized value.',
    long: 'Continuous Ranked Probability Score — generalizes absolute error to a full predictive distribution (lower is better). Reported as skill vs baselines: skill = 1 − CRPS/CRPS_baseline, so positive skill means beating random-walk-with-drift (or the bootstrap) on distributional accuracy.',
  },
  hit_rate: {
    name: 'Hit rate',
    short: 'Fraction of origins where the forecast called the sign correctly.',
    long: 'Sign agreement between the forecast median end-return and the realized end-return across rolling origins. 50% is a coin; sustained values above ~55% on daily horizons are meaningful.',
  },
  pretrain_overlap: {
    name: 'Pretrain overlap',
    short: 'Forecast window overlaps the model\'s training data — inflated skill.',
    long: 'The Kronos foundation model was pretrained on market data up to its cutoff. Any forecast or evaluation whose window predates the cutoff overlaps data the model may have memorized; results there are flagged and must be read as in-sample. Only post-cutoff evaluation measures real zero-shot skill (ADR-0009).',
  },
  verdict: {
    name: 'Verdict (A–F)',
    short: 'Equal-weight GPA over edge, robustness, risk, and sample grades.',
    long: 'Each dimension grades independently on fixed bands (edge = OOS Sharpe; robustness = count of null/DSR/CPCV/CI checks passed; risk = worse of drawdown and ruin bands; sample = OOS observation count), then the 4.0-scale GPA re-bands into the overall letter. The bands are auditable constants — hover any dimension to see exactly which band the number landed in.',
  },
  pass_probability: {
    name: 'Pass probability',
    short: 'Share of Monte-Carlo paths clearing the prop-firm evaluation.',
    long: 'Fraction of bootstrapped equity paths that reach the profit target without breaching drawdown/daily-loss rules within the horizon. Read together with bust probability (breach during eval OR after funding) and expected payout (mean net dollars across ALL paths including busts and fees).',
  },
}

export function glossaryEntry(key: string): GlossaryEntry | null {
  return GLOSSARY[key] ?? null
}
