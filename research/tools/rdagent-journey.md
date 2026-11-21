---
owner: research pipeline
sources:
  - apps/alpha-cli/src/alpha_cli/rdagent_journey*.py
  - apps/alpha-cli/src/alpha_cli/figures/rdagent_journey_figures.py
verified: 2d16c5abab942e68
---

# Follow one RD-Agent idea

**Reach for it when** you want to see why an idea stopped and which observations the judge used.

```text
uv run alpha ledger journey --run-dir <run-dir>
uv run alpha ledger journey --run-dir <run-dir> --factor <name> --out <directory> --theme dark
```

Every journey figure is the same white chart; `--theme dark` is accepted and changes nothing.

The command prints the path to the index. Each entry identifies an iteration, a factor name
and its full code hash. Selecting a name builds every matching iteration. The index lists
all judged ideas. Open the selected folder's `journey.json` for the seven steps and source files.

Read the quick test on the holding period the proposer declared. The cumulative line rises
when rankings favour the proposed direction. Compare years in the lower panel. The spread
compares the top and bottom thirds before costs. The trading picture shows the selected
third before and after costs against the full basket; a costed bottom third is not stored.

Each available PNG has a JSON file containing its plotted numbers. A missing picture has a reason in the journey.
The future-data check names how many dates ALPHA checked. Step six names the quick tests with recorded verdicts,
explains from stored screen figures why coins could not be ranked, and shows the agent's feedback in its own words.
Step seven shows ideas tested so far, coins with a usable number, prior exposure and shortlist
facts, and any fixed check run after the verdict. The journey is an exploratory reading of stored evidence.

In the Workstation, open Research → RD-Agent, select the run, then an idea. The screen reads
the run's own `journey/` folder; a missing journey shows the local build command. The CLI builds
journeys for judged factors only; a loop event can have a name with no linked evaluation.
Step one names the proposer and identifies a stand-in's answer. It leads with the complete valid
plain sentence or the description's lead, then the idea type, direction and any later choice of sign.
The full description stays in the idea's own words. Code can be an excerpt; long lines wrap. The run summary and the
final step's exploratory label show only recorded values; the picker reads verdicts from the run.
During a run, `alpha ledger proposal` shows the last results; to answer, see [propose and discuss](../../workers/rdagent/propose-and-discuss.md).
