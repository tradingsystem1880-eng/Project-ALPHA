---
owner: project layer
sources:
  - pyproject.toml
  - packages/*/pyproject.toml
  - apps/*/pyproject.toml
  - workers/*/pyproject.toml
  - workers/rdagent/source_pin.py
  - apps/alpha-web/frontend/package.json
  - docs/adr/0051-glue-rules-for-outside-projects.md
  - docs/adr/0052-licence-is-not-a-criterion.md
verified: d1815b0f82ab9b2d
---

# Outside projects: the register

Every open-source project ALPHA uses or has judged, in one table. An *outside project* is any
library, engine or tool ALPHA did not write. How one is chosen and joined is decided in
[ADR-0051](../../adr/0051-glue-rules-for-outside-projects.md) (the glue rules); what a proposal
must record is in [ADR-0011](../../adr/0011-evidence-gated-external-integrations.md). Licence is
not a criterion for any project ([ADR-0052](../../adr/0052-licence-is-not-a-criterion.md)).

## How to read it

- **How it is glued.** *Imported in X*: the main install, used by package X. *Own worker*: a
  separate program with its own install and lock file. *Vendored*: a copy of the project's
  files kept inside ALPHA. A dash means it is not in ALPHA.
- **State.** *In use*: installed and called today. *Approved, not yet added*: the owner approved
  it on 2026-11-15; it arrives in its own pull request. *Later*: fits a row that is not being
  built yet. *Reference only*: worth reading, never installed. *Refused*: judged and turned
  down; ask again only with new facts.
- Judgements of projects not in ALPHA were made on 2026-11-15 from their public package pages.
  None of those projects was installed or run against ALPHA.
- Rows marked *re-judged 2026-11-16* were first turned down or delayed partly for licence; they
  were judged again on fit, upkeep, weight and conflict with pins. The full study is an owner-facing
  study kept outside the repository.

## The register

| Project | What it does for ALPHA | How it is glued | State | Reason |
|---|---|---|---|---|
| RD-Agent | The AI research loop: proposes, codes and repeats ideas | Own worker; one pinned commit | In use | Core engine; ALPHA judges its output |
| RD-Agent's own libraries (LiteLLM, others) | Let RD-Agent run | Its runtimes, checksum-locked | In use | Come with the engine; ALPHA never imports them |
| Ollama | Text embeddings for RD-Agent, on this machine | Separate program, behind ALPHA's model gateway | In use | Keeps that step local and free |
| Qlib (`pyqlib`) | Trains models that rank stocks; standard features | Own worker, exact pins | In use | Mature toolkit; ALPHA replays its predictions |
| LightGBM, CatBoost, XGBoost | The model types Qlib trains | Qlib worker | In use | Qlib's standard models |
| Plotly, Graphviz | Drawing libraries Qlib needs | Qlib worker | In use | Required by Qlib, not used by ALPHA itself |
| MLflow | Qlib's own experiment notebook | Qlib worker only, brought by Qlib | In use | Fine inside the worker; refused in the main install |
| NautilusTrader | Simulates orders, fees; paper sessions | Imported in `alpha-backtest`, `alpha-strategies`, `alpha-cli` | In use | The one backtest engine |
| Kronos | Draws possible future price paths | Vendored in `alpha_forecast/_vendor` | In use | Upstream publishes no package |
| PyTorch and its helpers | Run the Kronos model | Imported in `alpha-forecast` | In use | Kronos needs them |
| Polars | Tables of data in every calculation | Imported across packages | In use | ALPHA's one dataframe library |
| pandas | Tables at three named edges only | Imported in `alpha-data`, `alpha-validation`, `alpha-forecast` | In use | Some libraries speak only pandas |
| numpy, SciPy | The arithmetic under the statistics | Imported in the numeric packages | In use | Standard, well tested |
| PyArrow | Reads and writes Parquet data files | Imported in `alpha-cli` | In use | The file format of the store |
| Matplotlib | Fixed, repeatable charts | Imported in `alpha-research`, `alpha-validation`, `alpha-cli`; AFML worker | In use | Same picture every run |
| quantstats-lumi | Draws one HTML performance report | Imported in `alpha-validation` (one file) | In use | Pictures only; never a judged number |
| exchange_calendars | Knows each market's trading days | Imported in `alpha-data`, `alpha-cli` | In use | Use more: year length from the calendar |
| yfinance | Free daily stock prices from Yahoo | Imported in `alpha-data` | In use | Free source for the Dell phase |
| ccxt | Prices from crypto exchanges | Imported in `alpha-data` | In use | One client for many exchanges |
| pydantic, pydantic-settings | Checked settings and records | Imported in `alpha-core` and above | In use | Catches malformed data early |
| Typer | Builds the `alpha` command | Imported in `alpha-cli` | In use | Small and standard |
| webauthn | Checks the owner is present (fingerprint) | Imported in `alpha-cli` | In use | Standard for that check |
| FastAPI, Uvicorn, Starlette, sse-starlette, AnyIO | The web server behind the Workstation | Imported in `alpha-web` | In use | Standard web stack |
| MCP SDK (`mcp`) | Lets AI clients call ALPHA's tools | Imported in `alpha-mcp` | In use | The standard for that link |
| React, TanStack Table and Virtual, cmdk | The Workstation's screens | Browser code in `alpha-web/frontend` | In use | Standard building blocks |
| lightweight-charts | Price charts in the Workstation | Browser code in `alpha-web/frontend` | In use | Use more: mark every setup match on the chart |
| BokehJS | Other charts in the Workstation | Browser code in `alpha-web/frontend` | In use | A second chart library; one per chart kind is the aim |
| pypdf | Reads the text of research papers | Literature worker | In use | The worker's one dependency |
| RiskLabAI 3.2.0 | Textbook label and weight methods | Own worker, `workers/afml` | In use | Primary; must agree with quantowl |
| quantowl 0.1.6 | A second writing of the same methods | AFML worker, commit `37a17de` | In use | Not on PyPI; young, never trusted alone |
| statsmodels 0.14.6, numba 0.68.1, scikit-learn | ADF test, compiled loops, forests | AFML worker only | In use | RiskLabAI needs statsmodels below 0.15 |
| DuckDB 2.0.0 | Asks one question across many stored files | Pinned in `alpha-cli`; in memory only | In use | A query tool, never the store |
| lifelines 0.30.3 | Which exit comes first, with censoring | Pinned in `alpha-cli` | In use | Proven estimator; replaces a biased hand count |
| pytest, Hypothesis, mypy, ruff, import-linter | Tests and code checks | Development tools only | In use | Never part of a result |
| statsmodels | Regression, regimes, Holm adjustment | `alpha-validation`, `alpha-research` | In use | Holm matches the old code exactly |
| arch | Side-by-side checks of bootstrap and SPA | `alpha-validation` tests only | In use (checks) | Replaces nothing: different draws and SPA statistic |
| ruptures | Finds dates where behaviour changed | Imported in `alpha-validation` | In use | New ability; needs only numpy and SciPy |
| pandas-datareader | Downloads the Fama-French factor series | For `alpha-data` | Approved, not yet added | That one reader only; lightly maintained |
| TimesFM 3.0, Chronos | General forecasting models | — | Later | Compare with Kronos on the Dell, scored by ALPHA; re-judged 2026-11-16 |
| scikit-survival | Survival models: target or stop first | — (worker or root) | Later | Re-judged 2026-11-16; ties lifelines; needs sklearn 1.9 |
| Arize Phoenix | Traces RD-Agent's model calls | — (own install, dev only) | Later | Re-judged 2026-11-16; LiteLLM has a hook; heavy; own install |
| STUMPY | Finds earlier lookalikes of the latest bars; scores novelty | `alpha-patterns`, `lookalike.py` only | In use | Fixed threshold; notes |
| numba, llvmlite | The compiler STUMPY runs on | Imported by STUMPY only | In use | Come with STUMPY; ALPHA never imports them |
| skfolio | Sizes a basket of positions | — | Later | When baskets need real sizing; heavy |
| alphalens-reloaded | Report pages for mined factors | — (a worker, if adopted) | Later | Leans on pandas; not for the main install |
| edgartools | Company figures from official filings | — | Later | Needs the owner's contact email; filing dates to check |
| alpaca-py | Talks to a broker practice account | — | Later | At the paper phase; could shrink ALPHA's adapter |
| pandera | Checks the shape of stored tables | — | Later | Only for the generic checks |
| TA-Lib | Standard indicators | — (tests first) | Later | As a comparison for ALPHA's own indicators |
| linearmodels | Factor regressions across many assets | — | Later | Same author as arch; one later row |
| QuantLib | Options pricing | — | Later | Large; only when options work starts |
| Vollib, FinancePy | Options maths | — | Later | Possible comparison or worker (ADR-0011) |
| inspect-ai | Scripted checks of an AI's whole journey | — | Later | Not yet studied in depth |
| apprise | Sends alerts | — | Later | Trading-phase work; not yet studied in depth |
| Machine Learning for Trading (book code) | A map of the ideas on ALPHA's checklist | — | Reference only | Notebooks for a book, not a library |
| open-code-review (Alibaba) | A second reader of code changes | — | Reference only | Trial found nothing ALPHA's reviewers missed; see notes |
| OpenBB | Ideas for a data-provider layer | — | Reference only | Dozens of packages; ADR-0011 decided this |
| TradingAgents, FinGPT, FinRobot, TensorTrade | Examples of AI trading agents | — | Reference only | Promise results; short tests; no trading authority |
| PyBroker, mlfinpy, RiskLabAI | Ideas ALPHA has with tests | — | Reference only | Too small; RiskLabAI superseded 2026-11-16 ([note][toolkit]) |
| pypbo | Overfitting maths (PBO, deflated Sharpe) | — | Reference only | Re-judged 2026-11-16; no release or packaging; write our own, cross-check |
| expectation | Tests you may peek at without false alarms | — | Reference only | Re-judged 2026-11-16; young; river covers it; revisit at paper phase |
| FinRL | Trains trial-and-error trading agents | — | Refused | A teaching framework; heavy; closes no row |
| vectorbt | A fast backtest engine | — | Refused | Conflicts with ALPHA's pandas pin; a second engine |
| bt, backtesting.py, zipline-reloaded, backtrader, Lean | Backtest engines | — | Refused | ALPHA has one engine and must judge with it |
| Freqtrade, Jesse, Hummingbot | Whole crypto trading bots | — | Refused | A second system with its own store and rules |
| pyfolio-reloaded, empyrical-reloaded | Performance reports and measures | — | Refused | Repeat what ALPHA already computes and draws |
| quantstats (the original) | The report library the fork came from | — | Refused for now | Recent corrections to its numbers; revisit after a quiet spell |
| MLflow in the main install | A second record of experiments | — | Refused | ALPHA is the record |
| Optuna | Automatic search for the best settings | — | Refused | Multiplies trials that must each be counted |
| hmmlearn | Regime models | — | Refused | In limited maintenance; statsmodels covers it |
| tsfresh | Makes hundreds of features automatically | — | Refused | Works against counting trials; Qlib supplies features |
| pandas-ta | Indicators | — | Refused | No maintained release found; re-check before any reuse |
| pandas_market_calendars | Trading calendars | — | Refused | Wraps what exchange_calendars already gives |
| Great Expectations | Data quality checks | — | Refused | Heavy; pandera would do the job |
| fredapi | Downloads macro series | — | Refused | Stale; ALPHA keeps its own dated store |
| ib_async | Talks to Interactive Brokers | — | Refused | Nautilus already carries that link |
| lightweight-charts-python, getFamaFrenchFactors, sec-edgar-downloader | Wrappers, downloaders | — | Refused | Stale, or do less |
| mlfinlab 0.12.3 (public archive) | The textbook methods, older code | — | Reference only | Answer key for the AFML worker; never installed |

## Judged in the November follow-up studies

Judged on 2026-11-16 from public package pages; none installed. Added by the file-system audit
so no verdict lives only in a private study. Rows already in a pull request are not repeated.

| Project | What it does for ALPHA | How it is glued | State | Reason |
|---|---|---|---|---|
| MAPIE | Forecast ranges with measured coverage; drift alarm | — | Later | For the Kronos view; needs a parity test against a hand-made split |
| river | Drift alarms on a live stream | — | Later | Paper-trading phase alerts |
| statsforecast | Plain forecasts every model must beat | — | Later | A baseline gauntlet for Kronos and Qlib forecasts |
| polars-ds | Rolling regressions inside Polars | — | Later | Only if ALPHA's own rolling regression stays |
| dtaidistance | Lookalikes allowed to stretch in time | — | Later | Only if STUMPY proves too rigid; fixed warping window and cap |
| tsdownsample, great-tables | Thin long series for screens; report tables | — | Later | Intraday charts; reports outside the Workstation |
| PyMC, Bambi | Shrink many small, noisy edges together | — (a worker) | Later | Heavy; only in its own install |
| scoringrules, pyextremes | Score forecasts; size tail losses | — | Later | Kronos scoring; "how bad can a day be" |
| RiskLabAI, quantowl | Textbook methods: labels, weights, purged checks | — (a worker) | Later | Under study ([note][toolkit]) |
| SEC EDGAR bulk files | Company filings dated by filing time | — (data source) | Later | Free; filing time is the known-from date |
| Binance public bulk files | Funding and open-interest history | — (data source) | Later | Free, with checksums; re-hash on every pull |
| CFTC and FINRA files | Futures positioning; short interest | — (data source) | Later | Free; publication delay must be checked first |
| aeon, tslearn, wildboar | Time-series shapes and distances | — | Reference only | Overlap STUMPY; small or pin clashes |
| darts, puncc, skchange | Forecasting, ranges, change points | — | Reference only | Overlap MAPIE, ruptures or a second framework |
| PyPortfolioOpt, pyfixest, CausalPy | Baskets, panel regressions, event impact | — | Reference only | Overlap skfolio, linearmodels, the event study |
| instructor, plotly-resampler, DVC, mem0 | AI output, charts, data versions, memory | — | Reference only | ALPHA has each already, or a second record |
| finmlkit, mlfinpy, fracdiff, timeseriescv | Textbook pieces | — | Reference only | Pin clashes or idle; the toolkit study covers them |
| Riskfolio-Lib | Portfolio risk models | — | Refused | Requires vectorbt, already refused |
| DoWhy, tfcausalimpact, pycausalimpact | Cause-and-effect estimates | — | Refused | Pin clashes (SciPy, pandas, TensorFlow) or idle since 2020 |
| granite-tsfm, polars-ols, mplfinance | Forecast models; regressions; charts | — | Refused | Unmaintained by their own account, or stale |
| cot_reports, fluke, overfit, confseq | Positioning reader; overfitting tests | — | Refused | Stale or brand new with no users; read CFTC files directly |
| PySR | Searches for formulas | — | Refused | A trial multiplier; installs a second language |
| Vibe-Trading, StockSharp, Qbot, myhhub stock, two script collections | Ideas on grounding, fills, layout | — | Reference only | Read 2026-10-03 |
| Moirai 2.0, TimeGPT, Lag-Llama, FinText, FinCast, Chronos-2, TimesFM 2.5 | More forecasting models | — | Later | Beside Kronos |
| FinBERT family, Fin-R1, FinGPT, Qwen3 embedding and reranker | Finance text and retrieval models | — | Later | Only after a measured gap; Codex first |
| PyOD, Ledoit-Wolf, CVXPY, cvxportfolio, EconML | Outliers, covariance, allocation, causal effects | — | Later | Each needs a named task first |
| Docling, BM25 | Reads filings and papers | — | Later | Native structured data first |
| investpy, findatapy, Twelve Data, QTPyLib, Moonshot, pybotters | Data and test helpers | — | Reference only | Overlap ALPHA |

[toolkit]: ../../roadmap/backlog/afml-toolkit-worker.md

## Notes on single rows

- **STUMPY** is a matrix-profile library: it compares every stretch of a price series with an
  example and scores how alike they are. Its default cut-off for a match is worked out from the
  whole series, so it uses later data. The adapter (`alpha_patterns/lookalike.py`, behind
  `alpha lookalike` and `alpha unusual`) takes a fixed threshold stated before the search, never
  calls the function with that default, and searches only bars before the query. The first call
  in a new process takes about half a minute while numba compiles STUMPY's code; numba's disk
  cache is not switched on. Contract and parity tests: `tests/unit/test_lookalike.py`; look-ahead
  guard: `tests/bias_guards/test_lookalike_future_poison.py`; smoke test:
  `tests/smoke/test_lookalike_smoke.py`. It replaces no ALPHA code.
- **open-code-review** was tried on two ALPHA branches. In the only mode that does not send code
  to a model provider it mostly filters the list of changed files and attaches a checklist per
  folder. Against the same branches it found 2 of the 10 and 2 of the 7 defects ALPHA's own
  reviewers found, and nothing they missed. Its launcher updates itself silently unless that is
  switched off, which breaks rule 4. Worth borrowing as ideas: checklists aimed at a path, and a
  required list showing every file was covered. Revisit when its higher-recall mode ships.

## Changing this file

- Add or change a row in the same pull request that adds, upgrades, removes or judges a project.
- A project moves to *In use* only with its adapter, its contract test and its smoke test
  (rule 6 of the glue rules), and to *Refused* with a reason a later session can check.
- Versions are not repeated here: the exact ones are in each `pyproject.toml` and lock file.
- Licences of what is installed are listed in the
  [dependency and licence matrix](../../governance/2026-07-19-dependency-license-matrix.md) and the
  Qlib worker's [notices file](../../../workers/qlib/THIRD_PARTY_NOTICES.md). That is information,
  not a criterion: licence never decides whether a project is used.
