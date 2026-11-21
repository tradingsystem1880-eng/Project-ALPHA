---
owner: pattern geometry layer
sources:
  - packages/alpha-patterns/src/**
  - tests/unit/test_pattern_*.py
  - tests/unit/test_*_bias_guard.py
  - tests/bias_guards/test_hs_no_lookahead.py
  - tests/bias_guards/test_pattern_no_lookahead.py
  - tests/bias_guards/test_indicator_no_lookahead.py
  - tests/bias_guards/test_oscillator_no_lookahead.py
  - tests/bias_guards/test_lookalike_future_poison.py
  - tests/unit/test_lookalike.py
  - apps/alpha-cli/src/alpha_cli/*lookalike*.py
verified: 2ba90d5fb0e8531e
---

# Pattern geometry invariants

What must hold in `alpha_patterns` (`packages/alpha-patterns/src/alpha_patterns/`): pure chart-pattern
geometry, swing structure and causal indicators over OHLCV bars. Project-wide look-ahead rules live in
[research integrity § Point-in-time reads](research-integrity.md#point-in-time-reads).

## Package boundary

- Import only `alpha_core` (numpy allowed; nothing here imports polars or pandas) — import-linter contract
  `alpha_patterns depends only on core`. See [engineering § Import layers](engineering.md#import-layers).
  The one outside library is STUMPY, imported lazily inside `lookalike.py` and nowhere else
  ([outside projects](../project/outside-projects.md)); `alpha_patterns/__init__.py` does not import that module.
- Report what was found and when it was knowable — never whether it "works". Intervals, controls against
  the null, multiplicity and significance belong to `alpha_validation` / `alpha_research`, composed by a
  driver above both.
- Current consumers are `alpha_strategies` (`rules.py`, `rule_strategy.py`) and `alpha_cli.chart_cmds`
  (lazily imported). Surfaces (`alpha_web`, `alpha_mcp`) are forbidden by contract from importing this
  package; a new consumer needs an import-linter contract review.
- A rule operand reads exactly the value the chart draws: `operand_series` must equal the
  `alpha chart overlays` series after warm-up. Enforced by `tests/unit/test_rules_indicators_parity.py`.

## Input series

- Every detector consumes the one validated `OHLCV` container from `series.py`. Do not re-validate or accept
  raw arrays elsewhere; fail-loud checks live in one place.
- `OHLCV` raises `DataError` on: mismatched shapes, non-finite values, fewer than two bars, timestamps not
  strictly increasing, high below low, open or close outside the bar range, or a non-positive close.
- `ts` is epoch milliseconds, not datetimes, so no time-zone semantics enter pattern geometry.
- Bad input raises a typed error with context, never a plausible number. The guards are exercised by
  `tests/unit/test_pattern_guards.py` — an unreached `raise` counts as missing.

## Knowable-at timing

General rule: [research integrity § Decide at close, fill at next open](research-integrity.md#decide-at-close-fill-at-next-open).

- Every event carries both `index` (where the structure sits, for geometry) and `confirmed_index` (the first
  bar a live trader could know it). Entries, signals and labels must key on `confirmed_index`; acting at
  `index` reads the future.
- A fractal swing with lookback `L` is confirmable only at `index + L`. Point-in-time questions go through the
  `*_known_by(events, bar)` filters (`swings_known_by`, `dc_known_by`, `extremes_known_by`, `harmonics_known_by`,
  `flags_known_by`), which keep `confirmed_index <= bar`.
- A multi-point pattern is knowable at the latest of its points' confirmations. For head and shoulders the
  right shoulder confirms last; pricing an entry at the head buys hindsight. Enforced by
  `tests/bias_guards/test_hs_no_lookahead.py`.
- Trendlines and breakouts are fitted on the bars before the decision bar, never including it
  (`trendline_fit.py`, flags trendline variant).
- Market-structure levels record the bar at which each level learned of an extreme; directional-change
  confirmation timing depends on how fast price turns and must not be assumed fixed.
- Corrupting every bar after a cut must leave detections at or before the cut byte-identical, and the guard
  must be non-vacuous. Enforced by `tests/bias_guards/test_pattern_no_lookahead.py` and the per-family
  `tests/unit/test_*_bias_guard.py` files (directional change/PIPs, flags, harmonics, market structure,
  trendline fit, runs/entropy/CMMA, visibility/reversibility, volatility indicators).

## Causal indicators

- Indicators, oscillators, cycles and levels use trailing windows only (`values[i-window+1 .. i]`). A centred
  window, a negative shift or a full-sample statistic is a leak.
- Warm-up values are explicit: NaN (or a documented neutral value, e.g. RSI 50) until a full window exists —
  never a value computed from a shorter or future window.
- Enforced by `tests/bias_guards/test_indicator_no_lookahead.py` (indicators and wedges) and
  `tests/bias_guards/test_oscillator_no_lookahead.py` (oscillators, cycles, levels).
- `runs.runs_z` and `alpha_validation.trade_dependence.runs_test` compute the same Wald–Wolfowitz statistic;
  parity is pinned in `tests/oracles/test_differential_runs_test.py`. Change both or neither.
- `vsa.rolling_ols_residual` has a pinned copy in `alpha_data.crypto.features`
  (`tests/unit/test_crypto_defi_tvl_feature.py`). Changing its closed form breaks that parity.
- Undefined values are documented, not invented: `runs_z` is NaN when every sign agrees (zero variance);
  `vsa_indicator` is 0.0 when the fit gate rejects the window; visibility graphs cap the window at
  `MAX_VG_LOOKBACK` (500).
- A harmonic pattern completes on its D bar (`confirmed_index == d`) and its position holds until the next
  extreme is confirmed.

## Lookalikes and novelty

`lookalike.py` is the STUMPY adapter (glue rules: [ADR-0051](../../adr/0051-glue-rules-for-outside-projects.md)).

- Both functions cut the series at their as-of bar before STUMPY sees it. `find_lookalikes` searches only
  `close[:query_start]`, so a match can overlap neither the query nor anything after it; matches are at
  least `exclusion >= window` bars apart. "What happened next" uses only bars up to the query's last bar.
- The threshold is the caller's fixed `max_distance`, recorded in the result. `stumpy.match` is never called:
  its default threshold comes from the whole distance profile and lets later bars change earlier matches.
  Distances come from `stumpy.mass`; flat candidate windows are skipped and counted. "Flat" is a high-low range
  within `NEAR_CONSTANT_RELATIVE` (1e-9) of the window's largest price, passed to STUMPY as its
  `*_subseq_isconstant` array: STUMPY's exact-zero test lets one-ulp jitter rescale to a perfect match.
  Outcome windows that reach the query's own bars are counted (`outcomes_into_query`) and labelled.
- `novelty_score` uses STUMPY's left matrix profile (`stump(...).left_I_`, exclusion zone `ceil(window/4)`)
  and recomputes each left distance from the z-normalised windows; parity with `stumpy.stumpi(...).left_P_`
  is pinned in `tests/unit/test_lookalike.py`. The percentile ranks the latest score against earlier scored
  windows after a declared warm-up (default five windows).
- Outcome summaries (`describe_outcomes`) are descriptive and withheld below `MIN_MATCHES_FOR_SUMMARY` (5).
- The commands (`apps/alpha-cli/src/alpha_cli/lookalike_cmds.py`): `lookalike` searches before the latest
  `--last` bars with `--max-distance` or the declared default (shape correlation 0.80, turned into a
  distance from the window length alone; the basis is stored beside it). Result folders are keyed by the
  settings and the bars' source fingerprint and never rewritten. Every output carries `N=`,
  "descriptive, not a forecast" and a multiple-looks label. Each folder (`lookalike/<id>/`, `unusual/<id>/`)
  holds `figure.png`, then `result.json` with spine-shaped facts. A lookalike run appends an exploratory
  `AlphaTrialV1` row (`rule = "lookalike"`, `run_id` null, no Sharpe, so it never enters a deflated Sharpe);
  `unusual` shows no outcome and records no trial.
- Enforced by `tests/bias_guards/test_lookalike_future_poison.py`: poisoning or cutting every bar after the
  as-of bar leaves matches, outcomes and novelty unchanged; each novelty score equals the score computed with
  as-of at its own last bar; a whole-series search and a two-sided profile (the leaky twins) are caught.

## Ports and provenance

- Code ported from neurotrader888 records its provenance in
  `docs/governance/2026-09-12-neurotrader888-provenance.md` and in the module docstring.
- An upstream repository without a licence is never copied: re-implement from the published formula only
  and say so in the docstring (`cmma.py`).
- A deliberate deviation from upstream is stated in the docstring, not left implicit — e.g. `hawkes.py`
  skips bar 0 instead of upstream's negative-index wrap to the series' last bar, a look-ahead artefact.

## Synthetic ground truth and controls

- `synthetic.py` injects patterns at known indices; a detector must recover exactly those.
  `geometric_brownian_series` alone is the null calibration — how often a detector invents patterns on noise.
- `controls.py` draws matched controls sharing the event's trend state and distance above the trailing low,
  excluding a buffer around each event so a control is never the event seen early.
- Every random draw takes an explicit seed — [research integrity § Deterministic seeds and identity](research-integrity.md#deterministic-seeds-and-identity).

## Code map

Pure chart-pattern geometry and causal indicators over OHLCV bars: swing structure, trendlines,
wedges, head and shoulders, order blocks, fair-value gaps, harmonics and oscillators, plus shape
lookalikes and novelty through STUMPY (`lookalike.py`, the one module that imports it). It imports
only `alpha_core`, numpy and that one library (import-linter contract "alpha_patterns depends only on core");
`alpha_strategies`, `alpha_study` and `alpha_cli` import it. A pattern must only be reported once
it was knowable from the bars seen so far.

- Code: `packages/alpha-patterns/src/alpha_patterns/` (one module per detector or indicator).
- Tests: one unit file per detector in `tests/unit/` (for example `test_wedge.py`, `test_harmonics.py`),
  `tests/unit/test_pattern_*.py`, `tests/unit/test_*_bias_guard.py`; bias guards
  `tests/bias_guards/test_hs_no_lookahead.py`, `test_pattern_no_lookahead.py`,
  `test_indicator_no_lookahead.py`, `test_oscillator_no_lookahead.py`, `test_lookalike_future_poison.py`
  (with `tests/unit/test_lookalike.py`).
- Parity tests pin other packages to this one: `tests/unit/test_rules_indicators_parity.py`
  (strategies read exactly what the chart draws) and `tests/oracles/test_differential_runs_test.py`.
- Check: `uv run python scripts/gate.py check`. This package is not in the quant tier.
- Tests: a no-look-ahead bias guard and a synthetic ground-truth case for every new detector.
