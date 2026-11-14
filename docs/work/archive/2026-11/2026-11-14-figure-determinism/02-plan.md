# Hash-bound figures depend only on their inputs

**Delivery state:** Completed — built and checked on branch `m4/figure-determinism`; done when its pull request merges (filed straight into the archive: the work-in-progress ceiling is reached).
**Build class:** hard — quant tier: `packages/alpha-research/src` (approval-bound) and `packages/alpha-validation/src`.

## For the owner

- What changes: the research charts (D0 detector, D1, D2 and the crypto research charts) and the
  tear-sheet charts now come out with the same bytes whatever ran earlier in the same process
  and whatever a local Matplotlib config file says. Today they do not: once anything restyles
  Matplotlib globally (QuantStats does when a tear sheet is first made), later research charts change.
- What does not change: a clean process makes exactly the same bytes as before, so stored figures
  still verify and no renderer version moves.
- One-off cost: one file under `packages/alpha-research/src` changes behaviour, so every research
  approval (D1, D2, crypto research contracts) made before this change stops verifying and must be
  re-approved by you once. Rule-lane approvals are not affected.
- Nothing for you to decide; no approval, promotion or acceptance is made by this work.

```json
{
  "schema_version": 1,
  "title": "Hash-bound figures depend only on their inputs",
  "context": "render_research_line_chart (alpha_research/rendering.py) renders inside rc_context(style) with only ten keys set, so every other key comes from the live, process-global rcParams. Importing quantstats_lumi (alpha_validation/tearsheet.py, on the first tear sheet) runs seaborn.set at import and changes 34 keys for the rest of the process; a matplotlibrc does the same in a fresh process. The research PNGs (detector-validity.png, d1-primary-association.png, d2-one-shot-confirmation.png, the crypto research charts) are hash-bound run artefacts, so their bytes depended on process history. The tear sheet (tearsheet.html, hash-bound in validate and portfolio runs) renders QuantStats under the live rcParams too. render_figure (alpha_research/figures) already seeds from rcParamsDefault and is immune. Fix both writers at the root, keep clean-process bytes identical, and add tests that render, pollute, render again for every writer.",
  "assumptions": [
    {
      "statement": "In a clean process with no matplotlibrc, rcParams equals rcParamsDefault, so seeding the research chart from rcParamsDefault keeps today's clean-process bytes.",
      "verified_by": "Fresh-process comparison of every rcParams key (no differences) and renders before and after a prototype of the fix: reference chart sha256 18538bf6... unchanged; golden-flow PNG sha256 unchanged."
    },
    {
      "statement": "QuantStats-Lumi 1.1.5 restyles Matplotlib only at the first import of quantstats_lumi._plotting.core (font.family, then seaborn.set), so re-running that module's top level on top of rcParamsDefault rebuilds the exact style a clean process renders the tear sheet under.",
      "verified_by": "Reading quantstats_lumi/_plotting/core.py lines 21-50; prototype tear sheet sha256 7d0caab1... equal before and after, also after an earlier rcParams change and under a hostile MATPLOTLIBRC."
    },
    {
      "statement": "No product command renders a tear sheet and a research chart in one process, and the web app and MCP server render through the CLI subprocess.",
      "verified_by": "Import of every alpha_cli module leaves rcParams unchanged; grep: render_tearsheet_html/render_returns_tearsheet only in validate_cmds and backtest_cmds; alpha_web/_figures.py and the suite runner use subprocesses; alpha_mcp imports no matplotlib."
    }
  ],
  "alternatives_considered": [
    "Wrap each of the six research chart call sites in apps/alpha-cli with a pinned rc_context: rejected, it scatters the fix over approval-bound CLI modules and leaves the renderer itself history-dependent.",
    "Bump the research rendering version and change the look: rejected, not needed; the fix keeps clean-process bytes and only removes the history dependence.",
    "Copy QuantStats' seaborn.set arguments into tearsheet.py: rejected, it needs seaborn as an undeclared direct dependency and silently drifts if QuantStats changes; re-running QuantStats' own module on pinned defaults, held by a fresh-process drift test, cannot drift unnoticed.",
    "Only fix the tests (reset rcParams in a fixture): rejected, the dependence is in the product and also reaches a fresh process through a matplotlibrc."
  ],
  "pre_mortem": [
    "Seeding from rcParamsDefault also sets 'backend', which rc_context does not restore and which would reset the process backend: excluded by key, as tested.",
    "Clean-process bytes change after all, so stored figures could no longer be reproduced: pinned sha256 values measured before the fix are asserted after it, for the research chart, the tear sheet and the golden flows.",
    "Reloading QuantStats' plotting module has a side effect outside rcParams: it is the same code the first import runs; rcParams are restored by rc_context and the test checks the process rcParams are unchanged after a tear sheet.",
    "The new tests are slow (a tear sheet takes seconds): pollutions per tear sheet are kept to a few."
  ],
  "slices": [
    {
      "title": "Research line chart renders under pinned Matplotlib defaults",
      "verify": "uv run pytest -q tests/unit/test_figure_history_determinism.py tests/unit/test_research_chart_rendering.py tests/unit/test_figure_render.py",
      "expected": "The research chart and render_figure (SVG and PNG) give identical bytes before and after each pollution; the reference research chart keeps sha256 18538bf605320bdfe580031d611b79cd745cd102f7af5247ea62c4bb804098b7.",
      "rollback": "Revert rendering.py and delete the new test file.",
      "files": [
        "packages/alpha-research/src/alpha_research/rendering.py",
        "tests/unit/test_figure_history_determinism.py"
      ],
      "status": "pending"
    },
    {
      "title": "Tear sheet renders under QuantStats' own style rebuilt from defaults",
      "verify": "uv run pytest -q tests/unit/test_figure_history_determinism.py tests/unit/test_tearsheet.py tests/integration/test_tearsheet_html.py",
      "expected": "The tear sheet keeps sha256 7d0caab1f81acd42b08c4ace3d0413adcf46fb74922cd111150627f2b7ce6e2b before and after each pollution; the rebuilt style equals a fresh process's rcParams after import quantstats_lumi; making a tear sheet leaves the process rcParams unchanged.",
      "rollback": "Revert tearsheet.py and the tear-sheet tests in the new file.",
      "files": [
        "packages/alpha-validation/src/alpha_validation/tearsheet.py",
        "tests/unit/test_figure_history_determinism.py"
      ],
      "status": "pending"
    },
    {
      "title": "Research golden pins PNG bytes instead of masking their size",
      "verify": "uv run pytest -q tests/integration/test_research_cmds_golden.py",
      "expected": "The golden records each PNG's raw sha256 and size; it passes alone and after a test that made a tear sheet in the same process.",
      "rollback": "Restore the size mask and the previous golden fixture.",
      "files": [
        "tests/integration/test_research_cmds_golden.py",
        "tests/fixtures/research_cmds_golden.json"
      ],
      "status": "pending"
    },
    {
      "title": "Owning documents",
      "verify": "uv run python scripts/gate.py check --all",
      "expected": "research and validation invariants state the rule; plan, roadmap and status regenerate cleanly; fs.py stale shows nothing for them.",
      "rollback": "Revert the two invariant sections and this task folder.",
      "files": [
        "docs/reference/invariants/research.md",
        "docs/reference/invariants/validation.md",
        "docs/work/archive/2026-11/2026-11-14-figure-determinism/01-brief.md",
        "docs/work/archive/2026-11/2026-11-14-figure-determinism/02-plan.md",
        "docs/work/archive/2026-11/2026-11-14-figure-determinism/04-verify.md",
        "docs/work/archive/2026-11/2026-11-14-figure-determinism/05-handoff.md",
        "docs/roadmap/README.md",
        "STATUS.md"
      ],
      "status": "pending"
    }
  ],
  "tier_impact": [
    "quant",
    "determinism"
  ],
  "docs_to_update": [
    "docs/reference/invariants/research.md",
    "docs/reference/invariants/validation.md"
  ],
  "out_of_scope": [
    "Any change to what a figure shows, RENDERER_VERSION, the research evaluator 'rendering' identity or FIGURES_CACHE_VERSION",
    "Cross-machine font differences (QuantStats asks for Arial first; a machine with Arial installed renders a different tear sheet)",
    "render_figure (alpha_research/figures), already seeded from rcParamsDefault",
    "Approving, re-approving or promoting anything"
  ],
  "files": [
    "packages/alpha-research/src/alpha_research/rendering.py",
    "packages/alpha-validation/src/alpha_validation/tearsheet.py",
    "tests/unit/test_figure_history_determinism.py",
    "tests/integration/test_research_cmds_golden.py",
    "tests/fixtures/research_cmds_golden.json",
    "docs/reference/invariants/research.md",
    "docs/reference/invariants/validation.md",
    "docs/work/archive/2026-11/2026-11-14-figure-determinism/01-brief.md",
    "docs/work/archive/2026-11/2026-11-14-figure-determinism/02-plan.md",
    "docs/work/archive/2026-11/2026-11-14-figure-determinism/04-verify.md",
    "docs/work/archive/2026-11/2026-11-14-figure-determinism/05-handoff.md",
    "docs/roadmap/README.md",
    "STATUS.md"
  ]
}
```

## Read first

| Read | Section | When |
|---|---|---|
| [research invariants](../../../../reference/invariants/research.md) | Figures and charts | always |
| [engineering rules](../../../../reference/invariants/engineering.md) | Hash-bound source bytes | always |
| [testing invariants](../../../../reference/invariants/testing.md) | Quant sweeps | always: the new test's name and the mutation gate's test selection |
| [rendering.py](../../../../../packages/alpha-research/src/alpha_research/rendering.py) | `render_research_line_chart` | slice 1 |
| [render.py](../../../../../packages/alpha-research/src/alpha_research/figures/render.py) | `render_figure` | slice 1: the seeding it already does |
| [tearsheet.py](../../../../../packages/alpha-validation/src/alpha_validation/tearsheet.py) | `_render_with_section` | slice 2 |
| [research chart tests](../../../../../tests/unit/test_research_chart_rendering.py) | `_series`, `_chart` | slice 1: the reference chart |
| [tear sheet tests](../../../../../tests/integration/test_tearsheet_html.py) | `test_returns_tearsheet_is_byte_stable_across_fresh_processes` | slice 2: the reference inputs |
| [research golden](../../../../../tests/integration/test_research_cmds_golden.py) | `_Normalizer._field`, `_main` | slice 3 |

## Slices

1. `rendering.py`, `render_research_line_chart`: import `rcParamsDefault` with `rc_context`, and
   enter `rc_context({**pinned, **style})` where `pinned` is every `rcParamsDefault` item except
   the `backend` key (rc_context never restores `backend`, and this renderer draws on an explicit
   Agg canvas). One short comment says why. Nothing else in the file changes.
2. `tearsheet.py`, `_render_with_section`: import `quantstats_lumi` inside a bare
   `matplotlib.rc_context()` so its import-time restyling does not outlive the import; add a
   private `_quantstats_style()` that, inside `rc_context(pinned defaults without backend)`, runs
   `importlib.reload(quantstats_lumi._plotting.core)` and returns the resulting rcParams without
   `backend`; render with `rc_context({**_quantstats_style(), "svg.hashsalt": ...})`. Docstring
   says what it rebuilds and why.
3. `tests/unit/test_figure_history_determinism.py` (in `tests/unit` because the mutation gate
   stages only unit, oracle and bias-guard tests; the name holds "determinism" for the sweep).
   Writers: the research chart (reference chart from `test_research_chart_rendering.py`, pinned
   sha256 above), `render_figure` SVG and PNG (a small two-panel time spec), and the tear sheet
   (reference inputs from `test_tearsheet_html.py`, pinned sha256 above). Pollutions, each applied
   inside a bare `matplotlib.rc_context()` so the test process is restored: one rcParams key
   (`xtick.major.size` = 6.0, the smallest known to change the old research PNG), QuantStats'
   restyle (reload its plotting module), a built-in style (`matplotlib.style.use("ggplot")`), a
   batch of keys a matplotlibrc might set (`font.size`, `lines.linewidth`, `timezone`,
   `axes.prop_cycle`, `text.hinting`), and "other figures first" (another research chart, a
   `render_figure` PNG, a pyplot figure created and closed). Each writer: render, pollute, render,
   assert identical bytes (the tear sheet with three of these pollutions to bound run time).
   Also: `_quantstats_style()` equals the rcParams a fresh `python -c` process has after
   `import quantstats_lumi` (compared key by key as `repr`), and making a tear sheet leaves the
   test process's rcParams unchanged.
4. Golden: `_Normalizer._field` keeps a `.png` entry's `sha256` and `size_bytes` raw (not
   tokenised, not masked) and drops the stale comment; regenerate the fixture with
   `uv run python tests/integration/test_research_cmds_golden.py --write`.
5. Documents (Claude): the research invariants line for `render_research_line_chart` and a tear
   sheet line in the validation invariants; this task folder.

## Test plan

Slices 1 and 2 are test-first: before the source change, the new pollution tests must fail for
the research chart and the tear sheet with a byte mismatch (not an import error), and pass for
`render_figure`; after it, all pass with the pinned clean-process hashes. Slice 3 passes alone and
after `tests/unit/test_figure_history_determinism.py` in one pytest process. `gate.py determinism`
runs the new file and the golden twice under other time zones and hash seeds.

## Look-ahead, determinism and import impact

No data access, statistic or point-in-time read changes. Determinism improves: the bytes of the
research PNGs and the tear sheet stop depending on process history and local Matplotlib config.
No new import edges; `quantstats_lumi` stays confined to `tearsheet.py`.
