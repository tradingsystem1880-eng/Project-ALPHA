---
owner: research primitives
sources:
  - packages/alpha-research/src/**
  - tests/unit/test_research_*.py
  - tests/bias_guards/test_research_*.py
  - tests/bias_guards/test_market_state_future_poison.py
  - tests/bias_guards/test_poison_variants.py
  - tests/unit/test_figure_*.py
verified: 580c5a0fe478
---

# Research primitive invariants

What must hold in `alpha_research` (`packages/alpha-research/src/alpha_research/`): pure, deterministic
primitives for the governed research phases. Phase codes: D0 = synthetic pilot (no market claim),
D1 = preregistered discovery on registered data, D2 = owner-approved one-shot sealed confirmation,
D3 = final holdout, prohibited to research. The phase workflow itself is
[research integrity § Research before strategy](research-integrity.md#research-before-strategy).

## Package boundary

- Quant tier: changes here carry the quant-tier obligations in [engineering § Quant tier](engineering.md#quant-tier),
  and this package's `.py` bytes feed owner-approved implementation hashes — see
  [engineering § Hash-bound source bytes](engineering.md#hash-bound-source-bytes).
- Import only `alpha_core` (numpy, scipy, deterministic Matplotlib allowed) — import-linter contract
  `alpha_research depends only on core`. No `alpha_data`, `alpha_patterns` or `alpha_validation` imports.
- No network, persistence, credentials, broker, scheduler, wall-clock read or dynamic code. Inputs arrive as
  values; `alpha_cli` reads storage, composes and records. The one file read is the packaged theme JSON.
- The package grants no strategy, validation, holdout, paper or execution authority. A primitive's output is
  evidence only after the CLI's governed admission re-verifies it.

## Phase allocation

- `ResearchEvidenceTopology` is the canonical group-atomic 60/20/20 chronological split
  (discovery / confirmation / final holdout). Any other window set raises `DataError`; at least five
  dependency groups are required, and groups must be contiguous, ordered and unique.
- Groups are indivisible: a date/session/dependence group never straddles a boundary. Because cuts are made on
  group counts, a final holdout below 10% of observations is rejected, not warned about.
- A non-zero forward-outcome horizon must be registered. Its final observations in every zone become
  ineligible event anchors; an outcome that would cross a zone boundary raises (`cross_boundary_outcomes: REJECT`).
- Alternative shares exist only as `ResearchEvidenceSharesV1` in `boundary.py`: D0 must be 0 for real groups,
  D1 and D2 positive, D3 at least 20%, total 100%. The event-blind, owner-approved-before-D1 requirement is
  enforced by the CLI, not here.
- `ResearchD2BoundaryV2` (compact, exact membership) is the format for new writes. `ResearchD2BoundaryV1` stays
  byte-identically readable and is never migrated; `research_d2_boundary_from_dict` dispatches on `schema` and
  rejects unknown schemas. Both re-derive and check `boundary_sha256`.
- Tests: `tests/unit/test_research_topology.py`, `tests/unit/test_research_boundary.py`,
  `tests/unit/test_research_d2_boundary.py`.

## Research bars and datasets

- `ResearchDatasetRef.scope` is permanently `research_only`. Research bars never become a daily snapshot,
  execution feed, validation input or paper input ([ADR-0020](../../adr/0020-intraday-event-research-is-not-daily-validation-evidence.md)).
- `ResearchBar` needs aware `start`, `end` and `available_at`, with `available_at` no earlier than `end`, finite
  positive prices and consistent OHLC. `EqualDurationResearchBars` rejects mixed durations, overlaps and disorder.
- `MarketStateV1` reads at session `t` only closes with `available_at` at or before that session's close. Warm-up and
  undefined correlation are explicit abstentions, never imputed; equity and crypto calendars stay separate
  ([ADR-0028](../../adr/0028-governed-market-state-and-model-candidates.md)). Enforced by
  `tests/bias_guards/test_market_state_future_poison.py`.

## Event studies and D1 families

General rule: [research integrity § Point-in-time reads](research-integrity.md#point-in-time-reads).
[ADR-0025](../../adr/0025-empirical-d1-research-runner-admission.md).

- The double-bottom event cannot fire before its second trough is causally confirmable. Enforced by
  `tests/bias_guards/test_research_double_bottom_future_poison.py`.
- Event-study evaluation sees nothing past its explicit cutoff (`tests/bias_guards/test_research_event_study_future_poison.py`).
  It purges overlapping outcomes and matches controls exactly on pre-event covariates.
- Results are "conditional predictive association; not a causal effect". Below ten effective clusters an
  estimate carries a typed low-cluster flag that consumers must surface; two clusters is a hard error.
- Rolling IC, rolling effect size, volatility-regime tags and rolling PCA use trailing windows only. Enforced by
  `tests/bias_guards/test_research_d1_future_poison.py`, `tests/bias_guards/test_research_descriptives_guard.py`,
  `tests/bias_guards/test_poison_variants.py` (extreme-value poison, non-finite poison that must fail loud, and
  leaky twins that must be caught) and `tests/unit/test_rolling_pca_bias_guard.py`.
- Forward returns past the sample end are explicit `None`, never a truncated return. Panel forward returns
  use only `t+h <= T-1`; a date below the `min_names` floor yields `None`; `inf` fails loud; NaN means absent.
- The PIP miner trains only on labels with `end_index + hold <= train_end` and reads only
  `log_close[: train_end + 1]`; an undefined Martin ratio is `None` (`tests/unit/test_pip_miner_bias_guard.py`).
- Panel primitives sort stably over the caller's canonical column order and use no randomness. Oracles:
  `tests/oracles/test_metamorphic_panel.py`, `tests/oracles/test_differential_panel_spearman.py` (scipy).
- Screening and descriptive outputs confer no research-gate authority. The lead-lag leakage diagnostic is an
  advisory screen for plan review, never admission.
- Fama-MacBeth fails loud on a rank-deficient (collinear) date. Descriptive coverage summaries report gaps
  instead of crashing on them.
- The AR(1) effective sample size is conservative, capped at the observation count and versioned
  (`AR1_EFFECTIVE_SAMPLE_SIZE_METHOD_VERSION`); change the version with the method.
- Rolling PCA scores project onto eigenvector columns with each component's largest loading positive (upstream
  projected onto rows). Retracement density fails loud on zero-height segments and degenerate samples.

## Confirmation and multiplicity

General rule: [research integrity § Statistical evidence](research-integrity.md#statistical-evidence).

- `classify_confirmation` is the single mechanical D2 classifier, applied in this order: an invalid reason
  gives `INVALID`; an effective sample below the frozen reliability floor gives `INCONCLUSIVE`; an interval
  wholly against the claim gives `CONTRADICTED`; an adjusted p above the frozen alpha gives `INCONCLUSIVE`;
  `SUPPORTED` only when the interval clears the minimum effect in the claimed direction.
  ([ADR-0027](../../adr/0027-tiered-research-readiness-semantics.md)).
- Low power or a weak effect is `INCONCLUSIVE`, never silently a failed hypothesis.
- Secondary hypotheses are adjusted by Holm over one immutable, preregistered family (`multiple_testing.py`).
- Power is prospective, under an explicit known-sigma model, with an explicit seed (default 7).

## Gate packets

- `build_research_gate_packet` is a pure projection over bounded control-plane inputs. It never reads storage
  and never upgrades synthetic D0 fixtures into empirical support.
- `SUPPORTED` or `advance_to_strategy` requires exactly one typed `SEALED_D2` evidence result bound to the
  active contract, with consumed D2 state for that contract and a classification equal to the owner outcome.
- `advance_to_strategy` is allowed only with outcome `SUPPORTED`. `CONTRADICTED` requires lineage-bound typed
  non-synthetic evidence.
- Untested fields stay `NOT_TESTED` and carry no empirical values or claim.
- The packet's `authority` block is fixed: not strategy-validated, not paper-ready, places no orders, never
  uses the final strategy holdout. Owner decisions are bound to project and active contract —
  [research integrity § Owner authority](research-integrity.md#owner-authority).
- Tests: `tests/unit/test_research_gate_packet.py`.

## D0 recomputation

- D0 acceptance is admitted by exact recomputation of the frozen detector, null, embargo and power criteria
  (composed in `alpha_cli/research_runtime.py` from these primitives), never by a stored pass flag.
- Changing any constant of a registered D0 generation (detector spec, fixture lows, power parameters and seed,
  runtime version) requires bumping that generation's `fixture_version`. Adding a new generation must not bump
  existing versions. A changed primitive here can therefore orphan completed D0 runs.
- D0 and D1 protocol seeds stay frozen at 7 and do not follow settings —
  [research integrity § Deterministic seeds and identity](research-integrity.md#deterministic-seeds-and-identity).
  The crowding plan rejects any `bootstrap_seed` other than 7.

## Figures and charts

- The figure engine draws; it never computes. Every number arrives pre-computed, and each figure ships with
  its catalogued question, uncertainty and caveat text.
- `FigureSpec` cannot express a secondary y-axis; two scales become two stacked panels.
- Rendering is pure and byte-stable within the locked environment: Agg/SVG backends only (never `pyplot`),
  rcParams from `rcParamsDefault`, pinned `svg.hashsalt`, date/software metadata stripped, bundled DejaVu fonts
  required, no `tight_layout`, module-placed ticks. Enforced by `tests/unit/test_figure_render.py` and
  `tests/integration/test_figure_determinism.py`.
- Bump `RENDERER_VERSION` on any visual change; it is folded into `svg.hashsalt`, so old cached figures become
  unreachable rather than stale. Change `FIGURES_CACHE_VERSION` only with `alpha_cli.figure_cache`, kept equal by a drift test.
- The default theme is `terminal_classic.json`; `alpha_dark.json` remains loadable. The SPA canvas tokens are
  generated from the default theme and drift-guarded by `tests/unit/test_theme_drift.py`.
- `render_research_line_chart` emits a byte-stable PNG with no creation timestamp. It seeds every
  rcParam from shipped defaults except `backend`, then applies its style, so process history and local
  Matplotlib configuration cannot change the bytes. The caller's backend is preserved. Clean-process
  hashes and all figure writers' history independence are pinned in `tests/unit/test_figure_history_determinism.py`.
