// Evidence Hub — one workflow surface with eleven sections (spec §6.2) that fill as the
// research case progresses, each rendering honest NOT_TESTED / empty states before then.
// Evidence for and evidence against share one component so their prominence is identical.

import type { IDockviewPanelProps } from 'dockview-react'
import { useEffect, useState } from 'react'

import { api } from '../api/client'
import type { ResearchEvidenceHub, ResearchEvidenceHubSections } from '../api/types'
import { Placeholder } from '../components/Placeholder'
import { usePanelLinked } from '../context/usePanelLinked'
import { stateChipClass } from './researchChipModel'
import { headlineBoard } from './researchHeadlineModel'
import { HypothesisCardView, ScorecardDetail, ScorecardStrip } from './researchViews'

type SectionId = keyof ResearchEvidenceHubSections

const SECTION_ORDER: ReadonlyArray<{ id: SectionId; label: string }> = [
  { id: 'overview', label: 'Overview' },
  { id: 'data', label: 'Data' },
  { id: 'literature', label: 'Literature' },
  { id: 'mechanism', label: 'Mechanism' },
  { id: 'exploration', label: 'Exploration' },
  { id: 'experiments', label: 'Experiments' },
  { id: 'evidence_for', label: 'Evidence for' },
  { id: 'evidence_against', label: 'Evidence against' },
  { id: 'falsification', label: 'Falsification' },
  { id: 'robustness', label: 'Robustness' },
  { id: 'decision', label: 'Decision' },
]

function FindingsSection({
  title,
  findings,
}: {
  title: string
  findings: ResearchEvidenceHubSections['evidence_for']['findings']
}) {
  if (findings.length === 0) {
    return (
      <Placeholder big="NOT_TESTED">
        No typed findings of this direction exist yet. Missing evidence stays visible — it
        never disappears.
      </Placeholder>
    )
  }
  return (
    <div className="research-findings" aria-label={title}>
      {findings.map((finding) => (
        <div key={finding.finding_id}>
          <span className="eyebrow">{finding.finding_id.replaceAll('_', ' ')}</span>
          <span className={stateChipClass(finding.status.toLowerCase())}>{finding.status}</span>
          <p>{finding.summary ?? 'No summary was recorded for this typed finding.'}</p>
        </div>
      ))}
    </div>
  )
}

function SectionBody({
  section,
  sections,
}: {
  section: SectionId
  sections: ResearchEvidenceHubSections
}) {
  switch (section) {
    case 'overview': {
      const overview = sections.overview
      return (
        <>
          <div className="development-spec">
            <div><span className="eyebrow">Original idea</span><p>{overview.original_idea || 'Not recorded.'}</p></div>
            <div><span className="eyebrow">Phase</span><span className="mono">{overview.phase.replaceAll('_', ' ').toUpperCase()}</span></div>
            <div><span className="eyebrow">Execution</span><span className="mono">{overview.execution_state.toUpperCase()}</span></div>
            <div><span className="eyebrow">Responsibility</span><span className="mono">{overview.responsibility.toUpperCase()}</span></div>
            <div><span className="eyebrow">Next action</span><span>{overview.next_action}</span></div>
            <div><span className="eyebrow">Latest finding</span><span>{overview.latest_finding ?? 'None recorded.'}</span></div>
          </div>
          <ScorecardStrip scorecard={overview.scorecard} />
          {overview.outstanding_questions.length ? (
            <div className="research-question-list">
              <span className="eyebrow">Outstanding questions</span>
              <ol>{overview.outstanding_questions.map((item) => <li key={item}>{item}</li>)}</ol>
            </div>
          ) : null}
          <HypothesisCardView card={overview.hypothesis_card} />
        </>
      )
    }
    case 'data':
      return (
        <Placeholder big={sections.data.status}>
          {sections.data.note} Registered datasets: {sections.data.registered_datasets.length}.
        </Placeholder>
      )
    case 'literature': {
      const literature = sections.literature
      const claims = literature.claims as Array<Record<string, unknown>>
      return (
        <>
          {claims.length === 0 ? (
            <Placeholder big="NO CLAIMS RECORDED">
              Claim-level literature evidence is drafted by Codex and elevated only by owner
              screening; screened sources are listed below in the meantime.
            </Placeholder>
          ) : (
            <div className="research-findings" aria-label="Claims map">
              {claims.map((claim) => {
                const claimId = String(claim['claim_id'] ?? '')
                const status = String(claim['status'] ?? 'draft')
                return (
                  <div key={claimId}>
                    <span className="eyebrow">
                      {String(claim['direction'] ?? '')} · {String(claim['strength'] ?? '')} ·{' '}
                      {String(claim['author_kind'] ?? '')}
                    </span>
                    <span className={status === 'screened' ? 'chip pass' : 'chip'}>
                      {status === 'screened' ? 'SCREENED' : 'DRAFT — UNSCREENED'}
                    </span>
                    <p>{String(claim['claim_text'] ?? '')}</p>
                    <p className="muted">{String(claim['limitations'] ?? '')}</p>
                  </div>
                )
              })}
            </div>
          )}
          {literature.sources.length ? (
            <div className="research-findings">
              {literature.sources.map((source) => (
                <div key={source.source_id}>
                  <span className="eyebrow">{source.provider} · {source.access_mode}</span>
                  <span className={source.screening === 'include' ? 'chip pass' : 'chip'}>
                    {source.screening ?? 'unscreened'}
                  </span>
                  <p>{source.title}</p>
                  <p className="mono muted">{source.locator}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="muted">No recorded sources.</p>
          )}
        </>
      )
    }
    case 'mechanism': {
      const mechanism = sections.mechanism
      return (
        <>
          <div className="development-spec">
            <div><span className="eyebrow">Mechanism</span><p>{mechanism.mechanism ?? 'Not yet materialized.'}</p></div>
            <div><span className="eyebrow">Interpretation</span><p>{mechanism.interpretation ?? 'Not yet materialized.'}</p></div>
          </div>
          {mechanism.alternatives.length ? (
            <div className="research-question-list">
              <span className="eyebrow">Competing explanations</span>
              <ul>{mechanism.alternatives.map((item) => <li key={item}>{item}</li>)}</ul>
            </div>
          ) : null}
          <div className="research-findings">
            {mechanism.confounders.map((confounder) => (
              <div key={confounder.text}>
                <span className="eyebrow">confounder</span>
                <span className={confounder.status === 'resolved' ? 'chip pass' : 'chip'}>
                  {confounder.status.toUpperCase()}
                </span>
                <p>{confounder.text}</p>
              </div>
            ))}
          </div>
        </>
      )
    }
    case 'exploration':
      return (
        <Placeholder big={sections.exploration.status}>
          Exploratory D1 artifacts render here with the {sections.exploration.watermark}{' '}
          watermark once the experiment engine runs. Charts so far:{' '}
          {sections.exploration.charts.length}.
        </Placeholder>
      )
    case 'experiments': {
      const attempts = sections.experiments.attempts
      if (attempts.length === 0) {
        return (
          <Placeholder big="NO ATTEMPTS RECORDED">
            Every attempted, failed, pruned, and completed unit of work will be ledgered here —
            negative results included.
          </Placeholder>
        )
      }
      return (
        <div className="research-findings">
          {attempts.map((attempt) => (
            <div key={attempt.attempt_id}>
              <span className="eyebrow">{attempt.phase} · {attempt.kind}</span>
              <span className={attempt.status === 'completed' ? 'chip pass' : 'chip'}>
                {attempt.status.toUpperCase()}
              </span>
              <p className="mono">{attempt.attempt_id}</p>
              <p className="mono muted">
                {attempt.run_id ?? 'no run'} · {attempt.config_fingerprint.slice(0, 16)}… ·{' '}
                {attempt.recorded_at}
              </p>
            </div>
          ))}
        </div>
      )
    }
    case 'evidence_for':
      return <FindingsSection title="Evidence for" findings={sections.evidence_for.findings} />
    case 'evidence_against':
      return (
        <FindingsSection title="Evidence against" findings={sections.evidence_against.findings} />
      )
    case 'falsification': {
      const falsification = sections.falsification
      return (
        <>
          <div className="research-findings">
            {falsification.falsifiers.map((falsifier) => (
              <div key={falsifier.text}>
                <span className="eyebrow">required falsifier</span>
                <span className={stateChipClass(falsifier.result.toLowerCase())}>
                  {falsifier.result}
                </span>
                <p>{falsifier.text}</p>
              </div>
            ))}
          </div>
          {falsification.stop_rules.length ? (
            <div className="research-question-list">
              <span className="eyebrow">Stop rules</span>
              <ul>{falsification.stop_rules.map((item) => <li key={item}>{item}</li>)}</ul>
            </div>
          ) : null}
        </>
      )
    }
    case 'robustness':
      if (sections.robustness.findings.length === 0) {
        return (
          <Placeholder big={sections.robustness.status}>
            Parameter-neighborhood, temporal, regime, and transportability stability findings
            appear here after deep research runs.
          </Placeholder>
        )
      }
      return <FindingsSection title="Robustness" findings={sections.robustness.findings} />
    case 'decision': {
      const decision = sections.decision
      return (
        <div className="development-spec">
          <div><span className="eyebrow">Outcome</span><span className="mono">{decision.outcome ?? 'NOT DECIDED'}</span></div>
          <div><span className="eyebrow">Disposition</span><span className="mono">{decision.disposition?.replaceAll('_', ' ').toUpperCase() ?? '—'}</span></div>
          <div><span className="eyebrow">D2 confirmation</span><span className="mono">{decision.d2_state.toUpperCase()}</span></div>
          <div><span className="eyebrow">D3 strategy holdout</span><span className="mono">{decision.d3_state.replaceAll('_', ' ').toUpperCase()}</span></div>
          <div><span className="eyebrow">Gate packet</span><span className="mono">{decision.packet_id ?? 'not yet terminal'}</span></div>
          <div><span className="eyebrow">Packet hash</span><span className="mono">{decision.packet_hash ?? '—'}</span></div>
        </div>
      )
    }
  }
}

export function EvidenceHub(props: IDockviewPanelProps) {
  const panelLink = usePanelLinked(props)
  const projectId = panelLink.linked.projectId
  const [hub, setHub] = useState<ResearchEvidenceHub | null>(null)
  const [scorecardOpen, setScorecardOpen] = useState(false)
  const [active, setActive] = useState<SectionId>('overview')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!projectId) {
      setHub(null)
      return
    }
    let live = true
    setError(null)
    api
      .researchEvidenceHub(projectId)
      .then((next) => {
        if (!live) return
        setHub(next)
      })
      .catch((reason: unknown) => {
        if (!live) return
        setHub(null)
        setError(reason instanceof Error ? reason.message : String(reason))
      })
    return () => {
      live = false
    }
  }, [projectId])

  return (
    <div className="panel">
      <div className="panel-toolbar">
        <span className="title">Evidence Hub</span>
        <span className="chip kind">READ-ONLY</span>
        <span className="muted">for & against · equal prominence · nothing disappears</span>
        <span className="spacer" />
        {hub ? (
          <button className="kbd" type="button" onClick={() => setScorecardOpen((open) => !open)}>
            {scorecardOpen ? 'sections' : 'full scorecard'}
          </button>
        ) : null}
      </div>
      <div className="panel-body panel-pad evidence-hub" tabIndex={0}>
        {error ? (
          <div className="workbench-notice" role="alert">
            <strong>EVIDENCE HUB UNAVAILABLE</strong>
            <span>{error}</span>
          </div>
        ) : null}
        {!projectId ? (
          <Placeholder big="NO CASE SELECTED">
            Select a case in the Research Backlog (or set the linked project) to open its
            evidence.
          </Placeholder>
        ) : null}
        {hub && scorecardOpen ? (
          <ScorecardDetail scorecard={hub.sections.overview.scorecard} />
        ) : null}
        {hub && !scorecardOpen ? (
          <>
            <div className="scorecard-strip" aria-label="Headline evidence board">
              {headlineBoard(hub.sections).map((category) => (
                <span
                  key={category.id}
                  className={stateChipClass(category.status.toLowerCase().replaceAll(' ', '_'))}
                  title={category.label}
                >
                  {category.label} · {category.status}
                </span>
              ))}
            </div>
            <div className="evidence-hub-tabs" role="tablist" aria-label="Evidence sections">
              {SECTION_ORDER.map((section) => (
                <button
                  key={section.id}
                  role="tab"
                  type="button"
                  aria-selected={active === section.id}
                  className={`kbd${active === section.id ? ' active' : ''}`}
                  onClick={() => setActive(section.id)}
                >
                  {section.label}
                </button>
              ))}
            </div>
            <div className="evidence-hub-body">
              <SectionBody section={active} sections={hub.sections} />
            </div>
          </>
        ) : null}
      </div>
    </div>
  )
}
