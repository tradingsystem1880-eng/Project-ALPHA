# ADR-0041: No hidden test suite; the seed tests are visible acceptance tests

**Status:** Accepted
**Date:** 2026-11-13
**Deciders:** Project ALPHA owner and AI build agents

## Context

[ADR-0034](0034-agent-operating-system-v2.md) (item 2) added a hidden suite at `tests/holdout/`:
behaviour tests the authoring agent may run but never read, so that code could not be tailored
to its tests. The 17 tests were staged in `tests/holdout_seed/` for the owner to move into place
with one `git mv`.

- **It was never activated.** `git log --all -- 'tests/holdout/*'` is empty on every branch.
  The seed tests ran anyway, as ordinary tests, in every test run.
- **Every review needed an owner exception.** The independent reviewer had to run the absent
  suite, so no review could pass without owner sign-off. About 25 per-delivery exceptions
  accumulated inside `.claude/agents/independent-reviewer.md` (649 lines, most of them
  exceptions), with four more records in `docs/records/`.

## Decision

- The hidden-suite requirement is removed from the reviewer, the manual and the rules.
- The 17 seed tests are visible acceptance tests at `tests/acceptance/` (gauntlet gates, DSR and
  PBO thresholds, walk-forward embargo geometry, t+1-open fills, fees, two benchmark defects).
  They stay in the fast tier (`tests/_tiers.py`) and in the set `gate.py check` always runs
  (`scripts/gate_select.py:ALWAYS`). Their test code, file names and `holdout` marker are
  unchanged.
- The exception passages move, verbatim, to
  [one historical record](../records/2026-11-hidden-suite-exceptions.md).
- The guard rules that deny agent access to `tests/holdout/**` (`.claude/settings.json`,
  `scripts/claude_hooks.py`) are left as they are: the folder does not exist, so they block
  nothing.

The original goal, code that is not tailored to its tests, is still served by checks that run:

- bias guards in `tests/bias_guards`, each with a must-fail leaky twin
  (`tests/bias_guards/test_future_poison_pattern.py`, `test_poison_variants.py`);
- known-truth calibration, metamorphic and differential oracles in `tests/oracles`;
- slow oracles and the mutation gate in CI whenever a quant source module changes
  (`scripts/gate_components.py`, backend component);
- the weekly exhaustive mutation sweep (`.github/workflows/mutation-weekly.yml`).

## Consequences

- A review can pass on its own evidence; no owner exception is needed for an absent suite.
- Anyone may read and extend the acceptance tests. Tests an author can read can in principle be
  gamed; the leaky twins, oracles and mutation testing above are what catch that.
- The reviewer prompt shrinks from 649 to 76 lines.
- The four earlier exception records in `docs/records/` and the dated plans stay as history.
- Anchors: `tests/acceptance/README.md`, `scripts/gate_select.py:ALWAYS`,
  `tests/unit/test_platform_tier.py::test_bias_guards_oracles_and_acceptance_are_never_platform`.
