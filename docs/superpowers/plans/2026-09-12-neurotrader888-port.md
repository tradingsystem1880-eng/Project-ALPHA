# neurotrader888 technique port — every public technique as a Project ALPHA asset

```json
{
  "schema_version": 1,
  "title": "neurotrader888 technique port: every public technique as a tested, point-in-time-safe ALPHA asset, exposed through chart overlays, rule operands, figures, the gauntlet, and a governed DefiLlama TVL family",
  "context": "The owner (2026-09-12) wants everything neurotrader888 publishes on GitHub usable inside ALPHA without re-deriving it from videos. The 14 public repos are pandas/matplotlib teaching scripts with no tests, in-sample fits (PIP miner, RSI-PCA), extremes reported at the extreme index rather than the confirmation index, forward-looking pattern returns, global np.random.seed, and dependencies ALPHA does not carry (pyclustering broken on numpy>=1.24, ts2vg, networkx, pandas_ta, sklearn). Thirteen repos are MIT and the owner additionally holds the author's personal approval for full use; IntramarketDifference has no LICENSE and is re-implemented from the published CMMA formula only. Exploration established: alpha_patterns already holds the rolling-window extremes (find_swings + swings_known_by), swing-anchored trendlines, head-and-shoulders, Donchian channel, RSI, ADX, ATR, Hurst; alpha_strategies already ships DonchianBreakout (`breakout`, window sweepable by alpha optim grid) and MovingAverageCrossover (`ma_crossover`); alpha_validation has randomized_price_null with the shared _rank_null (Davison-Hinkley (1+c)/(1+N)) and _synth.synthetic_bar_paths already does the gap/intrabar OHLC decomposition the bar permutation needs; profit factor exists only in native_tearsheet; tearsheet.build_outcomes and _artifacts.write_nulls are generic over null tier names; chart overlays, rule operands and the SPA duplicate the indicator table in four places with no drift test; ADR-0032 forbids adding a crypto family by analogy so DefiLlama TVL needs ADR-0036; api.llama.fi is egress-blocked in the build sandbox. The owner chose full exposure and all edge items.",
  "assumptions": [
    {
      "statement": "No new third-party runtime dependency is needed: k-means++/silhouette, HVG/NVG adjacency with BFS shortest paths, a weighted Gaussian KDE (Scott's rule), Lehmer-code ordinal patterns and OLS residuals are small numpy implementations; scipy is used only inside alpha_research/alpha_validation and in tests as a differential oracle.",
      "verified_by": "uv lock --check unchanged; uv run lint-imports; differential tests against scipy.stats.gaussian_kde, scipy.signal.find_peaks and a brute-force O(n^3) visibility reference"
    },
    {
      "statement": "alpha_patterns stays numpy+polars only and alpha_research cannot import alpha_patterns, so the PIP miner takes pre-extracted window arrays and composition happens in the caller.",
      "verified_by": "uv run lint-imports (contracts 'alpha_patterns depends only on core' and 'alpha_research depends only on core')"
    },
    {
      "statement": "Every detector reports index and confirmed_index and consumers only read the confirmed view, so overlays, rules and features are point-in-time by construction.",
      "verified_by": "future-poison bias guards per module (pytest -m bias_guard), leaky twins for trendline_breakout and the PIP miner label purge"
    },
    {
      "statement": "The existing breakout and ma_crossover strategies satisfy the 'demo strategies' scope; tree_strat is excluded (author-disowned, sklearn not a root dependency).",
      "verified_by": "apps/alpha-cli/src/alpha_cli/_strategies.py:400,414; tests/unit/test_public_seams.py:20 strategy list unchanged"
    },
    {
      "statement": "A walk-forward bar-permutation null joins the gauntlet as a third tier without changing build_outcomes or write_nulls, and its seeds derive from semantic namespaces.",
      "verified_by": "tests/holdout_seed/test_holdout_gauntlet_gates.py contract test; tests/unit/test_gauntlet.py; _seeds.semantic_seed namespaces asserted in RunMetadata"
    },
    {
      "statement": "A DefiLlama family requires its own accepted ADR before any family code lands, and the endpoint shape can only be verified on the owner's machine.",
      "verified_by": "docs/adr/0032 lines 92-96; ADR-0036 acceptance recorded; owner-run pytest -m network smoke and alpha provider check defillama receipt"
    },
    {
      "statement": "Replacing per-indicator pane literals with a generic sub-pane per indicator id and adding a marker annotation kind is one OpenAPI/TS contract change instead of one per indicator.",
      "verified_by": "uv run python scripts/generate_web_openapi.py --check; frontend gate; tests/unit/test_overlay_tables_drift.py"
    }
  ],
  "alternatives_considered": [
    "Vendor the upstream scripts under an author-named folder (rejected: pandas outside the sanctioned edges, unguarded look-ahead one import away from a strategy, cuts across the DAG, no tests).",
    "Add scipy to alpha_patterns for the market-profile KDE (rejected: widens the alpha_strategies transitive surface and the 14-wheel smoke; a 15-line numpy KDE differential-tested against scipy is cheaper).",
    "Add scikit-learn for the PIP miner k-means (rejected: new root dependency and license-matrix entry for ~60 lines of numpy).",
    "Port rolling_window and head_shoulders as new modules (rejected: find_swings/detect_head_shoulders already exist; equivalence is pinned by tests and recorded as not-ported).",
    "Library-only first phase (rejected by the owner, who chose full exposure; kept as the internal ordering A->B->C->E so every surface points at a finished, bias-guarded primitive).",
    "One pane literal per new oscillator (rejected: eight contract changes; generic pane keyed by indicator id is one)."
  ],
  "pre_mortem": [
    "A parity fixture generated from upstream pandas code encodes pandas rolling-quantile interpolation or ewm semantics that the numpy port legitimately differs on -> fixtures carry named tolerances and every deviation is listed per module in the provenance doc.",
    "The PIP miner's Martin-ratio labels cross the training boundary as they do upstream -> fit_pip_clusters raises DataError when end_index + hold > train_end and a bias guard poisons after train_end.",
    "The permutation p-value silently uses count/N and can be zero -> _rank_null is reused, not re-implemented, and the deviation is cited in /verify-quant.",
    "The awareness drift test fails the full gate because a module row was batched into the close-out slice -> every slice adds its rule row in the same commit with one gate.py ack.",
    "A new indicator is added to the CLI but silently dropped by the SPA because pane order, ARITY or marker detection is hard-coded -> generic pane, marker kind, and a Python<->TS table drift test land in E1/E2 before any indicator is exposed.",
    "The 1000-line commit guard blocks A5 or A6 -> both are pre-split into two commits and rows are moved, not squashed.",
    "DefiLlama endpoint drift or ToS forbids retention -> parser is written against a fixture, raw bytes stay private-local per ADR-0032, and the family is reported UNVERIFIED until the owner's live receipt exists.",
    "Visibility-graph shortest paths are O(L^3) per bar and stall the overlay subprocess -> lookback is capped at 500 with DataError and the overlay cache keys on argv.",
    "The in-sample MCPT re-optimises per permutation and takes hours -> it is a separate CLI command with an explicit --perms budget, never part of the default gauntlet.",
    "Mutation kill-rate < 0.90 on a quant module because tests are smoke-shaped -> oracles assert numeric relations (multiset preservation, calibration bands, closed forms)."
  ],
  "slices": [
    {
      "title": "A0 provenance + parity fixtures: governance doc, README row, license-matrix upstream row, upstream-generated JSON fixtures",
      "verify": "uv run python scripts/gate.py plan-check docs/superpowers/plans/2026-09-12-neurotrader888-port.md && ls tests/fixtures/neurotrader",
      "expected": "provenance doc maps every upstream file to an ALPHA module or an explicit not-ported entry; fixtures were generated once in the scratchpad from the pinned upstream SHAs (pandas allowed there only) and carry named tolerances",
      "rollback": "git revert the slice commits",
      "files": [
        "docs/governance/2026-09-12-neurotrader888-provenance.md",
        "docs/governance/README.md",
        "docs/governance/2026-07-19-dependency-license-matrix.md",
        "tests/fixtures/neurotrader/"
      ],
      "status": "done"
    },
    {
      "title": "A1 directional_change.py + pips.py (sigma directional change with confirmed_index/dc_known_by; find_pips euclid/perp/vertical; z-scored pip_windows) + find_swings equivalence test for upstream rolling_window",
      "verify": "uv run pytest -q tests/unit/test_directional_change.py tests/unit/test_pips.py tests/unit/test_dc_pips_bias_guard.py && uv run python scripts/gate.py fast",
      "expected": "synthetic zigzag ground truth recovered; every extreme carries confirmed_index >= index; future-poison after CUT moves nothing known by CUT; rw_top(order=k) == find_swings(lookback=k) except the documented tie rule; parity fixture within tolerance",
      "rollback": "git revert the slice commits",
      "files": [
        "packages/alpha-patterns/src/alpha_patterns/directional_change.py",
        "packages/alpha-patterns/src/alpha_patterns/pips.py",
        "packages/alpha-patterns/src/alpha_patterns/__init__.py",
        ".claude/rules/alpha-patterns.md",
        "tests/unit/test_directional_change.py",
        "tests/unit/test_pips.py",
        "tests/unit/test_dc_pips_bias_guard.py"
      ],
      "status": "done"
    },
    {
      "title": "A2 market_structure.py (LocalExtreme, extremes_sanity_checks raising DataError, streaming ATRDirectionalChange.update, HierarchicalExtremes with lag access)",
      "verify": "uv run pytest -q tests/unit/test_market_structure.py tests/unit/test_market_structure_bias_guard.py && uv run python scripts/gate.py fast",
      "expected": "streaming replay bar by bar equals the batch result; sanity checks reject non-alternating, non-monotone, and inverted extremes; poisoned tail changes no level-n extreme confirmed before CUT",
      "rollback": "git revert the slice commits",
      "files": [
        "packages/alpha-patterns/src/alpha_patterns/market_structure.py",
        "packages/alpha-patterns/src/alpha_patterns/__init__.py",
        ".claude/rules/alpha-patterns.md",
        "tests/unit/test_market_structure.py",
        "tests/unit/test_market_structure_bias_guard.py"
      ],
      "status": "done"
    },
    {
      "title": "A3 trendline_fit.py (LSQ+pivot+step-halving fit_trendlines_single/high_low, trendline_breakout on [i-lookback, i-1], breakout_features meta-label dataset: resist_slope_atr, tl_err_atr, vol_ratio, max_dist_atr, adx, label)",
      "verify": "uv run pytest -q tests/unit/test_trendline_fit.py tests/unit/test_trendline_fit_bias_guard.py && uv run python scripts/gate.py fast",
      "expected": "initial slope equals np.polyfit; optimised support/resistance have zero violations; a leaky twin that includes bar i fails the guard while the shipped function passes; features use only bars <= trade exit",
      "rollback": "git revert the slice commits",
      "files": [
        "packages/alpha-patterns/src/alpha_patterns/trendline_fit.py",
        "packages/alpha-patterns/src/alpha_patterns/__init__.py",
        ".claude/rules/alpha-patterns.md",
        "tests/unit/test_trendline_fit.py",
        "tests/unit/test_trendline_fit_bias_guard.py"
      ],
      "status": "done"
    },
    {
      "title": "A4 harmonics.py (HARMONIC_RATIOS for Gartley/Bat/Butterfly/Crab/DeepCrab/Cypher/Shark, log-ratio error, detect_harmonics over DC extremes) and flags.py (FlagPattern, detect_flags_pips, detect_flags_trendline) as two commits",
      "verify": "uv run pytest -q tests/unit/test_harmonics.py tests/unit/test_flags.py tests/unit/test_harmonics_flags_bias_guard.py && uv run python scripts/gate.py fast",
      "expected": "each named pattern is detected from its ideal ratios and rejected outside tolerance; D confirmed_index equals the DC confirmation; injected pole+channel yields one flag with breakout strictly after confirmation",
      "rollback": "git revert the slice commits",
      "files": [
        "packages/alpha-patterns/src/alpha_patterns/harmonics.py",
        "packages/alpha-patterns/src/alpha_patterns/flags.py",
        "packages/alpha-patterns/src/alpha_patterns/__init__.py",
        ".claude/rules/alpha-patterns.md",
        "tests/unit/test_harmonics.py",
        "tests/unit/test_flags.py",
        "tests/unit/test_harmonics_flags_bias_guard.py"
      ],
      "status": "done"
    },
    {
      "title": "A5 _kde.py (weighted Gaussian KDE, Scott's rule) + market_profile.py (support_resistance_levels, sr_penetration_signal) + hawkes.py (hawkes_process, hawkes_vol_signal) + vsa.py (rolling_ols_residual, vsa_indicator); split into two commits if > 1000 lines",
      "verify": "uv run pytest -q tests/unit/test_market_profile.py tests/unit/test_hawkes.py tests/unit/test_vsa.py tests/unit/test_vol_indicators_bias_guard.py && uv run python scripts/gate.py fast",
      "expected": "numpy KDE matches scipy.stats.gaussian_kde within 1e-9 on the test grid; peaks match scipy.signal.find_peaks; hawkes decay matches the closed form; a planted linear vol->range relation gives zero residual; signal at i uses levels from i-1",
      "rollback": "git revert the slice commits",
      "files": [
        "packages/alpha-patterns/src/alpha_patterns/_kde.py",
        "packages/alpha-patterns/src/alpha_patterns/market_profile.py",
        "packages/alpha-patterns/src/alpha_patterns/hawkes.py",
        "packages/alpha-patterns/src/alpha_patterns/vsa.py",
        "packages/alpha-patterns/src/alpha_patterns/__init__.py",
        ".claude/rules/alpha-patterns.md",
        "tests/unit/test_market_profile.py",
        "tests/unit/test_hawkes.py",
        "tests/unit/test_vsa.py",
        "tests/unit/test_vol_indicators_bias_guard.py"
      ],
      "status": "done"
    },
    {
      "title": "A6 runs.py + entropy.py + cmma.py + indicators.rsi_matrix (commit 1) and visibility.py + reversibility.py (commit 2)",
      "verify": "uv run pytest -q tests/unit/test_runs.py tests/unit/test_entropy.py tests/unit/test_cmma.py tests/unit/test_visibility.py tests/unit/test_reversibility.py tests/unit/test_complexity_bias_guard.py && uv run python scripts/gate.py fast",
      "expected": "textbook Wald-Wolfowitz z reproduced; constant series entropy 0 and iid ~1; VG adjacency equals a brute-force O(n^3) reference; symmetric series reversibility 0; lookback > 500 on VG raises DataError; CMMA cites Masters 2020 only",
      "rollback": "git revert the slice commits",
      "files": [
        "packages/alpha-patterns/src/alpha_patterns/runs.py",
        "packages/alpha-patterns/src/alpha_patterns/entropy.py",
        "packages/alpha-patterns/src/alpha_patterns/cmma.py",
        "packages/alpha-patterns/src/alpha_patterns/indicators.py",
        "packages/alpha-patterns/src/alpha_patterns/visibility.py",
        "packages/alpha-patterns/src/alpha_patterns/reversibility.py",
        "packages/alpha-patterns/src/alpha_patterns/__init__.py",
        ".claude/rules/alpha-patterns.md",
        "tests/unit/test_runs.py",
        "tests/unit/test_entropy.py",
        "tests/unit/test_cmma.py",
        "tests/unit/test_visibility.py",
        "tests/unit/test_reversibility.py",
        "tests/unit/test_complexity_bias_guard.py"
      ],
      "status": "done"
    },
    {
      "title": "A7 HSEvent.pattern_r2 (named for what it measures) + export audit + alpha-patterns rule table complete + uv run pytest -m bias_guard sweep",
      "verify": "uv run pytest -q -m bias_guard && uv run python scripts/gate.py full",
      "expected": "every new module has a rule-table row (test_repo_awareness_drift green), is exported from alpha_patterns, and appears in a bias guard; full gate stamps",
      "rollback": "git revert the slice commits",
      "files": [
        "packages/alpha-patterns/src/alpha_patterns/head_shoulders.py",
        "packages/alpha-patterns/src/alpha_patterns/__init__.py",
        ".claude/rules/alpha-patterns.md"
      ],
      "status": "done"
    },
    {
      "title": "B1 alpha_research/pip_miner.py (numpy kmeans_pp, silhouette_score, martin_ratio, fit_pip_clusters with end_index+hold<=train_end purge, predict_pip_cluster, walk_forward_pip_miner) + oracles",
      "verify": "uv run pytest -q tests/oracles/test_metamorphic_pip_miner.py tests/unit/test_pip_miner_bias_guard.py && uv run python scripts/gate.py full",
      "expected": "planted blobs recovered; silhouette within [-1,1] and maximal at the true k; identical seed gives identical clusters; a training window whose label crosses train_end raises DataError; /verify-quant PASS and /review-gate APPROVE recorded",
      "rollback": "git revert the slice commits",
      "files": [
        "packages/alpha-research/src/alpha_research/pip_miner.py",
        "packages/alpha-research/src/alpha_research/__init__.py",
        ".claude/rules/alpha-research.md",
        "tests/oracles/test_metamorphic_pip_miner.py",
        "tests/unit/test_pip_miner_bias_guard.py",
        ".agents/skills/quant-source-verification/SKILL.md"
      ]
    },
    {
      "title": "B2 alpha_research/retracements.py (segment_ratios, retracement_density) + rolling_pca.py (rolling_pca_scores via eigh, sign fixed by largest loading) + oracles",
      "verify": "uv run pytest -q tests/oracles/test_differential_retracement_kde.py tests/oracles/test_metamorphic_rolling_pca.py tests/unit/test_rolling_pca_bias_guard.py && uv run python scripts/gate.py full",
      "expected": "density matches scipy.stats.gaussian_kde; a planted 0.618 ratio produces the top peak; rolling PCA recovers a planted factor with stable sign across windows; poison after CUT leaves earlier scores unchanged",
      "rollback": "git revert the slice commits",
      "files": [
        "packages/alpha-research/src/alpha_research/retracements.py",
        "packages/alpha-research/src/alpha_research/rolling_pca.py",
        "packages/alpha-research/src/alpha_research/__init__.py",
        ".claude/rules/alpha-research.md",
        "tests/oracles/test_differential_retracement_kde.py",
        "tests/oracles/test_metamorphic_rolling_pca.py",
        "tests/unit/test_rolling_pca_bias_guard.py"
      ]
    },
    {
      "title": "B3 FigureDefinitions only (pip_cluster_examples, retracement_density, mcpt_null_histogram, trade_runs_test; section research; question/uncertainty/caveat required)",
      "verify": "uv run pytest -q tests/unit/test_figure_catalog.py && uv run python scripts/gate.py fast",
      "expected": "catalog_document lists the four ids with builder_not_implemented availability until E5 lands",
      "rollback": "git revert the slice commits",
      "files": [
        "packages/alpha-research/src/alpha_research/figures/catalog.py",
        "tests/unit/test_figure_catalog.py"
      ]
    },
    {
      "title": "C1 alpha_validation/bar_permutation.py (permute_bars, permute_bars_multi: log OHLC gap + intrabar components, separate multisets, prefix <= start_index untouched, shared permutation across markets) + oracles",
      "verify": "uv run pytest -q tests/oracles/test_metamorphic_bar_permutation.py && uv run python scripts/gate.py full",
      "expected": "multisets of gaps and intrabar rows preserved; prefix byte-identical; two markets receive the same order; seed determinism; every permuted bar keeps high>=max(open,close) and low<=min(open,close)",
      "rollback": "git revert the slice commits",
      "files": [
        "packages/alpha-validation/src/alpha_validation/bar_permutation.py",
        "packages/alpha-validation/src/alpha_validation/__init__.py",
        ".claude/rules/alpha-validation.md",
        "tests/oracles/test_metamorphic_bar_permutation.py"
      ]
    },
    {
      "title": "C2 alpha_validation/mcpt.py (permutation_test reusing _rank_null; walk-forward = start_index at train_end) + metrics.profit_factor promoted from native_tearsheet + calibration oracle",
      "verify": "uv run pytest -q tests/oracles/test_calibration_mcpt.py tests/unit/test_native_tearsheet.py && uv run python scripts/gate.py full",
      "expected": "under a no-edge scorer the rejection rate at 0.05 sits inside bernoulli_band; p-value uses (1+c)/(1+N) and the upstream count/N deviation is recorded; native_tearsheet profit factor unchanged byte for byte",
      "rollback": "git revert the slice commits",
      "files": [
        "packages/alpha-validation/src/alpha_validation/mcpt.py",
        "packages/alpha-validation/src/alpha_validation/metrics.py",
        "packages/alpha-validation/src/alpha_validation/native_tearsheet.py",
        "packages/alpha-validation/src/alpha_validation/__init__.py",
        ".claude/rules/alpha-validation.md",
        "tests/oracles/test_calibration_mcpt.py",
        "tests/oracles/_reference/tolerances.py"
      ]
    },
    {
      "title": "C3 alpha_validation/trade_dependence.py (trade_runs_test over Trade.realized_pnl signs ordered by entry_ts; typed None with reason on < 2 signs) + TradeStatistic row in native_tearsheet",
      "verify": "uv run pytest -q tests/oracles/test_differential_runs_test.py tests/unit/test_trade_dependence.py tests/unit/test_native_tearsheet.py && uv run python scripts/gate.py full",
      "expected": "Wald-Wolfowitz 1940 textbook z reproduced; parity with alpha_patterns.runs_z; empty trade log reports unavailable, never NaN",
      "rollback": "git revert the slice commits",
      "files": [
        "packages/alpha-validation/src/alpha_validation/trade_dependence.py",
        "packages/alpha-validation/src/alpha_validation/native_tearsheet.py",
        "packages/alpha-validation/src/alpha_validation/__init__.py",
        ".claude/rules/alpha-validation.md",
        "tests/oracles/test_differential_runs_test.py",
        "tests/unit/test_trade_dependence.py"
      ]
    },
    {
      "title": "C4 gauntlet tier bar_permutation (walk-forward, OOS window only): _gauntlet.py call beside Tier-2, _seeds namespaces validation.bar_permutation_wf, GauntletParams + RunMetadata knobs, validate_cmds third tier tuple, tests/holdout_seed contract test",
      "verify": "uv run pytest -q tests/unit/test_gauntlet.py tests/holdout_seed/test_holdout_gauntlet_gates.py tests/integration/test_validate_cli.py && uv run python scripts/gate.py full",
      "expected": "a failing bar_permutation tier vetoes the null gate; nulls parquet carries the third tier; run identity changes when the knob changes; /review-gate APPROVE bound to the tree",
      "rollback": "git revert the slice commits",
      "files": [
        "apps/alpha-cli/src/alpha_cli/_gauntlet.py",
        "apps/alpha-cli/src/alpha_cli/_seeds.py",
        "apps/alpha-cli/src/alpha_cli/validate_cmds.py",
        "packages/alpha-validation/src/alpha_validation/tearsheet.py",
        ".claude/rules/alpha-cli.md",
        ".claude/rules/quant.md",
        "tests/holdout_seed/test_holdout_gauntlet_gates.py",
        "tests/unit/test_gauntlet.py"
      ]
    },
    {
      "title": "C5 in-sample MCPT composer alpha_cli/_mcpt.py + `alpha optim mcpt SYM --strategy breakout --grid window=... --perms N` (re-optimises per permutation via _optim.run_optimization; writes mcpt_null.parquet; documented as an optimisation-overfit test, never OOS evidence) + info commands catalog + public seams",
      "verify": "uv run pytest -q tests/unit/test_mcpt_cli.py tests/unit/test_public_seams.py tests/integration/test_info_catalog_cli.py && uv run python scripts/gate.py full",
      "expected": "a 3-config grid with 5 permutations on the synthetic fixture completes deterministically twice with identical artifact bytes; seeds derive from validation.bar_permutation_is/<perm>",
      "rollback": "git revert the slice commits",
      "files": [
        "apps/alpha-cli/src/alpha_cli/_mcpt.py",
        "apps/alpha-cli/src/alpha_cli/optim_cmds.py",
        "apps/alpha-cli/src/alpha_cli/_artifacts.py",
        "apps/alpha-cli/src/alpha_cli/info_cmds.py",
        ".claude/rules/alpha-cli.md",
        "tests/unit/test_mcpt_cli.py",
        "tests/unit/test_public_seams.py"
      ]
    },
    {
      "title": "D0 ADR-0036 DefiLlama DeFi TVL as a supplemental research family (authority DefiLlama, market_type network, never execution-price evidence, attribution/retention notes, raw bytes private-local only) + index + CLAUDE.md reference",
      "verify": "uv run pytest -q tests/unit/test_repo_awareness_drift.py",
      "expected": "ADR accepted by the owner and referenced from the docs union; no family code lands before acceptance",
      "rollback": "git revert the slice commits",
      "files": [
        "docs/adr/0036-defillama-tvl-supplemental-family.md",
        "docs/adr/README.md",
        "CLAUDE.md",
        "docs/governance/README.md"
      ]
    },
    {
      "title": "D1 alpha_data/crypto/providers/defillama.py (closed _ENDPOINTS, defillama_url, fetch_defillama with host prefix + fetch_bounded, parse_chain_tvl -> chain/observed_at/tvl_usd/available_at) + contracts/capabilities/research family rows",
      "verify": "uv run pytest -q tests/unit/test_crypto_defillama.py tests/unit/test_crypto_contracts.py tests/unit/test_crypto_research_eligibility.py && uv run python scripts/gate.py fast",
      "expected": "unknown params and foreign hosts raise DataError; fixture bytes parse to a qualified frame; available_at is the next UTC day boundary; family rejected for execution_price purpose. Endpoint shape UNVERIFIED in the sandbox (egress-blocked) until the owner runs the live smoke",
      "rollback": "git revert the slice commits",
      "files": [
        "packages/alpha-data/src/alpha_data/crypto/providers/defillama.py",
        "packages/alpha-data/src/alpha_data/crypto/contracts.py",
        "packages/alpha-data/src/alpha_data/crypto/capabilities.py",
        "packages/alpha-data/src/alpha_data/crypto/research.py",
        ".claude/rules/alpha-data.md",
        "tests/unit/test_crypto_defillama.py",
        "tests/fixtures/defillama/"
      ]
    },
    {
      "title": "D2 provider registration + acquisition: providers.py _definition(defillama), verification receipt, crypto_data_cmds page budget + _defillama_parser_at + _acquire_result branch, network smoke",
      "verify": "uv run pytest -q tests/unit/test_provider_registry.py tests/integration/test_crypto_data_cli.py && uv run python scripts/gate.py full ; owner: uv run pytest -m network -q tests/integration/test_crypto_reference_live.py && uv run alpha provider check defillama",
      "expected": "alpha crypto-data acquire --family defi_tvl freezes raw bytes to a receipt before publishing parquet; provider check records a receipt on the owner's machine",
      "rollback": "git revert the slice commits",
      "files": [
        "apps/alpha-cli/src/alpha_cli/providers.py",
        "apps/alpha-cli/src/alpha_cli/crypto_data_cmds.py",
        "apps/alpha-cli/src/alpha_cli/provider_readiness.py",
        "tests/unit/test_provider_registry.py",
        "tests/integration/test_crypto_data_cli.py",
        "tests/integration/test_crypto_reference_live.py"
      ]
    },
    {
      "title": "D3 defi_tvl_residual feature (rolling log-log OLS via alpha_patterns.vsa.rolling_ols_residual, ATR-normalised, positive lags only, available_at propagated) + CryptoFamilyValue OpenAPI/TS regeneration + bias guard",
      "verify": "uv run pytest -q tests/unit/test_crypto_features.py tests/bias_guards/test_crypto_features_future_poison.py && uv run python scripts/gate.py full && cd apps/alpha-web/frontend && npm run lint -- --deny-warnings && npm run test:coverage && npm run generate:api && npm run build && npm run test:e2e",
      "expected": "feature availability never precedes any input availability; poisoned future TVL rows leave earlier residuals unchanged; generated.ts carries defi_tvl",
      "rollback": "git revert the slice commits",
      "files": [
        "packages/alpha-data/src/alpha_data/crypto/features.py",
        "apps/alpha-web/src/alpha_web/api/models.py",
        "apps/alpha-web/frontend/src/api/generated.ts",
        "apps/alpha-web/frontend/openapi.json",
        "tests/unit/test_crypto_features.py",
        "tests/bias_guards/test_crypto_features_future_poison.py"
      ]
    },
    {
      "title": "E1 chart overlays CLI + models: indicators hawkes/vsa/runs_z/perm_entropy/cmma/vg_path/reversibility/rsi_pc1, patterns dc_extremes/pips/market_profile/harmonics/flags/structure_levels; generic sub-pane per indicator id; ChartAnnotation.kind gains marker; per-indicator longest window guard; *_known_by filters",
      "verify": "uv run pytest -q tests/unit/test_chart_overlays.py tests/unit/test_chart_overlays_bias_guard.py tests/integration/test_web_api_overlays.py && uv run python scripts/generate_web_openapi.py --check && uv run python scripts/gate.py full",
      "expected": "every new id is in the bias-guard ARGS and bars after --end change nothing; each pattern reason names the bar it became drawable; OpenAPI regenerated",
      "rollback": "git revert the slice commits",
      "files": [
        "apps/alpha-cli/src/alpha_cli/chart_cmds.py",
        "apps/alpha-web/src/alpha_web/api/models.py",
        "apps/alpha-web/src/alpha_web/_candles.py",
        ".claude/rules/alpha-cli.md",
        "tests/unit/test_chart_overlays.py",
        "tests/unit/test_chart_overlays_bias_guard.py"
      ]
    },
    {
      "title": "E2 SPA overlays: chartOverlaysModel (ARITY, INDICATOR_PRESETS, PATTERNS/PATTERN_LABEL, pane order derived from response, marker kind branch, legend), PriceChartCanvas colours/pane heights, ChartAnnotationPrimitive marker style, IndicatorsDialog; TS/Python indicator-table drift test; committed static/app",
      "verify": "cd apps/alpha-web/frontend && npm run lint -- --deny-warnings && npm run test:coverage && npm run generate:api && npm run build && npm run test:e2e && uv run pytest -q tests/unit/test_overlay_tables_drift.py",
      "expected": "new indicators render in their own panes and markers draw at confirmed bars; the drift test pins chart_cmds.INDICATORS == TS ARITY; static/app clean",
      "rollback": "git revert the slice commits",
      "files": [
        "apps/alpha-web/frontend/src/panels/chartOverlaysModel.ts",
        "apps/alpha-web/frontend/src/panels/chartOverlaysModel.test.ts",
        "apps/alpha-web/frontend/src/components/PriceChartCanvas.tsx",
        "apps/alpha-web/frontend/src/components/ChartAnnotationPrimitive.ts",
        "apps/alpha-web/frontend/src/components/IndicatorsDialog.tsx",
        "apps/alpha-web/src/alpha_web/static/app/",
        "tests/unit/test_overlay_tables_drift.py"
      ]
    },
    {
      "title": "E3 rule operands hawkes/vsa/runs_z/perm_entropy/cmma/reversibility/vg_path in alpha_strategies.rules (INDICATOR_ARITY, bars_needed, operand_series, float-param parse path) + parity rows + run-identity test; resolve the rsi/macd warm-up exception instead of growing it",
      "verify": "uv run pytest -q tests/unit/test_rules_spec.py tests/unit/test_rules_indicators_parity.py tests/unit/test_rules_bias_guard.py tests/unit/test_run_identity_rules.py && uv run python scripts/gate.py full",
      "expected": "chart series and operand series agree bar for bar with warmup == bars_needed-1 for every indicator; a spec using vsa:168 forks the run id; /review-gate if _runner or _identity is touched",
      "rollback": "git revert the slice commits",
      "files": [
        "packages/alpha-strategies/src/alpha_strategies/rules.py",
        ".claude/rules/alpha-strategies.md",
        "tests/unit/test_rules_spec.py",
        "tests/unit/test_rules_indicators_parity.py",
        "tests/unit/test_rules_bias_guard.py",
        "tests/unit/test_run_identity_rules.py"
      ]
    },
    {
      "title": "E4 SPA rule builder: ruleBuilderModel ARITY/FIELDS/OPERAND_EXAMPLES + tests + static/app",
      "verify": "cd apps/alpha-web/frontend && npm run lint -- --deny-warnings && npm run test:coverage && npm run generate:api && npm run build && npm run test:e2e",
      "expected": "the picker offers the new operands and parses them identically to the CLI; validation stays a report",
      "rollback": "git revert the slice commits",
      "files": [
        "apps/alpha-web/frontend/src/panels/ruleBuilderModel.ts",
        "apps/alpha-web/frontend/src/panels/ruleBuilderModel.test.ts",
        "apps/alpha-web/src/alpha_web/static/app/"
      ]
    },
    {
      "title": "E5 figure builders mcpt_null_histogram (reads mcpt_null.parquet), pip_cluster_examples, retracement_density, trade_runs_test + BUILDERS keys + reportModel research leaf + synthetic run tests",
      "verify": "uv run pytest -q tests/unit/test_figure_builders_synthetic.py tests/integration/test_figure_builders.py tests/integration/test_figure_builders_reproducible.py && uv run python scripts/gate.py full && cd apps/alpha-web/frontend && npm run lint -- --deny-warnings && npm run test:coverage && npm run generate:api && npm run build && npm run test:e2e",
      "expected": "each builder computes nothing the renderer could not have been handed; byte-stable renders across two runs; every figure id resolves in the SPA report tree",
      "rollback": "git revert the slice commits",
      "files": [
        "apps/alpha-cli/src/alpha_cli/figures/_builders.py",
        "apps/alpha-cli/src/alpha_cli/figures/_sources.py",
        "apps/alpha-web/frontend/src/panels/reportModel.ts",
        "apps/alpha-web/frontend/src/panels/reportModel.test.ts",
        "tests/unit/test_figure_builders_synthetic.py"
      ]
    },
    {
      "title": "Z close-out: BUILD-STATUS append, plan Delivery state Completed, provenance deviations final, /retrospective",
      "verify": "uv run python scripts/gate.py full && uv run python scripts/gate.py brief",
      "expected": "brief reports open plan: none; every slice status done; retrospective written",
      "rollback": "git revert the slice commits",
      "files": [
        "docs/BUILD-STATUS.md",
        "docs/superpowers/plans/2026-09-12-neurotrader888-port.md",
        "docs/governance/2026-09-12-neurotrader888-provenance.md",
        "docs/operations/retrospectives/"
      ]
    }
  ],
  "tier_impact": [
    "quant",
    "risk",
    "protected",
    "bias",
    "determinism"
  ],
  "docs_to_update": [
    ".claude/rules/alpha-patterns.md",
    ".claude/rules/alpha-research.md",
    ".claude/rules/alpha-validation.md",
    ".claude/rules/alpha-cli.md",
    ".claude/rules/alpha-strategies.md",
    ".claude/rules/alpha-data.md",
    ".claude/rules/quant.md",
    ".agents/skills/quant-source-verification/SKILL.md",
    "docs/governance/2026-09-12-neurotrader888-provenance.md",
    "docs/governance/README.md",
    "docs/governance/2026-07-19-dependency-license-matrix.md",
    "docs/adr/0036-defillama-tvl-supplemental-family.md",
    "docs/adr/README.md",
    "CLAUDE.md",
    "docs/BUILD-STATUS.md"
  ],
  "out_of_scope": [
    "tree_strat (author-disowned decision-tree demo; sklearn is not a root dependency).",
    "Any ML model for the trendline meta-label features (none exists upstream; features only).",
    "New nautilus strategies (breakout and ma_crossover already exist).",
    "Copying any source or fixture from IntramarketDifference (no licence); CMMA is re-implemented from Masters 2020.",
    "Redistribution of DefiLlama bytes or any hosted surface for them.",
    "Changing the MCP tool pin (62), the DAG, or any import-linter contract."
  ],
  "files": []
}
```

## Why a port, not a vendored copy

1. **Look-ahead is the product risk.** Several scripts confirm a pattern at bar `i` but report it
   at the extreme's index (`rw_extremes`, `directional_change`), evaluate "pattern return" by
   reading `head_width` bars forward, or fit on the full sample (PIP miner, RSI-PCA). ALPHA's
   contract is *knowable-at* timing (`Swing.confirmed_index`, `swings_known_by`) plus a
   future-poison `bias_guard` per detector. Vendoring would put unguarded look-ahead one import
   away from a strategy.
2. **The DAG decides the layer, not the source repo.** `alpha_patterns` is geometry and
   trailing-window series with no inference (precedent: `cycles.py` holds Hurst and variance-ratio
   z-scores); `alpha_research` is inference, density estimation and ML; `alpha_validation` is
   gauntlet nulls; only `alpha_cli` may optimise a strategy inside a permutation loop.
3. **Determinism.** `np.random.seed` globals become explicit `seed` parameters, derived by the CLI
   with `alpha_cli._seeds.semantic_seed(master, "validation.bar_permutation.<mode>")`.
4. **Fail loud.** The scripts silently return 0/NaN on degenerate windows. ALPHA raises
   `DataError` or returns a typed `None`-with-reason, as `native_tearsheet.profit_factor` does.

Each ported function carries a docstring line
`Provenance: github.com/neurotrader888/<repo>/<file>@<sha> (MIT); adapted: <what changed and why>`;
`docs/governance/2026-09-12-neurotrader888-provenance.md` maps every upstream file to a module or
an explicit not-ported entry.

## Upstream inventory (verified 2026-09-12)

| Repo @ head | Technique(s) | Deps replaced | Notes |
|---|---|---|---|
| TechnicalAnalysisAutomation @ da99c20 (MIT) | rolling_window; directional_change; perceptually_important; head_shoulders; flags_pennants; harmonic_patterns (Gartley/Bat/Butterfly/Crab/DeepCrab/Cypher/Shark); retracement_ratios; mp_support_resist; trendline_automation; pip_pattern_miner + wf_pip_miner | scipy kde/find_peaks, pandas_ta, pyclustering | PIP miner labels cross the training boundary; H&S forward return; extremes at extreme index |
| TrendLineAutomation @ 63b1429 (MIT) | fit_trendlines_single/high_low, optimize_slope, check_trend_line | none | clean |
| TrendlineBreakoutMetaLabel @ 874d938 (MIT) | trendline_breakout; trendline_breakout_dataset (5 features + label) | pandas_ta | no ML model upstream |
| mcpt @ 2c0d70c (MIT) | bar_permute.get_permutation; in-sample and walk-forward MCPT; donchian/moving_average demos; tree_strat | tqdm, sklearn | p-value lacks +1; global seed |
| market-structure @ 36a7d89 (MIT) | LocalExtreme + sanity checks; ATRDirectionalChange; HierarchicalExtremes | none | streaming already PIT-friendly |
| VolatilityHawkes @ 51c8557 (MIT) | hawkes_process; vol_signal | pandas_ta | clean |
| VSAIndicator @ a95bf30 (MIT) | vsa_indicator | pandas_ta, scipy | window includes bar i (documented) |
| RSI-PCA @ f3b9735 (MIT) | multi-period RSI matrix; PCA via eigh | pandas_ta, seaborn | full-sample fit → rolling |
| IntramarketDifference (no LICENSE) | CMMA; intermarket difference; threshold-revert signal | pandas_ta | re-implemented from Masters 2020 only |
| TradeDependenceRunsTest @ 5f63804 (MIT) | Wald–Wolfowitz runs_test; rolling runs indicator | none | clean |
| TimeSeriesReversibility @ 3d76b9e (MIT) | ordinal patterns; KL reversibility (Zanin 2018); relative asynchronous index (Yang & Shang 2018) | ts2vg | cite papers |
| TimeSeriesVisibilityGraphs @ d646293 (MIT) | ts_to_vg NVG/HVG; shortest-path indicator | networkx, ts2vg | BFS replaces networkx |
| PermutationEntropy @ 890da37 (MIT) | ordinal_patterns; permutation_entropy | none | clean |
| TVLIndicator @ 00745d0 (MIT) | rolling log-log OLS TVL→close, ATR-normalised | requests | new governed family (ADR-0036) |

## Layer map

| Technique | Module | Public API | Look-ahead handling |
|---|---|---|---|
| Directional change | `alpha_patterns/directional_change.py` | `DCExtreme(index, confirmed_index, price, kind)`, `directional_change(bars, sigma)`, `dc_known_by(exts, bar)` | extreme knowable at the first bar retracing ≥ sigma |
| PIPs | `alpha_patterns/pips.py` | `find_pips(values, n_pips, *, distance)`, `pip_windows(close, *, lookback, n_pips, stride)` | closed window ending at `end_index` |
| Market structure | `alpha_patterns/market_structure.py` | `LocalExtreme`, `extremes_sanity_checks`, `ATRDirectionalChange.update(i, bars)`, `HierarchicalExtremes(levels, atr_lookback)`, `get_level_high/low(level, lag)` | streaming `update(i)` reads bars ≤ i |
| Trendline fit / breakout / meta-label features | `alpha_patterns/trendline_fit.py` | `fit_trendlines_single`, `fit_trendlines_high_low`, `trendline_breakout(close, lookback)`, `breakout_features(bars, lookback)` | fit on `[i−lookback, i−1]`, project to i; label from bars ≤ exit |
| Harmonics | `alpha_patterns/harmonics.py` | `HARMONIC_RATIOS`, `HarmonicPattern`, `detect_harmonics(exts, tolerance)` | D's `confirmed_index` = DC confirmation |
| Flags / pennants | `alpha_patterns/flags.py` | `FlagPattern`, `detect_flags_pips`, `detect_flags_trendline` | confirmed at window end; breakout strictly after |
| Market profile S/R | `alpha_patterns/market_profile.py` + `_kde.py` | `weighted_gaussian_kde`, `support_resistance_levels`, `sr_penetration_signal` | levels at i from `[i−lb+1, i]`; signal at i uses levels from i−1 |
| Hawkes volatility | `alpha_patterns/hawkes.py` | `hawkes_process(values, kappa)`, `hawkes_vol_signal(close, hawkes, lookback)` | causal recursion; trailing quantiles |
| VSA + OLS residual | `alpha_patterns/vsa.py` | `rolling_ols_residual(x, y, window, *, min_r2, require_positive_slope)`, `vsa_indicator(bars, norm_lookback=168)` | inclusive window, documented |
| Runs z | `alpha_patterns/runs.py` | `runs_z(signs)`, `rolling_runs_z(close, lookback)` | trailing |
| Permutation entropy | `alpha_patterns/entropy.py` | `ordinal_patterns(values, d)`, `permutation_entropy(values, *, d, mult)` | trailing `d!·mult` |
| Visibility graphs | `alpha_patterns/visibility.py` | `visibility_graph(values, *, horizontal)`, `average_shortest_path(adj)`, `rolling_vg_shortest_path(close, lookback)` | per-window; `lookback ≤ 500` |
| Reversibility | `alpha_patterns/reversibility.py` | `perm_ts_reversibility(values, d)`, `relative_async_index(values)`, rolling variants | per-window |
| CMMA / intermarket | `alpha_patterns/cmma.py` | `cmma(bars, lookback, atr_lookback)`, `intermarket_difference(a, b)`, `threshold_revert_signal(diff, threshold)` | trailing; sequential state machine |
| RSI matrix | `alpha_patterns/indicators.py` | `rsi_matrix(close, periods)` | trailing |
| PIP cluster miner | `alpha_research/pip_miner.py` | `kmeans_pp`, `silhouette_score`, `martin_ratio`, `fit_pip_clusters(windows, end_index, forward_returns, *, train_end, hold, k_range, seed)`, `predict_pip_cluster`, `walk_forward_pip_miner` | `end_index + hold ≤ train_end` purge; predictions only after `train_end` |
| Retracement density | `alpha_research/retracements.py` | `segment_ratios`, `retracement_density(ratios, grid)` | descriptive over supplied extremes |
| Rolling PCA | `alpha_research/rolling_pca.py` | `rolling_pca_scores(matrix, *, window, n_components)` | trailing covariance, sign fixed by largest loading |
| Bar permutation | `alpha_validation/bar_permutation.py` | `permute_bars(open, high, low, close, *, start_index, rng)`, `permute_bars_multi` | prefix ≤ `start_index` byte-identical |
| MCPT | `alpha_validation/mcpt.py` | `permutation_test(ohlc, score, *, n_perms, start_index, seed, threshold) -> NullResult` | walk-forward = `start_index` at train end; in-sample is an optimisation-overfit test only |
| Trade dependence | `alpha_validation/trade_dependence.py` | `trade_runs_test(pnl) -> RunsTestResult | None` | post-hoc trade record |
| In-sample MCPT composer | `alpha_cli/_mcpt.py` + `alpha optim mcpt` | re-optimises via `_optim.run_optimization` per permutation, writes `mcpt_null.parquet` | CLI-only composition |
| DefiLlama TVL | `alpha_data/crypto/providers/defillama.py`, `crypto/features.py::defi_tvl_residual` | closed endpoints, `parse_chain_tvl`, ATR-normalised OLS residual | `available_at` = next UTC day boundary; positive lags only |

Not ported (equivalence pinned by tests, recorded in the provenance doc): `rolling_window`
(≡ `find_swings`; tie handling differs), `head_shoulders` (only `neckline_r2` added to `HSEvent`),
`donchian`/`moving_average` demos (`breakout`/`ma_crossover` exist), `tree_strat`.

## Surface design decisions (Plan E)

- One generic sub-pane per indicator id (`pane = spec.id`, `price` sentinel) replaces the closed
  per-indicator `Pane` literal; `SUB_PANE_ORDER` derives from response order.
- `ChartAnnotation.kind` gains `"marker"`; the SPA branches on `kind`, not on label prefixes.
- Level sets reuse the two-anchor horizontal line the Fib grid already emits.
- Every pattern passes a `*_known_by(last)` filter and its `reason` names the bar it became drawable.
- A drift test pins `chart_cmds.INDICATORS`, `rules.INDICATOR_ARITY` and the TS `ARITY`/`FIELDS`.
- Rule operands: single-series only; PIP/MCPT never become operands (rules cannot see `alpha_research`).
- Figures compute nothing: builders read `mcpt_null.parquet`, `trades.parquet` sidecar stats, or
  research artifacts; `research` section gets a claiming leaf in `reportModel.ts`.

## Execution order and obligations

A (A0–A7) → B (B1–B3) → C (C1–C5) → E (E1–E5); D (D0–D3) after A5 (needs `rolling_ols_residual`),
interleaved. Every slice: failing test → minimal code → `__init__` export → rule-table row
(`gate.py ack`) → `gate.py fast` → `gate.py full` → conventional commit under 1000 non-docs lines.
B and C slices additionally owe `/verify-quant` PASS before Stop and `/review-gate` APPROVE before
commit, with primary sources: Arthur & Vassilvitskii 2007, Rousseeuw 1987, Martin & McCann 1989,
Scott 1992, Chung et al. 2001, Jolliffe 2002, Masters 2018 (permutation tests), Wald & Wolfowitz
1940, Davison & Hinkley 1997, Bandt & Pompe 2002, Zanin et al. 2018, Yang & Shang 2018,
Lacasa et al. 2008 (visibility graphs). C4 touches risk-tier `_gauntlet.py`/`_seeds.py`.

## Program acceptance

- `uv run pytest -m bias_guard -q` green with every new module represented.
- `uv run alpha chart overlays <SYM> -i hawkes:0.1:168 -p market_profile --json` returns
  `authority: none` rows whose values do not change when bars after `--end` are poisoned.
- `uv run alpha rules validate` accepts a spec using `vsa:168`; the run id differs from the same
  spec without it.
- `uv run alpha optim mcpt <SYM> --strategy breakout --grid window=20,55,100 --perms 50` writes a
  null artifact twice with identical bytes and `alpha figures render <run> mcpt_null_histogram`
  renders it.
- `alpha provider check defillama` records a receipt on the owner's machine (UNVERIFIED in the
  sandbox: `api.llama.fi` is egress-blocked).
