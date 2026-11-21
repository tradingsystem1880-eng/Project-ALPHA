"""The Ideas page's two reads: what `alpha idea list` and `alpha idea file` print.

The server relays them (see ``api/ideas.py``). A field the page does not name is dropped, never an
error. Lists are capped by the route; the caps are named there. Readings only: no grade, no advice.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class _Relayed(BaseModel):
    model_config = ConfigDict(extra="ignore")


class IdeaListRow(_Relayed):
    id: str
    claim: str = ""
    tested: bool = False
    not_stated: list[str] = []
    tests_linked: int = 0
    saved_at: str | None = None


class IdeaList(_Relayed):
    cards: list[IdeaListRow]
    total: int
    truncated: bool = False


class IdeaCardFacts(_Relayed):
    id: str
    claim: str | None = None
    mechanism: str | None = None
    other_side: str | None = None
    disproved_by: str | None = None
    baseline: str | None = None
    signal_forms: str | None = None
    held_for: str | None = None
    how_often: str | None = None
    edge_lasts: str | None = None
    source: str | None = None
    supersedes: str | None = None
    superseded_by: str | None = None


class IdeaMapStep(_Relayed):
    step: str
    state: str
    evidence: list[str] = []
    note: str = ""


class IdeaFollow(_Relayed):
    follow_id: str
    kind: str
    source_id: str
    assets: list[str] = []
    version: int
    started_at: str
    state: str
    sessions: int = 0
    stop_reason: str = ""
    paper_account_percent: float | None = None


class IdeaMeasure(_Relayed):
    name: str
    value: float | None = None
    interval_95: list[float] | None = None
    basis: str | None = None
    not_to_be_read: bool = False


class IdeaAimRow(_Relayed):
    measure: str | None = None
    observed: float | None = None
    aim: float | None = None
    interval_95: list[float] | None = None
    relation: str | None = None


class IdeaEvidence(_Relayed):
    word: str | None = None
    because: list[str] = []


class IdeaReadingCheck(_Relayed):
    name: str
    state: str
    detail: str = ""


class IdeaReadingCounts(_Relayed):
    trial_n: int | None = None
    family_trials: int | None = None
    variants_tried: int | None = None
    best_of: int | None = None
    family_id: str | None = None


class IdeaReadingAim(_Relayed):
    rows: list[IdeaAimRow] = []
    basis: str | None = None
    source: str | None = None


class IdeaReading(_Relayed):
    sentence: str | None = None
    evidence: IdeaEvidence = IdeaEvidence()
    measures: list[IdeaMeasure] = []
    checks: list[IdeaReadingCheck] = []
    counts: IdeaReadingCounts = IdeaReadingCounts()
    aim: IdeaReadingAim = IdeaReadingAim()


class IdeaToolCheck(_Relayed):
    tool: str
    word: str
    reading: str = ""
    recorded_at: str | None = None
    file: str = ""
    labels: list[str] = []


class IdeaTested(_Relayed):
    """What a linked test looked at. A rule test fills asset..held_back; a find, idea..assets."""

    asset: str | None = None
    rule: str | None = None
    data_from: str | None = None
    data_to: str | None = None
    scored_from: str | None = None
    scored_to: str | None = None
    held_back: str | None = None
    idea: str | None = None
    assets: list[str] = []
    context_bars: int | None = None


class IdeaStudy(_Relayed):
    id: str
    reading: str | None = None
    labels: list[str] = []
    occurrences: int | None = None
    problem: str | None = None


class IdeaFindTotals(_Relayed):
    accepted: int | None = None
    pending: int | None = None
    set_aside: int | None = None


class IdeaTest(_Relayed):
    """One linked test: a rule test or a setup find, in the order the file lists them."""

    kind: str
    id: str
    recorded_at: str | None = None
    tested: IdeaTested = IdeaTested()
    reading: IdeaReading | None = None
    word: str | None = None
    sentence: str | None = None
    aim: IdeaAimRow | None = None
    checks: list[IdeaToolCheck] = []
    figures_available: list[str] = []
    labels: list[str] = []
    studies: list[IdeaStudy] = []
    totals: IdeaFindTotals = IdeaFindTotals()
    problem: str | None = None


class IdeaTrial(_Relayed):
    run: str
    trial_n: int | None = None
    family_trials: int | None = None
    variants_tried: int | None = None


class IdeaChecksRun(_Relayed):
    total: int = 0
    declared: int = 0
    exploratory: int = 0


class IdeaCounts(_Relayed):
    tests_linked: int = 0
    rule_tests: int = 0
    setup_finds: int = 0
    distinct_assets: int = 0
    checks_run: IdeaChecksRun = IdeaChecksRun()
    variants_of_this_idea: int = 0
    trials: list[IdeaTrial] = []
    ledger_rows_naming_these_runs: int = 0


class IdeaNextStep(_Relayed):
    step: str
    command: str


class IdeaOpenPoints(_Relayed):
    not_stated: list[str] = []
    map_not_yet: list[str] = []
    too_little_to_read: list[str] = []
    next_steps: list[IdeaNextStep] = []


class IdeaFile(_Relayed):
    card: IdeaCardFacts
    map: list[IdeaMapStep]
    follows: list[IdeaFollow] = []
    readings: list[IdeaTest]
    counts: IdeaCounts
    open_points: IdeaOpenPoints
    readings_total: int = 0
    readings_shown_from: int = 0
