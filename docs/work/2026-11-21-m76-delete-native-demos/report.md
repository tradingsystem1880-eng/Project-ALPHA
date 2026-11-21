# Report: delete the Native Qlib and Nautilus demo screens

Result: the demos are deleted. 34 files changed, 4 lines added, 4,370 lines removed.

## Deleted
- `apps/alpha-cli/src/alpha_cli/native_qlib_pipeline.py` (483 lines) and `tests/unit/test_native_qlib_pipeline.py` (252).
- Frontend: `NativeQlibDemo.tsx`, `NativeNautilusDemo.tsx` (includes the pipeline pane), `nativeNautilusDemo.css`,
  `nativeQlibDemoModel.ts`/`.test.ts`, `nativeNautilusDemoModel.ts`/`.test.ts`.
- Folder `apps/alpha-web/frontend/public/demos/` (all files).
- Three panes and imports in `src/shell/documents.ts`; the Playwright loop in `e2e/backtest-result-card.spec.ts`
  (it only tested the two demo panes; the other specs stay).
- `_REVIEWED_READERS` line in `tests/unit/test_structural_digest.py`.
- Capability `native-engine-demos` in `docs/roadmap/capabilities.toml`.

## No-caller proof (grep in apps, packages, workers, tests, scripts, docs, `.github`)
- `native_qlib_pipeline`: only hits were its own test, the digest list line, and docs text. No import, no `python -m`,
  no subprocess call, no CLI command word. The frontend/web never called it (it had no route).
- Frontend panels and models: referenced only by each other, `documents.ts` and the e2e loop (all edited).
- `public/demos`: read only by the two panels and the two model tests (all deleted).
- Shared parts kept: `RecordedSeries` (used by `RecordedPanel`), `MiniLine`, `CopyCommand`, `Placeholder` (used elsewhere).

## Docs fixed
`STATUS.md` (regenerated), frontend `README.md`, `workers/qlib/README.md`, `cli-native.md`, `cli-ml.md`,
`components/qlib.md`, `components/nautilus.md`, `capability-trace.md`, `refactors/alpha-cli-subpackages.md`.
Left as history: ADR-0042, ADR-0045 and `triage-2026-11.md` (decision records).

## Decisions
- `workers/qlib/README.md` is under protected `workers/**`, but the brief names it. I edited the text only (one section removed).
- `workers/qlib/examples/native-synthetic/` (fixture of the deleted pipeline) now has no user. The brief did not name it and
  `workers/**` is protected, so I left it. The owner may delete it later.
- `test_native_nautilus_configs_are_paper_loopback_and_read_only` in `test_ibkr_paper.py` tests real IBKR config; kept.
- The gitignored built copy under `alpha_web/static/app/demos` is not tracked; no action.

## Code-size baseline (protected; not edited)
`tests/unit/test_code_size.py::test_baseline_entries_are_exact` is the one red test. Remove this entry from `.claude/code-size-baseline.json`:
- `apps/alpha-cli/src/alpha_cli/native_qlib_pipeline.py::build_pipeline`: 287 (line 62)

## Checks
- Tests first: not applicable (deletion only). Before the deletion the guards passed; after it, only the code-size test fails, as expected.
- Passed: `lint-imports` (13 kept), `tsc`, vitest (837 pass), `test_structural_digest`, `test_research_reads_are_cut`, `test_follow_separation`.
