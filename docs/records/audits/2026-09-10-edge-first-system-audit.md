# Project ALPHA Edge-First System Audit

- **Audit date:** 2026-09-10
- **Baseline:** `main` at fed2fb9 (Trader Terminal Phase 5 merged)
- **Scope:** data layer, research → strategy → validation pipeline, system footprint and process overhead, assessed strictly against the goal of finding tradable edge
- **Method:** three parallel read-only explorations plus direct spot checks of every load-bearing number
- **Readiness call:** **Trust machinery complete; edge-finding capacity not yet exercised. Zero promoted strategies; dataset too small for the methodology; no fast screening lane.**

## Context

The owner asked for a frank assessment of the whole system: where changes and simplifications would
most improve the odds of building profitable strategies, finding edge, and having better data,
process, collection, and analysis tooling.

The original v1 spec said it plainly: *"The point of v1 is not to find alpha. It is to build
machinery we can trust."* That machinery has been built, and then some. The audit's headline is
that the platform is now optimized for a research volume it has never produced. Three months in:

| Fact | Value |
|---|---|
| Strategies promoted (`data/store/promotions/`) | **0** |
| Runs ever recorded (`data/runs/`) | 27 (3 `validate`, all byte-identical duplicates on a UI fixture) |
| Distinct alpha ideas in `alpha_strategies` | 2–3 (TS momentum, mean reversion, breakout/MA-cross variants) |
| Usable equity data | 21 mega-cap survivors + SPY, daily, ~2015–2025 |
| Usable crypto data | 4 pairs daily + ~5 MB of proof-of-capability derivative slices |
| Production source | ~170k lines; ~22% alpha-relevant, ~37% UI, ~41% governance |
| Largest file | `apps/alpha-cli/src/alpha_cli/control_store.py`, 13,119 lines (governance SQLite) |
| Pre-commit gate | 616 s, of which pytest is 609 s; 188 stamps ≈ 31 h of gate time in 6 weeks |
| Owner commands from idea to validated strategy | ≈19, all serialized, some irreversible |

The DAG, the PIT firewall, the bias guards, the two-clock corporate actions, and the gauntlet
statistics are genuinely good and should be kept. Everything below is about redirecting effort,
not about lowering rigor.

## Findings (ranked by impact on finding edge)

### F1. The dataset cannot support the methodology
- 22 symbols × ~2,500 days is too small a sample for DSR/PBO/CPCV machinery to say anything.
  The hand-picked survivor universe makes every cross-sectional result uninterpretable
  (spec §13 accepted this for v1; it was never revisited).
- No fundamentals, no macro/regime series, no earnings/event calendar, no delisting history,
  no equity intraday (blocked at the type level: `packages/alpha-data/src/alpha_data/adapters/base.py:16`
  `Timeframe = Literal["1D"]`).
- Every stored corporate action has `announce_date: null`, so `knowledge_time` is an estimate
  everywhere (`alpha_core/.../corporate.py:38`) and the two-clock model is running on one clock.
- Crypto is the inverse problem: ~22k lines of adapters, quality checks, features, and 31 CLI
  commands for funding/OI/basis/options/on-chain, tested against ~1 MB of data. The hard part is
  built; the downloads were never done.

### F2. There is no fast screening lane
- The synthesis doc prescribed vectorbt-style triage ("thousands of param combos in seconds, never
  for validation"). It was never built. `alpha optim grid` runs the full Nautilus engine per cell.
- The only vectorized path is `apps/alpha-cli/src/alpha_cli/_cross_sectional.py` (245 lines,
  numpy), and it is a backtest with DSR+CI output, not a hypothesis scorer, and it does not get the
  gauntlet.
- Cross-sectional research tooling is `alpha_research/ic.py` at 52 lines. No IC decay, quantile
  monotonicity, Fama-MacBeth, turnover-adjusted IC, or factor orthogonalization.

### F3. The research funnel is a 19-command, owner-serialized, partly irreversible pipeline
- Path: capture → data register → sources add/freeze → draft → approve → D0 pilot → D1 deep →
  draft-confirmation → approve confirmation → one-shot D2 confirm → decision-view → decide →
  project version → experiment → seal-holdout → backtest → validate → report.
- D0 accepts exactly one operator (`research_runtime.py:279`, `double_bottom` only); a new idea
  cannot enter without new registered Python. D2 is one-shot and a pre-flight failure contaminates
  the sealed share.
- 44 `alpha research` + 27 `alpha project` commands = 42% of the CLI surface. `research_cmds.py`
  is 3,771 lines; `gate_packet.py` (1,274) is the biggest module in `alpha_research`, bigger than
  `event_study.py`.
- Owner-presence (Touch ID) and approvals gate promotion, which is right; but the crypto research
  lane hard-blocks on `approval_ready` before any number comes out.

### F4. The gauntlet is missing the two gates that matter most once screening exists
- PBO and White RC / Hansen SPA are implemented and oracle-tested but only wired into
  `_optim.py` (`:89-90`), not `_gauntlet.py`. These are precisely the multiple-testing punishments a
  screening lane needs.
- Cost model is flat bps + fixed spread. No ADV/participation impact, no borrow. This will bless
  any high-turnover cross-sectional signal.
- Portfolio construction is `equal | inverse_vol` only. No covariance-aware sizing.

### F5. The feedback loop is 10 minutes and the test mass is inverted
- 609 s of the 616 s gate is pytest; the tree-hash stamp invalidates on any byte change, so each
  edit-fix-commit cycle costs 10 minutes. 369 test files, 92k lines, most of `tests/unit` (62k)
  exercises control-plane CRUD.
- `test_crypto_binance.py` (1,245 lines) and `test_crypto_bybit.py` (1,052) each exceed the entire
  equity PIT+store+snapshot+corporate implementation (~540 lines); the PIT firewall test
  (`tests/bias_guards/test_pit_reader.py`) is 35 lines.
- Harness audit: 125 `over_eager_edit`, 69 pre-bash blocks, 90 ack/override events (~14% of all
  audit traffic); the expensive review/quant attestation paths fired 7 times total.

### F6. Three façades over one verb set, for one user
- 197 CLI commands, 126 REST paths (subprocess relay over the CLI), 62 MCP tools, and a 46k-line
  TS frontend. Every new capability costs three implementations plus OpenAPI/TS-client/Playwright
  regeneration. Of the last 60 commits, ~34 are terminal UI, ~12 docs, <8 touch data/backtest/
  validation semantics (and those are bug fixes).
- `alpha_options` (130 lines) and `alpha_screener` (140) are empty shells each carrying a wheel,
  an import contract, and a CI smoke step. QuantPad: ~900 lines and 11 MB of failure logs,
  `bars_manifests: 0`.

## Recommended program

Principle: **freeze the platform, feed the machine, shorten the loop.** Keep every invariant
(DAG, PIT, bias guards, determinism, sealed holdout, owner-only promotion). Add a
non-authoritative research lane in front of the governed one. No governance is deleted; it is
moved to where it earns its cost, which is candidate promotion, not idea triage.

### Phase A. Shorten the loop (1–2 sessions, highest leverage per hour)
1. Split pytest into an `alpha` tier (data, backtest, validation, strategies, research stats,
   bias_guards, oracles, holdout) and a `platform` tier (control store, web, MCP, CLI plumbing,
   frontend contracts). `gate.py fast` runs `alpha`; `gate.py full` runs both. Target: ≤2 min
   per iteration. Control-plane edit needs an `ack` (`scripts/gate.py`, `.claude/settings.json`).
2. Freeze surfaces: declare MCP (62), REST, and the terminal UI at Phase 5 as frozen in
   `CLAUDE.md`. New research capability ships as CLI `--json` only until it has produced a
   promoted strategy; the SPA/REST/MCP triple is added later, if ever.
3. Delete dead weight: `alpha_options`, `alpha_screener` (fold the 270 lines into
   `alpha_strategies` or drop), QuantPad adapter + archive + receipts, `.claude/worktrees/` venvs.
   Update import-linter contracts and the 14→12 wheel smoke in CI.

### Phase B. Feed the machine (data first; nothing else matters without this)
Pick one primary lane and go deep. Recommendation: **crypto derivatives first** (code is built,
data is free and survivorship-free by construction, funding/OI/basis are documented anomalies with
a mechanism), with **a survivorship-aware equity cross-section second**.
1. Backfill Bybit `funding`, `open_interest`, `derivative_bars`, `mark/index/premium` and Binance
   `market_bars` + `market_membership` for the top ~50 perps, full history, via the existing
   `crypto_data_cmds` acquire/quality path. Deliverable: a multi-GB governed snapshot, not a slice.
2. Add a `research lane` flag to the crypto acquisition chain so `acquire → quality → use` is
   legal for read-only research with provenance recorded but not blocking (profiles, liquidity
   freeze, asset master, eligibility stay mandatory for D2/promotion only).
3. Equity: add a point-in-time universe table `(symbol, effective_from, effective_to,
   delisting_return)` in `alpha_data` seeded from a free S&P 500 change log, and a survivorship
   bias guard that asserts the as-of universe includes later-removed names (the spec promised this
   guard in 2026-06 and it does not exist).
4. Populate `announce_date` from Tiingo where available; surface `knowledge_is_estimated` in
   quality reports so the single-clock state is visible.
5. Small side tables: macro/regime (VIX, DGS10/DGS2, DXY, HYG/LQD via the yfinance/FRED adapter
   pattern) and SEC XBRL `companyfacts` with filing dates for a thin, truly PIT fundamentals set.
6. Relax `Timeframe` to `Literal["1D", "1h"]`; CCXT already serves it (`ccxt_adapter.py:162`).

### Phase C. A fast, honest screening lane
1. `alpha scan hypotheses`: a vectorized (numpy/Polars) scorer over N signals × M universes
   returning IC, IC decay/half-life, quantile spread + monotonicity, turnover, and a
   turnover-adjusted IC. Labeled `authority: none`, no run manifest, no D0. Reuse the
   `_cross_sectional.py` core and `alpha_research/ic.py`.
2. Extend `alpha_research` with Fama-MacBeth, IC decay, quantile monotonicity, orthogonalization
   vs momentum/vol/size. Each is a small numpy primitive with an oracle test (quant attestation
   applies; that is the correct use of `/verify-quant`).
3. Generalize D0 from `double_bottom` to any registered `EventTableV1`/`FactorObservationTableV1`
   producer so a screened signal can enter the governed funnel without new Python.

### Phase D. Make the gauntlet punish the screening lane
1. Wire PBO and Reality Check/SPA from `_optim.py` into `_gauntlet.py`, taking the trial count
   from the scan that produced the candidate (so DSR's `n_trials` stops being a hand-entered
   number).
2. Give `alpha backtest cross-sectional` gauntlet parity (walk-forward, CPCV, null tiers).
3. Cost model: add an ADV-participation impact term and a borrow/funding cost to
   `alpha_backtest/frictions.py`; make the flat-bps model fail loud when turnover exceeds a
   threshold without an impact model.
4. Portfolio: add covariance-aware (risk-parity) weights to `_portfolio.py`.

### Phase E. Compress the governed funnel
1. Collapse the 19-command path to ~6 owner actions: `capture → screen (Phase C) →
   register-candidate → seal-holdout → run confirm (D2) → decide`. D1 becomes an optional deep
   dive rather than a mandatory phase. Keep one-shot D2, Touch ID, and promotion dossier intact.
2. Make D2 pre-flight failures non-contaminating when the failure is environmental (missing
   file, hash mismatch before any read), reserving contamination for an actual read.
3. Split `control_store.py` by concern (projects / research / jobs / owner-auth) as a
   behavior-preserving refactor; do not add to it.

## Explicit non-goals
- No new UI desks, MCP tools, or REST routes.
- No weakening of PIT, bias guards, determinism, sealed holdout, or owner-only promotion.
- No new asset class beyond the two lanes above until one produces a promoted strategy.

## Verification (per phase)
- A: `gate.py fast` wall time ≤120 s on a source edit; `gate.py full` still mirrors CI; wheel
  smoke count updated and green.
- B: snapshot manifests show full-history row counts (funding ≥ 8 h cadence × years × 50 symbols);
  survivorship bias guard fails on a survivor-only universe and passes on the PIT table;
  `knowledge_is_estimated` reported in quality output.
- C: `alpha scan hypotheses --json` on the Phase B snapshot returns in seconds; oracle tests for
  each new statistic pass `/verify-quant`.
- D: gauntlet manifest contains `pbo`, `reality_check` blocks; a synthetic over-fit sweep
  (1,000 random signals) is rejected; cross-sectional run manifest carries walk-forward folds.
- E: acceptance test `test_research_program_acceptance.py` rewritten for the 6-step path and
  green; command count in `docs/atlas/cli-flow.md` drops.

## Order of execution
A → B1/B2 (crypto backfill can run unattended while C is built) → C → D → B3–B6 → E.
Each phase is its own plan doc under `docs/superpowers/plans/` via `/plan-feature`; risk-tier
paths (`_gauntlet`, `alpha_backtest`, `alpha_validation`, `alpha_research`) go through
`/review-gate` and `/verify-quant`.
