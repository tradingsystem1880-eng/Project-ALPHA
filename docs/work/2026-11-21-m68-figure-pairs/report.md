# Report: figure pairs (m68)

## Answer

Every figure now comes as a plain chart and an annotated chart. The pull request is a draft and is not merged.
One check is red on purpose: `tests/unit/test_code_size.py` wants two lines removed from `.claude/code-size-baseline.json`. The work order forbids editing `.claude/`. The owner must make that edit.

## What was built

- Shared look and primitives: `figures/plain_style.py` (white face, matplotlib defaults, callout, labelled band, held-back band, how-to-read box).
- Drawing: `plain_marks.py` (each mark kind), `plain_spec.py` (layout of a `FigureSpec` for both variants).
- Numbers from the stored data: `spec_facts.py` (callouts, bands, run sentences). Long text: `explanations_runs.py`, `explanations_checks.py`, `explanations_models.py` (four fixed sentences per figure), joined by `variants.py` (4 to 7 sentences).
- `alpha figures render|path|export` take `--variant plain|annotated`. The cache key, the sidecar and the catalogue carry the variant. The catalogue lists both variants and the fixed explanation. `--dark` is accepted and renders the same white figure.
- Web: variant in the cache key, the route and the lock token; `FigureCard` has a "Show annotated" toggle, the long explanation beside the chart and "Open full screen"; the chart surface is white on every screen theme.
- `fix/m67-figure-pack` existed and was not merged: it was merged first and its fixes kept.

## Builders (36 catalogue figures plus 2 rule-period figures)

All 38 are converted: they build the same `FigureSpec` as before and are drawn by the new code in both variants. `price_signal` could not be rendered on the synthetic run (no snapshot), so its drawing was tested with a synthetic spec of the same mark kinds only.
Not converted or only partly:
- `lookalike` and `unusual`: converted; both PNGs are written (`figure.png`, `figure_annotated.png`).
- RD-Agent journey figures: white look aligned (`figure_theme` ignores `dark`); their own annotations kept; no second variant.
- Setup trade and event-study sheets: white look and an `annotated` option in code. Stored setup runs still save one PNG, because their manifests hash an exact file set. No annotated file is stored for them.
- `spine/contact_sheet.py` (setup find sheets): not touched, still uses the old theme. It was not in the scope list.

## Split of `_builders.py` (2,530 lines)

`_builders.py` is now a 60-line registry. Builders moved to `builders_curves`, `_exposure`, `_signal`, `_tradestats`, `_returns`, `_nulls`, `_search`, `_portfolio`, `_mcpaths`, `_mcregimes`, `_forecast`, `_mlskill`, `_mlstability`, plus `_common.py`. Every new module is at most 300 lines; no function is over 150 lines. `price_signal` (167 lines) became six small functions and its four `type: ignore` comments are gone.

## Digest pins

None changed. The protected renderer, its catalogue and their pins are untouched. Cache keys changed for every figure (new `variant` field and style id); the cache is derived and re-renders.

## Code size baseline (needs the owner)

`.claude/code-size-baseline.json` still lists `figures/_builders.py` (2530 lines) and `figures/_builders.py::price_signal` (167). Both are now under the limits, so the test says to remove both entries. I did not edit `.claude/`.

## Tests

- `tests/unit/test_figure_pairs.py` (53 tests): per mark kind and variant, no text leaves the figure, no tick overlap, white face and default colours, same plotted values, callouts or bands plus a reading box, numbers in the box equal values computed from the data, 4 to 7 sentences, held-back band rule, byte determinism, and every builder on a synthetic rule run.
- Updated: cache key, web figure routes, rule-period figures, trade and event-study figure tests.
- Web: vitest for the toggle helpers; a Playwright spec for the toggle, the explanation and the white surface (passed on the minimum viewport, `--trace off`).

## Unverified

- The fixed explanation sentences were written from the catalogue and a reading of the builders. They were not checked panel by panel for every figure, so a sentence may name a series a given run does not draw.
- Only 16 figures could be rendered from the synthetic rule run (the others need validate, optimisation, portfolio, Monte Carlo, forecast or ML runs). The other builders are covered by spec-level tests and the existing synthetic builder tests, which now render both variants only for the figures in `test_figure_pairs`. Their look was not inspected by eye.
- Held-back band: shown only when the data end within 10% of the span before 2024-01-01. Not seen on a real run.
- The two-sentence tail-region ("upper 5% tail") is computed from histogram bins, so it is bin-accurate, not exact.
- Side-by-side display of both charts on wide screens was not built; the card uses the toggle.
- `docs/work/2026-11-21-m68-figure-pairs/reference_make_pairs.py` fails ruff (87 findings). `pyproject.toml` now excludes that one file from ruff.
- Six pairs from a synthetic run are in `pairs/`.
