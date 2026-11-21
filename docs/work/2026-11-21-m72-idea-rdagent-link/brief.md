# Brief: link RD-Agent work and notes to an idea

Branch: `feat/m72-idea-rdagent-link`. Rules: `docs/work/_common-rules-2026-11-21.md`. Workspace: `apps/alpha-cli/CONTEXT.md` (idea
rows), `workers/rdagent/CONTEXT.md` (read only: do not edit `workers/**`), `apps/alpha-web/CONTEXT.md`.

## Why

The owner wants one page per idea that shows "the RD-Agent steps": proposal, code, quick test, trading test, feedback. Today an
RD-Agent idea has a stored journey (`apps/alpha-cli/src/alpha_cli/rdagent_journey.py`; the web serves it at
`/api/rdagent/runs/{run}/journeys/{idea}`; the screen is `panels/RdAgentJourney.tsx`), and an idea card has a file
(`alpha idea file <card> --json`, `spine/idea_file.py`, links in `ideas/links.jsonl` written by `spine/idea_card.py`). Nothing links the
two. The owner also wants notes and decisions per idea.

## Build

1. A new link kind `rdagent_journey` in `ideas/links.jsonl`: `alpha idea link <card> --rdagent <run>/<idea>` (and `--unlink`). The link
   is checked: the journey must exist. Links are outside the idea's identity, like the existing links.
2. `alpha idea new --from-rdagent <run>/<idea>`: makes an idea card from an RD-Agent idea, in the agent's own words (claim, mechanism),
   marks the source as "RD-Agent proposal" and links the journey. Missing card fields stay "not stated"; nothing is invented.
3. `alpha idea file --json` returns `rdagent[]`: for each linked journey the seven steps as plain text with their recorded numbers, the
   figure ids, and the words "exploratory" where the journey says so. The idea map gains a step "worked on by RD-Agent".
4. Notes: `alpha idea note <card> "<text>" [--decision]` appends to `ideas/notes/<card>.jsonl` (time, text, kind); the idea file returns
   them newest first. Append-only; no edit, no delete.
5. Web API: if `apps/alpha-web/src/alpha_web/api/ideas.py` exists on main (another build adds `/api/ideas/{card}`), extend its typed
   models with the new fields; if it does not exist yet, add nothing to the web and say so. If the page `panels/idea/IdeaWorkspace.tsx`
   exists on main, fill its section 9 (RD-Agent steps: a readable timeline reusing `RdAgentJourney` parts, with the journey's own figures
   at large size) and its notes section; otherwise leave the frontend alone.
6. The front door: `alpha next` names `alpha idea link` and `alpha idea note` where they fit (one line each).

## Tests

Link, unlink, a link to a missing journey refused; card from an RD-Agent idea on the synthetic journey fixture; the file's new fields;
notes append-only and ordered; old idea files unchanged when nothing is linked (byte-identical JSON for an existing fixture).

## Done

Draft pull request, `ci-ok` green, `report.md` in this folder: what was built on each side, decisions, what is unverified.
