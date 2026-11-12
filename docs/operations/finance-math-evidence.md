# Finance-math evidence and existing numerical skills

This is a source-intake and reuse guide for the existing `literature-review` protocol,
not a new knowledge store, research operator, or trading model. No new numerical implementation
is added. A useful mathematical idea needs three separate records: what its source supports,
what the implementation demonstrably computes, and what research authority has been granted.

## What the carousel establishes

The user supplied 14 screenshots of mirkovicdev's course-ranking carousel: the cover and slides
2/15 through 14/15. Slide 15/15 was not supplied. No book pages were supplied or read from the carousel.
A later bounded external reading pass is distinguished below from actual ALPHA ingestion.
The following is cover metadata transcribed from those screenshots, not a verified bibliography
or a statement about the books' contents. All 13 rows have **unverified book coverage**.
Visible edition labels still need verification against the actual copyright page.

| Slide | Course / pictured book | Authors shown | Edition visible |
| --- | --- | --- | --- |
| 2/15 | Calculus / Calculus, Volume I | Tom M. Apostol | Second |
| 3/15 | Complex Analysis / Complex Analysis with Applications | Nakhlé H. Asmar; Loukas Grafakos | Unknown |
| 4/15 | Optimization / Numerical Optimization | Jorge Nocedal; Stephen J. Wright | Second |
| 5/15 | Measure Theory / Measure, Integration & Real Analysis | Sheldon Axler | Unknown |
| 6/15 | Numerical PDEs / Numerical Models for Differential Problems | Alfio Quarteroni | Third |
| 7/15 | Stochastic Modelling / Stochastic Modeling | Nicolas Lanchier | Unknown |
| 8/15 | Partial Differential Equations / Partial Differential Equations | Lawrence C. Evans | Second |
| 9/15 | Statistics / Introduction to Probability | Joseph K. Blitzstein; Jessica Hwang | Second |
| 10/15 | Topology / Topology | James R. Munkres | Second |
| 11/15 | Numerical Analysis / Numerical Analysis | Rainer Kress | Unknown |
| 12/15 | Abstract Algebra / Abstract Algebra | David S. Dummit; Richard M. Foote | Third |
| 13/15 | Computational Statistics / Markov Chain Monte Carlo: Stochastic Simulation for Bayesian Inference | Dani Gamerman; Hedibert Freitas Lopes; Flávio Bambirra Gonçalves | Third |
| 14/15 | Linear Algebra / Linear Algebra Done Right | Sheldon Axler | Third |

The Statistics heading does not change the pictured probability book's title or establish
coverage of regression, multiple testing, or financial inference. Likewise, the Calculus cover
does not establish coverage of Itô calculus. Unknown editions remain unknown. Personal tier
rankings are the carousel author's opinions, not ALPHA's priority or validation policy.

## Verified source leads, not admitted book evidence

On 2026-11-09, a separate bounded reading pass checked the following public source metadata
and selected pages. These are acquisition leads, not governed evidence for book-attributed
formulas. Full book coverage remains unverified. No SourceAnchorV1 records were created,
no text was ingested into ALPHA, and no book files or extracted passages accompany this guide.
The numerical explanation below is our own derivation, not a quotation or a claim about what
an unacquired book teaches.

- **Sheldon Axler, Measure, Integration & Real Analysis:** the [author's site](https://measure.axler.net/)
  offers an [open-access PDF](https://measure.axler.net/MIRA.pdf), copyright 2020, title-page
  revision 12 June 2026, 426 PDF pages. The local reading copy's SHA-256 was
  `7a7ab07fb74f5394c3180da51875ec467a0d89627321c8b2624b6b9b9585fb4e`.
- **Sheldon Axler, Linear Algebra Done Right, fourth edition:** the [author's site](https://linear.axler.net/)
  offers the [4e PDF](https://linear.axler.net/LADR4e.pdf), copyright 2024, 404 PDF pages.
  This is **different from the photographed third edition**. The site labels its link
  4 November 2026; the actual downloaded title page says 30 October 2026. Retain both labels
  and the reading-copy SHA-256 `a76e3e3f39db8703e050ea43dd4df3ac27ebfce3c0854de9a783547adc273731`.
  Do not reuse this edition as a third-edition citation.
- Both Axler PDFs state [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/):
  covered noncommercial reuse requires author/source credit, a license link and an indication
  of changes; separately credited third-party material may have different terms. The notes
  here are original summaries, not unchanged book text. Free access does not establish
  unrestricted commercial republication or model-training permission. Resolve intended reuse
  before an intake or distribution that depends on the license.
- **Joseph K. Blitzstein and Jessica Hwang, Introduction to Probability, second edition:**
  [Harvard's Stat 110 site](https://stat110.hsites.harvard.edu/) links the free online version
  through [the book link](https://probabilitybook.net/). Its title page confirms the second
  edition, copyright 2019 Taylor & Francis Group, LLC; the viewer has 630 pages. Only a bounded
  selection was inspected in that viewer. Page mappings remain outside this guide until intake.
  **Download was denied by the owner** and print was disabled. No retry, bypass, downloaded
  PDF, bulk extraction or open reuse license is claimed. A readable viewer is not permission
  to reproduce or ingest the whole book.

**Specific intake gap:** this sparse successor does not contain a working isolated literature
worker or a project-bound extraction for these sources. External page/file hashes do not replace
`source_id`, `extraction_id`, character bounds and a verified `SourceAnchorV1`. The existing
local-PDF route records an owner-provided source; do not relabel an agent download to fit it.
For a later intake, restore/verify the existing isolated worker, obtain an actually
owner-selected bounded excerpt with lawful reuse confirmed, and retain the original title,
edition, license, full-source hash and excerpt-to-original page mapping. Use the existing
`alpha research import-pdf PROJECT_ID --file EXCERPT.pdf --title TITLE` route within its 10 MiB/200-page limits, check the resulting
extraction status, read the relevant page slices and create hash-verified anchors through the
existing claim path. Owner review and screening still apply. If that provenance or route is
unavailable, keep the source as metadata-only, or propose a separately reviewed selected-page
acquisition change. Do not silently split an entire book to evade the intake bound.

## Turn a topic into a usable claim

1. State one concrete finance question, the mathematical quantity and its units. For example:
   "What shared direction explains variation in these two return features?" is descriptive;
   "Does that direction predict later net returns?" is a separate empirical question.
2. Locate lawfully accessible supporting pages, verify title/edition and access status, and use
   the existing literature intake. Record actual source/extraction IDs and hash-verified
   `SourceAnchorV1` page anchors. An unavailable or truncated source cannot support an assertion
   about unseen pages. Report exactly what was read; do not fill citation gaps from a cover.
3. Separate a source's statement, your derivation, an implementation's documented behavior and
   measured test output. Record assumptions, domain, estimator, units and missing evidence.
   An extracted equation needs checking against its source before it informs code.
4. Reuse the existing implementation where it fits. Record the exact API/version, inputs and
   reference check. Scale numerical tolerances to the function, units, conditioning and dtype.
   A deterministic example is not a statistical-coverage experiment or market validation.
5. Use the existing research proposal, owner review and promotion path for any empirical test.
   A new topic label or working Python function does not register an analysis family or grant
   permission to execute, admit evidence, paper-trade or trade live.

The current local-PDF intake has 10 MiB and 200-page bounds. Do not silently remove those limits
to ingest a textbook. Metadata, access rights, actual acquired pages and extraction status must
remain explicit. Larger-book ingestion is separate work, not implemented by this guide.

## Reuse first, by topic

- **Linear algebra:** start with the existing trailing-window PCA demonstrated below. This is
  code reuse, not a claim that the pictured Axler book teaches this implementation.
- **Statistics, probability and computational statistics:** inspect existing `alpha_research`
  descriptives, rank IC, event-study, multiple-testing and power functions, and `alpha_validation`
  bootstrap/null methods before proposing another estimator. Coverage in the pictured books is
  unverified; using an existing function still requires matching its assumptions to the question.
- **Optimization:** a specific fitting objective or portfolio constraint must justify the work.
  Existing fitting routines do not establish a general constrained portfolio optimizer.
- **Calculus and numerical analysis:** Greeks or an implied-volatility solver are possible later
  uses, not supplied capabilities here. First specify the model, valid input domain, reference
  prices/derivatives and rounding/truncation-error regime; do not infer them from a title.
- **Stochastic modelling:** choose a process only after stating its assumptions and use. Fixed-seed
  reproducibility and many-seed statistical adequacy are different checks; a GBM or Poisson
  baseline is not evidence that markets obey that process.
- **Measure theory, complex analysis, numerical PDEs and PDEs:** defer specialist pricing work
  until a real use requires it and exact source pages are available. Measure changes, Fourier
  branches/damping, boundary conditions and American exercise cannot be inferred from a cover.
- **Topology and abstract algebra:** retain source leads as background. No current runtime
  requirement or tradable edge is established, and no implementation is added for these topics.

Qlib remains the model-workflow specialist, RD-Agent the bounded hypothesis/code-proposal worker,
and NautilusTrader the execution engine. This guide adds no competing adapters, solver stack,
registry, vector database or promotion gate.

## Worked skill: explain a shared synthetic return direction

**Question:** Can the existing PCA recover a deliberately planted one-dimensional relation?
**Inputs:** five invented observations of two decimal-return features, B = 2A. These are not
market data, prices, or point-in-time source records. Column order is fixed as `[A, B]`.
**API:** [`alpha_research.rolling_pca`](../../packages/alpha-research/src/alpha_research/rolling_pca.py).
It centers columns, uses sample covariance (`ddof=1`), orders eigenvalues descending and makes
each component's largest-magnitude loading positive. Stored components are rows; scores use
`(rows - mean) @ components.T`. It does not standardize column variances for the caller.

For x = [-2, -1, 0, 1, 2], returns are `[0.01x, 0.02x]`. Their mean is zero. The sample covariance
is `0.00025 * [[1, 2], [2, 4]]`, so the leading eigenvalue is 0.00125 and the normalized direction
is `[1, 2] / sqrt(5)`. Covariance/eigenvalue units are squared decimal returns; projected scores
remain decimal-return units. The exact rank-one construction explains all in-sample variance.
It is not a forecast or a portfolio allocation: PCA maximizes variance, not expected profit.

Run this Python-console example with ALPHA's installed dependencies. Its assertions are also
executable with `python -m doctest docs/operations/finance-math-evidence.md`.

```pycon
>>> import numpy as np
>>> from alpha_research.rolling_pca import pca_components, pca_scores, rolling_pca_scores
>>> x = np.arange(-2.0, 3.0)
>>> returns = np.column_stack((0.01 * x, 0.02 * x))
>>> fitted = pca_components(returns, n_components=1)
>>> tolerance = 64 * np.finfo(np.float64).eps
>>> np.testing.assert_allclose(fitted.mean, [0.0, 0.0], atol=tolerance * 0.04)
>>> np.testing.assert_allclose(fitted.explained_variance, [0.00125], rtol=tolerance, atol=tolerance * 0.00125)
>>> np.testing.assert_allclose(fitted.components[0], np.array([1.0, 2.0]) / np.sqrt(5), rtol=tolerance, atol=tolerance)
>>> scores = pca_scores(returns, fitted)
>>> np.testing.assert_allclose(scores[:, 0], 0.01 * np.sqrt(5) * x, rtol=tolerance, atol=tolerance * 0.04)
>>> np.testing.assert_allclose(fitted.explained_ratio, [1.0], rtol=tolerance)
>>> rolling = rolling_pca_scores(returns, window=3, n_components=1)
>>> assert bool(np.isnan(rolling[:2]).all())
>>> np.testing.assert_allclose(rolling[2:, 0], 0.01 * np.sqrt(5), rtol=tolerance, atol=tolerance * 0.04)
>>> later_changed = returns.copy()
>>> later_changed[-1] = [10.0, -10.0]
>>> changed_scores = rolling_pca_scores(later_changed, window=3, n_components=1)
>>> np.testing.assert_allclose(changed_scores[:4], rolling[:4], rtol=tolerance, atol=tolerance * 0.04, equal_nan=True)

```

The small tolerance is specific to this five-row float64 example with a distinct leading
component and known analytic answer. It is not a universal acceptance threshold. Rolling scores
fit rows `[i-window+1, i]`, including the current row, and are only usable once its inputs are
available. The two warm-up rows are NaN, not fabricated zeros. Changing a later row leaves earlier
scores unchanged in this example; this check does not replace the project's bias-guard suite.

**Failure/interpretation checks:** non-finite or zero-variance inputs cannot be treated as usable
fits; scaling a feature changes covariance PCA; sample selection and availability need separate
controls on real data. Nearly tied eigenvalues can rotate component directions, so a component's
sign convention does not make an unstable direction economically meaningful.

**Disposition:** the example demonstrates an existing numerical skill on synthetic inputs.
There is no book claim, market performance, confidence-interval coverage, registered PCA analysis
family, evidence admission or promotion decision. Save empirical proposals through the normal
research workflow, with independent out-of-sample and cost checks where appropriate.

## Original PCA derivation and reference checks

This explanation is derived directly from the finite data and the existing API, not attributed
to the source leads above. Let `Xc` be the `n`-by-`d` column-centered observation matrix, with
`n >= 2`. The implementation forms `S = Xc.T @ Xc / (n - 1)`. For any direction `v`,
`v.T @ S @ v = ||Xc @ v||^2 / (n - 1)`, so this covariance is symmetric positive semidefinite.
For unit `v`, the same expression is the sample variance of the projected observations.
Writing `v` in an orthonormal eigenbasis makes this a weighted average of the eigenvalues;
the leading eigenvector therefore attains the largest sample projection variance.

In exact arithmetic, centering gives `rank(Xc) <= min(n - 1, d)`, so covariance has at least
one zero eigenvalue when `d >= n`. An economy SVD `Xc = U @ diag(s) @ V.T` lists `min(n, d)`
singular values. The covariance eigenvalues are `s**2 / (n - 1)`, plus additional zeros beyond
that list when `d > n`. For `k <= min(n, d)`, the leading `k` right singular vectors span the
selected component subspace. Projection onto it gives a rank-at-most-`k` approximation of the
centered observations. Its squared Frobenius residual norm is the sum of the omitted squared
singular values, equivalently `(n - 1)` times the sum of the omitted covariance eigenvalues.
These finite-matrix identities do not require exchanging a limit and an expectation. They supply numerical reference checks, not a proof of statistical
consistency or an economic interpretation.

The focused test module also uses six invented observations of three decimal-return features,
with distinct eigenvalues, to compare the existing covariance implementation against NumPy SVD.
It checks the two-component projector rather than sign-dependent coordinates, eigenvalues,
orthonormality and the squared-residual identity. Tolerances use 64 float64 machine epsilons,
with residual absolute tolerance scaled by total squared input norm. They apply to these small,
well-conditioned fixtures, not to arbitrary financial data. A separate unchanged-window check
compares bytes exactly after changing only a later row within one process and runtime; this is
deterministic identity, not a statistical floating-point golden or a byte guarantee across
processes, platforms or BLAS thread settings. Zero total variance must still raise `DataError`.

A finite sample can have a computable covariance even when the population has no finite second
moments. Serial dependence, overlapping return horizons and nonstationarity need separate
inference assumptions. Cross-sectional correlation is expected in this use, not itself a PCA
failure. Covariance PCA depends on units and scaling. Near-tied eigenvalues can rotate directions
or swap their order across windows; a sign convention does not repair that instability.
Finally, uncorrelated does not imply independent, and in-sample component decorrelation does
not guarantee out-of-sample decorrelation. Including row `i` in its fitted window is descriptive
in-sample scoring and is usable only after all of that row's inputs are available.

## Source and collaboration record

- Carousel evidence: user-supplied screenshots 1/15 through 14/15, transcribed on 2026-11-09.
  The title/edition table above is derived only from the visible covers. No text from the
  pictured books is represented as ingested knowledge.
- Advisory design input: Claude consultation on 2026-11-09, two responses reviewed.
  Claude proposed separate source, numerical and promotion layers and
  reuse-first implementation. This is advisory design input, not a mathematical source citation
  or engineering approval. Codex checked the existing APIs and executed the example.
- Implementation evidence: the unchanged PCA module linked above, the unchanged research-protocol
  loader, and focused loader/content/example checks. No book-level validation, full-gate pass,
  activation, model/provider call or trading authority is implied.

- Follow-up source-metadata and numerical-review pass on 2026-11-09 used both Codex and Claude.
  Codex verified the public source metadata/pages and ran the unchanged numerical API; Claude
  reviewed abstract mathematics and source/evidence boundaries without private source files or
  book uploads. Claude did not claim to open the books. This is advisory review, not a formal
  gate approval. The external reading does not create governed book anchors or admit evidence.
