# Archive

Historical files kept for the record. Nothing here is current guidance, an active plan, a test
input or research evidence. Moved files keep their original bytes except where noted.

## Moved on 2026-11-13 (clean-base Phase 1)

| Archive path | Original path | Notes |
| --- | --- | --- |
| `2026-prompts/final-codex-plan-mode-refactor-prompt.md` | `PROJECT ALPHA — Final Codex Plan Mode Refactor & Research Infrastructure Prompt.md` (repository root) | One-off Codex planning prompt; nothing referenced it. |
| `research-one-offs/mizerxbt-eth/mizerxbt_eth_dossier.md` | `research/analysis/mizerxbt_eth_dossier.md` | July 2026 one-off trade review. |
| `research-one-offs/mizerxbt-eth/mizerxbt_eth_trade_quant.py`, `.png` | `research/analysis/` | Script and its chart. Only the `Run:` path in the docstring changed. The script writes its PNG next to itself. |
| `research-one-offs/mizerxbt-eth/mizerxbt_eth_short_1h.py`, `.png` | `research/charts/` | Script and its chart. Only the `Run:` path in the docstring changed. |
| `data-hygiene-2026-10-02/2026-10-02-report.json` | `output/data-hygiene/` | Output from `scripts/crypto_data_hygiene.py`. |
| `data-hygiene-2026-10-02/2026-10-02-public-api-probes.json` | `output/data-hygiene/` | Output from the same run. |
| `data-hygiene-2026-10-02/2026-10-02-final-selected-verification.json` | `output/data-hygiene/` | Output from the same run. |
| `data-hygiene-2026-10-02/2026-10-02-retirement-applied-audit.json` | `output/data-hygiene/` | The retirement-audit receipt that `docs/BUILD-STATUS.md` (2026-10-02) cites by sha256 `aa8cae59a5e73daecda4ba28ef50460eed5a8d4f46b9d8fa9ccebaa6c45972fb`. |

`output/data-hygiene/2026-10-02-retirement-audit.json` and
`output/data-hygiene/2026-10-02-retirement-final-audit.json` were byte-identical to
`2026-10-02-retirement-applied-audit.json` (same sha256 above), so only that one copy was kept.
It stands for all three names. Git history still has the originals.

## Moved on 2026-11-13 (CI is the merge gate)

| Archive path | Original path | Notes |
| --- | --- | --- |
| `readme-maintenance.md` | `docs/operations/readme-maintenance.md` | README review evidence (`gate.py attest --kind readme`) was removed by [ADR-0039](../adr/0039-ci-is-the-merge-gate.md); README is now reviewed in the pull request. Bytes unchanged. |

## Moved on 2026-11-14 (file-system switch-over, ADR-0040)

History only: none of these is a live source. Current rules live in `docs/reference/invariants/`,
routing in the root `CONTEXT.md` and each workspace `CONTEXT.md`.

| Archive path | Original path | Notes |
| --- | --- | --- |
| `2026-11-claude-rules/*.md` (16 files) | `.claude/rules/*.md` | Copies of the rule files before they became pointers to the workspace `CONTEXT.md`. Bytes unchanged except six relative links, rewritten to resolve from here. |
| `2026-11-context-maps/README.md` | `docs/context/README.md` | Context index; replaced by the root `CONTEXT.md`. Relative links rewritten to resolve from here. |
| `2026-11-context-maps/software-team.md` | `docs/context/software-team.md` | Engineering map; its facts are in `engineering.md`, `testing.md` and `scripts/CONTEXT.md`. Links rewritten. |
| `2026-11-context-maps/alpha-quant-platform.md` | `docs/context/alpha-quant-platform.md` | Platform map and the dated 2026-11-06 native-upstream crosswalk; its rules are in the invariants files. Links rewritten. |

## Moved on 2026-11-14 (delivery pipeline, M3)

History only, not a live source: how a change is made now lives in
[`workflow/CONTEXT.md`](../../workflow/CONTEXT.md) and its five stage files.

| Archive path | Original path | Notes |
| --- | --- | --- |
| `2026-11-claude-agents-commands-skills/claude/` | `.claude/agents/`, `.claude/commands/`, `.claude/skills/` | All nine agent prompts, ten commands and nine skill stubs as of commit `8fd5e6dc`, before the pipeline replaced them. The leading dot is dropped from the folder names. Bytes unchanged except two relative links, rewritten to resolve from here. |
| `2026-11-claude-agents-commands-skills/agents/` | `.agents/skills/*`, `.agents/references/` | The seven deleted skills, `UPSTREAM.md` and `definition-of-done.md`, same commit. Bytes unchanged except one relative link. |

## Moved on 2026-11-14 (research pipeline, M3)

History only, not a live source: these are the June 2026 pre-build research reports and the vendor
blueprint they answered. Their recommendations are dated; current decisions are the ADRs and
[`docs/ARCHITECTURE.md`](../ARCHITECTURE.md), and running a research case now lives in
[`research/CONTEXT.md`](../../research/CONTEXT.md) and its six stage files.

| Archive path | Original path | Notes |
| --- | --- | --- |
| `2026-06-research-notes/00-SYNTHESIS.md` | `research/00-SYNTHESIS.md` | June synthesis of reports 01–07. Bytes unchanged except two relative links, rewritten to resolve from here. |
| `2026-06-research-notes/01-*.md` … `07-*.md` (7 files) | `research/01-*.md` … `research/07-*.md` | Research briefs on data, storage, engine, validation, paper feeds, strategy encoding and architecture. Bytes unchanged. |
| `2026-06-research-notes/2026-06-vendor-blueprint-building-elite-ai-trading-software.md` | `research/` (same name) | The vendor blueprint the reports answered. Bytes unchanged. |

Links to these files from `ARCHITECTURE.md`, `records/specs/2026-06-14-project-alpha-v1-design.md` and the
archived context maps were rewritten (path only).
