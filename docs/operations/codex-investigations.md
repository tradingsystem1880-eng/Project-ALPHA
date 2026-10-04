# Codex recorded-run investigations

This is the first CLI increment of the [Codex-first plan](../superpowers/plans/2026-10-03-codex-research-runtime.md).
Codex reasons and chooses tools. ALPHA verifies the fixed run, enforces budgets and validates
receipt references. The output is retrospective advice, not admitted research or proof of edge.

## Run and resume

Use the isolated research checkout with `uv sync --locked` and an existing local Codex login.
The runtime currently requires a local `auth.json`; keychain-only authentication is not supported.
It references that file through a symlink in a dedicated Codex home; it never copies credentials.
Keep the entire case directory private and outside Git, including Codex conversation history.

```bash
uv run alpha research diagnostic investigate /absolute/private/cases/example \
  --run-id RUN_ID --as-of YYYY-MM-DD \
  --question 'Investigate this drawdown and identify the most useful next test.'

uv run alpha research diagnostic investigate /absolute/private/cases/example --resume
```

`RUN_ID` is an existing 16-hex v3 backtest/validation run in `ALPHA_DATA_DIR/runs` with the exact
recorded `research_cutoff`. Ordinary runs without that contract fail; the tool never rewrites a
historical manifest to make it eligible. Existing `diagnostic run-plan` can produce bounded runs.
Model defaults to `gpt-6-astra`; new cases can select another available Codex model explicitly.
Resume uses the frozen model/question/run/cutoff. Changing the question or scope requires a new
case and does not make previously exposed evidence untouched.

The completed checkpoint is reverified and returned without another model call. Explicit resume
after a known failure uses the same Codex thread and spent budgets. A crash leaving an ambiguous
reservation blocks replay. Do not delete reservations to replenish a budget. Transport events
support streaming, active-turn steering and interruption through `InvestigationTurn`; workstation
controls are not wired in this increment. CLI interruption closes the process group.

## Capabilities and limits

Only three parameterless tools are exposed:

| Tool | Result |
|---|---|
| `inspect_execution` | Verified execution counts, constraints, costs and coverage status |
| `inspect_losses` | Measured drawdown episodes and optional frozen snapshot comparisons |
| `suggest_followups` | Grounded starting questions, not executed follow-up experiments |

Execution inspection must succeed first. Source and policy hashes are reverified on every result,
including cached results. Each case permits at most six distinct action attempts, twelve total
requests including repeated/denied requests, and four model turns including failures. Each turn
has a five-minute collection deadline, six observed MCP calls and a bounded event count. Limits
persist across processes; concurrent sessions cannot reserve the same last slot. These are call
and time limits, not a claim of a hard token/dollar ceiling.

Case SQLite and conversation JSON are advisory sidecars. ControlStore remains authoritative for
governed research. An evidence receipt binds source bytes and an observation; it does not establish
that a model's causal explanation or recommendation is true. Final reports label that distinction
and reject nonexistent/unsuccessful citations. Rejected model completions are retained locally.

## Runtime boundary

The installed Codex 0.159.0 App Server protocol supplies stdio JSONL threads, resume, streaming,
steer and interrupt. Each process uses a dedicated configuration and an empty model workspace.
Shell, web, browser, apps, plugins, image generation, memory and subagent capabilities are disabled.
The code-mode host remains enabled because this CLI version requires it for native MCP discovery.
The only MCP server is the fixed-case facade, which subprocesses supported CLI commands.
Its three exact tools are preauthorized by configuration; generic approval requests are rejected.
No ordinary workspace MCP, arbitrary paths, provider credentials, owner actions or execution
commands are exposed to the model. There is no new public REST or trading surface.

Before a model turn, the actual App Server execution path must pass canaries for allowed input
read, denied owner-home/common-temp/sibling reads, denied symlink escape, denied writes and denied
network access. Start/resume must report the named `investigation` profile, read-only sandbox,
network disabled, exact model and no approval prompts. MCP inventory must match the three tools.
This certifies the tested local configuration; it is not a general proof against every Codex or OS
vulnerability. The trusted host and MCP service necessarily access the selected source run.

Protocol source: [official App Server documentation](https://learn.chatgpt.com/docs/app-server),
[MCP configuration](https://learn.chatgpt.com/docs/config-file/config-reference), and JSON schemas
generated from the installed CLI. No additional inference framework or model weights were added.

## Next acceptance work

This increment cannot establish macro causes, fit causal regimes,
implement strategy operators or activate learned skills. Those remain explicit subsequent slices.
Frozen-snapshot endpoint comparisons and bounded acquisition are available below. The next useful
increment is workstation integration after reconciling UI changes and live-provider acceptance.
Native Codex chart input,
isolated strategy engineering and evaluated procedure learning remain in the accepted roadmap.
Large finance models stay research candidates for later GPU trials; local Qwen vision is not part
of the near-term design. Historical Claude benchmark artifacts remain unchanged.

## Frozen snapshot comparisons

New investigations can include `--comparisons /absolute/path/comparisons.json`. The plan selects
one to four daily series from existing `ALPHA_DATA_DIR/snapshots` snapshots, with exact manifest
SHA-256 values reported by `alpha data snapshots --json`. Example structure (replace the hash):

```json
{
  "schema_version": 1,
  "series": [{
    "snapshot_id": "comparison_snapshot",
    "snapshot_sha256": "<64-character verified manifest SHA-256>",
    "symbol": "SPY",
    "role": "market"
  }]
}
```

Roles are `asset`, `market`, `sector` or `other`; they are operator-selected hypotheses and do not
establish benchmark suitability. Codex sees the available series and can inspect them through
the same `inspect_losses` tool. No additional model, MCP tool, network permission or dependency
is added. The case freezes plan contents, data root and comparison evidence in schema v3. Editing
the plan file cannot change the case; changing inputs requires a new case. Existing schema-v2
investigations retain their original identity, three tools, receipts, checkpoints and budgets.

For each existing top-three strategy drawdown window, the tool reports the comparison's exact
peak/trough session-label prices, endpoint fractional price change, and observed row count.
It uses the existing PIT reader and splits known/applied by the run cutoff. There is no nearest-date
substitution or forward filling. Prices exclude dividends, FX conversion, costs and leverage;
closes in different markets need not be simultaneous. Interior schedule completeness, historical
data vintage, data-quality certification and causality remain explicitly unverified/not established.
Do not interpret a strategy/comparison difference as alpha or a reason to accept/reject a strategy.

Missing snapshot members, v2 instrument/fetch provenance, or exact endpoint observations produce
explicit blockers and data requirements. Snapshot tampering, unsafe paths or malformed data fail
loudly. A fetch receipt is declared provenance, not proof that a historical data vintage is correct.
The runtime does not download missing data or silently substitute another source. Crypto bulk-store
JSON manifests are not supported by this ordinary snapshot reader.

Plan JSON is capped at 64 KiB. Before hashing, snapshots are capped at 1 MiB of manifest text,
128 members and 128 MiB total declared payloads; individual bar files are capped at 32 MiB and
action/provenance files at 1 MiB. The selected daily OHLCV table is capped at 50,000 rows before
materialization. Every read, including cached receipt reuse, rechecks source integrity and the
frozen comparison. These limits do not certify broader vendor or machine isolation.

The [comparison delivery plan](../superpowers/plans/2026-10-03-codex-comparison-evidence.md)
records scope and acceptance evidence. A live Codex test used a labeled synthetic fixture, with
40% strategy drawdown and 20% comparison decline. It retained the relevant limitations, proposed
reconciliation, and resumed identical findings without another model turn. This is operational
acceptance only; no real-market comparative result or general judgment benchmark follows.


## Bounded comparison acquisition

After execution and loss inspection, the trusted CLI can draft and execute one private batch:

```bash
uv run alpha research diagnostic acquisition-plan /absolute/private/cases/example \
  --symbol SPY --asset-class etf --role market > /absolute/private/comparison-request.json
uv run alpha research diagnostic acquire-comparisons /absolute/private/cases/example \
  /absolute/private/comparison-request.json
```

The strict request identifies up to four distinct Tiingo stock/ETF symbols, explicit roles, and
USD/US/XNYS metadata. Metadata and proxy suitability are operator declarations, not independently
verified instrument facts. All command-line symbols share the selected role/class; use the typed
JSON request for mixed roles/classes. Dates cover the parent's drawdown endpoints within its
recorded sessions and cutoff, with a maximum 3,660-day span. A Tiingo credential is required in
`ALPHA_TIINGO_API_KEY`; absent credentials fail before reserving the batch.

The entire batch is reserved before network access under the parent's `comparison-acquisition`
directory. Requests run sequentially in bounded child processes with only the required credential,
private home/temp directories, no redirects, an 8 MiB response cap and a 90-second worker deadline.
Known failures and ambiguous incomplete reservations never retry. Completed repeated commands
reverify retained evidence without networking. This is one batch per parent, not a global budget
across newly created cases; creating another case does not restore untouched research evidence.

The existing ingestion pipeline runs in private storage. It retains emitted raw receipts,
quality reports and quarantine artifacts; transport/parser failures can precede raw receipt
creation. Checks cover the existing OHLCV/action/duplicate rules and declared-calendar required
session coverage. Fresh-store comparison rows are zero: independent source agreement, complete
calendar validity, historical vintage and general quality certification are not established.
Cached success replays raw parsing and checks against a fresh store and compares the artifacts.

Only an all-pass batch publishes `comparisons.json` and a private snapshot. A failed batch emits
its receipt with a nonzero CLI exit status; it never silently publishes a successful subset.
Use the emitted comparison plan and `data_root` in a new investigation:

```bash
uv run alpha research diagnostic investigate /absolute/private/cases/with-comparisons \
  --run-id RUN_ID --as-of YYYY-MM-DD --question 'Compare these drawdown windows.' \
  --comparisons /absolute/private/cases/example/comparison-acquisition/comparisons.json \
  --comparison-data-root /absolute/private/cases/example/comparison-acquisition/data
```

The original run still resolves under `ALPHA_DATA_DIR`. Comparison inputs freeze into the new
case; root overrides are rejected on resume and without a comparison plan. The model's three
read-only tools remain unchanged. Acquiring data confers no admission or trading authority.

Live Tiingo acceptance remains **UNVERIFIED** because no credential is configured in this
environment. Fixture acceptance exercises parsing, quality checks, private publication and the
comparison handoff; it does not establish real-market coverage or provider availability.
