# PROJECT ALPHA — DEEP REFACTOR, SIMPLIFICATION & AI-NATIVE QUANT RESEARCH INFRASTRUCTURE AUDIT

You are operating locally inside the **PROJECT-ALPHA** repository in **Codex Plan Mode**.

This is a planning and architecture task.

**Do not begin implementing the refactor.**

Your job is to deeply inspect the actual local repository, understand how the entire system currently works, identify unnecessary complexity and technical debt, determine what should and should not be changed, and produce the final evidence-based implementation plan for a later Codex execution session.

The local repository is the authoritative source.

Do not assume:

- my description is completely accurate;
- existing documentation is completely accurate;
- previous AI-generated architecture decisions are automatically correct;
- existing complexity is automatically bad;
- newer code is automatically better;
- something is required simply because an old document says it is.

Inspect the repository and reach your own engineering conclusions.

---

# 1. OWNER CONTEXT

PROJECT ALPHA is a private, single-owner quantitative financial-market research and strategy-development platform.

It covers areas such as:

- stocks;
- crypto;
- financial-market data;
- quantitative research;
- hypothesis development;
- feature research;
- pattern research;
- event studies;
- strategy development;
- backtesting;
- parameter analysis;
- optimization;
- Monte Carlo analysis;
- statistical validation;
- machine learning;
- regime analysis;
- screening;
- forecasting;
- options;
- research literature;
- reporting;
- paper trading / later execution-related workflows;
- web/CLI interfaces.

The project has been developed almost entirely through **AI-assisted / vibe-coded development**.

I am not a professional software engineer.

AI coding agents will continue to be the primary developers of this repository.

Going forward, **Codex is intended to be a first-class and potentially primary coding agent**.

That fact should strongly influence the target architecture.

---

# 2. WHY THIS AUDIT EXISTS

Because the project has been built almost entirely by AI, I suspect it has accumulated some combination of:

- unnecessary abstractions;
- duplicated implementations;
- duplicated schemas;
- duplicated registries;
- duplicated documentation;
- unnecessary wrappers;
- large orchestration modules;
- custom infrastructure where standard tooling exists;
- overly elaborate AI-agent governance;
- excessive prose instructions;
- hand-maintained mappings;
- multiple sources of truth;
- stale compatibility layers;
- dead code;
- old migrations;
- overly fragmented packages;
- excessive indirection;
- repeated validation logic;
- inefficient processes;
- repetitive repository scans;
- large AI context requirements;
- AI being asked to remember or reason about things software could enforce.

These are hypotheses.

**Verify them. Do not assume them.**

PROJECT ALPHA may also contain unusual-looking complexity that is correctly protecting important quantitative or financial invariants.

Preserve those protections where justified.

---

# 3. PRIMARY OBJECTIVE

The overall objective is:

> **Make PROJECT ALPHA substantially simpler, clearer, smaller where appropriate, easier to navigate, more deterministic, more reproducible, and cheaper for AI agents to operate—while preserving or strengthening its quantitative research capability, financial correctness, statistical rigor and safety.**

This is primarily a:

- refactor;
- simplification;
- architecture cleanup;
- research-infrastructure cleanup;
- tooling cleanup;
- AI-development-environment redesign;
- reproducibility improvement;
- methodology standardization project.

It is **not primarily a new-feature project**.

Do not solve complexity by adding another large abstraction layer.

---

# 4. THE DEEPER OBJECTIVE

The most important long-term goal goes beyond ordinary code cleanup.

PROJECT ALPHA should become a **well-defined quantitative research laboratory for AI**.

Today, there is a potential failure mode inherent to AI-operated research:

Two prompts expressing effectively the same research question can result in different experiments because the AI independently decides:

- which dataset to use;
- which period to use;
- which provider to use;
- how to preprocess the data;
- how to split samples;
- what metric to optimize;
- which Monte Carlo method to use;
- what constitutes a null;
- how many simulations to run;
- which seed to use;
- which parameters to sweep;
- what parameter ranges to use;
- whether to use walk-forward analysis;
- whether to apply multiple-testing corrections;
- what charts to produce;
- which robustness tests to run;
- how to define the holdout;
- when evidence is strong enough;
- what methodology to use.

That means:

> **natural-language prompt variation can become hidden experimental variation.**

For quantitative finance, this is dangerous.

The architecture should instead move toward:

> **AI determines WHAT scientific/financial question is being asked.**

> **PROJECT ALPHA defines HOW approved methodologies are executed.**

AI should not rebuild the laboratory every time it receives a prompt.

---

# 5. CORE DESIGN PRINCIPLE

Use the following hierarchy when deciding where responsibility belongs:

**compiler / language guarantee**

↓

**type system / static analysis**

↓

**schema / contract**

↓

**single machine-readable source of truth**

↓

**generated code / generated documentation**

↓

**deterministic test**

↓

**small deterministic program**

↓

**concise human/agent documentation**

↓

**AI reasoning / instructions**

The lower down this hierarchy a purely mechanical responsibility sits, the more carefully you should question why.

The guiding question throughout this audit is:

> **Why is an AI being asked to reason about this if deterministic software can enforce it?**

Do not apply this blindly.

Some research choices genuinely require scientific judgment.

But mechanical work should remain mechanical.

---

# 6. IMPORTANT CLARIFICATION ABOUT “COMPILERS”

Do not interpret this task as:

> rewrite PROJECT ALPHA in Rust/C++/Go.

Python remains entirely appropriate for most quantitative/scientific work.

When I refer to compilers and proper tooling, I mean using things such as:

- Python's type system;
- strict static analysis;
- TypeScript compilation;
- schemas;
- code generation;
- dependency enforcement;
- build systems;
- automated formatting;
- linting;
- AST analysis;
- codemods;
- proper package boundaries;
- database constraints;
- reproducible environments;
- deterministic CLI programs;
- standard Unix/Git tooling.

Only recommend native/JIT/compiled implementations for numerical hotspots when:

- profiling demonstrates a real bottleneck;
- the expected improvement is material;
- complexity is justified.

Do not introduce another language merely to appear more professional.

---

# 7. IMPORTANT CURRENT REPOSITORY CONTEXT TO VERIFY

The repository currently appears to already contain significant quality infrastructure.

Verify the current local state rather than trusting this list.

It appears to use or contain:

- Python 3.12;
- `uv`;
- a workspace with multiple packages/apps;
- Ruff;
- strict `mypy`;
- import-linter;
- pytest;
- Hypothesis;
- high coverage requirements;
- bias-guard tests;
- oracle/metamorphic tests;
- holdout tests;
- deterministic execution expectations;
- wheel builds;
- TypeScript;
- `tsc`;
- oxlint;
- generated OpenAPI;
- generated TypeScript API bindings;
- Vitest;
- Playwright;
- package dependency contracts;
- explicit quantitative invariants.

It also appears to have significant custom AI-development infrastructure around:

- `AGENTS.md`;
- `CLAUDE.md`;
- `.claude/`;
- `.codex/`;
- `.agents/skills/`;
- path-specific rules;
- hooks;
- custom gates;
- agent attestations;
- awareness/index generation;
- custom Codex bridging;
- agent auditing;
- prompt-context injection.

Some current files appear very large, including custom gate/hook infrastructure.

This is an important audit target.

However:

**do not conclude that large = bad.**

First determine what real failure each mechanism prevents.

---

# 8. EXISTING GOVERNANCE IS IN SCOPE

Read all applicable repository instructions because they describe how the repository currently operates.

Respect them during this Plan Mode audit.

However:

**the architecture of those instructions and controls is itself part of the refactor scope.**

If existing documents say:

- Claude is authoritative;
- Codex is only a second opinion;
- particular files must remain authoritative;
- particular AI workflows must remain structured a certain way;

treat that as the **current design**, not necessarily an immutable owner requirement.

The future direction is:

- Codex can be a primary developer;
- repository operation should be agent-agnostic where possible;
- Claude-specific infrastructure should exist only where Claude-specific behavior requires it;
- Codex-specific infrastructure should exist only where Codex-specific behavior requires it;
- common methodology should live in the repository itself;
- deterministic enforcement should replace model-specific prompting wherever practical.

---

# 9. DO NOT DAMAGE THE QUANTITATIVE SAFETY SYSTEM

PROJECT ALPHA is not an ordinary CRUD application.

Do not simplify away protections against:

- look-ahead bias;
- survivorship bias;
- data leakage;
- label leakage;
- future contamination;
- timestamp mistakes;
- corporate-action timing errors;
- invalid session handling;
- improper asset identity;
- incorrect venue assumptions;
- optimistic fills;
- invalid transaction-cost assumptions;
- train/test leakage;
- walk-forward leakage;
- feature leakage;
- hyperparameter leakage;
- holdout contamination;
- multiple-testing bias;
- strategy-selection bias;
- backtest overfitting;
- invalid Monte Carlo construction;
- non-deterministic experiments;
- irreproducible results;
- silent NaN/inf behavior;
- unit mistakes;
- invalid statistical assumptions.

The correct objective is:

> **simpler implementation with equal or stronger guarantees.**

Whenever possible, move important safeguards from prose into executable enforcement.

---

# 10. DO NOT TURN THIS INTO ENTERPRISE SOFTWARE

PROJECT ALPHA is a private research platform.

Avoid unnecessary:

- microservices;
- Kubernetes;
- distributed systems;
- service meshes;
- event buses;
- message queues;
- enterprise IAM;
- plugin systems with one implementation;
- service abstractions around local function calls;
- huge dependency-injection systems;
- speculative extensibility;
- excessive configuration;
- generic frameworks for hypothetical users.

Professional engineering does not mean enterprise complexity.

Prefer boring, understandable infrastructure.

---

# 11. PHASE ONE — BUILD A FACTUAL REPOSITORY MAP

Before recommending major changes, map the repository from the actual local filesystem and code.

Measure where practical:

### Scale

Determine:

- tracked files;
- Python LOC;
- TypeScript/JavaScript LOC;
- shell LOC;
- production LOC;
- test LOC;
- documentation LOC;
- generated LOC;
- vendored LOC;
- AI-control-plane LOC;
- packages;
- applications;
- workers;
- modules;
- tests;
- custom scripts;
- dependencies.

Separate generated/vendored code from owned source.

### Architecture

Map:

- workspace/package dependency graph;
- application entrypoints;
- CLI layer;
- web layer;
- MCP layer;
- workers;
- data/provider boundaries;
- persistence/storage;
- research workflow;
- strategy workflow;
- backtest workflow;
- validation workflow;
- experiment/run identity;
- artifact lifecycle.

### Hotspots

Identify:

- largest owned files;
- largest functions/classes;
- high-complexity functions;
- high fan-in modules;
- high fan-out modules;
- modules with multiple responsibilities;
- repeated code;
- repeated literals;
- repeated registries;
- repeated schemas;
- repeated financial formulas;
- repeated parsing;
- repeated serialization;
- wrappers around wrappers;
- manual dispatch maps;
- obsolete compatibility paths;
- dead code;
- stale migrations;
- unnecessary public APIs.

Do not rank problems by LOC alone.

---

# 12. ESTABLISH A CLEAN BASELINE

Before designing the target architecture, determine the current health of the repository.

Use the repository's existing tooling first.

Inspect/run appropriate safe commands such as:

- `git status`;
- `git log`;
- relevant `git blame`;
- existing repo orientation/index commands;
- Ruff;
- formatting checks;
- strict mypy;
- import-linter;
- pytest;
- bias guards;
- relevant oracle tests;
- current coverage;
- wheel builds;
- frontend type checking;
- frontend lint;
- frontend tests;
- generation-freshness checks.

Where practical, record approximate execution time.

Do not change production code merely to complete this audit.

---

# 13. USE GIT HISTORY AS EVIDENCE

For suspicious complexity:

- inspect commits;
- inspect blame;
- inspect relevant ADRs;
- inspect previous designs;
- identify the original failure being solved.

Classify complexity as:

- still necessary;
- domain-critical;
- workaround;
- historical compatibility;
- obsolete;
- duplicated later;
- accidental AI growth;
- speculative architecture;
- compensating for limitations that no longer exist.

Apply Chesterton's Fence:

> Understand why something exists before recommending removal.

---

# 14. AUDIT “LLM TAX”

Define and measure **LLM tax**.

LLM tax is architecture that unnecessarily causes an AI agent to consume:

- context tokens;
- reasoning;
- tool calls;
- source searches;
- duplicated reading;
- repeated discovery;
- prompt instructions;
- synchronization effort.

Examples to search for:

- enormous mandatory manuals;
- the same invariant in many documents;
- repeated architecture descriptions;
- manual module maps;
- handwritten CLI maps;
- manually synchronized provider lists;
- duplicated frontend/backend enumerations;
- enormous path-rule files;
- multiple overlapping skills;
- context that could be discovered mechanically;
- historical information injected into every session;
- generated information represented as prose;
- repetitive prompts telling agents to perform checks already enforced by CI;
- AI reasoning about dependency rules already representable by import-linter;
- AI being instructed how to format code already handled by Ruff;
- AI checking generated consistency that could be generated from one source.

For significant examples report:

- what the AI currently needs to consume/do;
- why it exists;
- whether it remains necessary;
- deterministic replacement;
- expected reduction in LLM burden.

---

# 15. TARGET CODEX EXPERIENCE

A new capable Codex session should eventually be able to:

1. enter PROJECT ALPHA;
2. read one short root orientation document;
3. run one repository-orientation command;
4. identify the domain involved;
5. discover relevant architecture and invariants;
6. discover existing capabilities;
7. identify the correct implementation location;
8. make the smallest justified change;
9. run deterministic verification;
10. know whether the change is valid.

Codex should not need to ingest a giant encyclopedia before making a normal change.

Think:

> **map, not massive manual.**

Machine-discoverable information should preferably remain machine-discoverable.

---

# 16. AUDIT THE AI CONTROL PLANE DEEPLY

Pay particular attention to:

- `AGENTS.md`;
- `CLAUDE.md`;
- `.claude/`;
- `.codex/`;
- `.agents/`;
- `.agents/skills/`;
- `.claude/rules/`;
- `.claude/settings.json`;
- `scripts/gate.py`;
- `scripts/claude_hooks.py`;
- `scripts/harness_awareness.py`;
- `scripts/harness_models.py`;
- `scripts/harness_quant.py`;
- `scripts/codex_bridge.py`;
- generated awareness/index/state;
- attestation mechanisms;
- review agents;
- control-plane protections.

For each component answer:

1. What real failure does this prevent?
2. How severe is that failure?
3. Is another mechanism already preventing it?
4. Why is custom code required?
5. Could a standard tool enforce it?
6. Could CI enforce it?
7. Could a schema enforce it?
8. Could static analysis enforce it?
9. Could Git hooks/pre-commit/build tooling handle it?
10. Could several systems become one?
11. Does it materially improve Codex?
12. Does it materially increase LLM tax?
13. Does maintaining it cost more complexity than the risk it mitigates?

Be particularly suspicious of:

> **AI-generated infrastructure whose primary purpose is managing AI-generated infrastructure.**

But do not remove valuable controls simply because they are AI-related.

---

# 17. STANDARD TOOLING VS CUSTOM CODE

Search for custom implementations of problems mature tools already solve.

### Python

Evaluate use of:

- Python typing;
- dataclasses/Pydantic where appropriate;
- Ruff;
- mypy;
- pytest;
- Hypothesis;
- import-linter;
- package metadata;
- standard logging;
- `pathlib`;
- standard subprocess primitives;
- SQLite constraints where relevant;
- structured configuration.

### TypeScript

Evaluate:

- strict TypeScript;
- generated API contracts;
- duplicate type definitions;
- duplicate enums/unions;
- backend/frontend synchronization;
- manually maintained registries.

Prefer:

> **one canonical definition → generated projections**

over:

> Python list + TypeScript list + docs list + tests checking that all three stayed synchronized.

A drift test is good.

Making drift structurally impossible is better.

### Shell/process management

Audit:

- custom shell parsing;
- custom tokenizers;
- command interception;
- command allow-lists;
- process wrappers;
- environment handling.

Do not replace secure code with unsafe shell shortcuts.

But also do not maintain a miniature shell language unless there is strong justification.

---

# 18. SINGLE SOURCE OF TRUTH AUDIT

Search aggressively for repeated knowledge.

Examples:

- data providers;
- data families;
- capabilities;
- instruments;
- run types;
- strategies;
- indicators;
- overlays;
- CLI commands;
- MCP tools;
- API routes;
- frontend menus;
- artifact types;
- result schemas;
- package names;
- module maps;
- methodology definitions;
- testing classifications;
- research states.

For every repeated registry ask whether it can become:

- one typed registry;
- one schema;
- one manifest;
- one enum;
- one declarative definition;
- one generated catalogue.

Then generate:

- API types;
- UI definitions;
- docs;
- tests;
- validation tables;

where practical.

---

# 19. PACKAGE ARCHITECTURE AUDIT

Do not assume the current number of packages is right or wrong.

For every package determine:

- responsibility;
- reason for isolation;
- allowed dependencies;
- public API;
- number of consumers;
- amount of glue introduced by separation;
- whether the boundary prevents real errors.

Ask:

> Does this package represent a genuine domain boundary?

or:

> Did package fragmentation become architecture for architecture's sake?

I am willing to:

- retain the current packages;
- merge packages;
- split a genuinely overloaded package;

depending on evidence.

Prefer the smallest package structure that preserves meaningful boundaries.

---

# 20. ABSTRACTION AUDIT

Search for common AI-generated over-abstraction:

- interface with one implementation;
- protocol with one caller;
- abstract class with one subclass;
- factory with one product;
- manager/coordinator/orchestrator that mostly forwards calls;
- wrapper around one function;
- adapters without semantic conversion;
- generic configuration with one real mode;
- helpers used once;
- pass-through layers;
- DTO → DTO → DTO transformations;
- premature extensibility;
- unnecessary class hierarchies.

For each abstraction ask:

> **What concrete complexity does this abstraction eliminate today?**

If the answer is unclear, investigate simplification.

Do not inline meaningful domain concepts solely to reduce lines.

---

# 21. THE RESEARCH INFRASTRUCTURE PRINCIPLE

This is a central requirement.

PROJECT ALPHA should not merely contain quantitative functions.

It should provide **canonical research procedures**.

The architecture should separate:

## AI responsibility

AI is good at:

- understanding the owner's research question;
- forming hypotheses;
- proposing mechanisms;
- identifying competing explanations;
- locating relevant research;
- choosing among valid methodologies;
- interpreting evidence;
- identifying gaps;
- proposing the next experiment;
- explaining conclusions.

## Software responsibility

Software should own:

- calculations;
- data retrieval;
- timestamps;
- point-in-time availability;
- schemas;
- experiment specifications;
- execution;
- sample splitting;
- deterministic seeds;
- simulation;
- optimization;
- statistical procedures;
- artifact generation;
- provenance;
- validation;
- reproducibility.

This should be reflected directly in the target architecture.

---

# 22. SKILLS SHOULD GUIDE — CODE SHOULD EXECUTE

Audit every major AI skill.

A skill should primarily explain:

- when a method is appropriate;
- why it is appropriate;
- assumptions;
- limitations;
- what research question it answers;
- how to interpret its result;
- which procedure should be invoked next.

A skill should **not be the only implementation of methodology**.

Bad pattern:

> "When asked for Monte Carlo, have the AI manually write simulation code according to these instructions."

Preferred pattern:

> "For this class of uncertainty, select registered procedure `X`; PROJECT ALPHA owns its implementation, configuration validation, seeding and output."

Likewise for:

- backtesting;
- parameter optimization;
- cross-validation;
- literature search;
- event studies;
- ML experiments;
- validation.

---

# 23. CAPABILITY DISCOVERY

Codex should have a simple machine-readable way to discover:

> What can PROJECT ALPHA already do?

It should be possible to answer questions such as:

- What Monte Carlo procedures exist?
- What validation methods exist?
- What parameter-analysis methods exist?
- What datasets exist?
- Which provider owns this data family?
- Which backtest engine is canonical?
- What research workflows are available?
- What ML validation schemes are allowed?
- What artifact does this procedure produce?
- Which procedure handles this research intent?

Investigate whether existing registries/catalogues can be consolidated into a canonical **capability catalogue**.

Do not create another parallel registry if one can be extended.

---

# 24. CANONICAL PROCEDURE REGISTRY

Investigate whether PROJECT ALPHA would benefit from one machine-readable methodology/procedure registry.

Do not assume the exact representation.

Conceptually a procedure should be able to describe:

- procedure ID;
- version;
- purpose;
- valid questions;
- invalid uses;
- required inputs;
- optional inputs;
- deterministic defaults;
- context-dependent decisions;
- data requirements;
- preconditions;
- execution engine;
- seed policy;
- output contract;
- validation;
- failure conditions;
- provenance requirements;
- source/reference;
- interpretation guidance.

Possible conceptual examples:

- standard backtest;
- event study;
- bar-permutation null;
- trade-sequence bootstrap;
- parameter-sensitivity analysis;
- walk-forward parameter selection;
- temporal ML validation;
- regime analysis;
- literature review.

Do not blindly use these names.

Design around the existing architecture.

---

# 25. EXPLICIT DEFAULTS — NO SILENT IMPROVISATION

A material research choice should come from one of:

### Registered safe default

Methodologically acceptable for the procedure.

### Context-dependent decision

Requires explicit resolution based on the hypothesis/data.

### Owner decision

Requires the user.

### Invalid ambiguity

Execution must stop.

Avoid:

> "The AI selected 1,000 because that seemed reasonable."

For important choices, the system should know why.

Examples include:

- Monte Carlo paths;
- significance levels;
- training periods;
- test periods;
- parameter ranges;
- optimization objectives;
- transaction costs;
- execution assumptions;
- benchmark;
- prediction horizon;
- feature windows;
- retrain schedule.

---

# 26. EXPERIMENT SPECIFICATION

Investigate making substantial quantitative research compile into a machine-readable experiment specification before execution.

Conceptually:

```text
Research Question
        ↓
Hypothesis Contract
        ↓
Experiment Specification
        ↓
Validated Registered Procedure
        ↓
Versioned Data Snapshot
        ↓
Execution
        ↓
Typed Artifacts
        ↓
Evidence
        ↓
AI Interpretation
```

The experiment specification should contain enough material information that the experiment is reproducible without reconstructing decisions from chat history.

Potential information:

- research/project ID;
- hypothesis ID/version;
- procedure ID/version;
- code version;
- data snapshot;
- universe;
- market;
- venue;
- timeframe;
- sampling;
- parameters;
- execution assumptions;
- splits;
- seeds;
- statistical settings;
- expected outputs.

First determine how much of this already exists.

Do not duplicate existing run identity or research contract machinery unnecessarily.

---

# 27. EXPERIMENT IDENTITY

A critical principle:

> **Prompt wording is not experiment identity.**

If:

- hypothesis;
- procedure;
- data;
- configuration;
- code version;
- seed policy;

remain materially identical, differently worded prompts should resolve to the same experiment.

If a material methodology choice changes, experiment identity should change.

Investigate whether current deterministic run identity can be generalized or reused.

---

# 28. SAME INTENT → SAME PROCEDURE

One target acceptance property should be:

Several differently worded requests expressing the same methodological intent should resolve to the same canonical capability.

For example:

- "Monte Carlo test this strategy."
- "Check whether this survives randomized prices."
- "Run the appropriate randomisation robustness test."

If those requests are ambiguous between genuinely different Monte Carlo questions, PROJECT ALPHA should make the distinction explicit.

The AI should resolve the **research intent**.

It should not arbitrarily invent the method.

Likewise:

- "Optimize this strategy."
- "Find the best parameters."
- "Tune the settings."

should first resolve whether the user means:

- sensitivity exploration;
- parameter robustness;
- in-sample exploration;
- hyperparameter selection;
- walk-forward selection;
- model selection.

These are not automatically the same procedure.

---

# 29. CANONICAL DATA ACQUISITION

Audit whether data acquisition has one clear path controlling:

- instrument identity;
- venue;
- market type;
- provider authority;
- frequency;
- timezone;
- session;
- corporate actions;
- adjustments;
- knowledge time;
- available-at time;
- missing data;
- caching;
- provenance;
- snapshot/version identity.

An AI should describe the data requirement.

It should not invent acquisition logic where a supported adapter exists.

---

# 30. CANONICAL LITERATURE RESEARCH

Audit the research-paper/literature workflow.

The target should avoid:

> AI searches randomly, reads several papers and writes a confident summary.

Consider a canonical workflow:

```text
question
→ structured search strategy
→ source hierarchy
→ discovery
→ deduplication
→ source verification
→ methodology extraction
→ claims
→ contradictory evidence search
→ limitations
→ evidence classification
→ citations/provenance
→ synthesis
```

Preserve:

- queries;
- sources;
- paper identifiers;
- dates;
- rejected sources;
- claims;
- methods;
- limitations;
- relationship to the current hypothesis.

The research trail should be reconstructable.

---

# 31. CANONICAL HYPOTHESIS FORMALIZATION

A trading observation should not become a strategy immediately.

Investigate enforcing a procedure such as:

```text
raw observation
→ market mechanism
→ competing explanations
→ falsifiable hypothesis
→ variables
→ causal/knowledge timing
→ data requirements
→ confounders
→ expected relationship
→ falsification condition
→ bounded discovery analysis
→ frozen hypothesis/research contract
```

Only then should hypothesis-specific testing begin.

Inspect the existing research-first program before proposing anything new.

It appears PROJECT ALPHA already has significant infrastructure here.

Reuse/simplify it rather than recreating it.

---

# 32. CANONICAL FEATURE RESEARCH

Feature research should ideally have a repeatable procedure:

```text
feature idea
→ mechanism
→ formal definition
→ availability timestamp
→ implementation
→ unit tests
→ future-poison test
→ distribution
→ univariate evidence
→ conditional evidence
→ regime behavior
→ stability
→ redundancy/correlation
→ incremental value
→ robustness
→ admit/reject
```

An AI should not simply create an indicator and report correlation.

---

# 33. CANONICAL EVENT STUDIES

Audit whether event studies have reusable infrastructure defining:

- event construction;
- eligibility;
- overlapping events;
- reference time;
- pre/post windows;
- benchmark;
- abnormal-return calculation;
- clustering/dependence;
- confidence intervals;
- subgroup tests;
- multiple-testing treatment;
- structured output.

---

# 34. CANONICAL BACKTESTING

PROJECT ALPHA should have an obvious authoritative backtesting path.

It should control or require explicit configuration for:

- versioned data;
- strategy version;
- execution timing;
- fill convention;
- commissions;
- slippage;
- latency where relevant;
- corporate actions;
- position sizing;
- leverage;
- risk limits;
- warm-up;
- missing data;
- date boundaries;
- deterministic state.

Codex should not create temporary alternative backtest engines simply because a prompt asks for a quick test.

If multiple engines genuinely exist for different purposes, their responsibilities should be explicit.

---

# 35. CANONICAL MONTE CARLO INFRASTRUCTURE

This deserves particular attention.

"Run Monte Carlo" is **not a complete methodology**.

Different methods answer different questions.

Audit existing support and consider explicit registered methods where appropriate, potentially including:

- bar permutation;
- return permutation;
- trade-order permutation;
- trade bootstrap;
- block bootstrap;
- stationary bootstrap;
- randomized-price nulls;
- residual resampling;
- parameter perturbation;
- execution-cost perturbation;
- regime-conditioned simulation;
- path simulation.

Do not assume every method belongs in PROJECT ALPHA.

For each supported method define:

- question answered;
- null hypothesis where relevant;
- assumptions;
- preserved structure;
- destroyed structure;
- valid input;
- invalid use;
- seed policy;
- path count / precision policy;
- statistic;
- significance/confidence calculation;
- structured outputs;
- limitations.

Codex selects the methodology.

The implementation belongs to PROJECT ALPHA.

---

# 36. CANONICAL PARAMETER RESEARCH

Explicitly distinguish:

## Parameter exploration

Used to understand:

- sensitivity;
- shape of response;
- stable regions;
- interactions;
- mechanisms.

from:

## Parameter selection

Used to choose an actual configuration.

Parameter selection carries a much larger overfitting risk.

Audit whether infrastructure correctly controls:

- domains;
- constraints;
- search algorithm;
- number of trials;
- objective;
- secondary metrics;
- sample boundaries;
- multiple-testing implications;
- neighborhood stability;
- walk-forward selection;
- selected-parameter provenance;
- holdout protection.

The AI should not manually create arbitrary sweep ranges unless that choice is recorded as part of the experiment.

---

# 37. CANONICAL WALK-FORWARD / TIME-SERIES VALIDATION

Audit reusable definitions for:

- rolling vs expanding;
- training period;
- validation period;
- test period;
- refit schedule;
- purge;
- embargo;
- selection scope;
- preprocessing fit scope;
- parameter fit scope;
- OOS aggregation.

Avoid generic random train/test splitting in financial time series unless explicitly valid for the problem.

---

# 38. MACHINE-LEARNING EXPERIMENTS

ML experiments should have strong standardized contracts around:

- feature timestamp;
- label timestamp;
- prediction horizon;
- information availability;
- preprocessing;
- fit scope;
- leakage prevention;
- splitting;
- hyperparameter search;
- metric selection;
- class imbalance;
- probability calibration;
- threshold selection;
- seeds;
- baselines;
- feature importance;
- stability;
- regime behavior;
- final holdout.

An AI should not be able to accidentally produce an invalid financial ML experiment simply because the prompt says:

> try some machine learning.

---

# 39. STRATEGY VALIDATION PIPELINE

Audit whether PROJECT ALPHA should expose a standard validation composition.

Depending on the strategy and evidence, this may include:

- mechanical correctness;
- bias guards;
- execution correctness;
- baseline comparison;
- walk-forward;
- cost sensitivity;
- parameter stability;
- bootstrap analysis;
- Monte Carlo/null testing;
- multiple-testing adjustment;
- backtest-overfit diagnostics;
- regime robustness;
- subperiod robustness;
- cross-asset robustness where justified;
- holdout evaluation;
- reproducible evidence packet.

Do not force every strategy through irrelevant tests.

The procedure system should encode applicability.

---

# 40. STRUCTURED OUTPUT CONTRACTS

Research procedures should return predictable typed artifacts.

A backtest should not produce a different ad-hoc output structure every time because the initiating prompt changed.

Consider contracts for:

- manifest;
- metrics;
- equity;
- drawdown;
- trades;
- costs;
- parameter surfaces;
- Monte Carlo distributions;
- statistical tests;
- robustness results;
- warnings;
- provenance;
- figures;
- failure reasons.

The AI then interprets the structured evidence.

---

# 41. RESEARCH DECISIONS

Some choices require judgment.

When an AI makes a **material methodological decision**, preserve the decision—not hidden chain-of-thought.

A structured decision record may contain:

- decision;
- available alternatives;
- selected option;
- concise justification;
- evidence;
- affected procedure;
- whether it changes experiment identity.

This gives reproducibility without storing private reasoning.

---

# 42. CANONICAL MODE VS EXPERIMENTAL METHODOLOGY MODE

Do not make the system so rigid that methodological innovation becomes impossible.

Distinguish:

## Canonical mode

Normal research uses reviewed registered procedures.

## Experimental method-development mode

Used when the methodology itself is being researched.

A new method should require some combination of:

- explicit experimental status;
- formal definition;
- source/references;
- implementation;
- known-truth tests;
- differential/oracle tests;
- bias review;
- numerical validation;
- review;
- versioned registration.

An experimental method should not silently become a canonical procedure.

---

# 43. AI MUST USE EXISTING CAPABILITIES

Introduce or preserve a strong architectural principle:

> **If PROJECT ALPHA has a supported capability for a task, AI should use that capability rather than writing an ad-hoc alternative.**

Examples:

If there is a backtest engine:

- do not create another temporary backtester.

If there is a Monte Carlo implementation:

- do not create a custom simulation loop for the same methodology.

If there is a data provider adapter:

- do not bypass it with another library.

If there is a parameter-analysis framework:

- do not create an independent grid-search script.

If existing functionality cannot answer the research question, record the capability gap explicitly.

---

# 44. PROCEDURES SHOULD COMPOSE

Do not replace ad-hoc research with one giant all-purpose workflow.

Prefer composable validated procedures.

Conceptually:

```text
Strategy Validation
│
├── Backtest
├── Cost Sensitivity
├── Parameter Stability
├── Walk Forward
├── Monte Carlo
├── Regime Analysis
└── Holdout
```

Each component should have:

- a clear contract;
- applicability rules;
- deterministic execution.

The higher-level workflow composes them appropriately.

---

# 45. QUANTITATIVE COMPUTATION AUDIT

Apply a higher standard to financial/statistical code.

Look for:

- duplicated formulas;
- inconsistent formula definitions;
- inconsistent units;
- ambiguous annualization;
- inconsistent timestamps;
- inconsistent return definitions;
- inconsistent transaction-cost logic;
- duplicate Sharpe/Sortino/drawdown calculations;
- conflicting ATR/volatility conventions;
- repeated statistical primitives;
- unnecessary DataFrame conversions;
- loops that should be vectorized;
- numerical instability;
- silent undefined statistics.

There should generally be one authoritative implementation of each important financial/statistical primitive unless variants represent genuinely different definitions.

If variants exist, make the distinction explicit.

---

# 46. PERFORMANCE AUDIT

Correctness first.

But inspect:

- repeated disk scans;
- repeated Parquet reads;
- repeated SQLite reads;
- repeated repository scans;
- unnecessary hashing;
- repeated serialization;
- unnecessary subprocess startup;
- unnecessary pandas ↔ Polars ↔ NumPy conversion;
- DataFrame copies;
- repeated indicator computation;
- Python loops across large datasets;
- repeatedly regenerated state.

Only recommend optimization with:

- profiling;
- benchmark evidence;
- obvious redundant work;
- obvious asymptotic issue.

---

# 47. TEST ARCHITECTURE AUDIT

Do not optimize around raw coverage percentage.

Categorize tests into:

- financial correctness;
- bias guards;
- future-poison tests;
- mathematical oracles;
- metamorphic/property tests;
- integration tests;
- API contracts;
- UI tests;
- generated-drift tests;
- governance tests;
- implementation-detail tests.

Identify:

- duplicated tests;
- brittle tests;
- tests pinning irrelevant prose;
- tests that prevent safe refactoring;
- tests mirroring implementation;
- expensive tests with little incremental protection.

Preserve high-value:

- bias tests;
- statistical oracles;
- financial correctness tests;
- reproducibility tests.

Where possible prefer testing invariants over implementation shape.

---

# 48. DOCUMENTATION ARCHITECTURE

Separate documentation into:

### Current operational truth

Small, accurate and high priority.

### Domain methodology

Detailed when justified.

### Historical architecture decisions

Useful but not routine context.

### Generated reference material

Generated from source where practical.

### Agent instructions

Short and high-signal.

Audit whether:

- `CLAUDE.md` is too large;
- root `AGENTS.md` should become the primary map;
- path rules are too large;
- module maps should be generated;
- capability lists should be generated;
- skills overlap;
- completed phase plans should move out of routine context;
- historical state is mixed with current state.

A fresh Codex session should not pay tokens for old project history unless relevant.

---

# 49. POSSIBLE TARGET KNOWLEDGE MODEL

Evaluate—not blindly adopt—a structure such as:

```text
AGENTS.md
    short orientation + invariants + commands + pointers

ARCHITECTURE.md
    current architecture only

docs/
    architecture/
    methodologies/
    research/
    operations/
    decisions/
    history/

machine-readable registries
    packages
    capabilities
    procedures
    artifacts
    providers

generated references
    module map
    CLI reference
    API types
    capability reference
```

The important principle is:

> Human/AI documentation explains intent.

> Source/schema/config defines executable truth.

---

# 50. REFACTOR CODE, NOT JUST TEXT

Do not finish this audit by merely recommending that documentation be shorter.

The primary outcome should still include real code and architecture simplification such as:

- deleting redundant modules;
- consolidating duplicate implementations;
- reducing custom harness code;
- removing wrappers;
- converting multiple registries into one;
- generating consumers;
- simplifying control flow;
- reducing package fragmentation where justified;
- removing obsolete compatibility code;
- replacing custom infrastructure with mature tools.

Documentation cleanup is one workstream, not the entire solution.

---

# 51. DELETE AGGRESSIVELY WHERE JUSTIFIED

Produce explicit deletion candidates.

Possible categories:

- dead modules;
- unused helpers;
- pass-through wrappers;
- duplicate registries;
- stale migration code;
- historical runtime compatibility;
- old AI instructions;
- redundant skills;
- redundant rules;
- custom scripts replaced by existing tooling;
- manual docs replaced by generation.

For every deletion state:

> What responsibility disappears or what now performs it?

Deletion without understanding is not acceptable.

---

# 52. DO NOT OPTIMIZE FOR LOC

A 30-line opaque abstraction can be worse than 100 obvious lines.

Evaluate simplification based on:

- cognitive load;
- number of concepts;
- number of sources of truth;
- number of branches;
- number of synchronization points;
- testability;
- failure modes;
- discoverability;
- maintainability.

---

# 53. PROFESSIONAL ENGINEERING TARGET

The final repository should resemble a carefully engineered private quantitative research platform:

- straightforward Python;
- strong typing;
- clear modules;
- explicit domain models;
- minimal magic;
- minimal global state;
- deterministic runs;
- explicit provenance;
- reproducible experiments;
- explicit timestamps;
- explicit units;
- point-in-time correctness;
- fail-loud behavior;
- clear boundaries;
- one obvious path for common operations;
- generated interfaces;
- high-value testing;
- clean dependency direction;
- simple process execution;
- few custom frameworks;
- boring infrastructure where possible.

---

# 54. MEASURE BEFORE AND AFTER

Establish a baseline for metrics such as:

- owned production LOC;
- test LOC;
- AI-control-plane LOC;
- active agent-instruction LOC;
- documentation LOC;
- generated LOC;
- packages;
- custom scripts;
- custom gate/hook LOC;
- manually synchronized registries;
- duplicated definitions;
- largest modules;
- architecture boundaries;
- approximate fast/full verification time;
- fresh-agent mandatory context size.

Then use those measurements to establish realistic refactor targets.

Do not invent arbitrary targets before measurement.

---

# 55. CLASSIFY FINDINGS

For every significant finding provide:

### Finding

What exists.

### Evidence

Exact paths, functions, commands, relationships or measurements.

### Why it matters

Examples:

- correctness;
- complexity;
- LLM tax;
- duplication;
- performance;
- maintenance;
- reproducibility.

### Why it exists

Historical/domain reason where known.

### Proposed direction

What should change.

### Deterministic replacement

Where applicable.

### Risk

What could break.

### Expected improvement

Concrete result.

### Confidence

High / Medium / Low.

---

# 56. PRIORITIZE BY VALUE

Do not mix architectural issues with hundreds of style comments.

Use a qualitative framework such as:

> **Value = complexity removed + correctness improvement + reproducibility improvement + AI-navigation improvement + maintenance reduction − migration risk**

Classify recommendations roughly as:

- Critical;
- High value;
- Worthwhile;
- Low value / do not touch.

Avoid cosmetic churn.

---

# 57. EXPECTED WORKSTREAMS TO INVESTIGATE

Use these as investigation categories, not mandatory final phases:

### A. Repository architecture

Package/module structure and boundaries.

### B. AI control plane

Agents, hooks, rules, skills, gates, model-specific infrastructure.

### C. Deterministic tooling

Move enforcement from prompts into software.

### D. Single sources of truth

Registries, schemas, generated consumers.

### E. Quantitative procedure infrastructure

Canonical research methodology.

### F. Experiment/reproducibility system

Specs, identity, provenance, artifacts.

### G. Python simplification

Duplication, abstractions, large modules.

### H. CLI/API/MCP/web simplification

Composition and synchronized interfaces.

### I. Tests

Signal, speed and refactorability.

### J. Documentation/context

LLM tax.

### K. Performance

Only evidence-supported changes.

Change this breakdown if repository evidence suggests a better one.

---

# 58. SAFE REFACTOR SEQUENCING

Do not propose a big-bang rewrite.

Prefer:

```text
measure
→ understand
→ characterize behavior
→ protect invariants
→ introduce canonical replacement
→ migrate consumers
→ verify equivalence
→ delete old implementation
→ continue
```

Each stage should leave the repository operational.

For repetitive changes use:

- codemods;
- AST transformations;
- generators;
- scripted migrations;

where safer than hundreds of AI edits.

---

# 59. EVERY IMPLEMENTATION PHASE NEEDS ACCEPTANCE CRITERIA

For each phase of the final plan state:

- exact objective;
- affected modules;
- prerequisites;
- implementation sequence;
- files/subsystems likely affected;
- what gets introduced;
- what gets deleted;
- tests before change;
- tests after change;
- verification commands;
- quantitative invariants at risk;
- rollback point;
- measurable success criterion.

---

# 60. IMPORTANT QUESTIONS THE FINAL PLAN MUST ANSWER

I want explicit conclusions about:

### Repository

- Is PROJECT ALPHA genuinely over-engineered?
- Where?
- Where is complexity justified?

### Packages

- Are there too many?
- Which boundaries matter?

### AI system

- Is the custom harness worth its complexity?
- Which parts should remain?
- Which parts should become standard tooling?
- Can Claude-specific infrastructure be removed or isolated?

### Codex

- What is the minimum context Codex truly needs?
- What should `AGENTS.md` become?
- How should Codex discover architecture/capabilities?

### Research methodology

- Which procedures are already canonical?
- Which are still effectively prompt-driven?
- Where can different prompts currently produce different experiments?

### Quant execution

- Is there one canonical backtest path?
- One authoritative optimization path?
- Clearly distinct Monte Carlo procedures?
- Proper ML/time-series validation infrastructure?

### Reproducibility

- Can a research result be reconstructed from stored machine-readable state?
- Or does understanding it require chat history?

### Single sources of truth

- What is currently maintained in multiple places?
- What should become generated?

### Deletion

- What can safely disappear?

---

# 61. FINAL DELIVERABLE

Your Plan Mode response must be **repository-specific**.

Do not produce a generic software-refactoring checklist.

Produce the following:

## 1. Executive diagnosis

Explain what PROJECT ALPHA actually is today and the main sources of complexity.

---

## 2. What is already engineered well

Identify systems that should remain.

Do not destroy good engineering because the project was vibe-coded.

---

## 3. Measured baseline

Include meaningful codebase and control-plane metrics.

---

## 4. Current architecture map

Explain:

- packages;
- applications;
- workers;
- dependency direction;
- data flow;
- research flow;
- backtesting;
- validation;
- artifacts;
- AI control plane.

---

## 5. Complexity hotspots

Specific evidence.

---

## 6. LLM-tax audit

Explain where Codex/Claude currently perform work that deterministic software should handle.

---

## 7. AI-control-plane assessment

Specifically assess:

- `AGENTS.md`;
- `CLAUDE.md`;
- `.agents`;
- `.claude`;
- `.codex`;
- rules;
- skills;
- hooks;
- gates;
- awareness generation;
- Codex bridge;
- attestations.

---

## 8. Standard-tool replacement opportunities

For each major custom mechanism identify whether it should:

- remain;
- simplify;
- be replaced;
- be deleted.

---

## 9. Single-source-of-truth audit

Identify duplicate registries/schemas/definitions.

---

## 10. Package architecture conclusion

Explicitly state which packages should:

- remain;
- merge;
- split;
- change responsibility.

---

## 11. Code simplification findings

Give concrete modules/functions/abstractions.

---

## 12. Quantitative correctness findings

Identify safeguards that must remain unchanged or become stronger.

---

## 13. Research-procedure capability matrix

Fill a matrix similar to:

| Workflow | Engine Exists | Canonical Procedure | Typed Inputs | Deterministic Defaults | Reproducible | Structured Output | Skill Guidance | Prompt-Variance Risk |
|---|---|---|---|---|---|---|---|---|
| Data acquisition | | | | | | | | |
| Literature review | | | | | | | | |
| Hypothesis creation | | | | | | | | |
| Feature research | | | | | | | | |
| Event studies | | | | | | | | |
| Backtesting | | | | | | | | |
| Monte Carlo | | | | | | | | |
| Parameter exploration | | | | | | | | |
| Parameter selection | | | | | | | | |
| Walk-forward | | | | | | | | |
| ML research | | | | | | | | |
| Regime analysis | | | | | | | | |
| Strategy validation | | | | | | | | |
| Reporting | | | | | | | | |

Base this on the real repository.

---

## 14. Proposed research execution architecture

Show how:

```text
Owner / AI Question
       ↓
Intent Resolution
       ↓
Hypothesis / Research Contract
       ↓
Procedure Selection
       ↓
Experiment Specification
       ↓
Deterministic Quant Engine
       ↓
Versioned Artifacts
       ↓
Evidence
       ↓
AI Interpretation
```

should map onto the actual PROJECT ALPHA codebase.

Do not invent duplicate layers if equivalent infrastructure already exists.

---

## 15. Target repository architecture

Provide the proposed end-state architecture.

Use diagrams if useful.

---

## 16. Delete / Merge / Replace table

Use:

| Current Component | Action | Replacement | Why | Risk |
|---|---|---|---|---|

---

## 17. Test architecture plan

What remains, consolidates, improves or disappears.

---

## 18. Documentation / Codex-context plan

Explain the desired root-agent experience and how much context should be mandatory.

---

## 19. Phased implementation plan

Give an ordered set of safe phases.

The later implementation agent should be able to execute this plan.

---

## 20. Verification strategy

Specify how each stage proves:

- behavior preservation;
- quantitative correctness;
- no bias regression;
- reproducibility;
- architecture integrity.

---

## 21. Expected measurable improvement

After measuring the repo, estimate realistic improvements to:

- source complexity;
- duplicate definitions;
- custom infrastructure;
- LLM context;
- AI navigation;
- verification speed;
- maintainability;
- reproducibility.

---

## 22. Explicitly rejected changes

List attractive ideas you investigated and decided **not** to recommend.

This section is required.

Examples could include:

- a package merge that would destroy a useful boundary;
- replacing Python with Rust;
- deleting a statistical safeguard;
- introducing another workflow framework.

---

## 23. Final implementation roadmap

Finish with the exact order you recommend a future Codex execution session follows.

---

# 62. DO NOT IMPLEMENT YET

This session is intentionally Plan Mode.

Do not start refactoring.

Do not generate a superficial TODO list and then begin coding.

Use the local repository to do the difficult thinking now.

Explore broadly enough to understand the system.

Then narrow the recommendations to changes supported by evidence.

---

# 63. CHALLENGE MY ASSUMPTIONS

I believe PROJECT ALPHA contains vibe-coded slop and unnecessary complexity.

I may be wrong about specific areas.

If a subsystem is sophisticated because it genuinely solves an important problem, say so.

If an apparently professional mechanism is actually unnecessary ceremony, say so.

If existing infrastructure is already excellent, preserve it.

If my preferred solution would weaken the project, reject it.

I want your engineering conclusion—not agreement with my assumptions.

---

# 64. FINAL SUCCESS CONDITION

When this refactor program is complete, PROJECT ALPHA should feel less like:

> **a huge collection of AI instructions trying to make an AI behave correctly**

and more like:

> **a deterministic quantitative research platform whose architecture, schemas, procedures, tooling and tests naturally lead an AI toward correct work.**

The ideal final relationship is:

```text
                OWNER
                  │
                  ▼
             AI / CODEX
       scientific reasoning
        research judgment
                  │
                  ▼
       PROJECT ALPHA PROCEDURES
       versioned + inspectable
                  │
                  ▼
       TYPED EXPERIMENT SPEC
                  │
                  ▼
       DETERMINISTIC ENGINES
     data / research / backtest
     optimisation / ML / MC
                  │
                  ▼
       REPRODUCIBLE ARTIFACTS
                  │
                  ▼
          EVIDENCE + RESULTS
                  │
                  ▼
          AI INTERPRETATION
```

AI should spend its intelligence on:

- market reasoning;
- hypothesis generation;
- competing explanations;
- research design;
- procedure selection;
- interpretation;
- identifying unknowns;
- deciding what experiment should come next.

Software should handle:

- repetition;
- calculations;
- data lineage;
- point-in-time enforcement;
- methodology execution;
- seeds;
- parameter bookkeeping;
- builds;
- testing;
- schemas;
- interfaces;
- validation;
- provenance;
- reproducibility.

The final system should make it difficult for two semantically identical requests to accidentally produce materially different experiments merely because the prompt wording changed.

**Preserve the sophisticated quantitative capability.**

**Remove accidental complexity.**

**Reduce custom infrastructure.**

**Reduce LLM tax.**

**Reduce duplicate sources of truth.**

**Prefer deterministic systems.**

**Prefer executable methodology over prose methodology.**

**Prefer generated interfaces over synchronized copies.**

**Prefer simple code.**

**Prefer standard tooling.**

**Prefer evidence over assumptions.**

Now deeply inspect the local PROJECT-ALPHA repository and produce the final implementation plan.

Do not implement it yet.