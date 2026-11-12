# Native RD cumulative regression selection

Historical qualification record for frozen910ee456. For the later changed-worker
source, see [native worker hardening](native-worker-hardening.md); unchanged-worker
and exploratory typing statements below describe the retained baseline.

This successor qualifies the retained offline candidate with one coherent, explicitly
selected run. It does not extend research, process ownership, admission or accounting.
Predecessor1ef1bcfe6047d245e1f89471ced6dc6168a7f688 and all existing exports stay retained.
The exact final candidate and outcomes are recorded in the external qualification
manifest; no full/private gate stamp or release readiness is inferred.

## Defects found by cumulative checks

The original same-process selection ran all57test methods but failed4profile subtests:
inspection and profile journeys shared resume/cancel/exhaust/tamper output directories.
The operator and API journeys also shared named response files. Evidence now uses
fresh inspection, profile, operator-cli and api subdirectories beneath the caller's
ALPHA_STOCK_RECEIPTS root. Existing evidence is never reused or overwritten deliberately.
The native worker, application behavior, store/accounting and generated SPA are unchanged.

Production-only typing had omitted the new tests. The canonical gate's mypy target is
packages/apps/tests, so explicit cumulative checking found181diagnostics in9tests.
This correction annotates tests/helpers, checks JSON dictionary/list structure before
indexing, and uses real disposable SQLite connections for malformed/legacy row tests.
A read-only source snapshot is backed up into memory; only a TEMP event table is
varied, leaving the source and copied main-schema append-only controls untouched.
The copied connection is explicitly closed. A direct fixture regression covers the
actual occurred_at column, source/main row preservation, TEMP-row substitution,
retained append-only trigger and connection closure. It first failed on the mistaken
created_at key in the retained intermediate6b584f candidate; that failure is preserved. Casts remain only at deliberately invalid
snapshot-transport and immutable-mutation test boundaries. No ignore, configuration
exception, assertion removal or new skip was added to obtain a pass.

An exploratory strict check also found58diagnostics in the two standalone upstream
fixture worker files, outside the canonical gate's explicit mypy target. This does not
constitute a strict worker typing pass. The actual installed Python3.11 worker executes
under its pinned source/dependency profile in the selected runtime tests. Worker typing
and full installed-runtime qualification remain distinct from those execution receipts.

## Exact permitted Python selection

- tests/unit/test_native_stock_dispatch.py
- tests/unit/test_native_stock_fixture.py
- tests/unit/test_native_stock_inspect.py
- tests/unit/test_native_stock_snapshot.py
- tests/unit/test_native_stock_profile.py
- tests/unit/test_native_stock_result.py
- tests/unit/test_native_stock_operator_cli.py
- tests/unit/test_native_result_api.py
- tests/unit/test_native_result_web.py

The new _native_stock_test_support.py is imported by these tests, not a replacement
loop or another test runner. All57retained methods and272existing unittest assertions
remain, with one additional fixture-fidelity/closure regression.
New narrowing assertions fail loudly if a fixture shape is wrong.

Use the existing installed controller environment after its offline locked check:
uv sync --locked --check --offline at that environment's retained project root must
report no changes. A newer worktree differs only in editable source locations; no
sync/reinstallation is done. Explicit PYTHONPATH selects the candidate's public source
roots; module/source hashes and unchanged uv.lock bind this overlay. Native preflight
checks Linux/default ownership, upstream commit/source digest, source/runtime manifest,
implementation fingerprints and compatible installed dependencies. Record actual installed
names/versions against the saved284-package worker inventory; do not inspect credentials.

Supply ALPHA_RDAGENT_SOURCE (the existing exact pinned upstream source),
ALPHA_STOCK_PYTHON (its installed venv/bin/python), ALPHA_STOCK_RECEIPTS (a fresh existing
output root), and ALPHA_NATIVE_WEB_EVIDENCE (a separate directory that does not yet exist).
Use a disposable HOME and existing installed browser cache metadata. Run the exact nine
filenames above, together, through the documented Linux descendant owner:

    <controller-python> scripts/run_owned_test.py --timeout 900 -- \
      <controller-python> -m pytest -q <the nine explicit filenames> --junitxml=<new-file>

No root test discovery, protected support processing or private holdout is authorized by
this selection. The real browser test uses its dedicated fixture/config, not the default
Playwright seeder. It serves the existing built production SPA through actual loopback
Uvicorn, exercises actual synthetic owner receipt recovery and controlled failures,
and denies provider egress/credential access/store writes. No real inference or market
input is used. Artifact roots stay separate for repeated qualification attempts.

Cumulative lint/format covers all changed Python source and these tests/helper. Cumulative
strict typing covers all changed canonical apps/tests paths; full gate typing remains
unverified. Import contracts inspect the public source packages only. Frontend selection
is nativeResults.test.ts plus the already approved workflowModel/documents/documentTabs
compatibility tests. Reuse retained build/navigation evidence only when source and exact
artifact byte identities are unchanged; never copy another owner's generated bundle.

Shared README/CLAUDE/generated docs remain intentionally unchanged in this isolated
qualification correction. This guide records scoped behavior; the original full/private,
combined-tree, live-inference and publication restrictions remain in force.
