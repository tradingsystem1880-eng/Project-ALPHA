**Delivery state:** In progress (2026-09-11)

# Edge-first Phase C — a fast, honest screening lane: panel statistics in `alpha_research` and `alpha scan hypotheses`

```json
{
  "schema_version": 1,
  "title": "Edge-first Phase C: cross-sectional panel primitives (IC, IC decay, quantile spread/monotonicity, bucket turnover, Fama-MacBeth, orthogonalisation) in alpha_research and a non-authoritative `alpha scan hypotheses --json` lane over the PIT equity universe and the governed Bybit derivatives dataset",
  "context": "Audit finding F2 (docs/audit/2026-09-10-edge-first-system-audit.md): there is no fast screening lane; `alpha optim grid` runs the full Nautilus engine per cell, the only vectorised path (`_cross_sectional.py`) is a momentum backtest with a hard-coded signal, and `alpha_research/ic.py` is 52 lines with no IC decay, monotonicity, Fama-MacBeth, turnover or orthogonalisation. Phase B produced the data this lane needs: a point-in-time S&P 500 universe (`alpha data universe`) and ~30k governed Bybit manifests (funding, OI, mark/index/premium/derivative bars, top-50 USDT perps from 2022-01-01). Phase D will wire PBO/SPA into the gauntlet using the trial count this scan records, and Phase E will make a scan id the candidate's entry into the governed funnel.",
  "assumptions": [
    {
      "statement": "T×N numpy panels with NaN = 'name absent on that date' and a per-date min_names threshold are a sufficient contract for every primitive; inf anywhere fails loud; a date with fewer than min_names finite pairs yields None, never a value from a degenerate cross-section.",
      "verified_by": "tests/unit/test_panel_primitives.py NaN/inf/min_names cases; tests/oracles/test_metamorphic_panel.py"
    },
    {
      "statement": "`PointInTimeSource.as_of` physically truncates each symbol's bars at as_of, so no outcome can read past as_of; the remaining look-ahead risk is intra-panel (a forward return at row i needs row i+h), handled by the index rule outcome[i,h] defined iff i+h <= n_dates-1 and both closes finite, scored indices = range(warmup, n_dates-h), DataError when fewer than 3 scored dates remain, and per-horizon n_dates reported.",
      "verified_by": "tests/bias_guards/test_hypothesis_scan.py (panel-level poison of rows > n-1-h leaves outcomes at rows <= n-1-h-1 byte-identical; leaky twin using closes[t+1] scores IC≈1 on noise where the real lane scores ≈0)"
    },
    {
      "statement": "Universe membership must be applied per date (alpha_core.members_as_of(memberships, dates[t]) masks a name to NaN before its effective_from and from its effective_to), so pre-inclusion history of names added because they had already won never enters a 252-day signal; a name whose bars end at delisting uses UniverseMembership.delisting_return as the terminal outcome when present, else None counted in `truncated_outcomes`.",
      "verified_by": "tests/bias_guards/test_hypothesis_scan.py membership-mask cases; tests/unit/test_hypothesis_scan_signals.py delisting_return case"
    },
    {
      "statement": "Crypto row availability is derived from the manifest identity `timestamp_convention` (provider_event_utc -> row timestamp; interval_start_utc -> timestamp + frequency; any other value -> DataError), which matches the existing research_crypto_data.py convention; the daily cross-section at date t uses rows available <= t 00:00 UTC, the daily funding mean window is (t-1 00:00, t 00:00], and the 30-day z-score ends at t. Real manifests: funding/open_interest = provider_event_utc (funding identity frequency is `funding_interval`), bars = interval_start_utc.",
      "verified_by": "python3 inventory scan of data/crypto/manifests on 2026-09-11 (221 funding + 180 OI provider_event_utc; 307/280/286/30 bar manifests interval_start_utc); tests/bias_guards/test_hypothesis_scan.py three boundary cases"
    },
    {
      "statement": "CryptoBulkStore.inventory() already calls verify_manifest on every manifest, so inventory + quality.state == 'qualified' + provider == FAMILY_AUTHORITIES[family] is a verified read; concatenating windowed manifests is within ADR-0032 only when dataset identity (venue, market_type, units, timestamp_convention, base/quote asset, frequency) is byte-identical across every selected manifest and overlapping timestamps agree exactly.",
      "verified_by": "packages/alpha-data/src/alpha_data/crypto/storage.py:564-569; tests/unit/test_hypothesis_crypto_panel.py identity-mismatch and overlap-disagreement DataError cases"
    },
    {
      "statement": "A scan_id hashed over normalised INPUTS only (lane, PANEL_VERSION, canonical sorted symbols or universe name + universe file hash, as_of, snapshot_id or 'live', signals, horizons, cost_bps, min_names, sorted crypto manifest ids) is machine-stable; the result table is published under a separate `result_digest` labelled machine-dependent because lstsq/BLAS reductions are not bitwise-stable across builds.",
      "verified_by": "tests/unit/test_hypothesis_scan_signals.py scan_id stability under symbol reordering and result-independence; json.dumps(sort_keys=True, separators=(',',':'), ensure_ascii=True, allow_nan=False) with None->null and -0.0->0.0 pinned by test"
    },
    {
      "statement": "The screening lane is `authority: none` by construction: it writes no run manifest, no run-store entry, no control-store row, and it is excluded from the SPA new-run form because `scan` is already in info_cmds._NON_RUN_COMMAND_PREFIXES.",
      "verified_by": "tests/integration/test_hypothesis_scan_cli.py asserts authority none, no data/runs entry, and JSON-only output; apps/alpha-cli/src/alpha_cli/info_cmds.py:95"
    }
  ],
  "alternatives_considered": [
    "Reuse `_cross_sectional.py` as the scorer (rejected: it is a momentum long/short backtest with a hard-coded signal, intersection-of-dates panel, vol targeting and a bootstrap; a scorer needs a signal matrix input, union-of-dates with per-date membership, and no portfolio construction).",
    "Adopt vectorbt or alphalens (rejected: a new dependency for ~300 lines of numpy; alphalens is pandas-native and unmaintained; the repo's pandas edges are pinned to three vendor seams).",
    "Build the crypto panel over alpha_data.crypto.features (funding_features/open_interest_features) (rejected for this phase: those are single-instrument, stamp one scalar available_at per artifact and gate it >= quality.observed_end, which is the right contract for a research artifact but not for a daily cross-section that needs a row-level availability rule; the row-level rule is documented and bias-guarded here, and the two contracts are cross-referenced).",
    "Generalise D0 to any registered EventTableV1/FactorObservationTableV1 producer in this phase (deferred to Phase E: D0 acceptance is a per-operator runtime, a new alpha_study contract needs an ADR under ADR-0035, and Phase E's funnel compression makes a scan_id the candidate's entry, which supersedes a second entry path).",
    "Newey-West / overlapping-outcome corrections for the Fama-MacBeth and IC t-statistics (rejected: reported as plain t with an explicit `overlapping_outcomes: true` caveat for h > 1; a correction is Phase D gauntlet territory, and a screening lane must not look more rigorous than it is)."
  ],
  "pre_mortem": [
    "A universe name has bars in the store only for part of its membership -> interior NaN per name raises DataError (fail loud on gaps), leading/trailing NaN is listing/delisting and allowed; a mixed calendar (a name whose dates are not a contiguous run of the union) raises DataError.",
    "A name in the universe is absent from the store -> membership is decided against ParquetStore.list_symbols() before load_bars, listed under `missing`, and every DataError from load_bars propagates unchanged (never caught to build the missing list).",
    "The crypto reader silently merges an inverse contract, a USDC quote or a 5m frame with the 1h series -> identity byte-equality across selected manifests is enforced and a mismatch names both manifest ids in the DataError.",
    "np.argsort ties put the same name in different buckets depending on --symbols order -> symbols are canonicalised (sorted) at the panel boundary, bucketing uses argsort(kind='stable') over canonical order, and IC uses average ranks so ties never enter Spearman; the tie policy is documented in the JSON.",
    "fama_macbeth averages a minimum-norm solution on a rank-deficient date -> lstsq rank is checked and the call raises DataError (collinear factors are a caller error).",
    "The scan is treated as evidence -> every payload carries authority none, execution_authority false, `overlapping_outcomes`, `truncated_outcomes`, and per-horizon n_dates; the trial count is recorded so Phase D can charge it.",
    "Live-store equity reads cannot be re-derived after the next pull -> `--snapshot` threads through load_bars and the scan_id records snapshot_id or 'live'; a 'live' scan cannot be a Phase E candidate entry.",
    "Quant-tier obligations are missed -> tests/oracles/test_metamorphic_panel.py + /verify-quant PASS before Stop; /review-gate APPROVE before commit; mutation kill-rate >= 0.90 on alpha_research/panel.py."
  ],
  "slices": [
    {
      "title": "C1 alpha_research/panel.py: cross_sectional_ic, ic_decay + ic_half_life, quantile_returns (spread, monotonicity), bucket_turnover, cost_adjusted_spread, fama_macbeth, orthogonalize — numpy only, NaN = absent, inf fails loud, min_names per date; exported from alpha_research; oracle + metamorphic tests",
      "verify": "uv run pytest -q tests/unit/test_panel_primitives.py tests/oracles/test_metamorphic_panel.py tests/oracles/test_differential_panel_spearman.py && uv run python scripts/gate.py fast && /verify-quant",
      "expected": "Hand-computed 3×6 panel Spearman values reproduced exactly; perfect signal IC=1, reversed -1; Fama-MacBeth recovers known slopes on noiseless data; orthogonalised residuals have zero cross-sectional correlation with controls; constant ranking turnover 0, full reversal 1; QuantVerificationReport PASS",
      "rollback": "git revert the slice commit; no persisted state",
      "files": ["packages/alpha-research/src/alpha_research/panel.py", "packages/alpha-research/src/alpha_research/__init__.py", "tests/unit/test_panel_primitives.py", "tests/oracles/test_metamorphic_panel.py", "tests/oracles/test_differential_panel_spearman.py", "tests/fixtures/panel_fixtures.py", ".claude/rules/alpha-research.md"],
      "status": "in_progress"
    },
    {
      "title": "C2a equity lane: apps/alpha-cli/src/alpha_cli/_hypothesis_scan.py — union-of-dates close panel over a PIT universe or --symbols via _runner.load_bars(as_of, snapshot_id), per-date membership mask, built-in causal price signals (mom_12_1, mom_6_1, rev_1m, vol_63, range_52w), forward-return outcomes by the index rule with delisting_return terminal, scan_id over inputs, result_digest; `alpha scan hypotheses --json [--out PATH]` in scan_cmds.py",
      "verify": "uv run pytest -q tests/unit/test_hypothesis_scan_signals.py tests/integration/test_hypothesis_scan_cli.py tests/bias_guards/test_hypothesis_scan.py && uv run alpha scan hypotheses --universe sp500 --as-of 2025-12-31 --json | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d[\"authority\"], d[\"trials\"], len(d[\"results\"]))'",
      "expected": "authority none; trials = signals×horizons; results carry ic mean/std/icir/t/hit_rate, decay+half_life, spread/monotonicity, turnover, cost-adjusted spread, per-horizon n_dates, truncated_outcomes; bias guards pass and the leaky twin is rejected; wall time seconds on the sp500 universe",
      "rollback": "git revert; --out files are operational JSON under data/scans/ (gitignored) with no authority",
      "files": ["apps/alpha-cli/src/alpha_cli/_hypothesis_scan.py", "apps/alpha-cli/src/alpha_cli/scan_cmds.py", "tests/unit/test_hypothesis_scan_signals.py", "tests/integration/test_hypothesis_scan_cli.py", "tests/bias_guards/test_hypothesis_scan.py", ".claude/rules/alpha-cli.md"],
      "status": "pending"
    },
    {
      "title": "C2b crypto lane: apps/alpha-cli/src/alpha_cli/_crypto_panel.py — verified-inventory read of qualified normalized Bybit manifests (family authority, identity byte-equality, exact-overlap agreement, fetched_at <= as_of), row availability from timestamp_convention, daily panels for funding_z_30d, oi_chg_7d, mom_30d over derivative_bars 1d closes; `alpha scan hypotheses --lane crypto --symbols ... --category linear`",
      "verify": "uv run pytest -q tests/unit/test_hypothesis_crypto_panel.py tests/bias_guards/test_hypothesis_scan.py tests/integration/test_hypothesis_scan_cli.py && uv run alpha scan hypotheses --lane crypto --symbols BTCUSDT,ETHUSDT,SOLUSDT --category linear --as-of 2026-09-01 --json | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d[\"authority\"], d[\"n_manifests\"], len(d[\"results\"]))'",
      "expected": "Panel assembled from thousands of windowed manifests without merging identities; the three availability boundary guards pass (row after t 00:00 ignored, row at exactly t 00:00 and bar starting t-1 00:00 included, manifest fetched after as_of ignored); scan runs in seconds",
      "rollback": "git revert; manifests untouched (read-only)",
      "files": ["apps/alpha-cli/src/alpha_cli/_crypto_panel.py", "apps/alpha-cli/src/alpha_cli/_hypothesis_scan.py", "apps/alpha-cli/src/alpha_cli/scan_cmds.py", "tests/unit/test_hypothesis_crypto_panel.py", ".claude/rules/alpha-cli.md"],
      "status": "pending"
    },
    {
      "title": "C3 docs and closure: BUILD-STATUS Phase C record, alpha-research/alpha-cli rule rows, audit program status, plan Completed; D0 generalisation explicitly deferred to Phase E",
      "verify": "uv run pytest -q tests/unit/test_claude_md_relocation.py tests/unit/test_documentation_truth.py && uv run python scripts/gate.py full",
      "expected": "Zero-loss relocation test green; full gate PASS; plan header Completed",
      "rollback": "docs-only revert",
      "files": ["docs/BUILD-STATUS.md", "docs/audit/2026-09-10-edge-first-system-audit.md", "docs/superpowers/plans/2026-09-11-edge-first-phase-c-screening-lane.md"],
      "status": "pending"
    }
  ],
  "tier_impact": ["quant", "risk", "protected", "bias", "determinism"],
  "docs_to_update": [".claude/rules/alpha-research.md", ".claude/rules/alpha-cli.md", "docs/BUILD-STATUS.md", "docs/audit/2026-09-10-edge-first-system-audit.md"],
  "out_of_scope": ["Any SPA/REST/MCP surface (surface freeze; MCP stays 62)", "D0 generalisation (Phase E)", "PBO/SPA in the gauntlet and cost-model changes (Phase D)", "Newey-West or other overlapping-return corrections", "Fundamentals or intraday equity data", "Binance market_bars in the crypto lane (Bybit derivative_bars 1d is the venue-consistent close)"],
  "files": ["packages/alpha-research/src/alpha_research/panel.py", "packages/alpha-research/src/alpha_research/__init__.py", "apps/alpha-cli/src/alpha_cli/_hypothesis_scan.py", "apps/alpha-cli/src/alpha_cli/_crypto_panel.py", "apps/alpha-cli/src/alpha_cli/scan_cmds.py", "tests/unit/test_panel_primitives.py", "tests/oracles/test_metamorphic_panel.py", "tests/oracles/test_differential_panel_spearman.py", "tests/fixtures/panel_fixtures.py", "tests/unit/test_hypothesis_scan_signals.py", "tests/integration/test_hypothesis_scan_cli.py", "tests/bias_guards/test_hypothesis_scan.py", "tests/unit/test_hypothesis_crypto_panel.py", ".claude/rules/alpha-research.md", ".claude/rules/alpha-cli.md", "docs/BUILD-STATUS.md", "docs/audit/2026-09-10-edge-first-system-audit.md", "docs/superpowers/plans/2026-09-11-edge-first-phase-c-screening-lane.md"]
}
```

## Context

Phase C of the edge-first program (audit F2). The lane sits *in front of* the governed research funnel
and grants nothing: it answers "does this signal rank next-period returns, for how long, monotonically,
and after turnover?" in seconds so that the 19-command governed path is only paid for candidates that
survive triage. Phase D charges the recorded trial count in the gauntlet; Phase E makes `scan_id` the
candidate's entry.

## Design (post invariants audit, 2026-09-11)

### C1 primitives (`alpha_research/panel.py`, numpy only, quant tier)

All inputs are `T×N` float64 panels (dates × names). `NaN` means "name absent on that date"; `inf`
raises `DataError`; fewer than 3 dates raises; a date with fewer than `min_names` finite pairs yields
`None` for that date. Sorting is `np.argsort(kind="stable")` over canonical (sorted) symbol order;
IC uses average ranks (`_arrays.average_ranks`) so ties never enter Spearman.

| Function | Definition | Primary source |
|---|---|---|
| `cross_sectional_ic(signal, outcome, *, min_names=5) -> IcSeries` | per-date Spearman; `mean`, `std`, `icir = mean/std`, `t_stat = mean/std·√n`, `hit_rate`, `n_dates` | Grinold & Kahn, *Active Portfolio Management*, ch. 6 (IC, IR) |
| `forward_outcomes(closes, *, horizon) -> panel` | `closes[i+h]/closes[i]−1` iff `i+h ≤ T−1` and both finite, else NaN; never a truncated return; a non-positive present close raises (no silent `inf`/`0/0`) | index rule from the invariants audit |
| `ic_decay(signal, closes, *, horizons=(1,5,10,21), min_names)` + `ic_half_life(decay)` | full `IcSeries` per horizon (so per-horizon `n_dates` is reported); half-life over `{h: series.mean}` = first horizon where mean IC ≤ ½ of the shortest-horizon value (linear interpolation, inclusive), `None` if never | Qian, Hua & Sorensen, *Quantitative Equity Portfolio Management* (2007), IC decay |
| `quantile_returns(signal, outcome, *, quantiles=5, min_names) -> QuantileReport` | symmetric equal-count top/bottom buckets (`n // q` names each; leftover names sit unbucketed in the middle) by per-date stable rank; `quantiles <= min_names` is enforced so no scored date can produce an empty bucket; `mean_by_quantile`, `spread` (top−bottom), `monotonicity` = Spearman(bucket index, bucket mean), `n_dates` | Fama & French (1992) portfolio sorts; monotonicity reported as a rank correlation only (not the Patton–Timmermann MR test) |
| `bucket_turnover(signal, *, quantiles=5, min_names)` | mean over consecutive dates of the fraction of names present on both dates that leave the top or bottom bucket | Grinold & Kahn ch. 16; Alphalens quantile turnover |
| `cost_adjusted_spread(spread, turnover, *, cost_bps)` | `spread − 4·turnover·cost_bps/1e4` with `cost_bps` a ONE-WAY cost: each replaced slot sells the leaver and buys the entrant in a $1-per-leg book, so traded notional is `4·turnover` (review finding, 2026-09-11) | arithmetic, stated |
| `fama_macbeth(factors, outcome, *, min_names) -> FamaMacBeth` | per-date OLS with intercept via `lstsq`; a rank-deficient date raises `DataError` (fail loud, stricter than the audit's "yields None"; a collinear factor set is a caller error, not a data gap); `mean_slopes`, `t_stats = mean/std·√n`, `n_dates`, `overlapping_outcomes` caveat | Fama & MacBeth (1973) |
| `orthogonalize(signal, controls, *, min_names) -> panel` | per-date residual of OLS of signal on controls + intercept; NaN where any input NaN or below `min_names` | Gram–Schmidt per cross-section |

### C2 equity lane

- Panel: union of dates across the chosen names, `NaN` where a name has no bar. Leading/trailing NaN
  is listing/delisting; an **interior** NaN or a non-contiguous run raises `DataError`.
- Membership: for `--universe NAME`, each row `t` is masked with `members_as_of(memberships, dates[t])`,
  so pre-inclusion history never enters a signal window. Names absent from `ParquetStore.list_symbols()`
  are reported under `missing`; `load_bars` errors propagate unchanged.
- Outcomes: `forward_outcomes` index rule. A delisted name's terminal outcome is
  `UniverseMembership.delisting_return` when present, else `None` and counted in `truncated_outcomes`.
- Signals (causal, closes ≤ t only, NaN if any close in the window is NaN): `mom_12_1`, `mom_6_1`,
  `rev_1m`, `vol_63`, `range_52w`.
- `--snapshot` threads to `load_bars(snapshot_id=)`; the payload records `snapshot_id` or `"live"`.
- Identity: `scan_id = sha256(canonical JSON of inputs + PANEL_VERSION)`; `result_digest` is a separate
  sha256 of the result table labelled `machine_dependent: true`.
  Canonical JSON: `sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False`,
  `None → null`, `-0.0 → 0.0`.

### C2 crypto lane

- Read: `CryptoBulkStore.inventory()` (verifies every manifest) filtered to `artifact_kind ==
  "normalized"`, `dataset.provider == FAMILY_AUTHORITIES[family]`, `quality.state == "qualified"`,
  matching instrument/category, `fetched_at ≤ as_of`. Identity fields (venue, market_type, units,
  timestamp_convention, base/quote asset, frequency) must be byte-identical across the selected
  manifests; overlapping timestamps must agree exactly. The selected manifest ids enter `scan_id`.
- Availability: `provider_event_utc → timestamp` (funding, open_interest); `interval_start_utc →
  timestamp + frequency` (bars); anything else raises. Date `t` uses rows available ≤ `t 00:00 UTC`;
  the daily funding mean window is `(t−1 00:00, t 00:00]`; the 30-day z-score ends at `t`.
- Signals: `funding_z_30d`, `oi_chg_7d`, `mom_30d`; outcomes from `derivative_bars 1d` closes.
- Why not `alpha_data.crypto.features`: those functions are single-instrument and stamp one scalar
  `available_at ≥ quality.observed_end` per artifact, the right contract for a research artifact but not
  for a daily cross-section, which needs the row-level rule above. Both rules are bias-guarded.

## Test plan

Test files are named to land in the alpha tier (`tests/_tiers.py`: avoid the `test_crypto_` and
`test_research_` platform prefixes). The test-architect specification (57 ordered cases, hand-computed fixtures in
`tests/fixtures/panel_fixtures.py`: a 3×6 panel with per-date Spearman 1, −1, 29/35; sample-std
`ddof=1` pinned; zero-dispersion statistics are `None`; `ic_half_life` linear interpolation with an
inclusive boundary; Fama-MacBeth noiseless slopes 0.5/−0.2; orthogonalised residual equals the
constructed noise; a scipy `spearmanr` differential oracle) is the implementation contract. Its
pinned decisions: crypto `fetched_at` lives only on raw manifests, so the reader resolves it through
`input_manifest_ids` and excludes a normalized manifest whole if any raw input was fetched after
`as_of`; the funding identity frequency constant is imported from `_crypto_panel` by the fixtures.
The invariants audit's required guards are:

- panel-level poison (rows after `T−1−h` set to 1e9 leave earlier outcomes byte-identical) and the
  leaky twin (`closes[t+1]` signal scores IC≈1 on noise; the real lane ≈0);
- membership mask (pre-`effective_from` history excluded; later-removed names present while members;
  `delisting_return` used as terminal outcome);
- crypto availability boundaries: (a) a funding row at `t 00:00+1s` and a bar starting `t 00:00`
  valued 1e9 leave date-`t` signals unchanged; (b) a funding row at exactly `t 00:00` and a bar
  starting `t−1 00:00` do move them; (c) a manifest with `fetched_at > as_of` is ignored;
- determinism: `scan_id` invariant to `--symbols` order and to result values; JSON canonicalisation
  pinned; `fama_macbeth` `None` on a rank-deficient date.

Oracle/metamorphic tests under `tests/oracles/` and bias guards under `tests/bias_guards/` are
protected paths (one `gate.py ack` per file).

## DAG / look-ahead / determinism impact

- **DAG:** `alpha_research/panel.py` imports numpy + `alpha_core` only (contract "alpha_research
  depends only on core"). `_hypothesis_scan.py`/`_crypto_panel.py` live in `alpha_cli` (the only
  multi-package composer) and import `alpha_core`, `alpha_data`, `alpha_research`. No new edges, no
  MCP/REST/UI.
- **Look-ahead:** equities through `load_bars(as_of=)`; per-date membership; the outcome index rule;
  crypto availability from the identity convention; six bias guards.
- **Determinism:** no randomness in C1/C2 (no seeds); `scan_id` over inputs only; `result_digest`
  explicitly machine-dependent; stable sorts and canonical symbol order.
- **Authority:** none. No manifest, run-store, control-store or project state is written.

## C1 review record (2026-09-11)

The first `/review-gate` returned BLOCK: empty buckets when `quantiles > min_names` (fixed by
enforcing `quantiles <= min_names`), an untyped `ZeroDivisionError` in `bucket_turnover` on the
same input (same fix), `forward_outcomes` accepting non-positive closes (now raises), and an
ambiguous cost convention (now one-way `cost_bps`, drag `4·turnover·cost`). Low findings adopted:
`ic_decay` returns the full `IcSeries` per horizon; the `__init__` export list no longer re-sorts
pre-existing entries; the Phase B ledger `cause` hardening is committed separately; the table above
records the `DataError` deviation for rank-deficient Fama-MacBeth dates.

Second review (BLOCK on a flaky Hypothesis filter): the oracle strategies now build distinct rows
by construction (`unique=True`), never by filtering; `_panel` re-raises numpy conversion errors as
`DataError`; `ic_half_life` rejects non-finite values; `cost_adjusted_spread` rejects bools; the
IC-decay citation now points at Qian-Hua-Sorensen ch. 8 (information horizon) per the quant
verifier. Carried into C2 as a requirement: `bucket_turnover` counts leavers only among names
present on both dates, so a name that leaves by delisting or membership exit is NOT turnover; the
C2 payload must report `absent_leavers` (names that left the top/bottom bucket by disappearing)
next to `truncated_outcomes` so the cost-adjusted spread is not read as complete under churn.
