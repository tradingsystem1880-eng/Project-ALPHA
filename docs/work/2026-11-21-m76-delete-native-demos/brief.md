# Brief: delete the Native Qlib and Nautilus demo screens

Branch: `chore/m76-delete-native-demos`. Rules: `docs/work/_common-rules-2026-11-21.md` (deletion-only build).

The owner decided on 2026-11-21 to delete the native engine demos: they run on made-up data and nothing uses them.

Delete (verify each first): `apps/alpha-cli/src/alpha_cli/native_qlib_pipeline.py` and `tests/unit/test_native_qlib_pipeline.py`; the
`_REVIEWED_READERS` line that names it in `tests/unit/test_structural_digest.py`; the frontend panels `NativeQlibDemo`,
`nativeQlibDemoModel*`, `NativeNautilusDemo`, `nativeNautilusDemo*` and the pipeline demo pane; the folder
`apps/alpha-web/frontend/public/demos/`; their panes in `apps/alpha-web/frontend/src/shell/documents.ts` and menu entries; Playwright specs
and unit tests for them; the capability `native-engine-demos` in `docs/roadmap/capabilities.toml`; mentions in `workers/qlib/README.md`
and other docs. Do NOT touch the real Qlib worker, the ML lab, Kronos, or `alpha_validation.native_tearsheet`.

Done: draft then ready pull request, `ci-ok` green except possibly the code-size test (see the common rules), `report.md` here with the
file list, the no-caller proof per file, lines removed, and the baseline entries to lower.
