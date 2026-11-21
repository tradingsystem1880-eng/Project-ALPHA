# Brief: every figure as a pair, plain standard chart and annotated explained chart

Task: convert the matplotlib figure pack to the style the owner approved on 2026-11-21. Every figure comes as a PAIR with the same data and
the same axes: (1) `plain`, the standard chart as a quant draws it in a research notebook with matplotlib defaults; (2) `annotated`, the same
chart with teaching annotations and a long plain explanation. The Workstation shows the pair; charts stay white on the dark screen.

Workspace: `apps/alpha-cli/CONTEXT.md` and `apps/alpha-web/CONTEXT.md`. Read the rows your change matches.

## What the owner said (2026-11-21)

- "Your charts are starting to look vibe coded and AI slop. Stick to the official way quants use matplotlib to visualise data."
- "The charts you were making with RD-Agent were much better. I liked how it was annotated."
- "For each of them you can show the original chart and an annotated, more explained version."
- Asked to choose after ten sample pairs: "Yes, but more explanation." Charts on the dark screen: "Keep charts white."

## The approved style

The reference is `reference_make_pairs.py` in this folder (a standalone script that made the ten approved sample pairs from a stored
`alpha validate` run). Copy its conventions, not its file layout.

- **Plain:** white background, matplotlib default colour cycle, a light grid, a plain title ("SPY Drawdown (Underwater Curve)"), axis labels
  with units, a legend. No dark or navy theme, no custom fonts, no gradient fills, no decorative chrome. Monte Carlo: thin coloured paths, one
  thick red line labelled "Original", a black zero line.
- **Annotated:** the same chart plus (a) callouts with arrows on the points that matter, computed from the data (worst drawdown with its
  dates and depth, highest and lowest point, longest time below a peak, the observed value against a distribution, the 5% tail); (b) labelled
  shaded regions (tested period, named crisis windows, and a hatched "held back, not used" band at the right for time-series charts); (c) a
  "How to read this chart" box under the plot. The owner asked for MORE explanation than the samples: 4 to 7 plain sentences per figure:
  what each axis is, what each line or bar is, what to look for, how this run reads on it (numbers computed from the data), what the chart
  cannot tell you. Standard trading terms are fine. Readings only: no pass/fail, no grades, no advice, never a promise of profit.
- Annotations must not hide the data. No text may leave the figure. Numbers: percent with one decimal, dates as YYYY-MM.

## Scope

1. `apps/alpha-cli/src/alpha_cli/figures/_builders.py` (every builder in `BUILDERS`), `rule_periods.py`, `rdagent_journey_figures.py`
   (already close to the style: keep its annotations, align the plain look), `spine/setup_trade_figure.py`, `spine/event_study_figure.py`,
   `_lookalike_figures.py`. One shared helper module for the plain style and for the annotation primitives (callout, labelled band,
   held-back band, how-to-read box). The file `_builders.py` is 2,530 lines: split it by figure family while you are there; no function over
   150 lines; new modules at most 300 lines.
2. `alpha figures render` gains a variant option (`plain` | `annotated`); the JSON catalogue lists both and carries the long explanation
   text. The catalogue in `packages/alpha-research/src/alpha_research/figures/catalog.py` is PROTECTED (hash-bound): do not edit it; keep
   its short text and add the long text in a new file under `apps/alpha-cli`.
3. The dark and navy themes go: one white standard look. Remove the `--dark` code path only if nothing else needs it; otherwise make it
   render the same white figure and say so. Update the web side (`apps/alpha-web/src/alpha_web/_figures.py`, `components/FigureCard.tsx`,
   `FigureSurface.tsx`): each figure card shows the plain chart with a "Show annotated" toggle (or both side by side when wide), the
   long explanation beside it, an "open full screen" action, on a white card in both screen themes. Cache keys include the variant.
4. If the branch `fix/m67-figure-pack` exists on origin and is not yet merged, merge it into your branch first: it fixes defects in the
   same builders (overlapping labels, the parameter surface, clipped text, a wrong return series on rule tests). Keep its fixes.

## Tests (first)

- Per figure and variant: renders on a synthetic run; no text bounding box leaves the figure; no overlapping tick labels; the plain variant
  has a white face colour and uses the default colour cycle; the annotated variant has at least one callout or labelled band and a
  how-to-read box whose numbers equal values computed from the run's stored data.
- The plain and annotated variants plot the same data (same line/bar values).
- Figure digest pins: update only for figures you changed, and say so in the report.
- Web: unit tests for the toggle and the explanation; a Playwright spec (`--trace off`).

## Rules

- Protected paths, not to be edited: `packages/alpha-research/src`, `packages/alpha-validation/src`, `workers/**`, `apps/alpha-mcp/**`,
  `tests/bias_guards`, `tests/oracles`, `tests/unit/test_claude_harness_*.py`, `.semgrep/`, `.github/`, `.claude/`, `.agents/`, top-level
  `scripts/`, `uv.lock`, `CLAUDE.md`, `AGENTS.md`. The HTML tear sheet lives in the validation package: leave it.
- No `noqa`, `type: ignore`, `eslint-disable`, `vars(`, `__doc__`, `inspect`, `.__dict__`. No new dependency.
- If `tests/unit/test_code_size.py` asks to LOWER a baseline entry: do not pad and do not edit `.claude/`; report the numbers.
- Display only: figures read stored run artefacts; nothing reads past a run's cut-off or into the held-back period.
- Synthetic fixtures only in the repository. Docs updated and stamped (`uv run python scripts/fs.py verify <doc>`; `fs.py stale` 0).

## Done

A draft pull request from branch `feat/m68-figure-pairs`, `ci-ok` green, not merged. `report.md` in this folder lists: each builder
converted or not (with the reason), the split of `_builders.py`, digest pins changed, and what is unverified. Attach six pairs rendered
from a synthetic run to the pull request.
