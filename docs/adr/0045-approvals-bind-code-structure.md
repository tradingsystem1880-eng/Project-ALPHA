# ADR-0045: Research approvals bind what the code does, not its exact bytes

**Status:** Accepted
**Date:** 2026-11-14
**Deciders:** Project ALPHA owner (the decision) and AI build agents (the mechanism)

## Context

An owner-approved research contract freezes fingerprints of the code it was approved against
(`hashes.code`, and for the fixed rule lane `hashes.evaluator`). Until now both were SHA-256
digests of the exact source bytes, so fixing a comment or re-formatting a bound file invalidated
every approval, and the largest bound files (`control_store.py`, `research_runtime.py`, the
`alpha_research` tree) could not be tidied. On 2026-11-14 the owner decided to tie approvals to
code structure: an approval stays valid when only comments, formatting, blank lines or docstrings
change, and is invalidated by any change to what the code does.

The dangerous failure is "behaviour changed and the approval stayed valid"; the safe failure is
"an approval is invalidated when it need not be". Every choice below takes the safe side.

## Where code bytes are bound today, and what changes

| Site | Binds | Class | This ADR |
|---|---|---|---|
| `research_cmds.py::_implementation_hashes` → `hashes.code`, checked by `_implementation_drifted` | `alpha_research` tree + 4 research CLI modules | (a) owner approval | scheme 2 for new approvals; scheme 1 still verifies |
| `_native_rule_environment.py::rule_implementation_fingerprints` → `hashes.code`, `hashes.evaluator` | rdagent worker files, `rule_probe.py`/`costed_probe.py`, and for daily studies the `DAILY_GUARD_FILES` (25 here, 40 since [ADR-0048](0048-daily-rule-lane-binding-and-named-months.md); incl. `crypto_bulk_store.py`, `control_store.py`) | (a) owner approval | scheme 2 only (see Consequences) |
| `uv.lock`, worker `uv.lock`, rule/economics requirement locks (`hashes.dependency_lock`) | lock files | (b) environment | unchanged, bytes |
| `measure_rule_environment` (installed profile `site_files`, `source_files`, Python binary, `pyvenv.cfg`) | what is installed in the qualified rule venvs | (b) environment | unchanged, bytes |
| `SOURCE_SHA256` (`_native_loop_admission.py`, `workers/rdagent/source_pin.py`), Qlib `_SOURCE_PINS` | pinned upstream RD-Agent / Qlib files | (b) upstream pin | unchanged, bytes |
| `NativeLaunch.implementation_fingerprints` with no study, `StockFixtureLaunch.implementation_fingerprints` | synthetic fixture lanes, authority `none` | (c) synthetic qualification | unchanged, bytes |
| `measure_native_proposal`, `imported_worker_sha256`, container owner/watchdog hashes | launch identity, worker self-attestation, checked within one job | (c) launch identity | unchanged, bytes |
| `_identity.py` execution/strategy fingerprints, `_hypothesis_scan` code hash, `research_diagnostic_cmds` source hash, `comparison_acquisition` / `investigation_comparisons` / `research_suggestions` policy hashes, `native_qlib_pipeline` provenance, `ml_refit` worker inventory, Qlib `adapter_source_hash` | run ids and provenance; no approval | (c) | unchanged, bytes |

## Decision

### The digest (`apps/alpha-cli/src/alpha_cli/_structural_digest.py`, standard library only)

- **Basis.** Each Python file is parsed with Python 3.12's `ast.parse` (from bytes, so an encoding
  cookie is honoured; `type_comments=False`; warnings suppressed so a warning filter cannot change
  the result) and the tree is serialised by an explicit encoder over every `_fields` entry of every
  node, without positions. Constants keep their type and `repr` (so `1`, `1.0`, `True`, `'1'` and
  `b'1'` differ). The document hashed is domain-separated (`alpha-python-structure-v1`, the mode).
- **What is free:** comments (including `# noqa`, `# type: ignore`, `# fmt:`), blank lines,
  indentation style, line breaks, parenthesisation that does not change the tree, trailing commas,
  quote style and implicit string concatenation, and docstrings where nothing can read them.
- **What is bound:** every name, literal, operator, comparison, decorator, default argument,
  argument order, annotation (all of them, used at run time or not), import (including
  `from __future__`), `__all__`, f-string part, keyword, slice bound, class attribute and statement
  order. The tests show one behaviour edit of each kind changing the digest.
- **Docstrings.** Only the first statement of a module, class or function body that is a plain
  `str` literal is a docstring. They are dropped unless the file can read them: it names
  `__doc__`, `getdoc`, `pydoc`, `doctest`, `help`, `typer`, `click`, `pydantic`, `fastapi`,
  `vars`, `__dict__`, `globals` or `co_consts` (in any name position or as a string constant), has
  a string containing `__doc__`, or calls `getattr`/`hasattr` with a computed attribute name. Such
  a file keeps its docstrings (`structure-with-docstrings`). Readers in other modules are guarded
  by a repository scan
  (`tests/unit/test_structural_digest.py::test_no_unreviewed_code_reads_docstrings_or_source_of_other_modules`):
  every file that reads docstrings or source is listed and reviewed, and none of them is bound.
- **Layout that is behaviour.** A file is bound by its exact bytes when it can observe its own
  source, comments, line numbers or frames, or runs code built at run time: it names any of
  `inspect`, `linecache`, `traceback`, `tokenize`, `dis`, `getsource*`, `co_firstlineno`,
  `co_lines`, `f_lineno`, `f_back`, `_getframe`, `_current_frames`, `gi_frame`, `cr_frame`,
  `gi_code`, `__code__`, `__traceback__`, `lineno`, `findCaller`, `stack_info`, `__file__`,
  `__loader__`, `__spec__`, `get_source`, ... (pinned name by name in the tests); imports
  `warnings` or `logging` (warning de-duplication and log records depend on the calling line);
  calls the builtins `eval`, `exec`, `compile`, `__import__` or `breakpoint`; has a string
  containing `lineno`, `funcName`, `__code__`, `__file__`, `_getframe` or `f_back` (log formats,
  computed keys); or makes a computed `getattr`/`hasattr` lookup in a file that imports `sys` or
  `builtins`. Names are found in every position: loads, attributes, imports, keywords, function,
  class and argument names, `global`, `except ... as`, and match captures.
- **Boundary.** The scan finds every ordinary way Python exposes layout or docstrings, including
  the ones independent reviewers constructed (see the pull request). It cannot be complete against
  code written to hide its intent, for example an attribute name assembled from fragments and
  looked up on a generator or frame object reached through other computed lookups. Such code in an
  approval-bound file is a review defect in itself; the reviewer and the owner's approval remain
  the control for it.
- **Constant folding and Python versions.** The tree is taken before the compiler's optimiser, so
  `1 + 2` and `3` differ. The node set and serialisation are pinned to Python 3.12: the digest
  records `3.12` and refuses to run on any other minor version (`StructuralDigestError`); the
  research `environment` fingerprint already binds the exact patch version.
- **Fail closed.** A file that does not parse (syntax error, null byte, undecodable, too deeply
  nested) or holds a node or constant type the encoder does not know is bound by its exact bytes.
  A missing file, an empty set or an unsupported interpreter refuses. Nothing falls back to valid.
- **Non-Python files** (JSON themes, locks, schemas, templates) are bound by their exact bytes.
  Under scheme 2 the research tree's non-Python files (`figures/themes/*.json`, `py.typed`) are
  now bound too; scheme 1 never bound them.
- **The rules bind themselves.** The composite digest includes the SHA-256 of
  `_structural_digest.py`'s own bytes, so any change to these rules, even a comment, invalidates
  every scheme-2 approval.

### Versioning

- **Scheme 1 (exact bytes)** is the formula every existing approval was made with. It is kept,
  frozen, as `research_cmds.py::_byte_code_hash` (a test pins it to the pre-ADR formula).
- **Scheme 2 (structure)** is what `_implementation_hashes` now freezes for every new approval.
- `research_cmds.py::_approved_code_scheme` says which scheme reproduces an approved code hash
  from the code as it is now: 2 if the structural digest matches, 1 if the byte digest matches,
  otherwise none (drifted). The two hash different, domain-separated documents, so a scheme-1
  approval can be satisfied only by identical bytes, never by equal structure.
- **No approval is upgraded automatically.** An approval made under scheme 1 stays bound to bytes
  until the owner re-approves (a new contract drafted now is scheme 2). The stored record keeps the
  same five `hashes` keys; no field is reinterpreted.

## Consequences

- New research approvals survive comment, layout and unread-docstring edits to bound files. Run
  identity (`_identity.py`) still fingerprints bytes, so such an edit still changes new run ids,
  and the quant-tier gates still run on a touched quant module.
- **Rule lane, one-time invalidation.** `_native_rule_environment.py` is itself one of the
  `DAILY_GUARD_FILES`, so changing it necessarily changes every daily rule approval's code hash.
  Its comparisons are exact equality across the admission path (`_native_loop_admission.py`,
  `_native_fixture_store.py`, `_native_rule_completion.py`, `control_store.py::_d1_native_spec`),
  so carrying scheme 1 there too would need scheme selection threaded through those guarded
  files for approvals this pull request invalidates anyway. The rule lane therefore moves to
  scheme 2 only: every pending fixed-rule or daily-rule approval made before this change no longer
  verifies and must be re-drafted and re-approved by the owner. Nothing is accepted that was not.
- Research-lane approvals made before this change keep verifying exactly as before, because no
  research-bound file changes here.
- The digest module is not in the quant tier, and this change touches no quant-tier source, so the
  CI `quant` job does not select it. Adding it was rejected: the mutation gate stages every test
  that imports the module's package, which for `alpha_cli` is most of the suite. The module is
  instead held by its own tests, a mutation self-check recorded in the pull request, and the
  `slow_oracle` sweep, which runs nightly. Putting it under `scripts/handoff.py::GUARDED` (so a
  builder must declare a tier to change it) is a recommended follow-up; until then any edit to it
  invalidates every scheme-2 approval, which is the safe direction.
- Computing the research digest takes about half a second (36 files); it runs once per pilot,
  deep-research or confirmation start.
- Tests: `tests/unit/test_structural_digest.py` (invariance, one test per behaviour edit, fail
  closed, scheme 1 frozen, the reader scan, and a mutation sweep over real bound modules checked
  against an independent oracle, compiled line-free bytecode; `slow_oracle` runs all bound files).
