---
paths:
  - "packages/alpha-validation/**"
  - "packages/alpha-research/**"
  - "apps/alpha-cli/src/alpha_cli/_gauntlet.py"
  - "apps/alpha-cli/src/alpha_cli/_optim.py"
  - "tests/oracles/**"
---
# Quant-tier rules (statistical code has oracles, not just tests)

Verbatim relocation of the pre-v2 CLAUDE.md `Validation gauntlet gates` section, plus the quant-tier obligations the harness enforces mechanically.

- Every public statistical primitive must be *wrong-detectable*: metamorphic relations, a known-truth calibration, or a differential oracle in `tests/oracles/` (markers `oracle`, `slow_oracle`), with a primary-source citation in the docstring.
- `/verify-quant` (PASS `QuantVerificationReport` bound to the scoped diff hash) is owed before Stop; `/review-gate` APPROVE before commit. Never `float ==` in tests; tolerances come from documented Wilson/binomial bounds.
- Suppression growth (`# noqa`, `type: ignore`) in quant modules is blocked by `gate.py lint-harness` unless the baseline is re-approved.
- A changed quant SOURCE module must hold a mutation kill-rate ≥ 0.90 (or its recorded `.claude/mutation-baseline.json` floor for a legacy module) — `gate.py full` runs `gate.py mutate` and the slow oracles on-touch; `.semgrep/alpha.yml` bans bare/`pass` excepts, negative shifts, wall-clock reads, unseeded RNG, unsanctioned pandas, and float-literal equality here.

## Validation gauntlet gates (spec §8) — produced by `build_outcomes` → `ValidationOutcome`s
- `walk_forward_oos` (gate 2): passes on a finite OOS Sharpe. Fold geometry comes from the session calendar; the fixed rule strategy is causally primed on prior history without an engine, then a **fresh portfolio** executes once from the prior close through the contiguous OOS sessions. Metrics, equity, decisions, orders, fills, trades, indicators, and annotations are scoped from that same execution. Rule parameters are not refit; Qlib refits separately inside each fold.
- `randomized_price_null` (gate 3, headline): two tiers — Tier 1 `returns_level` (surrogate on resampled returns, scored on the walk-forward OOS window; `--null-model` selects bootstrap/student_t/garch) + Tier 2 `full_engine` (real engine on level-continuous synthetic OHLCV paths). Passes only if observed beats the `threshold` percentile in **every** tier (conservative) — except that a Tier-1 FAIL is demoted to advisory (`flagged_low_fidelity`, reported but not vetoing) when Tier-2 passed AND the measured close-fill vs t+1-open-fill `convention_divergence` of the same surrogate weights exceeds `tier1_divergence_tol` (the documented Tier-1 crediting bias for high-turnover strategies; see `docs/investigations/2026-06-23-tier1-surrogate-crediting-bias.md`). A Tier-2 fail is never rescued.
- `bootstrap_ci` (gate 4): passes when the Sharpe BCa lower bound > 0.
- `deflated_sharpe`: PSR/DSR of the OOS stream (single run → n_trials=1, DSR=PSR); passes when DSR ≥ `dsr_threshold`.
- `cpcv_oos`: distribution of OOS Sharpe across combinatorial purged CV folds of the OOS stream; passes when the mean fold Sharpe > 0.
A degenerate (flat/zero-variance) OOS short-circuits to a clean FAIL (degenerate gates), never an undefined-Sharpe crash. Overall `passed` = all gates pass.
- **Multi-trial gates (`alpha optim`):** Deflated Sharpe (deflated by the trial-Sharpe variance), PBO via CSCV, and White/Hansen Reality-Check/SPA judge a parameter sweep for selection bias — they only become meaningful with many configs, so they live in `_optim`, not the single-run gauntlet.

