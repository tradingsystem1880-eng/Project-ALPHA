# Report: link RD-Agent work and notes to an idea

## Built (command line)
- `spine/idea_rdagent.py`: link kind `rdagent_journey` in `ideas/links.jsonl`; `--unlink` adds a later line (no line is edited).
  The journey file must exist and name that idea; else the link is refused.
- `alpha idea link <card> --rdagent <run>/<idea> [--unlink]`; `alpha idea new --from-rdagent <run>/<idea>`.
- `spine/idea_notes.py`: `alpha idea note <card> "<text>" [--decision]`, append-only in `ideas/notes/<card>.jsonl`.
- Idea file: `rdagent[]` (seven steps, numbers, figure ids, "exploratory"), `notes` (newest first), map line "worked on by RD-Agent".
- `alpha next` names `alpha idea link` and `alpha idea note`.
- Docs: `research/tools/idea-card.md`, `apps/alpha-cli/README.md`, `commands.md` regenerated.

## Decisions
- The idea id is `<iteration>-<code sha256>-<name>`, as the web route uses. Run folders are read from `ALPHA_RDAGENT_RUNS_DIR`,
  else `<home>/runs/rdagent`, else `<home>/../runs`.
- RD-Agent link rows are not tests: `tested_ids`, `linked_tests` and `links_of` skip them.
- `rdagent` and `notes` keys, and the map line, appear only when non-empty, so old idea files stay byte-identical.
- Card from an RD-Agent idea: claim = the agent's own words (metadata lines removed); source "RD-Agent proposal"; all other
  fields "not stated". If the own words are not recorded, it fails loud instead of making an empty card.
- A journey that cannot be read later shows as a fault in `rdagent[].problem`; the map line is then not "done".

## Web side
Not built. `apps/alpha-web/src/alpha_web/api/ideas.py` and `panels/idea/IdeaWorkspace.tsx` do not exist on main.

## Fail-first
`tests/unit/test_idea_rdagent.py` first failed (`idea link` did not exist, exit code 2), then passed after the build.

## Unverified
- `gate.py check`: living documents FAIL only because documents are stale (listed, not blocked, per the rules; `fs.py verify` not run).
  Ruff, format, imports, mypy and mapped tests pass.
- Layout of real run folders on the owner's machine is not seen; only the synthetic fixture was used.
