---
owner: study projections
sources:
  - packages/alpha-study/src/**
  - tests/unit/study/test_*.py
  - tests/bias_guards/test_study_double_bottom_future_poison.py
  - tests/bias_guards/test_verified_semantic_read_future_poison.py
verified: 0377681b
---

# Study invariants

What must hold in `alpha_study` (`packages/alpha-study/src/alpha_study/`): strict, content-hashed
feature, event and factor contracts, reference-only authority projections, the closed operator
registry, and the blind semantic-read contract. The package is a projection layer, not an authority.

## Package boundary

- Import only `alpha_core`, `alpha_data`, `alpha_patterns` and `alpha_research`. Never import strategy,
  backtest, validation, forecast, CLI, MCP or web code. Enforced by the import-linter contract
  `alpha_study composes only research-plane primitives` in `pyproject.toml`; declared dependencies are
  pinned by `tests/unit/study/test_package_boundary.py`.
  [ADR-0035](../../adr/0035-generic-study-composition-and-external-capability-adapters.md).
- Lower layers and the MCP and web surfaces must not import `alpha_study`; their contracts forbid it.
  Only `alpha_cli` composes it. [engineering § Import layers](engineering.md#import-layers).
- The package owns no persistence, CLI commands, UI, external dependencies, approvals, D1/D2 transitions,
  promotion, paper, broker or order authority. D1 stays owner-launched.

## Projection only

- Every serialised contract carries `authority: "none"` and `lineage_verification: "unverified_reference"`;
  `from_dict` rejects any other claim. Keep projections derived, content-hashed references to existing
  authoritative records. [research integrity § Owner authority](research-integrity.md#owner-authority).
- Only an existing-authority CLI or ControlStore verifier may upgrade a reference into usable point-in-time
  lineage. Map any new analytical or authority-linked code to that seam before adding it.
- `authority.py` references (`OperatorRegistrationV1`, `DetectorValidationV1`, `ExplorationMandateV1`)
  are permanently `not_checked`. They perform no live lookup and create no D1 reservation, verdict or
  launch authority. `tests/unit/study/test_authority.py`.
- `projections.py` vocabularies (finding ids, statuses, relationship and action kinds) are closed sets;
  advisor proposals are non-executable.

## Clocks and canonical form

- Event rows: `event_start <= event_end <= printed_at <= confirmed_at <= available_at`, and every feature
  must be available by the event's `available_at`. Event tables hold no realized outcomes and no
  operational timestamps. `tests/unit/study/test_tables.py`.
- Factor rows: `cross_section_at <= observed_at <= available_at`, and `universe_available_at <= available_at`.
- Timestamps must be timezone-aware and serialise as UTC; floats must be finite; key sets must match
  exactly. Hash with `canonical_study_sha256`, the `alpha_research` canonical JSON convention.
  [research integrity § Immutable, hash-bound artefacts](research-integrity.md#immutable-hash-bound-artefacts).

## Operator registry

- `_operator_registry.py` is a closed, Git-owned registry. It holds only `double_bottom.v1`
  (`alpha_research.patterns.detect_double_bottom_events`), pinned by code, dependency-lock and environment
  hashes. An unregistered operator id raises `DataError`; mutable detector definitions never go to SQLite.
- `adapters.py` is the one thin projection of that detector into `EventTableV1`. It duplicates no geometry,
  requires the input artifact hash to equal the bar dataset hash, and uses the detector's full causal
  `confirmed_at` as availability. Guarded by `tests/bias_guards/test_study_double_bottom_future_poison.py`.

## Blind semantic read

- `semantic.py` hashes the complete D0 acceptance, events and chart artifacts, requires exact one-event
  identity and clock agreement, derives points only from the bound chart series, and emits only points
  available by the cutoff plus an aggregate masked count. Guarded by
  `tests/bias_guards/test_verified_semantic_read_future_poison.py`.
- Its cutoff is an unverified acceptance-measurement reference until the CLI verifier composes it.

## External capabilities

- No generic-study dependency is adopted. Each external candidate (Qlib, RD-Agent, indicator libraries)
  stays deferred until separately approved and isolated; the Qlib worker stays outside `alpha_study`.
  [ADR-0011](../../adr/0011-evidence-gated-external-integrations.md),
  [research integrity § Models and isolated workers](research-integrity.md#models-and-isolated-workers).
