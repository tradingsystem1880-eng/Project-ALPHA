# Exploratory Analysis Design

**Protocol id:** `exploratory-analysis` · **Packet kind:** `research_case`

## Purpose
Design descriptive, assumption-revealing analyses of the phenomenon that deliberately avoid
strategy fitting — exploration maps the terrain before confirmation stakes a claim.

## Method
1. Propose descriptive views bound to registered questions: event frequency and clustering,
   conditional forward-return distributions (not just means), pre-event control behaviour,
   sample composition over time.
2. Every proposed analysis names: the exact inputs, the statistic, the uncertainty treatment
   (cluster-aware where events overlap), the chart category it feeds, and what answer would mean
   what.
3. Prefer estimates with intervals over test decisions at this stage; exploration measures sizes,
   it does not declare victories.
4. Design against the registered evidence topology: exploration consumes D1 only, and every
   analysis must be executable inside the registered budget with a stated cost.
5. Act as a research teammate: propose up to three useful questions the owner did not ask.
   Prioritize what could change the next decision; explain a justified skip instead of filling a
   checklist. Each proposal names its evidence, competing explanation, test, missing data,
   decision value and stop condition. Suggestions do not authorize execution.
   For an already-permitted, observed diagnostic run, `alpha research diagnostic suggest RUN_ID --as-of DATE` provides a verified
   retrospective brief and a non-exhaustive question floor. Extend it with typed `--proposals`
   bound to its `basis_sha256`; resolved pointers establish binding, not truth.
   Consider loss concentration, execution defects, conditional performance, costs, asset transfer
   and search selection when relevant. Do not invent macro causes or remove losing periods.
6. Mark every output EXPLORATORY; nothing from this stage can be quoted as confirmation.

## Output contract
Analysis-plan candidates (descriptive families with registered grids) proposed for the owner's
contract; commentary as `test_design` notes.

## Boundaries
No parameter optimisation, no rule search, no peeking at D2/D3. An exploratory result is a
hypothesis refiner, never a headline.
