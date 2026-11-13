# Archived work

Finished tasks, filed by the month in their name (`YYYY-MM/`). A task is finished when its plan's
`**Delivery state:**` line says `Completed — <evidence>` or `Superseded by <relative path>`.

Two shapes live here:

- **Task folders** `YYYY-MM/YYYY-MM-DD-<slug>/` with the stage outputs `01-brief.md`,
  `02-plan.md`, `04-verify.md` and `05-handoff.md`. Stage 05 of the
  [delivery pipeline](../../../workflow/stages/05-land/CONTEXT.md) moves a finished task here.
- **Single plan files** `YYYY-MM/YYYY-MM-DD-<slug>.md`: every plan finished before 2026-11-14,
  when plans lived in `docs/superpowers/plans/`. They are historical records: their text and JSON
  front blocks are kept as written, so a path inside them may name a location that no longer
  exists. Links to moved documents were rewritten mechanically.

Two docstrings in `packages/alpha-research/src/alpha_research/panel.py` still name the old flat
paths of `2026-09/2026-09-11-edge-first-phase-c-screening-lane.md` and
`2026-09/2026-09-17-cancellation-and-research-walkthrough.md`; the bytes of that package feed the
research identity hash, so the paths are not rewritten there.

`tests/unit/test_plan_schema.py` checks that every plan here is finished and filed under the
month of its name. The [roadmap index](../../roadmap/README.md) counts plans per month.
