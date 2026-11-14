# A fixed-rule contract cannot be approved from the command line without the local confirmation

**Delivery state:** In progress on branch `m8/first-real-study` (filed straight into the archive).
**Build class:** small.

## For the owner

- What changes: if you approve the daily trading-rule study (or any fixed-rule study) with the
  command `alpha research approve exploration ...`, ALPHA now refuses and tells you to approve it
  in the Workstation instead. Today the command appears to succeed, but the study can then never
  run: its runs demand the Workstation's one-time local confirmation, and the Workstation can no
  longer approve a contract the command line already approved. The case would be stuck for good.
- What does not change: approving in the Workstation works exactly as before; every other kind of
  research case is still approved from the command line as before; no approval is made by this work.
- No approval is invalidated: the edited files are not among those approvals are bound to.

```json
{
  "schema_version": 1,
  "title": "A fixed-rule contract cannot be approved from the command line without the local confirmation",
  "context": "Fixed-rule contracts (the daily BTC rule lane and the synthetic fixed-rule lane; _native_rule_protocol.is_rule_contract) run only after RuleAuthority.verify finds the owner's review AND one consumed local-confirmation owner_action_receipt for approve_exploration whose actor equals the review actor (_native_rule_protocol.require_rule_confirmation). The Workstation creates that receipt (alpha_web/api/owner_auth.perform_action: verify_local_confirmation, then the CLI 'research approve exploration' subprocess with the receipt's actor). The bare CLI 'alpha research approve exploration' records the review and moves the case to 'pilot' without any receipt, so 'run pilot' then fails with 'fixed rule approval requires one exact consumed owner confirmation', and the Workstation can no longer approve because the phase is no longer exploration_review and the contract already has an owner review: the case is unrecoverable. Fix at the entry: the CLI approve refuses a fixed-rule exploration contract unless that exact consumed confirmation for the given actor already exists, before any review or phase change is written.",
  "assumptions": [
    {
      "statement": "The Workstation path consumes the local confirmation (writing the owner_action_receipt with used_at) before it runs the CLI approve subprocess with actor equal to the receipt actor, so a check of require_rule_confirmation inside the CLI approve passes on that path.",
      "verified_by": "Reading apps/alpha-web/src/alpha_web/api/owner_auth.py perform_action (verify_local_confirmation then _action_argv approve_exploration with actor=authorization['actor']) and owner_auth.py verify_local_confirmation (receipt outcome local_confirmation_consumed); the lifecycle test ceremony in tests/unit/test_native_daily_rule_lifecycle.py::_case does the same order."
    },
    {
      "statement": "research_cmds.py and _research_cmd_parts.py are not in any approval binding (research code hash: alpha_research plus research_intake, research_runtime, research_crypto_data, research_crypto_runtime; daily: DAILY_GUARD_FILES), so the change invalidates no approval.",
      "verified_by": "docs/reference/invariants/cli-research.md Implementation hash; apps/alpha-cli/src/alpha_cli/_native_rule_environment.py DAILY_GUARD_FILES on origin/main 947d911e."
    }
  ],
  "alternatives_considered": [
    "Put the check inside ControlStore.review_research_contract: rejected for now, control_store.py is in DAILY_GUARD_FILES (editing it invalidates daily approvals) and a large split of it is planned.",
    "Let 'run pilot' accept a CLI-only review for rule contracts: rejected, it would weaken the consumed-confirmation rule the lane was built on.",
    "Document the trap only: rejected, a documented trap that destroys a case is still a defect."
  ],
  "pre_mortem": [
    "The check breaks the Workstation path: a test drives the same ceremony as the Workstation (local_confirmation_options, verify_local_confirmation, then the CLI approve with the receipt actor) and asserts success.",
    "The check leaks into non-rule cases: a test approves an ordinary double-bottom exploration contract from the CLI without any receipt and asserts it still succeeds unchanged.",
    "research_cmds.py grows past its frozen size baseline: the edit there is line-neutral (one existing line replaced by one call); the helper lives in _research_cmd_parts.py."
  ],
  "slices": [
    {
      "title": "CLI approve refuses a fixed-rule contract without its consumed local confirmation",
      "verify": "uv run pytest -q tests/unit/test_rule_cli_approval_confirmation.py tests/unit/test_daily_native_cli.py tests/integration/test_research_cli.py",
      "expected": "Without a receipt: exit code non-zero, message names the Workstation local confirmation, no review row, phase still exploration_review. With the Workstation-order ceremony: approve succeeds and phase becomes pilot. Ordinary non-rule contract: CLI approve unchanged.",
      "rollback": "Revert the helper, the one-line call and the new test file.",
      "files": [
        "apps/alpha-cli/src/alpha_cli/research_cmds.py",
        "apps/alpha-cli/src/alpha_cli/_research_cmd_parts.py",
        "tests/unit/test_rule_cli_approval_confirmation.py"
      ],
      "status": "planned"
    }
  ],
  "tier_impact": [
    "none"
  ],
  "docs_to_update": [
    "docs/reference/invariants/cli-native.md",
    "research/stages/02-data/CONTEXT.md"
  ],
  "out_of_scope": [
    "control_store.py, owner_auth.py, any DAILY_GUARD_FILES member, workers/rdagent, alpha_web",
    "Confirmation-scope contracts (rule lanes have no D2)",
    "Approving, re-approving or promoting anything"
  ],
  "files": [
    "apps/alpha-cli/src/alpha_cli/research_cmds.py",
    "apps/alpha-cli/src/alpha_cli/_research_cmd_parts.py",
    "tests/unit/test_rule_cli_approval_confirmation.py"
  ]
}
```

## Read first

| Read | Section | When |
|---|---|---|
| [command line native](../../../../reference/invariants/cli-native.md) | Approval fingerprints | always |
| [research_cmds.py](../../../../../apps/alpha-cli/src/alpha_cli/research_cmds.py) | `approve` | the call site |
| [_native_rule_protocol.py](../../../../../apps/alpha-cli/src/alpha_cli/_native_rule_protocol.py) | `is_rule_contract`, `require_rule_confirmation` | the rule being enforced |
| [_native_rule_authority.py](../../../../../apps/alpha-cli/src/alpha_cli/_native_rule_authority.py) | `RuleAuthority.verify` | what a run demands |
| [owner_auth.py (web)](../../../../../apps/alpha-web/src/alpha_web/api/owner_auth.py) | `perform_action` | the Workstation order |
| [lifecycle test](../../../../../tests/unit/test_native_daily_rule_lifecycle.py) | `_case` | the test ceremony to reuse |

## Slices

1. `_research_cmd_parts.py`: add `_require_cli_rule_confirmation(store, scope, project_id,
   contract_id, actor) -> ResearchContractScope`. It validates the scope as `approve` does today
   (same error text), returns it typed, and for scope `exploration`: reads the contract payload in
   a read transaction (`store._require_research_contract`); if `is_rule_contract(payload)`, calls
   `require_rule_confirmation(connection, project_id, contract_id, actor)` and on its `DataError`
   raises `DataError("this fixed-rule study is approved in the Workstation with its one-time local
   confirmation; open the case there and choose Approve. The command line cannot approve it.")`.
   Imports of `_native_rule_protocol` stay inside the function.
2. `research_cmds.py`, `approve`: line-neutral. The three lines that check the scope, raise and
   cast it become exactly three lines: a local
   `from alpha_cli._research_cmd_parts import _require_cli_rule_confirmation as _rule_check`, a
   blank line, and `typed_scope = _rule_check(store, scope, project_id, contract_id, actor)`
   (as `draft_daily` already imports locally). The file keeps exactly 3,539 lines and `approve` keeps its line count
   (`tests/unit/test_code_size.py`; `.claude/code-size-baseline.json` is not edited). Nothing else
   in the file changes.
3. New `tests/unit/test_rule_cli_approval_confirmation.py`, test-first (must fail before slice 1-2
   with the CLI approve succeeding): (a) a daily or synthetic fixed-rule contract in
   `exploration_review`, CLI `research approve exploration` without a receipt is refused with the
   Workstation message, and the store shows no review and the phase unchanged; (b) the same after
   the ceremony in Workstation order (`owner_auth.action_binding`, `local_confirmation_options`,
   `verify_local_confirmation`, then the CLI approve with `--actor` equal to the receipt actor)
   succeeds and moves to `pilot`; (c) an ordinary non-rule exploration contract is approved from
   the CLI with no receipt, unchanged. Reuse existing fixtures; do not need Docker or RD-Agent.

## Test plan

Test-first as in slice 3; then the focused files in the slice `verify`, and `gate.py check`.

## Look-ahead, determinism and import impact

No data access, statistic, fingerprint or point-in-time read changes. No new import edge across
layers (`alpha_cli` internal only).
