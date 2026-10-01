# Bounded discovery workflow

Use for an open research question, indicator investigation or model request. This is a discovery procedure; existing case, source-pack, one-shot confirmation and owner gates still apply.

1. State the exact target, decision time, permitted data window and intended output. Inspect available commands and verified snapshot coverage before drafting variants. Record the current question, baseline, maximum three candidates, inspected/failed attempts and stop rule in one append-only ledger.
2. Check representability and authority. Distinguish an unsupported governed operator from an available standalone diagnostic. Never silently change the target to fit a recipe, use an owner override, or call a proposed protocol completed research. If execution is blocked, record the exact command/error and missing capability; stop variant generation.
3. Run one baseline before variants. For a single-symbol next-week-close classifier, `alpha research diagnostic weekly-classifier SYMBOL --snapshot ID --as-of YYYY-MM-DD` produces immutable discovery evidence with chronological partitions, majority/momentum benchmarks and separate next-open economic measurements. Inspect its assumptions and results; Qlib's fixed recipe is a different target. Missing sessions and inadequate labels fail rather than being filled silently.
4. For fixed-rule/regime questions, use existing `alpha backtest run` and `alpha validate` with the same frozen snapshot/cutoff, supported strategy/rules, and public authority checks. Inspect `--help` before invoking. First measure the unfiltered baseline. A recurring-regime hypothesis needs a trailing, decision-time state and chronological evaluation; a hindsight good/bad label is not a filter. If the proposed filter is not representable, report that exact boundary and the baseline evidence rather than inventing performance.
5. Only after baseline evidence, predeclare up to three candidate identities and their kill criteria. Count all inspected variants, including failed and abandoned ones. Do not interpret a single-run DSR as correcting an entire search. Stop when the budget is exhausted, a feasibility block persists, or evidence fails the frozen kill rule. Record the stop even when asked to keep trying; offer only a materially new, bounded hypothesis.
6. Specialist review follows measurements. Data review checks availability and provenance; overfitting review checks temporal leakage, all attempted variants and dependence; economic/market-structure review checks fills, costs and missing implementation evidence. A research lead reconciles findings and cites artifacts. Use the typed `SpecialistReview` envelope; `alpha research diagnostic check-review FILE` verifies local JSON hashes/selectors and schema, not claim truth. These are advisory contracts, not autonomous agents or approval grants.
7. Report empirical completion separately from conclusion: `completed_evidence`, `honest_block`, `method_failure`, or `infrastructure_invalid`. A completed null result is useful evidence. An honest block is not a performance test. Separate signal evidence, value of further research, and deployability. No model vote can replace deterministic gates.

`ResearchWorkflowPlan` remains an advisory candidate/reviewer contract. The executable first slice is deliberately narrower: `BaselineExecutionPlan` in `alpha_cli.research_execution` runs a fixed `ts_momentum` or frozen `rules` baseline and validation, with zero model calls and zero variants. It does not execute the advisory plan or constitute an autonomous multi-agent system.

## Executable bounded baseline

Write a JSON plan (use your verified snapshot and symbol):

```json
{"symbol":"SPY","snapshot":"my-frozen-snapshot","as_of":"2025-12-31","seconds":900}
```

Run `alpha research diagnostic run-plan plan.json`. The closed configuration supports the momentum lookback/skip/volatility/rebalance settings, costs, leverage up to one, starting cash, validation train/test/embargo and seed. It fixes CASH/long-only, 252 periods/year and one worker. Existing validation default null/resampling settings are retained. There are no arbitrary commands, extra flags, owner overrides or tuning loops. Strategies other than `ts_momentum` and `rules` require a separate operator; do not relabel this baseline as a regime study or a completed general research question.

The controller verifies the frozen snapshot, dispatches at most two child commands sequentially, awaits their terminal outcomes, checks configuration/source identity, reconciles session timestamps against the snapshot and existing walk-forward splitter, and publishes `research_executions/<identity>/receipt.json` with a hash manifest. Baseline and validation populations stay separate. A failed baseline prevents validation. Measurement completion is separate from the validation PASS/FAIL result; completed negative results remain evidence, never admission.

The 30–1500 second budget withholds ten seconds from child dispatch for cleanup and reconciliation. Storage and operating-system cleanup are not hard wall-time bounded. Attempts are recorded before launch; failed/interrupted attempts are not automatically retried, and restarting cannot replenish the same plan's execution budget. The identity binds plan, snapshot, execution fingerprint and controller/digest code. A changed plan or implementation is a new experiment, so the caller must still maintain the broader search ledger. Repeating a completed plan re-verifies its bound evidence. Concurrent identical invocations are refused.

Timeout, keyboard interruption and SIGTERM during active child execution reap its process group and produce a terminal result. Abrupt controller death (including SIGKILL) cannot guarantee cleanup; a resumed receipt marks uncompleted attempts infrastructure-invalid and does not start replacement work. Preflight-invalid inputs fail before accepting or dispatching an experiment.

Every completed step includes an artifact-derived execution digest: session coverage, order statuses including denied/rejected orders, fill events, closed trades and per-instrument trade counts, configuration/cost assumptions, validation result, and evidence hashes. `alpha research diagnostic execution-digest RUN_ID --as-of DATE` also inspects retained evidence. Standalone validation digests reconcile counts against manifest folds; the controller additionally checks actual snapshot session timestamps. Missing sidecars or semantic count/linkage inconsistencies fail. Rejection reasons and terminal open positions are explicitly unavailable because these sidecars do not record sufficient evidence; they are never inferred as zero.

**Information boundary:** the controller requires the same cutoff for its own operations and rejects later result timestamps. It does not hide the full snapshot, other reports, charts, shell access or prior messages from a surrounding agent. Agent-wide temporal isolation remains unverified and requires a fresh isolated context with physically restricted data and knowledge-time corporate-action filtering. Previously exposed information cannot be repaired by setting a later `as_of` flag.


## Frozen rule execution

For an existing saved rule, build the plan with the canonical specification embedded as a JSON
string. For example, this local Python snippet freezes the current named rule once:

```python
import json
from pathlib import Path
from alpha_cli.rules_cmds import resolve_rules_spec
from alpha_core.config import AlphaSettings

plan = {"symbol": "SPY", "snapshot": "my-frozen-snapshot", "as_of": "2025-12-31",
        "strategy": "rules", "rebalance_every": 1,
        "rules_spec": resolve_rules_spec("rules", "my-rule", AlphaSettings().data_dir)}
Path("plan.json").write_text(json.dumps(plan))
```

Then use the same `alpha research diagnostic run-plan plan.json` command. The parser validates
and canonicalizes the embedded string before identity is calculated. Changing a saved name later
has no effect. The controller publishes exact UTF-8 canonical bytes in its immutable `rules.json`;
both children receive `--rules-file PATH --rules-sha256 SHA256`. These inputs are exclusive with
`--rules NAME`, must be supplied together, and require `--strategy rules`. Each child reads once,
hashes and parses those same bytes before loading market data. Noncanonical bytes (including an
added newline), invalid UTF-8, oversized inputs and hash mismatches are rejected. Returned baseline
and validation manifests must contain the exact frozen specification; replay checks it again.

The existing rule parser, warmup, trading signals and statistical validation are unchanged. The
controller still uses CASH/long-only; short conditions do not enable short positions. Lookback/skip
are retained RunSpec metadata, not momentum overlays on the rule signal. Train size must satisfy
the existing strategy warmup checks. This is one fixed rule measurement, not regime discovery or
an automatic strategy search. Completed validation may reject the hypothesis.

File/hash options are excluded from the default launch-form catalog. No REST schema or MCP tool
was added; existing authorized generic CLI transport may relay these options. Catalog exclusion
is a discovery convention, not a filesystem or authority boundary.
