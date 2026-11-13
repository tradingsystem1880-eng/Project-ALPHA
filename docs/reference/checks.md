---
owner: development tooling
sources:
  - .github/workflows/ci.yml
  - .github/workflows/nightly.yml
  - .github/workflows/mutation-weekly.yml
  - .github/actions/setup/action.yml
  - scripts/gate.py
  - scripts/gate_components.py
  - pyproject.toml
verified: b8823a6a6e3f
---

# Checks

Every automated check, the breakage it exists to catch, where it runs and how long it takes.
Pull requests merge on the one required check, `ci-ok`. Times are wall time on GitHub's
standard runners, measured on pull request #134 (run 43482233439, 2026-11-13) unless marked otherwise.
`tests/unit/test_checks_reference.py` fails when a CI job or a pytest marker is missing here.

Tiers: **PR** runs on every pull request and every push to main. **PR (paths)** runs on a pull
request only when its paths (or the workflow and gate files) change, and always on main.
**PR (quant)** runs when quant-tier source changes ([engineering § Quant tier](invariants/engineering.md#quant-tier)).
**Nightly** and **Weekly** run on main on a schedule. **Local** cannot run on GitHub.

## The table

| Check | Breakage it catches | Tier | Time |
|---|---|---|---|
| `changes` job: picks the conditional jobs | a path-filtered job silently skipped (unknown history selects all) | PR | 8 s |
| `static` job: `uv lock --check`, `uv sync --locked` | a dependency change without its lock file | PR | 7 s (job 1.4 min) |
| `static`: ruff lint and format | style and simple bug patterns (unused names, bad comparisons) | PR | 1 s |
| `static`: import contracts (`lint-imports`) | a package importing a layer it must not (the import DAG) | PR | 0.4 s |
| `static`: mypy, one strict run over packages, apps, tests and harness scripts | type errors | PR | 45 s |
| `static`: harness lint and doctor | a removed deny rule, unwired hook, lowered coverage floor or `-x` in CI (the doctor's machine-readiness section is listed, not enforced, on CI) | PR | 0.2 s |
| `static`: semgrep over the whole repo, plus its rule contracts | wall-clock reads, unseeded random numbers, negative shifts, silent excepts | PR | 13 s |
| `static`: OpenAPI freshness and authority | a web route changed without regenerating `openapi.json`, or an unsafe operation | PR | 3 s |
| `static`: wheel build and wheel smoke | a package that no longer builds or imports, or a web wheel without its SPA | PR | 5 s |
| `tests` job, four shards: all root tests but `network`, `slow_oracle` | any unit, integration, smoke or acceptance failure | PR | 4.5-5.7 min each |
| `bias_guard` marker (inside `tests`) | look-ahead: output before the cutoff changes when later data is poisoned | PR | in `tests` |
| `oracle` marker (inside `tests`) | wrong statistics: metamorphic and differential checks fail | PR | in `tests` |
| `tests/acceptance` (inside `tests`, no marker) | the gauntlet, threshold and execution contracts break | PR | in `tests` |
| `smoke` marker (inside `tests`) | the installed `alpha` and `alpha-web` programs break end to end | PR | in `tests` |
| `platform` marker (inside `tests`) | nothing extra: it only moves files out of the fast local check | PR | in `tests` |
| determinism, identity and golden tests (inside `tests`) | a result that is not byte-stable across fresh processes | PR | in `tests` |
| `coverage` job: changed product lines (`packages/*/src`, `apps/*/src`) | new or changed code shipped without tests (below 85% of changed lines) | PR | 30 s |
| `coverage`: whole-suite line coverage | nothing (reported in the job summary, never gated) | PR | in `coverage` |
| `quant` job: `slow_oracle` marker | a statistic that no longer recovers known truth | PR (quant) | not measured here |
| `quant` job: mutation gate on the touched modules | tests too weak to notice a changed statistic (kill rate < 0.90) | PR (quant) | ~21 min per module |
| `frontend` job: lint, build with types, unit tests with coverage | TypeScript, lint and component failures | PR | 22 s (job 9.6 min) |
| `frontend`: API client freshness | `src/api/generated.ts` out of date with `openapi.json` | PR | in `frontend` |
| `frontend`: browser journeys at the reference viewport (plus reference-only ones) | broken Workstation screens and flows, real backend | PR | 8.6 min |
| `qlib-worker` job | the isolated Qlib worker's lint, types or tests | PR (paths) | 5.7 min |
| `literature-worker` job | the literature worker's lint, types or tests | PR (paths) | 0.5 min |
| `eval` job | the agent benchmark's lint, types or tests | PR (paths) | 0.7 min |
| `ci-ok` job | any job failing or cancelled; a skip counts only when `changes` said so | PR | 4 s |
| `harness-nightly` job: semgrep, determinism double-run, raise-site coverage | results that change with hash seed or time zone | Nightly | 13.4 min |
| `slow-oracles` job: every `slow_oracle` test | the same as the `quant` job, for statistics not touched by a pull request | Nightly | 1.1 min |
| `frontend-full` job: browser journeys at all four viewports | layout breaking at the minimum or wide viewports | Nightly | 23.3 min |
| `mutation-sweep` job: dispatches the weekly sweep on demand | (see the weekly rows) | Nightly (manual) | — |
| `modules`, `mutate`, `aggregate` jobs: every quant module, every mutant | weak tests anywhere in the quant tier (report only) | Weekly | ~70 min |
| `network` marker | live vendor feeds changed | Local | — |
| tests that need stored runs or data (`tests/integration/test_figure_builders.py`) | figures over real stored runs | Local (skip on GitHub) | — |
| native browser lane (`ALPHA_RDAGENT_SOURCE`, `ALPHA_STOCK_PYTHON`) | the native RD-Agent result screen | Local (skip on GitHub) | — |

## How to change it

- A new CI job or pytest marker needs a row here; the unit test names what is missing.
- Re-measure times from `gh run view <id> --json jobs` and update the column in the same change.
- Shard balance comes from `scripts/gate_test_durations.json`; refresh it from the `test-durations`
  artifact of a recent run (`gate.py durations`). Stale times unbalance shards but never drop tests.
- Moving a check between tiers must not weaken bias guards, oracles, acceptance or determinism
  tests ([research integrity § Protected and hidden tests](invariants/research-integrity.md#protected-and-hidden-tests)).
