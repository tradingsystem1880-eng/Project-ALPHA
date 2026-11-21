---
owner: research pipeline
sources:
  - apps/alpha-cli/src/alpha_cli/idea_cmds.py
  - apps/alpha-cli/src/alpha_cli/spine/idea_card.py
  - apps/alpha-cli/src/alpha_cli/spine/idea_file.py
  - apps/alpha-cli/src/alpha_cli/spine/idea_rdagent.py
  - apps/alpha-cli/src/alpha_cli/spine/idea_notes.py
verified: 3f0a08439aa088f3
---
# Idea card

**Reach for it when** the owner states an idea and no test has run yet. Write the card first.

**Command**
```text
uv run alpha idea new --claim "<owner's words>" --disproved-by "<what would kill it>" --json
uv run alpha idea new --from research/examples/idea-card.example.toml
uv run alpha idea show <id>
uv run alpha idea list --json
uv run alpha idea file <id>
uv run alpha idea new --from-rdagent <run>/<idea>
uv run alpha idea link <id> --rdagent <run>/<idea> [--unlink]
uv run alpha idea note <id> "<text>" [--decision]
```

A card holds nine short fields: the idea (the owner's sentence), why it could work, who is on the other side,
what would disprove it, the baseline it must beat, and four clocks (signal forms, trade held, how often, edge lasts).

**How to read it**
- Any field may be empty ("not stated"). There is no score and no pass mark.
- The id is a short hash of the card's text. The same words give the same id. A card never changes: a changed
  card is a new card (`--supersedes <old id>`) and the old one stays.
- Link a test: add `idea_card = "<id>"` to a rule-test spec (or `--idea-card <id>` on `alpha test`) or to a
  setup spec. The link is not part of the test identity, so no id, result or trial count changes.
- A run first stored with the link names the card in `manifest.json` (`spine.idea_card` for a rule test,
  `idea_card` for a setup find). A card reads "linked to a test" only after a run stored its result.
  An unknown id stops the test, and the error names it.
- RD-Agent: `alpha idea link --rdagent` links a stored journey (it must exist); `--unlink` adds a later line, none is removed.
  The idea file then shows `rdagent` (the seven steps) and the map line "worked on by RD-Agent". Notes sit in
  `ideas/notes/<id>.jsonl`, append-only, newest first in the file. Both keys are absent when empty.
- `alpha next` counts the cards. `alpha idea file <id> [--json]` is one read-only page: card, map, readings, counts.

A card can start from a published idea: `alpha library card <id>` ([library](library.md)); its `source` is not in the id.

**What it cannot tell you** Whether the idea is good. A card is a note made before the data.

**Next** `uv run alpha test <spec.toml> --json` with the card id in the spec ([rule test](rule-test.md)).
