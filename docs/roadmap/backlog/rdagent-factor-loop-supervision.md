# RD-Agent factor loop under the command line's job supervisor

**Status:** Scoped
**Rough size:** M

## Problem / why

The ALPHA-judged factor loop ([ADR-0049](../../adr/0049-alpha-judges-rdagent-factors.md)) is
started by `workers/rdagent/factor_loop_launch.py`: one command that verifies the pinned source
and runtime, freezes the panel, starts the model gateway with its call cap, runs the loop in its
own process group with a wall-clock limit, cleans up on cancel and writes a receipt. It is not yet
an `alpha` command: no ControlStore job, no budget reservation before launch, no single-owner
lock, no recovery screen. `apps/alpha-cli/src/alpha_cli/native_supervisor.py` accepts only its
closed launch types (fixture, rule, costed, daily, stock) and refuses anything else by design.

## What "done" looks like

- A typed launch (`FactorLoopLaunch`) beside `NativeLaunch` and `StockFixtureLaunch`, with a fixed
  command built from the measured factor runtime profile, the source digest and the frozen panel
  receipt; accepted by `start_synthetic_owner`'s type check and `_entry`.
- A ControlStore job (`stage: "rdagent_native"`) with a reservation of model calls and wall
  seconds made before spawn, consumed even when interrupted, as the stock route does.
- `alpha research diagnostic native-result` reads the run's receipt and `evaluations.jsonl`.
- The gateway's run cap equals the reservation; the launcher's own refusal above 60 calls stays.

## Dependencies

None from the owner for the mechanism. Touches `native_supervisor.py` and `control_store.py`,
which other work also changes; coordinate first.

## Sources

- [Task record](../../work/archive/2026-11/2026-11-14-rdagent-alpha-judged-loop/02-plan.md)
- [Command line native invariants](../../reference/invariants/cli-native.md)
