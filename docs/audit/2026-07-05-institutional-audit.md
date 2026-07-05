# Institutional Final Audit — 2026-07-05

**Scope:** every package, app, test, config, workflow, and document in the repository
(~8,100 source lines, ~6,900 test lines at completion).
**Method:** full manual read of all source plus a 10-auditor multi-agent sweep
(5 subsystem deep-dives + 5 cross-cutting sweeps: security, determinism, test quality,
build/deps/docs, quant correctness), findings deduplicated and then verified — by adversarial
re-reading where code inspection sufficed, and **empirically against the live engine** where
runtime behavior was in question. Every fix below landed TDD-style (failing test → fix → green)
in its own conventional commit on `claude/institutional-audit-improvement-7050ri`.

---

## 1. Executive summary

The platform is unusually well-built for its size: the architecture DAG is real and enforced,
the statistical core matches the literature it cites (BCa, stationary bootstrap, PSR/DSR,
CSCV-PBO, White RC), typing is strict, and the test culture is strong. The audit nevertheless
found **one critical data-corruption bug** (yfinance double split-adjustment), **two
pre-verified structural biases in the headline validation gate** (Tier-1 crediting convention;
Tier-2 seam jumps), **one empirically confirmed execution bug** shipping in every default
config (CASH + `allow_short=True` strands stale longs), a **reproducibility contract that did
not hold** (`--snapshot` provenance-only; run ids polluted by `max_workers`; manifests missing
result-affecting inputs), and a **look-ahead** in portfolio inverse-vol weighting. All are fixed.

| Dimension | Before | After | Note |
|---|---|---|---|
| Architecture | 9 | 9 | DAG enforced by import-linter; unchanged by design |
| Maintainability | 8 | 8.5 | registry declares params; dead dep removed; docs re-synced |
| Reliability | 6 | 8.5 | atomic writes, crash-consistent artifacts, fail-loud guards, MCP timeout |
| Performance | 7 | 7 | no hot-path regressions found; GARCH loop noted (see §6) |
| Security | 5 | 8 | CSRF/DNS-rebinding + path traversal + injection hardening |
| Testing | 7 | 8.5 | +40 tests incl. future-poison, gate fail-branches, empirical fixtures |
| Documentation | 7 | 8.5 | CLAUDE.md/README now match code; investigation doc honored |
| Production readiness | 5 | 8 | the reproducibility contract now actually holds |
| Code quality | 8 | 8.5 | consistent fail-loud style extended to the gaps |

**Verdict:** fit for research use at institutional standards. The remaining recommendations
(§6) are ranked; the top three concern dividend crediting, equity-based sizing, and the Tier-1
root-cause resampler.

---

## 2. Findings report

Severity · finding · root cause → impact · **status**.

### Critical

1. **yfinance prices are split-adjusted at source; the PIT reader adjusted again**
   (`alpha_data/adapters/yfinance_adapter.py`, `alpha_data/pit.py`).
   Yahoo's chart OHLCV is retroactively split-adjusted; `auto_adjust=False` only skips the
   dividend adjustment (verified against yfinance's own `utils.auto_adjust`/`back_adjust`
   sources — the fixture suite had encoded the wrong vendor assumption). The PIT reader then
   applied the split again: once a split was known, every pre-ex bar was double-divided
   (AAPL 2019 close read ≈$18 instead of ≈$73) and a fake ~ratio-sized jump appeared at each
   ex-date — catastrophic for any strategy on a split symbol. The prior "live spine verified"
   run could not have caught it: its fetch window contained no ex-date.
   **FIXED** — parser reconstructs raw prices from in-window split events (volume and dividend
   amounts rescaled to traded basis), with a fail-loud cross-ex-date discontinuity check that
   refuses the frame if Yahoo's convention ever drifts. `PARSER_VERSION` → 2.

### High

2. **Tier-1 surrogate crediting bias produced false headline-gate FAILs**
   (`_surrogate.py`, `_gauntlet.py`; pre-documented in
   `docs/investigations/2026-06-23-tier1-surrogate-crediting-bias.md`, never implemented).
   The close-fill surrogate diverges from the engine's t+1-open fills by Σ(gap×Δweight) —
   structural for high-turnover strategies (sign-flipping on near-zero-edge books).
   **FIXED** (investigation §7.1 + §7.3) — the gauntlet scores the *same* surrogate weights
   under both conventions on the real opens, records `convention_divergence` in the manifest
   (schema v2), and demotes a Tier-1 FAIL to advisory only when Tier-2 passed and divergence
   exceeds `--tier1-divergence-tol` (0.25). Tier-1's observed statistic and null are now scored
   on the walk-forward OOS window (§7.3), the same window every other gate measures.

3. **Tier-2 synthetic paths spliced raw price levels** (`_synth.py`).
   Block seams jumped between absolute price levels (e.g. 380→110, a fictitious −70% overnight
   move on any trending series), polluting the null's volatility/signal structure — and
   flattering observed runs (a negative-Sharpe fixture ranked above half its distorted nulls).
   **FIXED** — relative-bar chaining: each picked row contributes its own overnight gap and
   intrabar H/O-L/O-C/O shape to a running level; continued blocks are exact scaled copies.

4. **Default config strands stale long positions** (`base.py`/`ts_momentum.py` × CLI defaults;
   **empirically confirmed**: 10/20 orders denied, position stuck long through a 60-bar
   downtrend, 1.30M vs 1.61M final equity vs the correctly-specified long-flat book).
   Every command defaulted to `allow_short=True` on a CASH account; the venue denies a
   short-entry SELL wholesale, so the strategy cannot even flatten.
   **FIXED** — `run_full_backtest` rejects the combination with guidance; `--allow-short`
   defaults tri-state by account (MARGIN→True, CASH→False).

5. **`--snapshot` was provenance-only** (`_runner.load_bars`).
   Runs always read the live store (which `data pull` wholesale-replaces) while stamping the
   snapshot id into manifest and run_id — "same snapshot → same results" was false.
   **FIXED** — with `--snapshot` the read is rooted at the snapshot (same store layout) after
   `verify_snapshot` re-hashes it.

6. **Dividend cash never credited anywhere** (`pit.dividends_as_of` has no consumer).
   Equity total returns systematically excluded dividends; the two-clock channel existed but the
   engine hook was never built. **FIXED (follow-up)** — the equity recorder entitles the pre-ex
   holding and credits cash at pay date (shorts debited); dividends load snapshot-aware and
   thread through backtest/validate (observed + Tier-2 nulls)/optim/portfolio/prop-firm.

### Medium

7. **Fill-session fee invisible in the equity curve; final-session fills lost** (`engine.py`;
   **empirically confirmed**: fee surfaced one session late; a last-quote fill's fee never
   appeared, overstating `final_equity`). **FIXED** — terminal re-sample after `engine.run()`;
   the (intentional) intra-curve sampling convention is now documented instead of misdocumented.
8. **Portfolio inverse-vol weights were look-ahead** (`_portfolio.py`) — one static weight per
   leg from its FULL OOS volatility (future vol re-weighted the past; proven by a future-poison
   test that fails on the old code). **FIXED** — causal per-date trailing-window weights.
9. **Split applied between announce and ex** (`pit.py`) — a known-but-future split rescaled the
   whole visible series away from traded prices. **FIXED** — price channel now gated on
   `ex_date <= as_of` (knowledge still gates visibility).
10. **Non-atomic wholesale-replace writes** (`store.py`, `_artifacts.py`) — a crash mid-pull
    destroyed the only copy; a crash mid-run left a manifest-visible run with missing series.
    **FIXED** — temp-file + `os.replace`; manifest written last.
11. **SPA studentized with i.i.d. std** (`reality_check.py`) — understates the variance of the
    mean on dependent returns. **FIXED** — Hansen's bootstrap long-run variance from the same
    seeded draws.
12. **Unknown `--param`/grid names silently ignored** (`_strategies.py`) — results attributed to
    knobs never applied. **FIXED** — registry declares each strategy's params; typos fail loud.
13. **Run ids/manifests broke the reproducibility contract** (`validate_cmds.py`, `tearsheet.py`)
    — `max_workers` (execution-only) hashed into run_id; manifest omitted `account_type`,
    `null_model`, path counts, thresholds, CPCV geometry. **FIXED** — run_id excludes
    `max_workers`; `RunMetadata` records every result-affecting input.
14. **Web IDE: no CSRF/Host protection on subprocess-spawning POSTs; run_id path traversal**
    (`alpha_web`, `alpha_mcp`, `report_cmds`) — loopback binding does not stop a malicious page
    in the same browser (cross-origin form POSTs reach 127.0.0.1), DNS rebinding forges Host,
    and `../` run ids probed outside `data_dir`. **FIXED** — Host allowlist + foreign-Origin
    rejection middleware; 16-hex run_id validation before any path join (web, MCP, CLI report).
15. **MCP subprocess without timeout** (`alpha_mcp/_invoke.py`) — a hung `alpha` child hung the
    tool call forever. **FIXED** — 1h ceiling with a typed error.
16. **Cross-sectional book was frictionless** (`_cross_sectional.py`) — a fully re-ranking
    dollar-neutral book with zero costs materially overstates edge. **FIXED** — fee+slippage on
    rebalance turnover (defaults matching the other commands).
17. **Prop-firm Monte Carlo resampled the flat warmup span** (`_propfirm.py`) — structural zeros
    diluted pass/bust/payout probabilities. **FIXED** — leading flat span trimmed.
18. **`periods_per_year` hardcoded to 252** across the CLI while ccxt (24/7 crypto) is a
    first-class source — ~20% annualization/sizing skew. **FIXED** — CLI flag, default 252.
19. **CI never gated the lockfile** (`uv sync` without `--locked`); duplicate push+PR runs.
    **FIXED** — `--locked`, concurrency group, timeout, push-on-main only.
20. **Vol-target sizing uses static starting cash, never current equity; no kill-switch**
    (`base.py`). Real risk-control gap on MARGIN (leverage drifts up in drawdowns).
    **FIXED (follow-up, opt-in)** — `--size-on-equity` re-bases sizing on current net-liq and
    `--halt-drawdown F` flattens for good at `peak×(1−F)`; defaults preserve prior results, and
    the gauntlet/optimizer reject the knobs (Tier-1 cannot model equity-path-dependent sizing).

### Low / hardening (all FIXED)

21. `CorporateAction` accepted `ratio=inf`/`amount=inf` (isnan-only check) → `isfinite`.
22. Negative `fee_bps`/`slippage_bps` accepted silently (fees became income) → fail loud.
23. Sub-daily bars silently produced a non-chronological feed (zero-fill runs) → fail loud with
    measured spacing.
24. ccxt stored the in-progress (still-forming) daily candle when `--end` reached today →
    current UTC day excluded (clipping now a pure, tested helper).
25. Stooq ticker interpolated into the request URL unquoted → URL-quoted (`^`/`.` preserved).
26. `snapshot_id` joined into paths unvalidated (`../` escape) → charset-validated.
27. Store accepted duplicate / tz-naive timestamps → fail loud (positional reads assume one
    tz-aware row per session).
28. `garch_paths(df<=2)` gave silent all-NaN paths or raw `ZeroDivisionError` → typed error.
29. Non-integer grid values for integer axes silently truncated (duplicate trials skew
    PBO/DSR/SPA) → fail loud.
30. `GauntletParams(seed=None)` drew OS entropy while the manifest recorded a seed → explicit
    integer required.
31. Web job registry grew unbounded → oldest finished jobs pruned beyond 100.
32. Tear-sheet title (symbol names) flowed into quantstats HTML unescaped → markup stripped.
33. Portfolio/cross-sectional manifest bytes depended on shell argument order; seeds hardcoded
    → canonical sorted symbols, `--seed` resolved from `AlphaSettings`, recorded in manifest.
34. Portfolio/cross-sectional bootstrap CIs aborted on a zero-variance block resample → score 0.
35. Undeclared direct deps (alpha-cli: numpy/polars; alpha-web: anyio); alpha-backtest declared
    never-imported alpha-data; stale yfinance floor → all corrected.
36. 82KB pre-project vendor blueprint at repo root → moved to `research/` with dated name.
37. DSR/CPCV gate fail-branches had no regression tests (an inverted flag would ship green) →
    tests added.

### Findings reviewed and *not* treated as defects
- CPCV's one-sided (post-test) embargo — documented, correct for the daily horizon-1 labels used.
- Prop-firm presets' exact terms (e.g. Topstep lock level) — explicitly illustrative.
- Tier-1's remaining close-fill convention *inside the null* — mitigated by the divergence
  guard; root fix is §6.3.
- The stooq anti-bot gate failing loud — by design.

---

## 3. Improvement report (why / benefit / trade-offs)

Each finding above marked FIXED corresponds to one atomic conventional commit (18 commits;
`git log --oneline main..` reads as the change list). Cross-cutting improvements:

- **Empirical verification harness for engine claims.** Two findings (4, 7) were settled by
  running the real engine, not by reading code; the discriminating fixtures were kept as tests.
- **Future-poison test pattern extended to composition layers** (portfolio weighting) — the
  golden rule's enforcement now covers the layer where the only real look-ahead was found.
- **Reproducibility contract made real**: snapshot read-through + complete manifests + pure
  run ids + canonical ordering + explicit seeds. Trade-off: run ids change for `validate`
  (schema v2), by design; old artifacts remain readable.
- **Honest null distributions** (Tier-1 window + Tier-2 level continuity + SPA long-run
  variance). Trade-off: gate numbers shift versus old runs — the old numbers were the bug.

## 4. New features report (measurable-value additions only)

- `convention_divergence` diagnostic + `flagged_low_fidelity` advisory demotion on the headline
  gate (manifest schema v2) — prevents false FAILs on high-turnover strategies while keeping the
  conservative AND-gate wherever the faithful tier agrees.
- `--tier1-divergence-tol`, `--periods-per-year`, portfolio/cross-sectional `--seed`,
  cross-sectional `--fee-bps/--slippage-bps` CLI knobs.
- Cross-site/DNS-rebinding protection middleware on the web IDE.
- Snapshot integrity verification on read (`--snapshot` now implies `alpha data verify`).

## 5. Breaking changes

Behavioral changes are all bug-fix-motivated; none change public APIs' shapes:

1. Defaults: `--allow-short` now resolves by account type; `CASH + allow_short=True` fails loud
   (was: silent stale longs).
2. `--snapshot` now reads (and verifies) the frozen snapshot (was: live store).
3. `validate` run ids change (gauntlet knobs completed, `max_workers` excluded, schema v2).
4. Headline-gate numbers shift (OOS-window Tier-1, level-continuous Tier-2, flag semantics).
5. yfinance pulls now store reconstructed raw prices (`PARSER_VERSION=2`) — re-pull any stored
   symbol whose window contains a split.
6. Portfolio inverse-vol results change (causal weights); cross-sectional results change
   (frictions); prop-firm probabilities change (warmup trim).
7. Portfolio/cross-sectional symbol order is canonicalized (sorted).

## 6. Remaining recommendations (ranked)

Items 1 (dividend crediting), 2 (equity sizing + kill-switch), 4 (crypto instruments), and 6
(fresh-process byte check) from the original list were implemented in the follow-up commits on
this branch. Still open, ranked:

1. **Tier-1 root-cause fix (investigation §7.2)** — bar-pair `(gap, intraday)` resampling so the
   surrogate can fill at synthetic opens; retires the close-fill convention entirely (the
   divergence guard neutralizes the false-FAIL harm meanwhile).
2. **Exchange-true instrument specs** — the new 5-decimal crypto pair fixes sub-dollar pricing,
   but real per-venue tick sizes, lot sizes, and fee schedules are still generic.
3. **Realistic composed-run fixtures** — most integration fixtures still use
   open=high=low=close bars; the new gapped/dividend fixtures cover the highest-risk paths, but
   broad fixture realism remains worthwhile.
4. **SPA/RC block-length sensitivity** — expose `mean_block` per test and document the
   Politis-White automatic choice as a future refinement (noted in `bootstrap.py`).
5. **GARCH path generation is a Python loop** (~1000 paths × n days × per-step RNG calls);
   vectorize per-path innovations if `--null-model garch` becomes a default workflow.
6. **FRED/macro store** (non-OHLCV) and the multi-instrument engine for full-engine
   cross-sectional — carried over from the roadmap, unchanged.
