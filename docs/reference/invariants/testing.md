---
owner: test suite and quant sweeps
sources:
  - tests/_tiers.py
  - tests/conftest.py
  - tests/bias_guards/test_future_poison_pattern.py
  - tests/bias_guards/test_poison_variants.py
  - tests/acceptance/**
  - tests/unit/test_gate_process_supervisor.py
  - scripts/gate.py
  - scripts/gate_select.py
  - scripts/harness_quant.py
  - scripts/run_owned_test.py
  - scripts/claude_hooks.py
  - pyproject.toml
  - .semgrep/alpha.yml
verified: 00f70c232ea5
---

# Testing invariants

How the root test suite under `tests/` is laid out, marked, tiered and swept. The isolated workers and
`tools/alpha-eval` have their own suites ([workers](workers.md), [eval](eval.md)). The general rule on
protected and hidden tests is [research integrity § Protected and hidden tests](research-integrity.md#protected-and-hidden-tests);
this file holds the mechanics.

## Test layers

- `tests/unit/` pure units; `tests/integration/` CLI and engine; `tests/bias_guards/` future-poison
  guards; `tests/oracles/` metamorphic, calibration and differential oracles (shared reference code and
  named tolerances in `tests/oracles/_reference/`); `tests/fixtures/` goldens; `tests/acceptance/`
  17 visible behaviour tests of the gauntlet, threshold and execution contracts.
- Statistical goldens carry named tolerances (`tests/oracles/_reference/tolerances.py`), never exact float
  equality. Semgrep rule `alpha-float-literal-equality` flags literal float equality.
- Warnings are errors (`filterwarnings = ["error", ...]` in `pyproject.toml`): a new warning fails the test.
- `tests/conftest.py` sets `NO_COLOR` and removes `GITHUB_ACTIONS`, `FORCE_COLOR` and `PY_COLORS` before
  typer loads, so CLI output assertions match on every terminal.

## Markers and tiers

- Markers are strict (`--strict-markers`): `bias_guard`, `network`, `oracle`, `slow_oracle`,
  `platform`. An unregistered marker fails collection, and `gate.py lint-harness` fails if strict markers
  are turned off.
- Never add `platform` by hand. `tests/conftest.py` applies it at collection from
  `tests/_tiers.py::classify_platform`, which defaults to fast and opts files out by directory-scoped
  filename prefix (`PLATFORM_PREFIXES`), by measured slow file (`SLOW_FILES`, about ten seconds or more),
  with `ALPHA_ALLOWLIST` pulling statistical modules back into the fast tier. A new file's name decides
  its tier.
- What runs where:
  - `gate.py check --all`: `-m "not platform and not network and not slow_oracle"`.
  - `gate.py check`: `-m "not network and not slow_oracle"` over the `gate_select.py` selection.
  - CI backend (`gate.py component backend`): `pytest -q -n auto -m "not network and not slow_oracle" --cov`
    with coverage `fail_under = 93`; it adds `-m slow_oracle` and the mutation gate only when a quant
    source module changed.
  - `network` tests never run in CI.
- `gate_select.py` always runs `tests/bias_guards`, `tests/oracles` and `tests/acceptance`, plus changed
  test files, test files whose text imports a changed module (a text search, not an import graph), and
  last failures. Over 400 mapped tests it keeps only files named after the changed modules; a changed
  `conftest.py` is left to CI. CI still runs everything on the pull request.

## Bias guards

- Every data or strategy unit gets a future-poison test marked `@pytest.mark.bias_guard`.
  [research integrity § Point-in-time reads](research-integrity.md#point-in-time-reads).
- The template is `tests/bias_guards/test_future_poison_pattern.py`: poisoning data after the cutoff must
  leave every output up to the cutoff identical, and must change at least one later output, or the guard
  has no discriminating power.
- The hardened form (`tests/bias_guards/test_poison_variants.py`) adds non-finite poison that must fail
  loud, and a must-fail leaky twin (a deliberately non-causal version) that the same predicate must reject.
- The marker comes from `pytestmark` in each module, not from the directory: an unmarked file in
  `tests/bias_guards/` is skipped by `pytest -m bias_guard`. Guards may live elsewhere if marked
  (`tests/unit/test_rules_bias_guard.py`).

## Oracles

- `oracle` marks fast metamorphic and differential checks; `slow_oracle` marks known-truth calibration and
  coverage oracles. Every module in `tests/oracles/` carries one of the two.
- Slow oracles run in CI only on a quant-source change, or locally with `uv run pytest -q -m slow_oracle`.

## Protected and hidden tests

- `tests/unit/test_claude_harness_*.py`, `tests/bias_guards/**` and `tests/oracles/**` are protected control
  plane: change them only in a reviewed pull request. No hook blocks these edits; review does.
- The path `tests/holdout/` does not exist. Its guards remain: `.claude/settings.json`
  denies Read, Edit and Write on `tests/holdout/**`, and `scripts/claude_hooks.py` blocks file tools on any
  path containing `tests/holdout`. Never create, read or shell-write that path.
- There is no hidden test suite ([ADR-0041](../../adr/0041-no-hidden-test-suite.md)). The 17 tests in
  `tests/acceptance/` (`test_acceptance_*.py`, no marker) are ordinary visible tests in the fast tier and in
  every `gate.py check`; anyone may read and extend them (`tests/acceptance/README.md`).
- The research final holdout (`alpha project reveal-holdout`, `tests/integration/test_backtest_holdout_cli.py`)
  is a different thing: an owner-authority research control that agents are denied.

## Owned test processes

- A Linux test whose spawned descendants can outlive their parent must use
  `@pytest.mark.usefixtures("owned_test_process")` before spawning. The fixture fails setup unless the run
  is owned by `scripts/run_owned_test.py` (an `ALPHA_TEST_OWNER` identity matching a live ancestor).
- `gate.py` wraps every `uv run pytest` in that owner on Linux. By hand:
  `uv run python scripts/run_owned_test.py -- uv run pytest <selection>`.
- Add each such node id to `ORPHAN_NODES` in `tests/unit/test_gate_process_supervisor.py`. Ordinary
  subprocess tests, tests whose parents reap their own children, and tests of the wrapper do not need it.
- Never install the reaping loop inside pytest or the application; only the dedicated owner process reaps.

## Quant sweeps

- The quant tier is `gate.py::matches_quant`: every `.py` under `packages/alpha-validation/src/` and
  `packages/alpha-research/src/`, plus package source files whose name contains dsr, psr, pbo, deflated,
  bootstrap, reality_check, spa, montecarlo, walkforward, cpcv, multiple_testing or overfitting.
  [engineering § Quant tier](engineering.md#quant-tier).
- `gate.py mutate`: mutmut per module in a staged tree. Kill rate = killed / (total - skipped); a module
  passes when rate + 0.005 >= min(0.90, its floor in `.claude/mutation-baseline.json`). `--write-baseline`
  changes are reviewed in the pull request.
- The weekly exhaustive sweep (`.github/workflows/mutation-weekly.yml`, owner-selected cadence) runs frozen,
  deterministic mutant fragments in at most eight isolated jobs of two mutmut workers each and aggregates
  them exactly; `timeout` and `no_tests` mutants are never counted as kills. Its scores are report-only, and the
  0.90 minimum, 0.005 tolerance and baseline floors stay as above.
- `gate.py semgrep`: fail-closed Semgrep through `scripts/semgrep_runner.py`, which pins `SEMGREP_VERSION` and
  checks the installed version before every scan, with `.semgrep/alpha.yml` over
  `packages`, `apps`, `scripts` and `tests` (`--changed` for changed files). Rules ban silent `except: pass`,
  negative shifts, wall-clock reads in packages, unseeded RNG, pandas outside sanctioned edges, literal
  float equality, bare `# type: ignore` and reasonless skips.
- `gate.py determinism`: runs every `tests/**/test_*determinism*.py`, `*identity*` and `*golden*` file twice,
  with `PYTHONHASHSEED=0 TZ=UTC` and `PYTHONHASHSEED=31337 TZ=Pacific/Kiritimati` (`OMP_NUM_THREADS=1`).
  Name a byte-stability test with one of those words or the sweep never sees it.
- `gate.py raise-cov`: lists `raise` lines in quant modules that the unit, oracle and bias-guard tests never
  reach. Nightly runs it report-only (no `--fail`).
- `.github/workflows/nightly.yml` runs the whole-repo Semgrep, determinism and raise-cov sweeps; CI's backend
  job runs Semgrep on every pull request.
- `gate.py lint-harness` fails when a deny rule is removed, a hook is unwired, coverage `fail_under` drops,
  strict markers are off, quant-module `# noqa` / `# type: ignore` counts grow, or CI pytest uses `-x` or
  `--maxfail`. [engineering § Checks and commits](engineering.md#checks-and-commits).
