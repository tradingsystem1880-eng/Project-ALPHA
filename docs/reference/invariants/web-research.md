---
owner: web research surfaces
sources:
  - apps/alpha-web/src/alpha_web/_assistant.py
  - apps/alpha-web/src/alpha_web/_investigations.py
  - apps/alpha-web/src/alpha_web/_rules.py
  - apps/alpha-web/src/alpha_web/_scans.py
  - apps/alpha-web/src/alpha_web/_research.py
  - apps/alpha-web/src/alpha_web/_development.py
  - apps/alpha-web/src/alpha_web/api/assistant.py
  - apps/alpha-web/src/alpha_web/api/investigations.py
  - apps/alpha-web/src/alpha_web/api/rules.py
  - apps/alpha-web/src/alpha_web/api/rule_evaluation_models.py
  - apps/alpha-web/src/alpha_web/api/scans.py
  - apps/alpha-web/frontend/src/panels/AssistantDock.tsx
  - apps/alpha-web/frontend/src/panels/ConditionChecklist.tsx
  - apps/alpha-web/frontend/src/panels/RunInvestigation.tsx
  - apps/alpha-web/frontend/src/panels/StrategyBuilder.tsx
  - apps/alpha-web/frontend/src/panels/Scanner.tsx
  - apps/alpha-web/frontend/src/panels/Alerts.tsx
  - apps/alpha-web/frontend/src/panels/ResearchCockpit.tsx
  - apps/alpha-web/frontend/src/panels/ResearchBacklog.tsx
  - apps/alpha-web/frontend/src/panels/V3Workbenches.tsx
  - apps/alpha-web/frontend/src/panels/actions.ts
verified: d0fffa796f8e
---

# Web research surfaces

Rules for the Workstation surfaces closest to research decisions: the advisory assistant, Codex investigations, rule
conditions, the Strategy Builder, scans and alerts, the Research Case read plane and the project workspace. General
backend rules are in [web-api.md](web-api.md), browser rules in [web-frontend.md](web-frontend.md), and the CLI side of
the advisory surfaces in [cli-assistant.md](cli-assistant.md).

## No authority on these surfaces

- None of these surfaces approves, admits evidence, launches D1 or D2, promotes, reveals a holdout, or touches paper,
  broker or order control. An owner step goes only through the owner confirmation routes
  ([web-api § Owner confirmation routes](web-api.md#owner-confirmation-routes)); see
  [research-integrity § Owner authority](research-integrity.md#owner-authority).
- Assistant answers, structured rule drafts and investigation reports stay advisory: no model tools, no generated-code
  execution, no automatic owner action.
- The browser sends identifiers only (symbol, as-of date, run, snapshot, manifest, project, rule name and hash), never
  bars, market evidence or file paths. The CLI resolves and hashes the context.
- Rule, scan and condition responses carry `authority: none`. A scan is a screen and a condition row is a check; neither
  is evidence.

## Advisory assistant

- `api/assistant.py` relays only `alpha assistant readiness|create|show|turn|check` (`_assistant.py`). A turn runs as a
  background CLI job. Create, turn and check require the owner origin (`owner_auth._require_owner_origin`).
- One turn at a time: starting a turn while another runs returns 409.
- A session for a saved rule pins `rules_name` and `rules_sha256` when it is created; archive, run and snapshot sessions
  send no rule. Opening a scan result keeps the evaluated rule hash, so the session pins the rule that was scanned.
- Before a draft is used, the dock calls `check` (the CLI re-verifies the context hash) and then `POST /api/rules/validate`.
  A stale context or an invalid draft is refused and never applied.
- The CLI journal outlives the in-memory job handle. While a saved turn is `running` the dock keeps polling the session,
  and a failed or cancelled job's terminal error is shown even if no turn was recorded. Never invent a terminal state.

## Codex investigations

- `api/investigations.py` relays only `alpha research investigations list|eligibility|create|show|run|draft|acquire`
  (`_investigations.py`) and imports no engine. Investigation ids are opaque 32-hex strings and run ids 16 hex, checked
  by the path pattern.
- Every mutating POST requires the local same-origin workstation (`same_origin`: loopback host, exactly matching Origin,
  `Sec-Fetch-Site` absent or `same-origin`), else 403.
- One investigation operation runs at a time (409). A price comparison is drafted first (`comparison-plan`, a preview)
  and only then acquired as a separate job; never acquire without the explicit preview.
- Evidence is immutable and budgets are durable, both owned by the CLI; the web adds only `active_job_id`.
  Investigations do not reopen research admission, D2, paper, broker or order authority.

## Rule conditions and the Strategy Builder

- `POST /api/rules/validate` is a report: an invalid spec returns `valid: false` with the CLI's defect text, never a 4xx.
  The SPA judges no rule.
- `POST /api/rules/evaluate` relays `alpha rules explain` for a canonical stored instrument only. The request model has
  no archive, run or snapshot field, and the checklist shows those contexts as unavailable instead of falling back.
- Condition rows come from the strategy's own comparators. A side that short-circuits after a failed condition reports
  the rest as not evaluated, and a missing operand is `unavailable` with a reason — never a guessed pass or fail.
- `Test in sandbox` launches `backtest run --strategy rules --rules <id>` in the standalone sandbox; `Open in Strategy
  Lab` only prefills a governed run.

## Scans and alerts

- Scans run through `alpha scan run` (point-in-time bars, optional as-of) and `alpha scan check`, which appends only
  changed signals to `scans/alerts.jsonl`. See [cli-runs § Rules, scans and chart overlays](cli-runs.md#rules-scans-and-chart-overlays).
- The Alerts tab re-reads the log when the activity `alerts` area changes, and checks every saved scan once on mount and
  after each `bars` change (a finished pull). The SPA evaluates no rule and derives no signal.
- Opening a scan result clears archive, run and snapshot identity and keeps the evaluated date and rule hash
  (`actions.openScannedMarket`).

## Research Case read plane

- The Study tab renders only the server-masked semantic projection (`GET /api/research/cases/{id}/semantic-projection`,
  `alpha research semantic-projection`). Masked future points stay masked: the SPA never fetches, reconstructs or
  estimates them, and a projection the server marks unavailable or stale is shown as such.
- `ResearchStudyStatusV1` and the projection carry `authority: none`. Owner steps the case waits on are offered only as
  owner confirmation buttons; masked and blocked text from the server is shown verbatim.
- The Workstation records research captures and proposals as created by `workstation` (`--created-by workstation`); the
  command's own default actor stays `codex`.
- New Idea capture asks for no trading-rule inputs. Scorecard and checklist semantics come from Python projections.

## Project workspace

- The Development Center reads `StrategyProjectWorkspaceV1` through `alpha project workspace show` and may invoke only
  the bounded generated-reference refresh, `alpha project workspace sync` (`POST /api/projects/{id}/workspace/refresh`).
- The web never opens SQLite, repairs generated bytes or copies artifacts for it, and the workspace grants no
  research-gate, promotion, sandbox, paper, broker or order authority. The panel offers no execution action.
