# README upkeep during Codex delivery

README upkeep is part of the existing Codex implementation task. The session that understands
and changes the code also reviews and edits README **before delivering its branch**. It uses the
current coding session; the checker makes no model call, introduces no API credential or spending
setup, and adds no GitHub inference workflow. Normal engineering CI stays unchanged.

## Coding-session workflow

1. Read AGENTS.md, CLAUDE.md and the existing feature workflow. Fetch `origin/main` through the
   already authorized repository route. Review the **whole final branch**, including earlier
   commits, current architecture, implemented entry points and tracked plans. Plans are not proof
   of implementation. Never inspect private tests, credentials or owner data for this review.
2. Update README where readers need a different explanation: purpose, how components fit,
   implemented versus planned work, practical entry points, setup and limitations. Preserve useful
   accurate technical material and link deeper details. Keep plain English and a concise overview;
   avoid an endless changelog. Verify claims against code and check affected links/anchors, including
   external documentation when needed. Engineering tests do not establish trading readiness.
3. If the final branch has no reader impact, leave README bytes unchanged and explain why its
   existing statements remain accurate. An updated timestamp or pointless rewording is not upkeep.
   `updated` means README differs from main somewhere on this branch; it need not change again in
   every commit. A later internal fix can retain an earlier useful README update after fresh review.
4. Finish code, docs and generated outputs. Stage the candidate and prepare a short native review
   report. The existing full gate and independent review still apply. Any final-tree content change
   or fetched-main movement invalidates the README evidence and requires review again.

Inspect the native scope and tree binding using the same Python seam as the existing review gate:

```bash
uv run python - <<'PY'
import json
import sys
sys.path.insert(0, "scripts")
import gate
import readme_review
root = gate.repo_root()
print(json.dumps({"reviewed_tree_hash": gate.compute_tree_hash(root),
                  "changed_paths": readme_review.context(root)["paths"]}, indent=2))
PY
```

Write the session's actual decision to a temporary JSON file (substitute the inspected tree hash):

```json
{
  "reviewed_tree_hash": "<64-character final tree hash>",
  "disposition": "updated",
  "rationale": "README now explains the implemented delivery review step and links its native evidence command. Existing startup, research and authority limits remain accurate."
}
```

Use `no_change` when README has no branch diff, with a substantive reason specific to the task.
Do not copy a stock rationale without doing the review. Record it through the existing gate:

```bash
uv run python scripts/gate.py attest --kind readme < /tmp/readme-review.json
uv run python scripts/gate.py full
```

Native evidence lives in ignored `.alpha/state/readme-review.json`, alongside existing gate and
review records. It binds the final tree, fetched main comparison and changed paths, and records
`updated` or `no_change` with a rationale. Local inline Markdown file targets must exist in the staged repository and are checked without network
access. The checker rejects unknown comparison bases, stale trees/base/scope, wrong disposition,
missing README, malformed reports and missing/out-of-repository local link targets. It does not
write README or require a no-impact branch to edit it. Summarize the decision in the normal PR/task
handoff; keep the existing feature plan rather than starting a separate documentation system.

## Worked example: this task

The final branch adds native README review to the existing delivery guard. The coding session
keeps the project's reader-friendly component guide, replaces the API-based upkeep instructions
with this workflow, and adds a short README development paragraph explaining the real local
review/evidence step. Existing startup commands and product limits are preserved. It records
`updated` with a code-grounded rationale, then runs the full gate and independent review before a
normal guarded commit/push. This is an actual change on this branch, not an invented product feature.

For a later task that only repairs an internal test fixture, the session reads the final diff and
confirms that documented behavior, setup and limits remain accurate. If README has no branch diff,
it records `no_change` with that concrete explanation and leaves the file untouched. The installed
commit guard still requires fresh evidence for that final tree.

## Enforcement limits

The installed local Git precommit guard blocks delivery commits without matching README review
evidence, after checking the existing full-gate/staged-tree requirements. Review and quant guards
retain their normal requirements. Evidence validates structure, freshness, branch scope and local
file links; it **does not prove semantic correctness**, source truth, external URLs or every anchor.
The coding session and normal reviewer remain responsible for claims and usefulness.

This is local installed-hook feedback, not a guarantee over all arbitrary pushes. Clients without
the repository's Git guards, bypassed hooks, merges made elsewhere and unrelated agents outside
these instructions cannot be claimed covered. Existing CI tests the harness but a fresh GitHub
checkout cannot recover the ignored local review record or prove that a particular session read
the prose. Normal review, branch protections and owner-authorized publication/merge remain intact.
Do not infer scientific, provider, paper or live-capital authority from this record.

The earlier API-based PR head and its tests are preserved as superseded evidence. The revised
branch removes that workflow, secret dependency, extra Actions write/dispatch capability and
architecture-only scaffolding. No credentials, spending configuration or paid inference is needed
for this delivery check. Private test coverage remains UNVERIFIED under the owner's task-scoped
absence-only exception; all other required checks still block when they fail or cannot run.
