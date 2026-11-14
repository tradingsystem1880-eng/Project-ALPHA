# Verify: make the weekly mutation sweep measure, not hang

## Commands run

- `uv run python scripts/gate.py check --all` on c202e414 (after `git merge origin/main`):
  all checks passed, whole fast tier, 143 s. The first run failed on a 232-character table row in
  `checks.md`; that was fixed and the check rerun.
- `uv run pytest -q tests/unit/test_mutation_fragment.py tests/unit/test_mutation_public_staging.py tests/unit/test_mutation_sweep.py tests/unit/test_mutation_legacy.py tests/unit/test_code_size.py tests/unit/test_checks_reference.py`:
  118 passed, and 59 in `test_mutation_sweep.py` after the diagnostics test was added.
- Root cause, measured locally on the staged `rendering.py` tree with ten mutants:
  - Fork mode: the two mutants `x__tick_values__mutmut_11` and `_12` were blocked in
    `futex_do_wait` at under 1% CPU, single-threaded, until mutmut's wall limit, (81.35 s + 1) x 15
    = 1,235 s, ended them as timeouts.
  - The parent mutmut process held `polars-0..5`, tokio and jemalloc threads.
  - A Polars reproducer (warm parent, fork, `group_by` in the child) deadlocks; the cold one does not.
  - Forkserver mode: all ten done in 8m46s (7 killed, 3 survived, 0 timed out).
- Local fragment 0 of `rendering.py` through `scripts/mutation_sweep.py run --index 153` with the fix:
  complete in 2,473 s (preflight 132 s, mutation 2,339 s). 95 mutants: 53 killed, 42 survived,
  0 timed out, 0 no-tests; no tests excluded. The preflight had 1174 passed, against 4 failed and
  1 error before.

## End-to-end check

Workflow dispatch run 43563791459 on this branch (commit c202e414) with
`module=packages/alpha-research/src/alpha_research/rendering.py`: success. Only the three
`rendering.py` fragments ran, and `aggregate` was skipped as designed.

| Fragment | Mutants | Killed | Survived | Timed out | Minutes (before, run 43483950887) |
|---|---|---|---|---|---|
| 0 | 95 | 49 | 46 | 0 | 42.4 (failed at 91.4, 38 timed out) |
| 1 | 94 | 52 | 42 | 0 | 24.4 (67.7, 45 timed out) |
| 2 | 94 | 44 | 50 | 0 | 32.1 (85.8, 56 timed out) |

Whole module: 283 mutants, 145 killed, 138 survived, 0 timed out. The kill rate of 0.512 is above
the module's recorded floor of 0.4662 but below 0.90, which is report-only. No test was excluded
from the preflight.

Local fragment 0 and the GitHub fragment 0 disagree on 8 of 95 verdicts, in both directions. Some
`rendering.py` kills depend on the machine (Matplotlib output). This was not caused by this change,
and it is not investigated here.

## Not run

- The full weekly sweep (all modules) on GitHub: not needed to prove this fix. The first scheduled
  run after the merge measures it, and the backlog note waits for two of them.
- Whether constant-only modules (the mutmut 2.5.1 path) honour the new key: mutmut 2.5.1 reads
  only the keys its commands ask for, so the key is ignored. This was read in the source, not run.

## Review findings

- Built by Codex (`gpt-6-astra`, `high`, one fix round), recorded in `03-build.json`.
- Reviewer (Claude Opus, given the diff only), six findings:
  1. Medium-high: under forkserver the parent never sees the stats child's tracer hits. Fixed in
     4b4bf23c: the child reports them and the certificate requires them to be empty.
  2. Medium: the diagnostics could raise inside `finally`. Fixed: they are guarded, read logs with
     replacement and print the error first.
  3. Low-medium: exclusions are not printed when the harness raises before a report exists.
     Accepted: the preflight log tail is printed on error.
  4. Low: the workflow `if:` relied on null coercion. Fixed.
  5. Low: the "fragment 0" label on unfragmented jobs. Fixed.
  6. Informational: no change.
- On re-review, all fixes were confirmed. Two low notes were left as they are: one unreadable log
  stops the printing of the later logs, and a SIGTERM during diagnostics still escapes. Neither
  affects the exit status.
- Codex reviewed Claude's fixes (`handoff.py review`, `gpt-6-astra` medium): 0 findings.
