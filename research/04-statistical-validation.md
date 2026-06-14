# Project ALPHA — Statistical Validation & Risk Engine

**Module:** 04 — Statistical Validation & Risk Engine
**Scope:** Heavy-tailed validation of backtested strategies; distinguishing genuine edge from overfitting/luck.
**Constraints:** $0 budget, open-source Python only, institutional-grade, mathematically correct.
**Date:** 2026-06-14

---

## 0. Executive Orientation

This document does two jobs:

1. **Specifies** the correct math + Python for the three Monte Carlo methods in the original blueprint (Part A), the best-practice validation methods the blueprint **missed** (Part B), and the sizing/vol math (Part C), the library survey (Part D).
2. **Vets** the blueprint's math, with a hard, quantitative verdict on the prop-firm "positive EV from sizing" claim (Part E).

**Notation conventions used throughout:**
- $r_t$ = per-period return (decimal). $\mu, \sigma$ = per-period mean and standard deviation of returns unless annualized is stated.
- $\widehat{SR}$ = sample (non-annualized) Sharpe ratio $= \hat\mu/\hat\sigma$.
- $\Phi(\cdot)$ = standard normal CDF, $\Phi^{-1}(\cdot)$ = its inverse (quantile).
- $T$ or $n$ = number of return observations.
- $\gamma_3$ = skewness, $\gamma_4$ = (non-excess) kurtosis (normal = 3).

**A word on rigor.** Where a result is textbook-established (gambler's ruin, GARCH likelihood, Kelly), I say so. Where a result is a *model-dependent approximation* that practitioners contest (e.g., "number of independent trials" in the Deflated Sharpe Ratio, GBM as a model of an equity curve), I flag it explicitly. The single most important meta-point: **every method below is only as good as its independence/stationarity assumptions, and financial returns violate them.** Treat all p-values as decision aids, not truth.

---

# PART A — The Three Monte Carlo Methods (Correct Formulation)

## A.1 Reshuffling / Bootstrap Monte Carlo (trade-return resampling)

### Purpose
Build empirical distributions of path-dependent statistics — **maximum drawdown**, time-to-recovery, terminal wealth, "sequence-of-returns" risk — that have **no closed form** and that a single historical ordering cannot reveal. The single realized equity curve is one draw from a distribution; resampling exposes the rest.

### Two distinct resampling schemes — DO NOT conflate them
1. **Permutation (shuffle without replacement):** reorder the *same* set of trade returns. This holds the multiset of returns fixed and **isolates sequence risk** — i.e., "how bad could the drawdown have been if the same trades arrived in a different order?" Terminal return is *identical* across all permutations (for additive log returns), so this is **only** for path statistics (max DD, ulcer index, longest underwater period), not for distribution-of-CAGR questions.
2. **Bootstrap (sample with replacement):** draw $N$ trades with replacement from the realized set. This perturbs *both* the sequence and the composition, giving sampling distributions for CAGR, Sharpe, and max DD. This is the one to use for confidence intervals (see B.5).

### Correct formulation
Let realized per-trade (or per-bar) returns be $\{r_1,\dots,r_N\}$.

**Drawdown of a path.** For a return path producing equity $E_t = E_0\prod_{i\le t}(1+r_i)$, running peak $P_t=\max_{s\le t}E_s$, drawdown $D_t = E_t/P_t - 1$, and **maximum drawdown** $\text{MDD}=\min_t D_t$.

For each Monte Carlo replication $b=1,\dots,B$:
- Permutation: draw a random permutation $\pi^{(b)}$, form path $r_{\pi^{(b)}(1)},\dots,r_{\pi^{(b)}(N)}$.
- Bootstrap: draw $r^{(b)}_i \sim \text{Uniform}(\{r_1,\dots,r_N\})$ with replacement, $i=1,\dots,N$.

Compute the statistic $\theta^{(b)}$ (e.g. MDD). The empirical distribution $\{\theta^{(b)}\}_{b=1}^B$ yields percentiles, e.g. the 95th-percentile drawdown, $P(\text{MDD} < -20\%)$, etc.

### CRITICAL pitfall — IID resampling destroys autocorrelation
Plain bootstrap/permutation assumes trade returns are **IID**. Real strategy returns exhibit **volatility clustering and serial correlation**, especially for:
- trend-following (returns are positively autocorrelated — momentum),
- anything sampled at fixed time bars (daily/hourly) rather than per-trade,
- overlapping positions.

IID resampling **systematically understates tail risk** (real drawdowns cluster). **Fix: use the block bootstrap.**

- **Stationary bootstrap (Politis & Romano 1994):** resample blocks of random geometric length (mean block length $\approx 1/p$). Preserves short-range dependence and yields a stationary resampled series. This is the bootstrap underlying White's Reality Check (B.4).
- **Circular block bootstrap (Politis & Romano 1992):** fixed block length $L$, wraps around the end.

Library: [`arch.bootstrap`](https://arch.readthedocs.io/en/latest/bootstrap/bootstrap.html) provides `IIDBootstrap`, `StationaryBootstrap`, `CircularBlockBootstrap`, `MovingBlockBootstrap` — all with a uniform `.apply()` / `.conf_int()` API. **This is the single most important library for Part A and B.5.**

### Python sketch
```python
import numpy as np
from arch.bootstrap import StationaryBootstrap, IIDBootstrap

def max_drawdown(returns):
    eq = np.cumprod(1.0 + returns)
    peak = np.maximum.accumulate(eq)
    return np.min(eq / peak - 1.0)

# Sequence risk via PERMUTATION (composition fixed)
def permutation_mdd(returns, B=10000, rng=None):
    rng = rng or np.random.default_rng(42)
    return np.array([max_drawdown(rng.permutation(returns)) for _ in range(B)])

# Distribution of MDD/CAGR via STATIONARY block bootstrap (preserves autocorr)
def bootstrap_stat(returns, stat_fn, block=5, reps=10000):
    bs = StationaryBootstrap(block, returns)
    return np.array([stat_fn(d[0][0]) for d in bs.bootstrap(reps)])

mdd_dist = bootstrap_stat(returns, max_drawdown, block=5)
print(np.percentile(mdd_dist, [50, 95, 99]))   # median / 95th / 99th pct drawdown
```

**Other pitfalls:** (i) choose block length to match observed autocorrelation decay (e.g. via `arch`'s `optimal_block_length`); (ii) per-trade resampling ignores that position *sizes* vary — resample *returns on equity*, not raw P&L, or you mix scales; (iii) report the *whole distribution*, not just the mean — the point is the tail.

---

## A.2 Regime-Switching Monte Carlo (Markov transition matrix)

### Purpose
IID/block bootstrap cannot generate **regime persistence** of the kind markets actually show (long trending stretches punctuated by mean-reverting chop). A Markov-switching simulator produces synthetic return paths whose *statistical regime* evolves, giving more realistic stress paths and drawdown tails.

### Correct formulation (Hamilton-style Markov-switching model)
Let $S_t \in \{1,\dots,K\}$ be a hidden regime following a first-order Markov chain with **transition matrix** $P$, $P_{ij}=\Pr(S_{t+1}=j\mid S_t=i)$, rows summing to 1. Each regime has its own return law, e.g. Gaussian (or Student-t, see A.3):
$$
r_t \mid S_t=i \;\sim\; \mathcal{N}(\mu_i,\sigma_i^2).
$$
For a 2-state trend/mean-revert model: state 1 = "trend" (e.g. higher $\mu$, moderate $\sigma$, positive autocorrelation), state 2 = "mean-revert/chop" (e.g. $\mu\approx0$, higher $\sigma$). The **expected regime duration** is $1/(1-P_{ii})$ periods — a direct, interpretable knob.

**Stationary distribution** $\pi$ (long-run time in each regime) solves $\pi P = \pi$, $\sum_i\pi_i=1$ — the left eigenvector of $P$ for eigenvalue 1.

**Simulation loop** for path length $T$:
1. Draw $S_0\sim\pi$ (or a chosen start state).
2. For $t=1..T$: draw $S_t$ from row $P_{S_{t-1},\cdot}$; draw $r_t$ from regime $S_t$'s distribution.
3. Form equity path; compute statistics. Repeat $B$ times.

### Estimating the model from data (two routes)
- **Known/labeled regimes:** if you label each historical bar (e.g. by a trend filter), $\hat P_{ij} = n_{ij}/\sum_k n_{ik}$ (count of $i\to j$ transitions over count of departures from $i$) — the MLE for a Markov chain.
- **Hidden regimes (preferred):** fit a **Markov-switching model by EM / maximum likelihood**. Use [`statsmodels.tsa.regime_switching.MarkovRegression`](https://www.statsmodels.org/stable/generated/statsmodels.tsa.regime_switching.markov_regression.MarkovRegression.html) (switching mean/variance) or `MarkovAutoregression` (adds switching AR dynamics — good for trend vs mean-revert). For Gaussian-mixture-style hidden states you can also use `hmmlearn` (`GaussianHMM`), but `statsmodels` is the more rigorous econometric choice and reports the estimated transition matrix directly.

### Python sketch
```python
import numpy as np
import statsmodels.api as sm

# 1) FIT a 2-regime switching model (switching mean AND variance)
mod = sm.tsa.MarkovRegression(returns, k_regimes=2, trend='c', switching_variance=True)
res = mod.fit()
P   = res.regime_transition_matrix[..., 0]   # KxK transition matrix
mu  = res.params[[0, 1]]                      # regime means (indexing depends on spec)
# smoothed_marginal_probabilities gives P(S_t = k | data) for regime labeling

# 2) SIMULATE forward
def simulate_regime_paths(P, mus, sigmas, T, B, rng=None):
    rng = rng or np.random.default_rng(0)
    K = P.shape[0]
    # stationary dist = left eigenvector for eigenvalue 1
    w, v = np.linalg.eig(P.T); pi = np.real(v[:, np.argmin(abs(w-1))]); pi /= pi.sum()
    out = np.empty((B, T))
    for b in range(B):
        s = rng.choice(K, p=pi)
        for t in range(T):
            s = rng.choice(K, p=P[s])
            out[b, t] = rng.normal(mus[s], sigmas[s])
    return out
```

### Pitfalls
- **Regime instability / label switching:** EM can swap regime identities across fits; pin them down by an economic constraint (e.g. force $\sigma_1<\sigma_2$). Estimated $P$ near the boundary (a regime that almost never recurs) is unreliable.
- **Small-sample transition estimates:** rare regimes have few transitions ⇒ noisy $\hat P_{ij}$. Consider a Bayesian (Dirichlet) prior on each row.
- **First-order Markov is memoryless within a regime:** real durations are often non-geometric. A 2-state model is a *caricature*; validate that simulated drawdown/vol statistics actually bracket the realized ones before trusting it.
- **In-sample fitting of regimes is itself an overfitting surface** — the regime model must be fit on the SAME training data as the strategy, never on the test fold.

---

## A.3 Parametric Monte Carlo with Student's t (fat tails)

### Purpose
Generate synthetic returns from a **fat-tailed** parametric law so tail/drawdown estimates aren't bounded by the historical sample. The Gaussian is rejected by virtually all financial return series (excess kurtosis ≫ 0); the **Student-t** is the standard minimal fat-tailed upgrade.

### Density (location–scale Student-t)
The standardized Student-t with $\nu$ degrees of freedom has density
$$
f_\nu(x)=\frac{\Gamma\!\left(\frac{\nu+1}{2}\right)}{\sqrt{\nu\pi}\,\Gamma\!\left(\frac{\nu}{2}\right)}\left(1+\frac{x^2}{\nu}\right)^{-\frac{\nu+1}{2}}.
$$
For returns we fit the **location–scale** version $r=\mu+ \sigma_s\, t_\nu$ (here $\sigma_s$ is the *scale*, **not** the standard deviation):
$$
f(r\mid \nu,\mu,\sigma_s)=\frac{1}{\sigma_s}\,f_\nu\!\left(\frac{r-\mu}{\sigma_s}\right).
$$
Key facts:
- Mean exists iff $\nu>1$ (equals $\mu$); **variance exists iff $\nu>2$** and equals $\sigma_s^2\cdot\frac{\nu}{\nu-2}$.
- **Kurtosis** is finite iff $\nu>4$: excess kurtosis $=6/(\nu-4)$. So $\nu\in(4,\infty)$ controls tail fatness; small $\nu$ (e.g. 3–5) ⇒ very heavy tails. **Empirical daily equity-index returns typically fit $\nu\approx 3$–$6$.**
- As $\nu\to\infty$, t → Gaussian.

### Fitting (location, scale, df)
Use **MLE**, not method-of-moments (MoM breaks when $\nu\le4$ because sample kurtosis has no population target). `scipy.stats.t.fit` does constrained MLE returning `(df, loc, scale)`.

```python
import numpy as np
from scipy import stats

# FIT df (nu), loc (mu), scale (sigma_s) by MLE
nu, loc, scale = stats.t.fit(returns)

# SIMULATE B paths of length T from the fitted fat-tailed law
def simulate_t_paths(nu, loc, scale, T, B, rng=None):
    rng = rng or np.random.default_rng(7)
    return stats.t.rvs(nu, loc=loc, scale=scale, size=(B, T), random_state=rng)

# Tail risk readouts
paths = simulate_t_paths(nu, loc, scale, T=252, B=20000)
term  = np.prod(1 + paths, axis=1) - 1
print("VaR/CVaR(99%) of 1y return:",
      np.percentile(term, 1), term[term <= np.percentile(term, 1)].mean())
```

### Pitfalls
- **Independence assumption remains:** parametric-t draws are IID — fat-tailed in the *marginal* but with **no volatility clustering**. Realized fat tails come *partly* from clustering, so an IID-t simulator still understates the *temporal* concentration of losses. The institutional-grade move is to combine: **GARCH(1,1)-t** (C.2) which produces fat tails *and* clustering, then bootstrap/simulate the standardized residuals. Prefer this over plain IID-t for drawdown work.
- **Don't confuse scale with σ:** report $\sigma=\sigma_s\sqrt{\nu/(\nu-2)}$ if you need volatility; for $\nu\le2$ the variance is infinite (a red flag if your fit returns $\hat\nu\le2$).
- **Skew:** plain t is symmetric. If losses are fatter than gains, use **skewed-t** (Hansen 1994; available as `dist='skewt'` in `arch`, or `scipy.stats.skewnorm`/`jsu` families).
- **Estimation risk in $\nu$:** $\hat\nu$ has wide confidence intervals in small samples; do a sensitivity sweep over $\nu\in\{3,4,5,6\}$.

---

# PART B — Best Practices the Blueprint MISSED (Critical)

> These are the methods that separate "institutional-grade validation" from "a Sharpe ratio and a backtest curve." Monte Carlo (Part A) tests *risk of a given strategy*; Part B tests whether the strategy's *edge is real or an artifact of the search process*. **The blueprint's omission of Part B is its most serious gap.**

## B.1 Walk-Forward Analysis (anchored vs rolling)

**Idea.** Repeatedly (1) optimize/calibrate on an in-sample (IS) window, (2) trade frozen parameters on the immediately following out-of-sample (OOS) window, (3) advance. Concatenate OOS segments into a single OOS equity curve — *that* is your honest performance estimate.

- **Anchored (expanding):** IS start fixed; IS window grows each step. Uses all history; assumes the distant past stays relevant; more stable parameters.
- **Rolling (sliding):** fixed-width IS window that moves forward. Adapts to regime change; discards stale data; noisier parameters. **For non-stationary markets, rolling is usually preferred** but test both.

**Diagnostics:** Walk-Forward Efficiency = OOS performance / IS performance (want it not collapsing toward 0); stability of selected parameters across windows (wildly jumping optima ⇒ overfit objective surface).

**Python:** `sklearn.model_selection.TimeSeriesSplit` (expanding; `max_train_size` makes it rolling). For finance-aware splitting use `skfolio` (B.2). Backtest engines `vectorbt` / `backtesting.py` have walk-forward helpers.

```python
from sklearn.model_selection import TimeSeriesSplit
tscv = TimeSeriesSplit(n_splits=8, max_train_size=None)  # None=anchored; int=rolling
for tr, te in tscv.split(X):
    params = optimize(X.iloc[tr]); oos.append(evaluate(params, X.iloc[te]))
```

**Pitfall:** WFA still tests *one* path through time. It does not correct for the fact that you tried many strategies (use B.3/B.4) and it has only one OOS realization per period (use B.2 to get many).

## B.2 Combinatorial Purged Cross-Validation (CPCV) + Purging & Embargo

**Source:** Marcos López de Prado, *Advances in Financial Machine Learning* (2018), Ch. 7 & 12. ([Wikipedia: Purged cross-validation](https://en.wikipedia.org/wiki/Purged_cross-validation))

**Why standard k-fold CV is invalid in finance:** (i) it shuffles, breaking time order and leaking the future; (ii) labels are built from *overlapping* windows (e.g. a 5-day forward return), so train and test observations **share information** even without shuffling.

**Two fixes (apply to every CV scheme):**
- **Purging:** drop from the **training** set any observation whose label's evaluation window **overlaps in time** with any test-set label. Removes the leakage from overlapping outcomes.
- **Embargo:** additionally drop a small buffer of training observations **immediately after** each test block (embargo fraction $h$, e.g. 0.01–0.05 of samples), because serial correlation lets information bleed forward across the test→train boundary.

**CPCV proper:** partition the timeline into $N$ groups; choose $k$ of them as the test set (with $k>1$). There are $\binom{N}{k}$ such combinations. Each combination is purged+embargoed and produces OOS predictions on $k$ groups. By recombining, CPCV reconstructs **$\varphi = \binom{N}{k}\cdot k/N$ distinct backtest paths** (e.g. $N=10,k=2 \Rightarrow 45$ splits, 9 paths) instead of a single equity curve — giving a *distribution* of Sharpe/return, which feeds PBO (B.3) directly.

**Python (free):**
- [`skfolio.model_selection.CombinatorialPurgedCV`](https://skfolio.org/generated/skfolio.model_selection.CombinatorialPurgedCV.html) — **recommended, BSD-licensed, actively maintained.** Constructor: `CombinatorialPurgedCV(n_folds=10, n_test_folds=8, purged_size=0, embargo_size=0)`; exposes `n_splits` and `n_test_paths`. (Note: skfolio's default `n_test_folds=8` produces a very large number of paths; for a per-strategy backtest, `n_folds=6..10, n_test_folds=2` is the usual López-de-Prado setting.)
- `sklearn`-compatible `PurgedKFold` / `CombinatorialPurgedKFold` implementations exist in the community (the reference implementation is in AFML Ch.7; `mlfinlab` has it but is **not free** — see D).

```python
from skfolio.model_selection import CombinatorialPurgedCV
cv = CombinatorialPurgedCV(n_folds=10, n_test_folds=2, purged_size=10, embargo_size=5)
paths_perf = []
for train_idx, test_idx in cv.split(X, y):
    paths_perf.append(backtest(strategy, X, y, train_idx, test_idx))
# -> distribution of OOS Sharpe across paths; feed to PBO
```

**Pitfall:** purging/embargo sizes must be set from the **label horizon** and the autocorrelation length, not guessed. Too small ⇒ leakage; too large ⇒ wasteful. CPCV is combinatorially expensive — cost grows with $\binom{N}{k}$.

## B.3 Deflated Sharpe Ratio (DSR) & Probability of Backtest Overfitting (PBO)

### Probabilistic Sharpe Ratio (PSR) — foundation
**Source:** Bailey & López de Prado (2012/2014). Probability the *true* SR exceeds a benchmark $SR_0$, correcting for sample length and **non-normality**:
$$
\widehat{PSR}(SR_0)=\Phi\!\left(\frac{(\widehat{SR}-SR_0)\,\sqrt{T-1}}{\sqrt{\,1-\gamma_3\,\widehat{SR}+\frac{\gamma_4-1}{4}\,\widehat{SR}^2\,}}\right),
$$
where $\widehat{SR}$ and $SR_0$ are **non-annualized** (per-period), $T$ = #returns, $\gamma_3$ = skew, $\gamma_4$ = (non-excess) kurtosis. The denominator is the asymptotic **standard error of $\widehat{SR}$** (Mertens/Lo): negative skew and fat tails *inflate* the SE, *lowering* PSR — exactly the correction fat-tailed strategies need.

### Deflated Sharpe Ratio (DSR) — multiple-testing correction
**Source:** Bailey & López de Prado, *The Deflated Sharpe Ratio* (2014), [SSRN 2460551](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551), [PDF](https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf).

DSR = PSR evaluated at a **data-driven benchmark** $SR_0$ equal to the *expected maximum Sharpe ratio under the null of no skill* across $N$ trials (the "False Strategy Theorem"):
$$
\boxed{\,SR_0=\sqrt{V[\widehat{SR}_n]}\left[(1-\gamma)\,\Phi^{-1}\!\Big(1-\tfrac{1}{N}\Big)+\gamma\,\Phi^{-1}\!\Big(1-\tfrac{1}{N e}\Big)\right]\,}
$$
where $V[\widehat{SR}_n]$ = **variance of the Sharpe ratios across the $N$ trials**, $\gamma\approx0.5772$ (Euler–Mascheroni), $e\approx2.718$, $\Phi^{-1}$ = inverse normal CDF. Then
$$
\widehat{DSR}=\Phi\!\left(\frac{(\widehat{SR}-SR_0)\sqrt{T-1}}{\sqrt{1-\gamma_3\widehat{SR}+\frac{\gamma_4-1}{4}\widehat{SR}^2}}\right).
$$
**Interpretation:** the more strategies you tried ($N$↑) and the more dispersed their Sharpes ($V$↑), the higher the bar $SR_0$ your winner must clear. DSR < 0.95 ⇒ the "best" backtest is plausibly luck.

```python
import numpy as np
from scipy.stats import norm

def psr(sr, sr0, T, skew, kurt):  # sr, sr0 NON-annualized
    se = np.sqrt((1 - skew*sr + (kurt-1)/4*sr**2) / (T-1))
    return norm.cdf((sr - sr0) / se)

def deflated_sr(sr, T, skew, kurt, sr_trials):
    N = len(sr_trials); V = np.var(sr_trials, ddof=1); g = 0.5772156649
    sr0 = np.sqrt(V) * ((1-g)*norm.ppf(1 - 1/N) + g*norm.ppf(1 - 1/(N*np.e)))
    return psr(sr, sr0, T, skew, kurt), sr0
```

**CONTESTED / pitfall — the crux:** $N$ is the number of **independent** trials, which is **not** observable. Correlated trials (e.g. 1,000 parameter tweaks of one idea) have far fewer *effective* independent trials; naively plugging $N=1000$ over-deflates, while $N=1$ (ignoring the search) under-deflates. López de Prado recommends estimating the *effective number of independent trials* via clustering of the trial-return correlation matrix. **Document your $N$ assumption explicitly; report DSR over a range of $N$.** This is an approximation under an assumed-Gaussian-of-Sharpes model — treat it as a strong heuristic, not an exact p-value.

### Probability of Backtest Overfitting (PBO) via CSCV
**Source:** Bailey, Borwein, López de Prado, Zhu, *The Probability of Backtest Overfitting* ([SSRN 2326253](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253), [PDF](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf)).

**Method (Combinatorially-Symmetric Cross-Validation, CSCV):** Build a matrix of per-configuration returns ($T$ rows × $S$ strategy-configs). Split the $T$ rows into $S_{cv}$ even blocks; for each of the $\binom{S_{cv}}{S_{cv}/2}$ ways to choose half the blocks as IS (rest OOS): pick the config with best **IS** performance, find its **OOS rank**. PBO = the fraction of splits in which the IS-best config lands in the **bottom half** OOS:
$$
PBO=\Pr[\,\bar\omega_c<0.5\,], \qquad \bar\omega_c=\text{relative OOS rank (logit) of the IS-best config}.
$$
High PBO (→1) ⇒ selecting on IS performance is *anti-predictive* OOS ⇒ overfit. **PBO is model-free, non-parametric, and symmetric** — its main strength over DSR. Free implementation: port the reference (R package [`pbo`](https://cran.r-project.org/web/packages/pbo/), GitHub `mrbcuda/pbo`) to Python, or compute directly from your CPCV/grid-search return matrix (a ~40-line numpy function).

## B.4 White's Reality Check & Hansen's SPA (data-snooping / multiple testing)

**Problem:** you tested $m$ rules; the best one's outperformance must be judged against the distribution of the *maximum* of $m$ noisy statistics, or you'll "discover" spurious winners.

- **White's Reality Check (RC), White 2000** ([A Reality Check for Data Snooping](https://www.ssrn.com/abstract=685361)): test $H_0:\max_{k} E[f_k]\le 0$ where $f_k$ = performance of rule $k$ minus benchmark. Statistic $\bar V=\max_k \sqrt{n}\,\bar f_k$; its null distribution is obtained by the **stationary bootstrap** (Politis–Romano) of the centered $f_k$. The bootstrap p-value controls the **family-wise error rate** across all rules at once.
- **Hansen's SPA (2005):** same goal, but (i) **studentizes** each statistic ($\sqrt{n}\bar f_k/\hat\omega_k$) and (ii) **removes irrelevant poor models** from the null (uses a sample-dependent recentering instead of the least-favorable configuration). Result: SPA is **less conservative / more powerful** than RC, which loses power when many junk rules are included. **Recommend SPA over RC.**

**Python (free):** [`arch.bootstrap.SPA`](https://arch.readthedocs.io/en/latest/bootstrap/multiple-comparison.html) implements Hansen's SPA (and RC as the `'consistent'`/`'lower'` variant), plus `StepM` (stepwise multiple testing, Romano–Wolf) and `MCS` (Model Confidence Set, Hansen–Lunde–Nason). This is the canonical free implementation.

```python
from arch.bootstrap import SPA
# losses: DataFrame (T x m) of NEGATIVE returns (or -PnL) per candidate rule
# benchmark: T-vector benchmark losses
spa = SPA(benchmark_losses, candidate_losses, reps=5000, block_size=10)
spa.compute()
print(spa.pvalues)   # 'lower' (RC-like), 'consistent', 'upper' bounds
```

**Pitfall:** block size must reflect dependence; RC's conservatism vs SPA's power; both assume the candidate set is fixed *a priori* (sequential search still cheats).

## B.5 Bootstrap Confidence Intervals for Sharpe / CAGR

A point estimate of Sharpe or CAGR is nearly useless without an interval — and the Sharpe SE is sensitive to fat tails and autocorrelation (so the textbook $\sqrt{(1+SR^2/2)/T}$ Gaussian SE is *wrong* for real returns).

- **Use the block/stationary bootstrap** (preserves dependence) and report **BCa** (bias-corrected and accelerated) intervals, which correct for skew in the bootstrap distribution.
- For Sharpe specifically under serial correlation, also know the **Lo (2002)** adjustment (deflates annualized Sharpe for autocorrelation) and the **Ledoit–Wolf (2008)** robust Sharpe-difference test.

```python
import numpy as np
from arch.bootstrap import StationaryBootstrap

def sharpe(x):  # per-period
    return x.mean() / x.std(ddof=1)

bs = StationaryBootstrap(10, returns)              # block bootstrap
ci = bs.conf_int(sharpe, reps=10000, method='bca') # BCa interval
print("Sharpe 95% CI:", ci.ravel())
```

**Pitfall:** IID bootstrap CIs are too *narrow* for autocorrelated returns (overstate confidence). Always block-bootstrap. CAGR CIs are wide and right-skewed — report the interval, not just the median.

---

# PART C — Position Sizing & Volatility Modeling

## C.1 ATR-based volatility targeting (VET the blueprint's formula)

**The standard risk-per-trade formula (what the blueprint should say):**
$$
\boxed{\text{Position size (units)}=\frac{\text{Equity}\times \text{risk fraction}\;f_{\text{risk}}}{\text{ATR}\times k_{\text{ATR}}\times \text{point value}}}
$$
where $k_{\text{ATR}}$ is the stop-distance multiple of ATR (e.g. 2×). The denominator $=\text{ATR}\times k_{\text{ATR}}=$ **dollar risk per unit** if the stop is hit; the formula sets units so that hitting the stop loses exactly $f_{\text{risk}}\cdot$Equity. This is dimensionally correct **iff** the stop is actually placed at $k_{\text{ATR}}\cdot\text{ATR}$ from entry. **Vet checklist for the blueprint's version:**
1. **Dimensional consistency:** numerator is dollars; denominator must be *dollars per unit* (ATR in price units × point/contract multiplier). A common blueprint bug is omitting the contract/point multiplier (futures, FX) ⇒ wrong size by the multiplier.
2. **ATR must be contemporaneous and lagged** (use ATR known at entry, not including the entry bar's future range) — else lookahead.
3. **risk fraction $f_{\text{risk}}$** is *fraction of equity risked if stopped*, typically 0.25%–1%. It is **not** the Kelly fraction and not the target vol.

**Portfolio volatility targeting (the complementary, often-better approach):**
$$
\text{leverage}_t=\frac{\sigma_{\text{target}}}{\hat\sigma_t},\qquad w_t=\text{leverage}_t\cdot w^{\text{base}}_t,
$$
where $\hat\sigma_t$ = forecast of *strategy* volatility (e.g. trailing realized vol of strategy returns, or GARCH forecast C.2), $\sigma_{\text{target}}$ = desired annualized vol (e.g. 10%). Scale positions so expected portfolio vol ≈ target. **This stabilizes risk through regimes and is what "institutional vol targeting" means.** ATR sizing is the *per-instrument* analog; portfolio vol targeting is the *book-level* version. Use ATR for stop-based single-instrument sizing, vol targeting for overall exposure.

**Pitfall:** vol targeting uses a *forecast*; trailing realized vol lags spikes (you de-lever *after* the crash). GARCH or EWMA forecasts react faster. Also: vol targeting raises turnover and can be pro-cyclical.

## C.2 GARCH volatility via the `arch` library

**Model — GARCH(1,1)** (Bollerslev 1986): with mean equation $r_t=\mu+\varepsilon_t$, $\varepsilon_t=\sigma_t z_t$, $z_t\sim$ (Normal or **Student-t**),
$$
\sigma_t^2=\omega+\alpha\,\varepsilon_{t-1}^2+\beta\,\sigma_{t-1}^2,\qquad \omega>0,\ \alpha,\beta\ge0,\ \alpha+\beta<1.
$$
Stationarity/finite long-run variance requires $\alpha+\beta<1$; **unconditional variance** $=\omega/(1-\alpha-\beta)$. Persistence $=\alpha+\beta$ (often ≈0.95–0.99 for daily). **$h$-step variance forecast:**
$$
\sigma^2_{t+h}=\bar\sigma^2+(\alpha+\beta)^{\,h-1}\big(\sigma^2_{t+1}-\bar\sigma^2\big),\quad \bar\sigma^2=\tfrac{\omega}{1-\alpha-\beta}.
$$
For asymmetry (leverage effect — vol rises more after losses) use **GJR-GARCH** (`o=1`) or **EGARCH**. Fit by **maximum likelihood**; with `dist='t'` you get fat-tailed conditional returns (recommended for ALPHA).

**Library:** [`arch`](https://arch.readthedocs.io/) (Kevin Sheppard) — the canonical free Python GARCH library.
```python
from arch import arch_model
# GJR-GARCH(1,1) with Student-t innovations on returns scaled to ~%
am  = arch_model(returns*100, mean='Constant', vol='GARCH', p=1, o=1, q=1, dist='t')
res = am.fit(disp='off')
print(res.params)                       # mu, omega, alpha[1], gamma[1], beta[1], nu
fc  = res.forecast(horizon=10, reindex=False, method='analytical')
sigma_fc = (fc.variance.iloc[-1]**0.5)  # /100 to undo the scaling
```
**Pitfalls:** (i) `arch` strongly recommends **scaling returns to roughly 1–1000** (e.g. ×100 for daily) for optimizer stability — remember to *unscale* forecasts; (ii) horizons >1 for asymmetric models need `method='simulation'`/`'bootstrap'` (no closed form); (iii) GARCH forecasts **conditional** vol — don't confuse with unconditional; (iv) refit periodically (parameters drift).

## C.3 Kelly fraction & fractional Kelly

**Discrete (Bernoulli) Kelly:** with win prob $p$, loss prob $q=1-p$, net odds $b$ (win $b$ per 1 risked):
$$
f^\star=\frac{p\,b-q}{b}=\frac{bp-(1-p)}{b}=p-\frac{1-p}{b}.
$$
**Continuous / Gaussian-returns Kelly** (the relevant one for sized strategies): maximize expected log-growth $g(f)=f\mu-\tfrac12 f^2\sigma^2$ (excess return $\mu$ over the risk-free rate, variance $\sigma^2$). $g'(f)=\mu-f\sigma^2=0\Rightarrow$
$$
\boxed{\,f^\star=\frac{\mu}{\sigma^2}\,}\qquad(\text{single asset; }=\Sigma^{-1}\mu\text{ for a vector of assets}).
$$
The optimal **growth rate** is $g(f^\star)=\tfrac12(\mu/\sigma)^2=\tfrac12 SR^2$ — note Kelly growth $=$ half the **squared Sharpe**. So $f^\star=SR/\sigma$ as well (Sharpe over vol).

**Fractional Kelly:** use $f=\lambda f^\star$, $\lambda\in(0,1)$ (half-Kelly $\lambda=0.5$, quarter-Kelly $\lambda=0.25$). Growth as a function of $\lambda$: $g(\lambda f^\star)=(\lambda-\tfrac12\lambda^2)\,2g^\star = (2\lambda-\lambda^2)g^\star$. **Half-Kelly keeps ~75% of the growth ($2(0.5)-0.25=0.75$) for ~half the volatility of wealth and far smaller drawdowns** — the standard practitioner trade-off.

**Pitfalls (why full Kelly is dangerous here):**
- $f^\star$ uses the **true** $\mu,\sigma$. Estimates are noisy; **plugging in $\hat\mu$ massively over-bets** (Kelly is extremely sensitive to $\mu$ error). Fractional Kelly is partly an *estimation-error* hedge.
- Kelly assumes returns are **IID and you can rebalance continuously** with no constraints. Fat tails (Part A.3), jumps, and gaps mean realized drawdowns exceed the Gaussian-Kelly prediction — **bet less.**
- Full Kelly's drawdowns are brutal (expected max DD ~50%+). For ALPHA, treat $f^\star$ as an *upper bound* and run at $\le$ half-Kelly, cross-checked against the bootstrap MDD distribution (A.1).
- Kelly maximizes long-run log-wealth, **not** Sharpe or any finite-horizon utility — it is the right objective only if you actually have log-utility / infinite horizon.

---

# PART D — Risk Metrics & Libraries (Survey + Recommendation)

| Library | Role | License | Status (2026) | Verdict for ALPHA |
|---|---|---|---|---|
| **empyrical / empyrical-reloaded** | Core metric functions (Sharpe, Sortino, max DD, Calmar, tail ratio, alpha/beta). No tear sheets. | Apache-2.0 | `empyrical` original is stale; **`empyrical-reloaded`** (stefan-jansen) is the maintained fork, Py3.10+. | **USE** as the metrics engine under the hood. |
| **quantstats** | One-call HTML tear sheets, many ratios, benchmark compare. | Apache-2.0 | Maintained; cleaner API than pyfolio; some users pin versions. | **USE** for fast reporting / tear sheets. |
| **pyfolio-reloaded** | Full tear sheets + Bayesian analysis; round-trip/position analytics. | Apache-2.0 | Maintained fork (stefan-jansen) of dead Quantopian pyfolio. | Optional — heavier; use if you want position/round-trip tear sheets. |
| **ffn** | Lightweight stats + `GroupStats`, drawdown, price-series helpers. | MIT | Maintained. | Optional, handy for quick multi-series comparisons. |
| **skfolio** | Portfolio optimization **+ finance-aware model selection (CPCV, purged/embargo CV), stress tests**. | BSD-3 | **Actively maintained, sklearn-compatible.** | **USE** — this is your free CPCV/purging engine (B.2) and portfolio layer. |
| **mlfinlab** | AFML reference implementations (purging, CPCV, fractional diff, meta-labeling, PBO). | **Proprietary, "all rights reserved," NOT free; commercial license required from Hudson & Thames.** ([license](https://github.com/hudson-and-thames/mlfinlab/blob/master/docs/source/additional_information/license.rst)) | Source on GitHub but **non-commercial use restricted**. | **AVOID** under the $0/free constraint. Use `skfolio` + your own ports of the AFML algorithms instead. Community alternatives: `mlfinpy` (check its license before use). |

**Also use:** `arch` (bootstrap, SPA/MCS, GARCH — Parts A/B/C), `scipy.stats` + `statsmodels` (distributions, MLE, Markov-switching), `numpy/pandas`. **Recommended stack:** `empyrical-reloaded` + `quantstats` for metrics/reporting; `skfolio` for CPCV & portfolio; `arch` for bootstrap/SPA/GARCH; `scipy`/`statsmodels` for the parametric and regime models. **Do not depend on `mlfinlab`.**

---

# PART E — THE HONEST SANITY CHECK (Prop-Firm EV Claim)

## E.1 The claim, restated precisely
The blueprint claims: by optimizing **leverage/position sizing** against a prop firm's barriers (daily loss limit, trailing/static max drawdown, profit target), a strategy with **near-zero expected value** can be turned into **positive net EV** — modeled via first-passage time of Brownian motion with drift.

## E.2 Verdict: PARTLY a fallacy. The strong version is FALSE. Precisely:

**(1) Sizing cannot create edge out of zero/negative drift. This part of the claim is a fallacy.**
Consider the trader's *own* account with no fee structure, equity following GBM-type dynamics $dX=\mu\,dt+\sigma\,dW$ (per unit capital). Scaling position size by leverage $\ell$ gives $dX=\ell\mu\,dt+\ell\sigma\,dW$. The **drift and diffusion scale together by $\ell$**. Therefore:
- If $\mu=0$ (zero edge): the process is a **driftless martingale** at any leverage. By the optional stopping theorem, **for a fair game the expected payoff of any bounded stopping strategy is zero** (or negative once costs/fees enter). Leverage changes the *variance* and the *split* between hitting the upper vs lower barrier, but it **cannot manufacture positive drift**. For a symmetric driftless walk between barriers at $+A$ (profit target) and $-B$ (loss limit), the probability of hitting $+A$ first is $B/(A+B)$ — independent of leverage — and the expected terminal equity is exactly $0$. No sizing fixes this.
- If $\mu<0$ (negative edge after costs/slippage — the realistic case for most retail strategies): every barrier-hitting EV is **strictly negative**, and **higher leverage makes it worse** (more variance pushes mass toward the loss barrier faster *and* you pay the negative drift on a larger base). Sizing is strictly harmful.

**Why the intuition fools people:** changing leverage *does* change $P(\text{pass the eval})$ and the *shape* of the equity distribution. With a profit *target* (a barrier that lets you stop on a win), a **driftless** trader can make pass-probability as high as they like by setting a tiny profit target relative to the loss limit ($A\ll B \Rightarrow P_{\text{pass}}=B/(A+B)\to1$). But the **EV is still zero** (large prob of a small win exactly offsets small prob of a large loss), and **once the firm's fee is subtracted, EV is negative.** Manipulating pass-probability ≠ manipulating EV. This conflation is the core error.

**(2) The ONLY way the *combined* (trader + prop payout) EV is positive is if the strategy has genuine positive edge, OR the fee/payout structure itself is exploitably mispriced.** Two legitimate channels — note both require something real, not "free EV from sizing":

- **(a) Genuine $\mu>0$:** then sizing is an *optimization*, not alchemy. There exists a leverage that **maximizes the probability of reaching the profit target before the loss/drawdown barrier** (a real, well-posed first-passage optimization — E.3). Too little leverage: the drift is real but you may time-out / never reach target; too much: variance dominates and you hit the loss barrier despite positive drift. The optimum is interior. **This is the defensible, mathematically sound part of the blueprint — but it presupposes edge.**
- **(b) Fee-structure arbitrage / asymmetric payout:** prop firms charge an eval fee $C$ and, after a pass, share profits (trader keeps fraction $s$ of subsequent profits, often 80–90%) while the trader's downside on the *funded* account is capped (you lose the account, not your own capital, beyond the fee). This creates a **convex, option-like payoff**: bounded loss ($-C$ on the eval; loss of account when funded), unbounded-ish upside (profit split). Net combined EV is
$$
\mathrm{EV}_{\text{net}} = P_{\text{pass}}\cdot\big(\underbrace{s\cdot \mathbb{E}[\text{funded profits} \mid \text{pass}]}_{\text{payout}} - C_{\text{remaining}}\big)\; -\;(1-P_{\text{pass}})\cdot C - (\text{costs}).
$$
Because the downside is **truncated** (limited liability past the fee) while upside is shared not capped, a strategy with **exactly zero or even slightly negative raw drift can in principle have positive *combined* EV IF the convexity (limited downside + retained upside fraction $s$) outweighs the eval fee $C$ and the firm's barriers.** This is *option-value*, not drift creation — you are buying a cheap call on your own volatility. **Whether it's actually positive is an empirical question dominated by $C$, $s$, the barrier geometry, payout reliability, and — critically — the firm's incentive to not pay (see E.5).** In practice, prop firms price $C$ and set barriers precisely to keep this EV $\le 0$ for zero-edge traders; the limited-liability convexity is real but is usually *more than* offset by the fee and tight daily-loss/trailing-drawdown barriers.

**Bottom line (unambiguous):**
- **Zero raw edge, no fee asymmetry → net EV = 0 (fallacy to claim otherwise).**
- **Negative raw edge → net EV < 0; leverage makes it worse (fallacy).**
- **Positive raw edge → sizing optimization is sound and valuable (true).**
- **Zero/near-zero raw edge BUT exploitable limited-liability convexity (low fee relative to retained-profit option value) → net EV *can* be positive** — but this is **payout/fee arbitrage, not "sizing turning a coin-flip into gold,"** and it lives or dies on the fee, the profit split, and whether the firm actually pays. **Do not assume it; model it explicitly and stress-test the firm-default risk.** The blueprint's phrasing ("sizing makes near-zero-EV strategies positive") is **misleading at best and false as a general claim.**

## E.3 Correct first-passage / pass-probability formulas (build it right regardless)

Model funded/eval equity (per unit capital, drift already net of costs) as arithmetic Brownian motion $X_t$, $X_0=0$:
$$
dX_t=\mu\,dt+\sigma\,dW_t.
$$
Let the **profit target** be at $+A>0$ and the **loss limit** (or max-drawdown floor) at $-B<0$. The classic **two-barrier exit (continuous gambler's ruin)** result — derived via the exponential martingale $M_t=e^{-\frac{2\mu}{\sigma^2}X_t}$ and the **optional stopping theorem** (since $\mathbb{E}[M_\tau]=M_0=1$) — gives the probability of hitting the **profit target before the loss barrier**:

$$
\boxed{\,P(\text{hit }+A\text{ before }-B)=\dfrac{1-e^{\frac{2\mu B}{\sigma^2}}}{e^{-\frac{2\mu A}{\sigma^2}}-e^{\frac{2\mu B}{\sigma^2}}}\,}\qquad(\mu\neq0).
$$

Driftless limit ($\mu\to0$): $P=\dfrac{B}{A+B}$ (pure ratio of distances — **leverage-independent**, the key fact in E.2).

Equivalent **scale-function** form (good for adding more barriers / numerics): with $s(x)=e^{-2\mu x/\sigma^2}$,
$$
P(\text{hit }A\text{ first}\mid X_0=x)=\frac{s(x)-s(-B)}{s(A)-s(-B)}.
$$

**Expected time to resolution (mean exit time), $\mu\neq0$:**
$$
\mathbb{E}[\tau]=\frac{1}{\mu}\Big(A\cdot P_A - B\cdot(1-P_A)\Big),\quad P_A=P(\text{hit }+A\text{ first}),
$$
and for $\mu=0$: $\mathbb{E}[\tau]=AB/\sigma^2$. Use $\mathbb{E}[\tau]$ to check feasibility against any **time limit** the firm imposes (many evals have a max-days or min-days rule).

**Single-barrier / daily-loss-limit (one absorbing barrier at $-B$, reflecting nothing):** probability of *ever* hitting $-B$ (ruin) for a process with drift $\mu$:
$$
P(\text{ever hit }-B)=\begin{cases}1,&\mu\le0\\[2pt]e^{-2\mu B/\sigma^2},&\mu>0.\end{cases}
$$
This is the right tool for the **daily loss limit** (a barrier that resets each day) and for the **static max-drawdown** floor. For a **trailing** drawdown barrier (the floor ratchets up with the running max), there is no simple closed form — use **Monte Carlo simulation** of the GBM/GARCH path with the ratcheting barrier (tie this directly into Part A).

**Effect of leverage made explicit.** Scaling size by $\ell$ replaces $(\mu,\sigma)\to(\ell\mu,\ell\sigma)$, so the key ratio in every exponent is
$$
\frac{2\mu}{\sigma^2}\;\longrightarrow\;\frac{2\ell\mu}{\ell^2\sigma^2}=\frac{2\mu}{\ell\sigma^2}.
$$
**Higher $\ell$ shrinks the drift's influence per unit of barrier distance** (the $1/\ell$). With $\mu>0$, there is an interior $\ell^\star$ maximizing $P(\text{hit }+A\text{ first})$ subject to also respecting the daily-loss and time barriers — *that* is the legitimate optimization. With $\mu=0$ the ratio is $0$ for all $\ell$ ⇒ pass-probability is leverage-invariant (it's $B/(A+B)$) ⇒ **sizing provably cannot help.** This is the mathematical proof that the strong claim is false.

```python
import numpy as np
def p_target_before_loss(mu, sigma, A, B):  # arithmetic BM, X0=0
    if abs(mu) < 1e-12:
        return B / (A + B)
    a = np.exp(-2*mu*A/sigma**2); b = np.exp(2*mu*B/sigma**2)
    return (1 - b) / (a - b)

def expected_exit_time(mu, sigma, A, B):
    if abs(mu) < 1e-12: return A*B/sigma**2
    pA = p_target_before_loss(mu, sigma, A, B)
    return (A*pA - B*(1-pA)) / mu

# Optimize leverage for pass-prob ONLY IF mu>0; for trailing DD use MC simulation.
```

## E.4 What to actually build
1. A **pass-probability engine** using the formulas above for static daily-loss + profit-target + time barriers (closed form), and a **Monte Carlo path simulator** (Part A, with GARCH-t innovations) for **trailing** drawdown barriers.
2. A **net-EV calculator** that inputs your *measured* (and bootstrapped-CI, Part B.5) $\hat\mu,\hat\sigma$ — **after realistic costs/slippage** — the firm's $C$, profit split $s$, barrier geometry, and outputs combined EV with confidence bands. **Refuse to report a positive EV that depends on $\mu>0$ unless DSR/PBO (B.3) say the edge is real.**

## E.5 Non-mathematical caveats (state them plainly)
- **Edge must be net of costs/slippage/financing** — most "near-zero EV" strategies are actually negative once these hit. Garbage-in.
- **GBM is a poor model of an equity curve:** fat tails and volatility clustering (Part A.3/C.2) make real loss-barrier hits **more likely and sooner** than the Gaussian first-passage formula predicts. The closed forms are a *lower bound on ruin risk*; trust the Monte Carlo more.
- **Counterparty/payout risk:** the profit split is only EV if the firm pays. Firm-default / rule-change / "consistency rule" risk is a real haircut not in any first-passage formula. Model it as a discount on the payout term.
- **Daily-loss-limit interaction:** intraday it acts as a *much* tighter barrier than the overall drawdown; many evals fail on the daily limit, not the total — your model must include both, and the daily limit usually dominates pass-probability.

---

## References (authoritative)

- Bailey, D. & López de Prado, M. — *The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting, and Non-Normality.* SSRN 2460551 — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551 ; PDF: https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf
- Bailey, Borwein, López de Prado, Zhu — *The Probability of Backtest Overfitting.* SSRN 2326253 — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253 ; PDF: https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf
- López de Prado, M. — *Advances in Financial Machine Learning* (Wiley, 2018), Ch.7 (CV/purging/embargo), Ch.11–12 (CPCV, PBO).
- Wikipedia — Deflated Sharpe ratio: https://en.wikipedia.org/wiki/Deflated_Sharpe_ratio ; Purged cross-validation: https://en.wikipedia.org/wiki/Purged_cross-validation
- White, H. (2000) — *A Reality Check for Data Snooping.* SSRN 685361 — https://www.ssrn.com/abstract=685361
- Hansen, P. R. (2005) — *A Test for Superior Predictive Ability.* (Journal of Business & Economic Statistics).
- `arch` docs — volatility forecasting: https://arch.readthedocs.io/en/latest/univariate/univariate_volatility_forecasting.html ; bootstrap & multiple comparison (SPA/RC/MCS/StepM): https://arch.readthedocs.io/en/latest/bootstrap/multiple-comparison.html
- `skfolio` — CombinatorialPurgedCV: https://skfolio.org/generated/skfolio.model_selection.CombinatorialPurgedCV.html
- Politis, D. & Romano, J. (1994) — *The Stationary Bootstrap.* JASA.
- mlfinlab license (non-free): https://github.com/hudson-and-thames/mlfinlab/blob/master/docs/source/additional_information/license.rst
- Kelly, J. (1956); Thorp, E. — *The Kelly Criterion in Blackjack, Sports Betting and the Stock Market.* (continuous Kelly $f^\star=\mu/\sigma^2$).
- Karlin & Taylor, *A First Course in Stochastic Processes* — two-barrier exit probabilities / scale function (gambler's ruin for diffusions).
