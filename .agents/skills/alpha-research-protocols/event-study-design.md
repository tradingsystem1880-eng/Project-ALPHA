# Event-Study Design

**Protocol id:** `event-study-design` · **Packet kind:** `experiment`

## Purpose
Specify a time-correct event study for the registered claim: exact events, exact clocks, exact
controls — the difference between an estimate and an accident.

## Method
1. Define the event precisely from the contract: detection rule, the exact bar at which it becomes
   knowable (availability), and the action clock relative to it. Every timestamp must answer
   "what was knowable then?"
2. Define outcome windows in trading time with explicit handling for sessions, gaps, and early
   closes; never mix calendar and trading clocks silently.
3. Handle overlap: overlapping outcome windows are dependent — purge overlaps or model the
   dependence with the registered cluster unit; state the effective sample size, not the raw one.
4. Specify matched controls: pre-event windows matched on the registered confounder strata,
   drawn point-in-time, never re-used across events in ways that leak.
5. Register the estimator (event-minus-control), the uncertainty method (cluster-aware bootstrap),
   the multiplicity family it belongs to, and the exact grid — no unregistered variations.
6. Cost the design against the budget and define checkpoints so a killed run resumes exactly.

## Output contract
A registered event-study spec for the analysis plan (`test_design` note + analysis-plan
proposal); execution happens only through the governed durable runner.

## Boundaries
No fills, no orders, no costs, no sizing — this is a phenomenon measurement, not a backtest.
