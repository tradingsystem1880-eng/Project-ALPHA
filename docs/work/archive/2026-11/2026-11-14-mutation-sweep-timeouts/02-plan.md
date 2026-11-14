# Make the weekly mutation sweep measure, not hang

**Delivery state:** In progress — built on branch `m4/mutation-sweep-timeouts`; done when its pull request merges.
**Build class:** hard — tier protected (`scripts/harness_quant.py`, `.github/workflows/mutation-weekly.yml`).

Filed straight into the archive, as `2026-11-14-shared-helpers` was: the work-in-progress ceiling
admits no new live plan. The owner approved the clean-up plan covering `scripts/` and
`.github/workflows/**`; every protected file touched is listed in the pull request.

## For the owner

- Measured cause: mutmut's default "fork" mode runs the whole test suite once in its main process,
  which starts Polars' thread pool there; every mutant is then a fork of that process, and a forked
  child that calls Polars waits forever for threads that do not exist in it. Those mutants are not
  caught, they are stuck until mutmut's wall limit ((test time + 1) x 15 seconds) ends them.
- Fix: run mutmut in its "forkserver" mode, which upstream provides for exactly this case. The same
  ten `rendering.py` mutants took 8m46s locally with 7 killed, 3 survived, 0 timed out; in fork mode
  two of them were still stuck after 20 minutes.
- The staged copy now holds `docs/` and all of `scripts/`, so five tests that were silently dropped
  for every `alpha_research` module run again; anything still dropped is printed in the job log.
- A failing sweep job now prints why (error and the tail of its logs).
- Expect the next weekly sweep to show fewer timeouts and more honest survivors (weaker scores in
  places): survivors are real gaps the timeouts were hiding. Scores stay report-only.

```json
{
  "schema_version": 1,
  "title": "Make the weekly mutation sweep measure, not hang",
  "context": "Weekly sweep run 43483950887: rendering.py fragment 0 hit its 5,400 s budget at 73 of 95 mutants with 38 timeouts; 2,983 of 15,066 alpha_research mutants timed out across the sweep (alpha_validation: 191 of 6,915).",
  "assumptions": [
    {"statement": "The timeouts are fork deadlocks, not slow tests.", "verified_by": "local run: timed-out children are single-threaded and blocked in futex_do_wait for 20+ minutes at <1% CPU; the parent mutmut process holds polars-0..5, tokio and jemalloc threads; a 10-line reproducer (polars group_by in parent, fork, group_by in child) deadlocks, the cold variant does not"},
    {"statement": "forkserver isolation removes them without changing what counts as a kill.", "verified_by": "same 10 mutants, same staged tree: fork mode 2 done in 20 min (2 stuck); forkserver 10 done in 8m46s, 7 killed, 3 survived, 0 timeout"},
    {"statement": "mutmut 2.5.1 (constant-only modules) ignores the new key.", "verified_by": "mutmut 2.5.1 config_from_file reads only the keys a command asks for"},
    {"statement": "The five excluded tests are real potential killers.", "verified_by": "test_finance_math_protocol doctests call alpha_research.rolling_pca; test_rdagent_foundation_contract calls alpha_research._canonical and ResearchArtifactRef; both fail in staging only because docs/ and scripts/rdagent_foundation_contract.py were not copied"}
  ],
  "alternatives_considered": [
    "Lower mutmut's timeout_multiplier: rejected; the stuck mutants would still be unmeasured (timeout is not a kill here), just cheaper.",
    "Split rendering.py into more fragments: rejected; 95 mutants x ~280 s per deadlock on CI is still 3.7 runner-hours per fragment, and splitting hides nothing it fixes.",
    "Narrow test selection: rejected; the 42 associated tests (81 s locally) are mutmut's own coverage association, and a survivor runs all of them in ~33 s on CI, well inside budget."
  ],
  "pre_mortem": [
    "Collection in the fork server itself starts a Polars pool (a test module computing at import): every mutant would deadlock again. The local forkserver run and the remote one-module run check this.",
    "The no-tests certificate weakens because stats now run in a child: the adapter records import origins in that child and fails loud when they are missing.",
    "Copying docs/ and scripts/ makes a staged test pass for the wrong reason: they are unmutated copies of the repository, which the root pytest config already puts on the path."
  ],
  "slices": [
    {"title": "Forkserver isolation and a complete staged copy (harness_quant, mutation_fragment)", "verify": "uv run pytest -q tests/unit/test_mutation_fragment.py tests/unit/test_mutation_public_staging.py tests/unit/test_mutation_legacy.py", "expected": "all pass", "rollback": "revert the slice commit", "status": "pending"},
    {"title": "A failing fragment prints why; preflight exclusions are printed (mutation_sweep)", "verify": "uv run pytest -q tests/unit/test_mutation_sweep.py", "expected": "all pass", "rollback": "revert the slice commit", "status": "pending"},
    {"title": "Optional one-module dispatch input (mutation-weekly.yml)", "verify": "uv run pytest -q tests/unit/test_checks_reference.py tests/unit/test_mutation_sweep.py", "expected": "all pass", "rollback": "revert the slice commit", "status": "pending"}
  ],
  "tier_impact": ["protected"],
  "docs_to_update": ["docs/reference/invariants/testing.md", "docs/reference/checks.md", "docs/roadmap/backlog/weekly-mutation-sweep.md"],
  "out_of_scope": ["packages/", "apps/", ".claude/mutation-baseline.json", "mutation thresholds", "apps/alpha-cli/src/alpha_cli/_suite.py", "apps/alpha-cli/src/alpha_cli/research_cmds.py"],
  "files": ["scripts/harness_quant.py", "scripts/mutation_fragment.py", "scripts/mutation_sweep.py", ".github/workflows/mutation-weekly.yml", "tests/unit/test_mutation_fragment.py", "tests/unit/test_mutation_public_staging.py", "tests/unit/test_mutation_sweep.py"]
}
```

## Read first

| Read | Section | When |
|---|---|---|
| [scripts workspace](../../../../../scripts/CONTEXT.md) | How to change it | always |
| [testing invariants](../../../../reference/invariants/testing.md) | Quant sweeps | always |
| [engineering rules](../../../../reference/invariants/engineering.md) | Code size | always: `harness_quant.mutate` is capped at 180 lines and may not grow |
| [`scripts/harness_quant.py`](../../../../../scripts/harness_quant.py) | `stage_mutation_tree` | slice 1 |
| [`scripts/mutation_fragment.py`](../../../../../scripts/mutation_fragment.py) | `run_fragment` | slice 1 |
| [`scripts/mutation_sweep.py`](../../../../../scripts/mutation_sweep.py) | `run_module` | slice 2 |
| [`.github/workflows/mutation-weekly.yml`](../../../../../.github/workflows/mutation-weekly.yml) | — | slice 3 |

## Slices

1. **Forkserver and the staged copy.** In `harness_quant.stage_mutation_tree`: write
   `process_isolation = "forkserver"` into the staged `[tool.mutmut]` table (with a Python comment
   giving the reason: Polars' thread pool in a forked parent deadlocks the children); copy the whole
   `scripts/` directory (ignoring `__pycache__`) instead of only `run_owned_test.py`; copy `docs/`
   and add `"docs"` to `also_copy`. In `mutation_fragment.run_fragment`: the audited runner factory
   requires `ForkServerRunner` (message: "Certified collection requires pinned forkserver
   isolation"); because stats now run in a forked child, the import-origin evidence is recorded in
   that child (wrap the runner's test-runner class so its `run_stats` writes the target module's
   origin, `staged` or `mismatched`, to a JSON file at an absolute path chosen by the parent) and the
   parent reads and deletes it after collection; a missing or malformed file raises `ValueError`.
   Every other certificate check stays as it is. Tests: the staging test asserts the isolation line,
   `docs/` and `scripts/` copies and `also_copy`; the fragment tests switch to a fake
   `ForkServerRunner` and add a case where the child reports no origins (must fail) and one where it
   reports `mismatched` (must fail).
2. **Say why.** In `mutation_sweep.run_module`, when a fragment ends in state `error`, print to
   stderr: the module, fragment, error, the report's `status` for that module when present, and for
   each recorded command log the last 40 lines (carriage returns turned into newlines, at most 4,000
   characters per log). On every completed or failed fragment, print the preflight's
   `excluded_tests` (one per line) when there are any. Put this in a helper so `run_module` stays
   under 150 lines. Tests: an error run prints the error and a bounded tail; a long log is truncated.
3. **One module on demand.** `mutation-weekly.yml` gains a `workflow_dispatch` string input
   `module` (default empty). When set, the `modules` job filters the matrix to that module's
   fragments (passed through `env`, never interpolated into the script) and fails when none match;
   the `aggregate` job is skipped, since a partial sweep is not a sweep. Schedule and
   `workflow_call` behave as before.

## Test plan

The three mutation test files plus `test_checks_reference.py`; the fast tier (`gate.py check --all`);
locally, fragment 0 of `rendering.py` through `mutation_sweep.py run`; on GitHub, one dispatch
with `module=packages/alpha-research/src/alpha_research/rendering.py`.

## Look-ahead, determinism and import impact

None: harness and workflow only. No product byte, threshold, baseline or guard changes.
