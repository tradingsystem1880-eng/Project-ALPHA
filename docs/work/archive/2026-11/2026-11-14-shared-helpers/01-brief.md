# One copy of each duplicated helper

## What the owner wants

From the clean-up milestone "agent-sized code": "Earlier audits found duplicated JSON/hash/validator
helper functions across packages. Find them properly (do not trust that sentence; measure), and
consolidate where one honest shared home exists that respects the import-boundary contracts.
Leave duplicates that exist for a boundary reason and say why." Also: guard
`_structural_digest.py` in `scripts/handoff.py`; delete functions only tests call, keeping anything
a component page says is planned; check the `--created-by codex` default.

In one sentence: measure the duplication, remove the copies that can honestly share one home, and
say why each remaining copy stays.

## What done looks like

- Each consolidated helper exists once; behaviour is unchanged (any exception is named).
- Every duplicate left in place has a stated reason.
- Functions that only tests called are gone, or kept with a reason.
- A builder cannot change the approval digest rules without declaring a tier.

## How they will see it

Nothing visible in the app, except that a research idea captured in the Workstation is now
recorded as created by `workstation` rather than `codex`.

## Out of scope

Approval-bound files (no research or rule approval may be invalidated), the data layer (another
stream is working in `packages/alpha-data`), the quant-tier `alpha_validation`.
