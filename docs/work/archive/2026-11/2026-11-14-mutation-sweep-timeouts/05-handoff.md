## What changed for you

- The weekly mutation sweep had been failing because many mutants of `alpha_research` code got
  stuck rather than being tested. mutmut's default "fork" mode runs the test suite once inside its
  own process, which starts Polars' thread pool there; every mutant is then a copy of that process,
  and a copy that calls Polars waits forever for threads it does not have. Those mutants were
  recorded as timeouts: neither killed nor survived, just unmeasured. In run 43483950887 that was
  2,983 of 15,066 `alpha_research` mutants, and it pushed one `rendering.py` fragment past its
  5,400-second budget (73 of 95 mutants done, 35 killed, 38 timed out).
- The sweep now uses mutmut's "forkserver" mode, which upstream provides for exactly this case.
  The mutants are measured properly: they are killed, or they survive.
- Five tests that had been silently dropped for every `alpha_research` module now run. They failed
  in the staged copy only because `docs/` and `scripts/rdagent_foundation_contract.py` were
  missing, and they exercise `rolling_pca`, `_canonical` and `ResearchArtifactRef`. A test that
  still fails only in staging is printed in the job log.
- A failing sweep job now prints its error and the last 40 lines of its own logs in the job log.
- You can run one module on GitHub with
  `gh workflow run mutation-weekly.yml --ref <branch> -f module=<path>`.
- Expect lower scores in places in the next weekly sweep: mutants that were stuck now show as
  honest survivors, which are real gaps in the tests. Scores stay report-only, and no threshold,
  floor or product byte changed.

## How to see it

The proof run on this branch: see "Checks run".

## Checks run

- Local, same staged `rendering.py` tree and the same ten mutants:
  - fork mode: 2 of 10 done after 20 minutes. Two children were blocked in a futex wait at under
    1% CPU until mutmut's wall limit, (81 s of tests + 1) x 15 = 1,235 s, ended them as timeouts.
  - forkserver mode: all 10 done in 8m46s (7 killed, 3 survived, 0 timed out). The two stuck
    mutants survived.
- A 10-line reproducer confirms the deadlock: Polars `group_by` in the parent, then fork, then
  `group_by` in the child hangs. The same test without the parent call does not.
- Local preflight of the staged copy: before, 4 failed, 1134 passed, 1 error; after, 1174 passed.
- `uv run python scripts/gate.py check --all`: all checks passed (whole fast tier).
- Remote proof: PENDING (filled in after CI is green).

## Who built and who reviewed

- Built by Codex (`gpt-6-astra`, effort `high`, class hard: tier protected) through
  `scripts/handoff.py build --task`. It took 7m46s with one fix round; 2,614,427 tokens in
  (2,476,928 cached), 22,091 out.
- Reviewed by Claude (Opus, a separate reviewer agent), with six findings:
  1. The no-tests certificate no longer saw tracer hits from the stats child. Fixed by Claude: the
     child now reports them.
  2. The diagnostics could raise inside `finally`. Fixed.
  3. Exclusions are not printed when the harness raises before producing a report. Accepted: the
     preflight log tail is printed in that case.
  4. The workflow `if:` relied on null coercion. Fixed.
  5. Unfragmented jobs were labelled "fragment 0". Fixed.
  6. Informational only; no change.
- Codex reviewed Claude's fixes (`handoff.py review`): 0 findings.

## The one document updated

`docs/reference/invariants/testing.md` (Quant sweeps), plus `docs/reference/checks.md` (the
one-module dispatch) and the backlog note `docs/roadmap/backlog/weekly-mutation-sweep.md`. The
note stays open until two scheduled weekly runs pass.

## What I am unsure about

- Whether forkserver mode is slower per mutant on GitHub's runners than fork mode would have been
  without the deadlock. The one-module run measures it.
- The whole sweep has not been rerun, so the change in kill rates across all modules is not yet
  measured.

## Protected files touched

- `scripts/harness_quant.py`
- `.github/workflows/mutation-weekly.yml`
- `scripts/mutation_fragment.py`, `scripts/mutation_sweep.py` (under `scripts/`, covered by the
  owner-approved clean-up plan)
