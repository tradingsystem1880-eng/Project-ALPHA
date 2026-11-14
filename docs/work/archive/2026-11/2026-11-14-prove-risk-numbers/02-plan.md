# Prove "Risk numbers that state what they are based on" end to end

**Delivery state:** Completed — built, reviewed and verified on branch `m8/prove-risk-numbers`; done when its pull request merges.
**Build class:** standard — four files; a provenance fix and a text note in one alpha-cli command, tests and a smoke check; no quant-tier source.

Filed straight into the archive, as `2026-11-14-prove-crypto-data` was: the work-in-progress
ceiling admits no new live plan, and the work is finished in one sitting. The four live risk plans
this capability lists are archived with it.

## For the owner

- A new automatic check runs the real `alpha` program and the Workstation to compute the risk
  figures (volatility, drawdown, VaR, CVaR, Sharpe, total return under five stress scenarios) and
  recomputes every one with independent code. "Risk numbers" can now count as Working.
- Fixed: for a validation run the risk page said it was based on no snapshot; it now names the
  snapshot the run used.
- The text output now says how the stress scenarios are built: the "-3 sigma" and "-5 sigma" shocks
  are one bad day added after the last day, so they rarely change the worst drawdown.
- Nothing for you to decide here.

```json
{
  "schema_version": 1,
  "title": "Prove Risk numbers that state what they are based on end to end",
  "context": "risk-numbers is Partial: CLI and web tests run in-process and a Playwright journey runs against a test server. Run through the installed alpha and alpha-web on a real validate run (Alpaca SPY 2016-2026, 2,205 OOS returns): all 30 scenario figures matched an independent numpy recomputation exactly (0.0 difference) and the web route returned the identical payload; unknown run 404, confidence 1.2 422. Findings: provenance.snapshot_id is null for validate runs because the command reads manifest['snapshot_id'] while validate manifests keep it in metadata.snapshot_id (snapshot_hash is top level, so the provenance was self-inconsistent); the -3 and -5 sigma shock scenarios append one day after the last return, so max drawdown was identical to base (-0.2601) and VaR identical between the two shocks, which the text output does not explain.",
  "assumptions": [
    {"statement": "Validate manifests carry snapshot_id only under metadata, backtest_run manifests at top level.", "verified_by": "real runs on the Dell, 2026-11-14: validate 415f2b81ae0ec262 has metadata.snapshot_id 'alpaca-starter-2026-11-14' and no top-level key; backtest_run 7ae65f55a03a01c5 has top-level snapshot_id"},
    {"statement": "alpha-web's /api/risk/scenario runs the installed `alpha risk scenario ... --json` as a subprocess, so the CLI fix also fixes the web payload.", "verified_by": "apps/alpha-web/src/alpha_web/_risk.py scenario()"},
    {"statement": "The web RiskReport model accepts a string snapshot_id in provenance.", "verified_by": "the backtest_run case already returns a string snapshot_id through the route (tests/integration/test_c04_web_metric_basis.py)"},
    {"statement": "risk_cmds.py is not in DAILY_GUARD_FILES and not quant tier.", "verified_by": "apps/alpha-cli/src/alpha_cli/_native_rule_environment.py; docs/reference/invariants/engineering.md"}
  ],
  "alternatives_considered": [
    "Write snapshot_id at the top level of validate manifests: rejected, it changes the run artefact contract and the validate command's bytes; the reader should follow the producer's layout.",
    "Move the shock day to the start of the worst drawdown: deferred to the backlog, it changes alpha_validation.scenario (quant tier) and every recorded figure; disclosure now.",
    "Narrow --confidence to (0.5, 1) as the web route does: rejected here, an existing completed test pins the current message for confidence 1."
  ],
  "pre_mortem": [
    "The fallback reads a metadata snapshot_id that is not the one the equity came from: validate writes metadata from the same load that produced the equity; the fallback is used only when the top-level key is absent.",
    "The smoke check's recomputation reuses alpha_validation: it uses numpy only (std ddof=1, numpy.quantile default, cumprod with a leading 1) and reads equity_curve.parquet directly.",
    "Rewriting an immutable run's equity in the smoke home leaks: the tampering happens only in a copied throwaway home, after making the copied file writable."
  ],
  "slices": [
    {"title": "Snapshot provenance for validation runs; explain the scenarios", "verify": "uv run pytest -q tests/integration/test_risk_cli.py tests/integration/test_c04_risk_anchor_disclosure.py tests/integration/test_risk_strict_json.py tests/integration/test_risk_equity_clocks.py", "expected": "all pass; the new tests fail on main", "rollback": "revert risk_cmds.py and test_risk_cli.py", "status": "done"},
    {"title": "Risk smoke check through the installed alpha and alpha-web", "verify": "uv run python scripts/run_owned_test.py --timeout 900 -- uv run pytest -q -m smoke -n 0 tests/smoke/test_risk_smoke.py", "expected": "passed", "rollback": "delete tests/smoke/test_risk_smoke.py", "status": "done"}
  ],
  "tier_impact": ["none"],
  "docs_to_update": ["docs/roadmap/capabilities.toml", "STATUS.md", "docs/roadmap/README.md", "docs/roadmap/wip-limit.json", "docs/roadmap/backlog/risk-shock-placement.md"],
  "out_of_scope": ["packages/alpha-validation/src", "apps/alpha-web/src", "apps/alpha-cli/src/alpha_cli/_artifacts.py", "apps/alpha-web/frontend"],
  "files": [
    "apps/alpha-cli/src/alpha_cli/risk_cmds.py",
    "tests/integration/test_risk_cli.py",
    "tests/smoke/test_risk_smoke.py"
  ]
}
```

## Read first

| Read | Section | When |
|---|---|---|
| [tests workspace](../../../../../tests/CONTEXT.md) | How to change it | always |
| [risk command](../../../../../apps/alpha-cli/src/alpha_cli/risk_cmds.py) | `scenario` | always |
| [scenario metrics](../../../../../packages/alpha-validation/src/alpha_validation/scenario.py) | — | always (read only) |
| [smoke harness](../../../../../tests/smoke/_harness.py) | `alpha`, `web_server`, `get_json` | slice 2 |
| [smoke homes](../../../../../tests/smoke/conftest.py) | — | slice 2 |
| [validation smoke](../../../../../tests/smoke/test_validation_smoke.py) | `_GAUNTLET` | slice 2 |

## Slices

### 1. Snapshot provenance for validation runs; explain the scenarios

In `apps/alpha-cli/src/alpha_cli/risk_cmds.py`:

- `provenance.snapshot_id`: `manifest["snapshot_id"]` when the key is present (even if null);
  otherwise `manifest["metadata"]["snapshot_id"]` when `metadata` is a dict holding a string
  `snapshot_id`; otherwise `None`. A small helper `_snapshot_id(manifest)`.
- Text output (not `--json`), after the existing scenario lines, two lines:
  `"Shock scenarios append one day of -3 or -5 sample standard deviations after the last
  recorded return; the drawdown changes only if that day deepens one."` and
  `f"VaR and CVaR: historical, one period, {confidence:.0%} confidence, positive numbers are
  losses; volatility scaling keeps the mean and scales every return, flat days included."`
  JSON output is unchanged apart from the provenance fix.

Tests first in `tests/integration/test_risk_cli.py` (must fail on main): a run whose manifest is
`{"command": "validate", "metadata": {"snapshot_id": "snap-1"}, "snapshot_hash": "h"}` reports
`provenance.snapshot_id == "snap-1"`; a top-level `"snapshot_id": null` stays null even with a
metadata value; the text output contains both new lines.

### 2. Risk smoke check through the installed alpha and alpha-web

`tests/smoke/test_risk_smoke.py` (new; `pytestmark = [pytest.mark.smoke,
pytest.mark.usefixtures("owned_test_process")]`). Uses `backtest_home`, `data_home`,
`copy_home`, `SNAPSHOT`, `STRATEGY` from `tests.smoke.conftest`, `_GAUNTLET` from
`tests.smoke.test_validation_smoke`, and `alpha`, `web_server`, `get_json` from the harness.
A module helper recomputes the five scenarios from an equity array with numpy only: returns
`e[1:]/e[:-1]-1`; base; `m + (r - m) * 1.5` and `* 2.0`; `r` with `-3 * std(r, ddof=1)` and
`-5 * ...` appended; for each, Sharpe `mean/std(ddof=1)*sqrt(252)`, annual vol, max drawdown
`min(w/cummax(w) - 1)` with `w` = cumprod with a leading 1, VaR `max(0, -quantile(r, 1-c))`, CVaR
`max(0, -mean(r[r <= quantile]))`, total return `w[-1] - 1`.

1. `test_backtest_risk_figures_recompute_and_state_their_basis(backtest_home, tmp_path)`:
   `alpha risk scenario --from-run <id> --json --include-metric-basis`: scenario names in order
   `base, vol +50%, vol +100%, -3σ shock, -5σ shock`; every figure equals the recomputation
   (abs 1e-12, Sharpe rel 1e-12); provenance `source_command == "backtest_run"`, `snapshot_id ==
   SNAPSHOT`, `snapshot_hash` equals the run manifest's, `source_artifact_sha256` equals the
   SHA-256 of `equity_curve.parquet`, `as_of` equals the last equity timestamp in ISO form,
   `metric_basis.anchor_value` equals the first equity and `anchor_ts` the first timestamp. The
   same command without `--include-metric-basis` equals that payload with `metric_basis` removed.
   With `--confidence 0.99` the VaR and CVaR equal the recomputation at 0.99. The text output has
   five scenario lines, the `Anchor: first recorded equity` line and the new shock line.
   `--include-metric-basis` without `--json` exits 2.
2. `test_workstation_serves_the_same_risk_payload(backtest_home, tmp_path)`: on a copy of the
   home, `web_server(home)`; `GET /api/risk/scenario?run_id=<id>&include_metric_basis=true` equals
   the CLI JSON with basis; an unknown 16-hex run id gives HTTP 404 and `confidence=1.2` gives
   422 (catch `urllib.error.HTTPError` and check `.code`).
3. `test_validation_run_risk_names_its_snapshot(data_home, tmp_path)`: on a copy, `alpha validate
   SPY *STRATEGY *_GAUNTLET --snapshot smoke-v1`, then risk scenario `--json --include-metric-basis`
   on it: `source_command == "validate"`, `snapshot_id == SNAPSHOT`, the base Sharpe, VaR, CVaR,
   max drawdown and total return equal the validate manifest's `oos_metrics` values (abs 1e-12).
4. `test_disordered_or_broken_equity_is_refused(backtest_home, tmp_path)`: on a copy, make the
   run's `equity_curve.parquet` writable and rewrite it (polars) with the second timestamp equal
   to the first: risk scenario exits 2 with `strictly increasing` in the output and prints no
   scenario; rewrite it with one equity value `inf`: exits 2.

Do not change product code in this slice. If the installed programs do not behave as listed,
stop and report the exact output instead of adjusting the expectation.

## Test plan

Slice 1's tests fail on main. Slice 2 starts the installed programs and binds a loopback port;
run it outside any sandbox. Existing risk tests must pass.

## Look-ahead, determinism and import impact

No read path changes beyond which manifest field names the snapshot. Deterministic. No import
changes.
