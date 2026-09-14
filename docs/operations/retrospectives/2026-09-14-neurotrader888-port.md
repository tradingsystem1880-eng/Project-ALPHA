# Retrospective — neurotrader888 technique port (2026-09-12..14)

Plan `docs/superpowers/plans/2026-09-12-neurotrader888-port.md` (Completed, 26/26 slices, PR #50,
branch `claude/integrate-trader-github-xy6rxs`); provenance
`docs/governance/2026-09-12-neurotrader888-provenance.md`; delivery record in `docs/BUILD-STATUS.md`
("neurotrader888 technique port"). Audit window 2026-09-12T01:25 → 2026-09-14T03:38
(`.claude/state/harness-audit.jsonl`, 395 events); session
`.claude/state/session-5fcbb26b-8df2-553d-862f-b253da4e8f76.json`. 19 commits on the branch
(`bd0493f` plan … `f865378` D) at the time the journal was read; stream E landed as the two
2026-09-14 commits that follow.

## What the harness caught

- Full gate: `gate_failed tier=fast step=mypy` (2026-09-12T07:21) — the first honest signal that the
  sandbox cannot import torch; every later commit went through the audited override (below).
- Task-completion guard: `blocked_task-completed` ×2 (07:53, 2026-09-13T10:20) refused to close a
  task naming `tests/unit/test_directional_change.py` while it still failed.
- Post-edit lint: `blocked_post-edit` ×13, every one on a freshly written module or test
  (`pip_miner.py`, `test_pip_miner*.py`, `test_differential_retracement_kde.py`, `bar_permutation.py`,
  `test_calibration_mcpt.py`, `test_trade_dependence.py`, …).
- Control plane: `blocked_pre-edit-guard` on `tests/oracles/test_differential_runs_test.py`
  (2026-09-13T10:14) and `blocked_config-change` with no ack in the window (2026-09-14T02:02); 31
  `ack_written` events, all `authorized_by: agent (owner token not configured)`.
- Mutation gate (27 `mutation_gate` events): `pip_miner.py` failed ×4 (22:28→23:00) before passing
  at 0.9024 (23:05); `retracements.py` and `rolling_pca.py` both failed (2026-09-13T02:37/02:39) and
  passed only after the B2 oracles were hardened (04:10); `bar_permutation.py` failed once after
  the citation fix (05:07) and re-passed (05:11); `native_tearsheet.py` failed ×2 before passing
  (11:02).
- Reviewer/verifier loops (dispatch events): B1 "Re-verify pip_miner after citation fix", B2
  "Re-verify/Re-review after fail-loud fix", C1 "after citation fix", C2 "after export fix" ×2
  (the reviewer BLOCK on `profit_factor` exported but not imported; the verifier DISCREPANCY on the
  Masters-vs-upstream attribution of the profit-factor criterion), C3 review (the BLOCK on
  `runs_test` counting raw value changes instead of signs — `trade_dependence.py` mutation ran
  twice, 10:21 and 10:32, around the fix). Six `review_attested` / eight `quant_attested` events.
- Relocation zero-loss guard: ack 2026-09-13T05:36 "restore the verbatim metrics.py row in
  `.claude/rules/alpha-validation.md` … carry the profit_factor note in the mcpt.py row instead";
  C4 acks (11:12) had to say "relocated lines untouched; new rows appended"; E5 tripped it again
  on the `alpha figures` row (restored verbatim, growth recorded on a new line).
- Stop guard: `blocked_stop-guard` ×3 then `stop_budget_exhausted` (2026-09-13T09:43, "stop allowed
  with unverified edits") — the budget did its job of forcing a fast stamp attempt, then yielded.
- Subagent schema: `blocked_subagent-stop` (22:51) rejected a quant-verifier reply that was not a
  bare `QuantVerificationReport` JSON.
- C4 review verdict (`.claude/state/review-verdict.json`, APPROVE with 7 findings) flagged consumers
  the diff did not touch: `_suite.py three_null_families` has no `tier3_paths` knob, `gates.ts
  nullStory` never names a vetoing Tier 3, MCP `_VALIDATE_OPTIONS` lacks `tier3-paths`.

## What the harness missed

- The full-gate stamp was never obtainable: `torch==2.12.1+cpu` is egress-blocked
  (`download-r2.pytorch.org`, 12 session `failures[]`). All 18 `override_written` events (one per
  non-docs commit; 15 `override_consumed`) are agent self-serve with the same reason and a
  hand-run checklist; CI on PR #50 is the authoritative gate. The harness cannot distinguish an
  environment-only failure from a real one, so it could only audit, not verify.
- `gate.py mutate` on `native_tearsheet.py` reported `status=unavailable: FileNotFoundError
  .claude/state/mutation/native_tearsheet` (05:35, 05:36) and the run hit the 10-minute tool
  timeout (session failure 05:46:38); the gate has no per-module runtime budget.
- Playwright e2e failed at launch on a browser-revision mismatch (pre-installed
  `/opt/pw-browsers/chromium_headless_shell-1194` vs the 1228 revision Playwright 1.61.1 pins)
  until the expected revision directory was aliased to the installed one; `gate.py doctor`
  (`scripts/gate.py:1042`) checks hooks/skills/rules, not the browser install.
- DefiLlama live shape is UNVERIFIED (`api.llama.fi` egress-blocked; D override, plan slice D,
  provenance row); the family ships against a recorded fixture and the owner's first
  `alpha provider check defillama` receipt is the real test.
- Second-model review never ran: 11 `codex_call` events, all `available=False` (codex CLI not on
  PATH); `review-verdict.json` carries `codex_unavailable: true`.
- `over_eager_edit` recorded 97 events, most of them shell tokens (`data.size:`, `0.0`, `=`,
  `counts[1]`) rather than paths — the detector adds noise to the brief instead of signal.
- 111 `blocked_pre-bash-guard` events, almost all subagent sandbox friction (`git -C`, `sed -n`,
  `UV_NO_SYNC=1 uv run python`, redirections) rather than policy violations.

## Assumptions and pre-mortem, revisited

- Assumptions 1–4, 6 held as written (`uv lock` unchanged, 15/15 import contracts in every
  override, bias guards per module, ADR-0036 accepted before D code). Assumption 5 held but the C4
  review found the suite/SPA/MCP consumers of the third tier were not in the slice (`review-verdict`
  findings 1–3); E2 later added the `nullStory` narration (plan slice E2 title).
- Assumption 7 held: one OpenAPI/TS contract change and `tests/unit/test_overlay_tables_drift.py`.
- Pre-mortem "mutation kill-rate < 0.90 because tests are smoke-shaped" materialised three times
  (pip_miner, retracements, rolling_pca) and was resolved as planned (oracles assert relations).
- Pre-mortem "awareness drift test fails because a rule row was batched" did not materialise —
  every slice acked its row in the same commit — but the *inverse* did: rewording a verbatim row
  tripped the relocation guard (C2, E5).
- Pre-mortem "DefiLlama endpoint drift / ToS" is unresolved by construction: honest UNVERIFIED.
- Pre-mortem "1000-line guard blocks A5/A6" did not fire; A4/A6 were pre-split (commit sequence).
- Not foreseen: the full-gate stamp being unobtainable for the whole program; the Playwright
  revision mismatch; `native_tearsheet` mutation runtime.

## Watch-outs

- Run the pytest suite with `.venv/bin` first on PATH (system `python3` is 3.11 and cannot import the venv's numpy); otherwise `alpha` subprocess tests fail on the entrypoint.
- One `gate.py mutate` module per invocation; `native_tearsheet` alone approaches the 10-minute tool timeout and a second module wipes its `.claude/state/mutation/<module>` dir.
- `files_reviewed` in `/review-gate` and `/verify-quant` attestations must be repo-relative paths or the tree binding does not match.
- Never `pkill -f <pattern>` where the pattern appears in your own shell command — it kills the caller.
- The `uv run` web server for Playwright needs `UV_NO_SYNC=1` in this sandbox (every plain `uv run` tries to fetch the torch wheel and dies).
- Add new rows to `.claude/rules/alpha-*.md`; never reword a verbatim relocated MODULE MAP row (zero-loss guard, C2 ack 2026-09-13T05:36, E5 ack 2026-09-14).
- Definition-only catalogue entries break `{FIGURES} == set(BUILDERS)` (`tests/integration/test_figure_builders_reproducible.py:114`); definitions land with their builders (B3 folded into E5).
- A zero-range bar makes the Hawkes normalised range 0/0; guard with `np.errstate` and the `_NAN_AFTER_WARMUP` policy (`apps/alpha-cli/src/alpha_cli/chart_cmds.py`).

## Rule to add

- `gate.py doctor` check "playwright browser revision": compare the chromium revision pinned by
  `apps/alpha-web/frontend/node_modules/playwright-core` with the directories under
  `PLAYWRIGHT_BROWSERS_PATH` (here `/opt/pw-browsers`); FAIL with the alias hint. Proposed for
  `scripts/gate.py:doctor`; needs an acked edit.
- `.claude/rules/tests.md` line: "Offline sandbox: run pytest via `.venv/bin/python -m pytest` and
  the e2e web server via `UV_NO_SYNC=1 uv run …`; a `uv run` that re-syncs is an environment
  failure, not a test failure." Plus the same paragraph in `docs/operations/claude-code-harness.md`.
- Hook check: `over_eager_edit` should record a token only if it resolves to an existing path or
  matches `^[\w./$-]+\.\w+$`; 97 noise events this program. Proposed for `claude_hooks.py`.
- `.claude/rules/docs.md` line (promoted — recurred in C2, C4 ×2, E5): "Relocated MODULE MAP rows
  are byte-frozen; extend by appending a row, never by editing."
- Full-gate stamp unobtainable: none — accepted limitation, because the torch wheel is
  egress-blocked and CI is the authoritative full gate; the override reason already lists the
  hand-run checks per commit.
- DefiLlama live shape: none — accepted limitation, because the endpoint is egress-blocked and the
  owner's provider-check receipt is the designed verification path (ADR-0036).
