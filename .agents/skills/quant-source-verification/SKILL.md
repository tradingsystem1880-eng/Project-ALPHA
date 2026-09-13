---
name: quant-source-verification
description: Verify statistical and quantitative-finance code against primary academic sources. Use whenever code under packages/alpha-validation/src, packages/alpha-research/src, or any dsr/psr/pbo/deflated/bootstrap/reality_check/spa/montecarlo/walkforward/cpcv/multiple_testing/overfitting module changes — formulas, estimator conventions, assumptions, parameter defaults, and sign conventions must match the cited literature before the change may stand.
---

# Quant Source Verification

SR 11-7 conceptual soundness, mechanized. A statistical formula that "looks right" is
not evidence; the primary source is. This skill produces the `QuantVerificationReport`
that `scripts/gate.py attest --kind quant` validates and binds to the current
quant-scope diff. The Stop guard demands it whenever quant paths were edited.

## Protocol

1. **Scope the diff.** `git diff HEAD -- packages/alpha-validation/src packages/alpha-research/src`
   plus any quant-named module (`dsr|psr|pbo|deflated|bootstrap|reality_check|spa|montecarlo|walkforward|cpcv|multiple_testing|overfitting`)
   under `packages/*/src`. Empty diff ⇒ say so and stop; never attest an empty scope.
2. **Extract every mathematical claim** the diff introduces or alters: formulas,
   estimator choices, distributional assumptions, default parameters, sign/direction
   conventions, degrees-of-freedom corrections, small-sample adjustments.
3. **Check each claim against the primary source** (bibliography below; WebSearch/WebFetch
   for the paper when needed). Verify the exact equation, not a paraphrase. Record
   `VERIFIED`, `DISCREPANCY` (code disagrees with source — quote both sides), or
   `UNVERIFIABLE` (no primary source found — say what was searched).
4. **Docstring citations.** Every changed public statistical function must cite its
   primary source in the docstring. Missing citation ⇒ report it in
   `docstring_citations.missing`.
5. **Verdict.** `overall: PASS` requires every claim `VERIFIED` and citations complete.
   Anything else is `FAIL`. Never attest around a FAIL — fix the code or the citation,
   then re-verify.

## Bibliography (module → primary source)

| Module / concept | Primary source |
|---|---|
| `dsr.py` — Probabilistic Sharpe Ratio | Bailey & López de Prado, "The Sharpe Ratio Efficient Frontier" (2012), JoR 15(2) |
| `dsr.py` — Deflated Sharpe, expected max Sharpe | Bailey & López de Prado, "The Deflated Sharpe Ratio" (2014), JPM 40(5); E[max] uses the Euler–Mascheroni approximation |
| `overfitting.py` — PBO via CSCV | Bailey, Borwein, López de Prado & Zhu, "The Probability of Backtest Overfitting" (2016), Journal of Computational Finance |
| `reality_check.py` — Reality Check | White, "A Reality Check for Data Snooping" (2000), Econometrica 68(5) |
| `reality_check.py` — SPA | Hansen, "A Test for Superior Predictive Ability" (2005), JBES 23(4) — studentized, recentered null |
| `bootstrap.py` — stationary bootstrap | Politis & Romano, "The Stationary Bootstrap" (1994), JASA 89(428) — geometric block lengths |
| `bootstrap.py` — BCa intervals | Efron, "Better Bootstrap Confidence Intervals" (1987), JASA 82(397) — bias correction z0 + acceleration a via jackknife |
| `walkforward.py` / `cpcv.py` — purging, embargo, CPCV | López de Prado, *Advances in Financial Machine Learning* (2018), ch. 7 |
| `multiple_testing.py` — Holm | Holm, "A Simple Sequentially Rejective Multiple Test Procedure" (1979), Scand. J. Statist. 6(2) |
| `montecarlo.py` — GARCH nulls | Bollerslev, "Generalized Autoregressive Conditional Heteroskedasticity" (1986), J. Econometrics 31(3) |
| `pip_miner.py` — k-means++ seeding, Lloyd iterations | Arthur & Vassilvitskii, "k-means++: The Advantages of Careful Seeding" (2007), SODA — D²-weighted seeding; Lloyd, "Least Squares Quantization in PCM" (1982), IEEE Trans. Inf. Theory 28(2) |
| `pip_miner.py` — silhouette | Rousseeuw, "Silhouettes: a graphical aid to the interpretation and validation of cluster analysis" (1987), J. Comput. Appl. Math. 20 — s(i) = (b − a)/max(a, b), singletons 0 |
| `pip_miner.py` — Martin ratio / Ulcer index | Martin & McCann, *The Investor's Guide to Fidelity Funds* (1989) — UI = √mean(drawdown-from-running-peak²); their Ulcer Performance Index is (return − risk-free) / UI, while the port keeps upstream's numerator (raw log-return sum, no risk-free term, un-annualised) as a documented deviation |
| `retracements.py` — Gaussian KDE of log ratios | Silverman, *Density Estimation for Statistics and Data Analysis* (1986) §2.4 — f̂(x) = (1/nh) Σ φ((x − xᵢ)/h); Scott, *Multivariate Density Estimation* (1992) — bandwidth as a multiple of the sample standard deviation (SciPy scalar `bw_method`, ddof=1) |
| `rolling_pca.py` — principal components | Jolliffe, *Principal Component Analysis* (2nd ed., 2002), ch. 1 and §3.5 — eigenvectors of the sample covariance ordered by eigenvalue; SVD of the centred data gives the same components; sign is a free convention (fixed here by the largest loading) |
| `bar_permutation.py` — bar permutation | Masters, *Testing and Tuning Market Trading Systems: Algorithms in C++* (Apress 2018), ch. 7 "Permutation Tests", companion code `MCPT_BARS.CPP` — log-price decomposition into close-to-open gaps and open-relative intrabar moves, shuffled as two separate multisets, basis bar unchanged so the series starts and ends at its original values; the shared order across markets and the `start_index` generalisation follow upstream neurotrader888/mcpt bar_permute.py@2c0d70c |
| `mcpt.py` — Monte Carlo permutation test | Masters, *Testing and Tuning Market Trading Systems* (Apress 2018), ch. 7, companion `MCPT_BARS.CPP`/`MCPT_TRN.CPP` — re-optimise on every permutation, replication 0 is the unpermuted series, `count/nreps` with `count` seeded at 1 and `>=` comparison. Davison & Hinkley, *Bootstrap Methods and their Application* (1997) ch. 4 eq. (4.11) — `(1 + #{T* ≥ t}) / (1 + R)`; upstream neurotrader888/mcpt seeds its counter at 1 over N−1 draws, the same estimator. The walk-forward variant (permute only the bars after the last training bar) is upstream's construction (walkforward_donchian_mcpt.py@2c0d70c), not a Masters program |
| `metrics.py` — profit factor | Gross profit / gross loss — the criterion of upstream neurotrader888/mcpt@2c0d70c `donchian.py` (`sig_rets[sig_rets > 0].sum() / sig_rets[sig_rets < 0].abs().sum()`) and the native tear sheet; Masters' own MCPT_BARS/MCPT_TRN programs score total return, so the ratio is not attributed to him; undefined (`None`) without a loss |
| `trade_dependence.py` — runs test | Wald & Wolfowitz, "On a Test Whether Two Samples are from the Same Population", *Ann. Math. Statist.* 11(2) (1940) — run count `R` over `n_pos`/`n_neg` exchangeable signs has `E[R] = 2 n_pos n_neg / n + 1`, `Var[R] = 2 n_pos n_neg (2 n_pos n_neg − n) / (n² (n − 1))` (equivalently `(E−1)(E−2)/(n−1)`), asymptotically N(0,1); two-sided p = `2 Φ(−|z|)`; upstream neurotrader888/TradeDependenceRunsTest@5f63804 `runs_test.py` is the same statistic (zeros counted in `n`, run broken); the exhaustive-enumeration oracle recomputes both moments without the formula |
| Sharpe conventions | Sharpe, "The Sharpe Ratio" (1994), JPM 21(1) — ex-post, annualization by √periods |

Repo-specific conventions that are DESIGN, not literature (verify against CLAUDE.md
instead): protocol-frozen seeds (D0 power seed, D2 seed 7), the Tier-1/Tier-2 null
split and `tier1_divergence_tol` demotion, and the A–F verdict bands.

## Output

Emit exactly one JSON object and pipe it to the gate:

```json
{
  "claims": [
    {"claim": "...", "source": "...", "location": "path.py:123", "verdict": "VERIFIED"}
  ],
  "docstring_citations": {"ok": true, "missing": []},
  "overall": "PASS"
}
```

```bash
uv run python scripts/gate.py attest --kind quant < report.json
```

The gate rejects malformed reports, FAIL verdicts, and PASS verdicts containing
non-VERIFIED claims; a successful attest binds to the current quant-diff hash and
is invalidated by any further in-scope edit.
