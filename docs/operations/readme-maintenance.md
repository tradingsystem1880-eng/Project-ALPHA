# README maintenance

This workflow is implemented as a candidate change, **not deployed or live-verified**. It keeps the
plain-English reader guide near the top of README aligned with merged code. Everything outside
`codex-reader-guide:start/end` remains unchanged, including setup instructions, screenshots,
research protocols and technical architecture. If Codex finds those details inaccurate, the run
fails visibly and requires a normal correction; it does not quietly declare the README current.

## What happens after a merge

1. A push to `main` (including a merged branch) starts **README maintenance**. A manual run is also
   available after deployment for recovery. It checks out current `main`, not an old event SHA.
2. The helper compares tracked changes since the guide's last incorporated source SHA. Tests,
   image-only changes and README-only changes do not need inference. Pending source changes
   remain visible across cancelled runs because comparison is cumulative, not just the latest push.
3. For relevant changes, Codex receives a bounded evidence packet: the existing README,
   architecture, platform and authority maps, and changed tracked source/plan files. Deleted paths
   remain listed. Private tests, untracked owner data, environment dumps and credentials are excluded.
   Large files use explicitly labelled changed hunks; oversized diffs/packets fail loudly
   instead of silently discarding evidence.
4. A fresh inference job downloads only that packet, schema and trusted validator; it has no
   repository checkout, Git history or private tests. Codex runs with pinned CLI/action versions,
   read-only permissions, privilege reduction and fresh configuration. Product MCP servers are not loaded. Repository
   content is explicitly untrusted data; there is no PR-body interpolation into executable commands.
5. Only schema JSON can cross to the separate delivery job. Validation rejects unexpected fields,
   nonlocal/missing evidence links, HTML, known secret patterns, exact injected credentials and
   excessive text. A no-op changes no bytes. Changed prose replaces only the owned section.
6. The exact README candidate passes the existing canonical full gate and installed Git guards
   before a conventional Git commit. Only README may differ. The workflow pushes an ordinary
   `codex/readme-<source SHA>` branch and opens a docs PR. It never pushes to `main`, force-pushes,
   approves its own PR, fabricates a review receipt, changes branch protections or bypasses gates.
7. Existing CI is explicitly dispatched on that branch. The CI backend rejects stale generated
   README branches and verifies their SHA-bound README-only scope. Normal required checks and
   owner review/authorized merge still apply. Automatic prose generation is not automatic approval.

The model can still be wrong about meaning. The reviewer must check implemented-versus-planned
claims against links and code. Lexical validation cannot prove semantic truth or guarantee that
arbitrary sensitive text is absent. Never add credentials or private owner records to tracked source.
Passing engineering checks does not establish a trading edge, provider acceptance or live readiness.

## Authentication, permissions and cost

Official [Codex Action documentation](https://github.com/openai/codex-action) requires an inference
API credential. A ChatGPT subscription or a local CLI login does not authenticate this Actions job.
The implementation references an existing authorized repository secret named `OPENAI_API_KEY`;
it does not create or configure one. No credential is available in the task environment, and
repository secret existence has not been verified. No inference call or hosted workflow was run.

The smallest inference setup action is owner authorization to add an OpenAI project API key as the
repository Actions secret `OPENAI_API_KEY`, with API billing and access to `gpt-6-astra`. Do not post
it in chat or Git. This setup action is pending, not performed. No new GitHub App or PAT is needed.
The workflow uses the repository's short-lived `GITHUB_TOKEN` for branch/PR delivery and CI dispatch.
Its delivery job requests `contents: write`, `pull-requests: write` and `actions: write`; the model
job has `contents: read`. The repo/org must already permit workflow-created PRs. If policy denies
that, report the exact denial and ask the owner before changing the setting; never change it here.

The implementation itself touches protected workflow paths and needs independent review. The
private `tests/holdout/` suite is absent. Under the current reviewer instructions that is a blocking
unrun check for this new task; historical exceptions do not apply. Restore the original suite or
obtain an explicitly scoped owner exception before guarded publication. Private coverage stays
UNVERIFIED. No private content was read or modified.

Relevant runs consume OpenAI API tokens plus GitHub Actions minutes. The input packet is capped
at 500,000 characters, individual files at 80,000, output at 12,000 characters / 1,600 words, and
assessment at 12 minutes. The prompt targets 900 words. Qualification may use up to 90 minutes,
including all existing components and browser tests; CI then checks the committed branch again.
There is no guarantee of a fixed dollar charge: pricing, model usage and runner billing vary.
There is no persistent response cache; duplicate events may repeat an assessment, but they do not
create a second PR for the same source SHA. Consider lower frequency only if cost becomes material.

Pins checked 2026-10-31: OpenAI Action `13e9c17417b29e9a276f73ec6ed7fb574137d3c3`, Codex CLI
`0.166.0`; checkout/upload/download/setup-uv/setup-node use full commit SHAs in the workflow. Review
pin upgrades as ordinary protected code changes. The model name is explicit and API access must
be validated at activation. See [Codex Action inputs and safety](https://github.com/openai/codex-action/blob/13e9c17417b29e9a276f73ec6ed7fb574137d3c3/README.md)
and [GitHub workflow triggers](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow).
Current GitHub documentation allows token-created PR runs in an approval-required state; explicit
`workflow_dispatch` avoids depending on someone approving those runs. Existing protection rules
still decide which checks/reviews are required; the workflow does not change those settings.

## Failure and recovery

Runs are serialized and newer pushes cancel older work. Each publication checks `main` before
commit and push/PR creation; stale work fails instead of rebasing generated prose onto unseen code.
The delivery job closes obsolete bot-authored generated PRs, including after failed inference.
Human branches and the separate delivery-marker branch are unaffected. Normal CI also rejects a
generated PR whose source SHA no longer matches `main`. A final merge-time race is governed by
existing branch protection: reviewers must not merge obsolete PRs. The workflow does not grant
or imply a protection-policy change.

A self-generated README merge has only README differences from its recorded base, so it does not
call Codex again. If other source changes arrived meanwhile, the cumulative comparison assesses
them. Human README-only edits are also no-ops when no source changes await incorporation.
A semantically unchanged assessment preserves the original source marker; later assessments may
revisit those still-relevant source changes. That costs tokens but cannot create an infinite PR loop.

Missing auth, action/API errors, failed output validation, oversize evidence, stale `main`, guard
failure, failed CI dispatch or failed gates all produce a failed Actions run. No success marker is
written on failure. The failed run is the visible drift signal; there is no silently successful
fallback or guarantee that the guide is current. Inspect job logs before rerunning **README
maintenance** on `main`. Model output artifacts expire after one day and never contain transcripts.
A PR that exists but whose CI dispatch failed is recoverable by rerunning the workflow: its
per-source branch/PR is reused and CI is dispatched again. A pushed branch without a PR is recovered only when its complete tree equals the newly tested
candidate. Different bytes require inspection; never force-push or delete unknown changes.

After authorized deployment, verify a manual run first, then merge one controlled reader-relevant
source/documentation change through normal review. Record the real push run, resulting README PR,
full gate, seven CI jobs and ordinary merge. Confirm that its README-only merge causes no further
PR. Fixture tests are not this live verification.

Rollback is a normal PR removing `.github/workflows/readme-maintenance.yml`, reverting the small CI
manual-trigger/freshness additions, and removing the bounded guide/helper if desired. Credentials
and repository settings are separate owner-managed resources; this implementation creates none.
