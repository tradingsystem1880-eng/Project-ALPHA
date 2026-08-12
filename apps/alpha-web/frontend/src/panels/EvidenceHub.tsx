// Evidence Hub — one workflow surface with eleven sections (spec §6.2) that fill as the
// research case progresses, each rendering honest NOT_TESTED / empty states before then.
// Evidence for and evidence against share one component so their prominence is identical.

import { useEffect, useState } from 'react'

import { api, type LiteratureAcquisitionResult, type LiteratureDiscoveryResult } from '../api/client'
import type { ResearchEvidenceHub, ResearchEvidenceHubSections } from '../api/types'
import { contentAddressHash, payloadHash, performOwnerAction, researchCaseRevision } from '../auth/ownerAuth'
import { Placeholder } from '../components/Placeholder'
import type { PanelHandleProps } from '../context/panelHandle'
import { usePanelLinked } from '../context/usePanelLinked'
import { stateChipClass } from './researchChipModel'
import { headlineBoard } from './researchHeadlineModel'
import { HypothesisCardView, ScorecardDetail, ScorecardStrip } from './researchViews'
import { FigureReport } from './FigureReport'

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

function LiteratureSection({
  literature,
  projectId,
  onRefresh,
}: {
  literature: ResearchEvidenceHubSections['literature']
  projectId: string
  onRefresh: () => void
}) {
  const claims = literature.claims as Array<Record<string, unknown>>
  const recommendation = literature.recommendation as Record<string, unknown>
  const actions = Array.isArray(recommendation['allowed_next_actions'])
    ? recommendation['allowed_next_actions'] as Array<Record<string, unknown>>
    : []
  const [query, setQuery] = useState('')
  const [email, setEmail] = useState('')
  const [discovery, setDiscovery] = useState<LiteratureDiscoveryResult | null>(null)
  const [acquisition, setAcquisition] = useState<LiteratureAcquisitionResult | null>(null)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [reason, setReason] = useState('I reviewed the cited text and its stated limitations.')
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setDiscovery(null)
    setAcquisition(null)
    setSelected(new Set())
    setError(null)
  }, [projectId])

  async function discover() {
    setBusy('discover')
    setError(null)
    try {
      setDiscovery(await api.researchLiteratureDiscover(projectId, {
        query,
        unpaywall_email: email,
        max_candidates: 20,
        max_full_texts: 5,
      }))
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : String(failure))
    } finally {
      setBusy(null)
    }
  }

  async function acquire(candidateId: string) {
    if (!discovery) return
    setBusy(candidateId)
    setError(null)
    try {
      const result = await api.researchLiteratureAcquire(projectId, {
        discovery_id: discovery.discovery_id,
        candidate_id: candidateId,
      })
      setAcquisition(result)
      onRefresh()
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : String(failure))
    } finally {
      setBusy(null)
    }
  }

  async function ownerAction(action: 'screen_source_claim' | 'reject_source_claim', claimId: string) {
    setBusy(`${action}:${claimId}`)
    setError(null)
    try {
      const current = await api.researchCase(projectId)
      await performOwnerAction({
        action_type: action,
        project_id: projectId,
        artifact_hash: contentAddressHash(claimId),
        expected_case_revision: await researchCaseRevision(current),
        consequence_summary: action === 'screen_source_claim'
          ? 'Elevate this exact anchored draft into owner-screened literature evidence.'
          : 'Reject this draft claim while preserving its immutable history.',
        reason,
        payload: { claim_id: claimId },
      })
      onRefresh()
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : String(failure))
    } finally {
      setBusy(null)
    }
  }

  async function freezePack() {
    const sourceIds = [...selected].sort()
    const payload = {
      source_ids: sourceIds,
      definition: { workflow: 'LiteratureV1', balanced_review_required: true },
    }
    setBusy('freeze')
    setError(null)
    try {
      const current = await api.researchCase(projectId)
      await performOwnerAction({
        action_type: 'freeze_source_pack',
        project_id: projectId,
        artifact_hash: await payloadHash(payload),
        expected_case_revision: await researchCaseRevision(current),
        consequence_summary: `Freeze exactly ${sourceIds.length} selected source(s) into an immutable pack.`,
        reason,
        payload,
      })
      onRefresh()
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : String(failure))
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="literature-workflow">
      <div className="workbench-notice">
        <strong>DRAFT — UNSCREENED DECISION SUPPORT</strong>
        <span>{String(recommendation['authority'] ?? 'Suggestions cannot make gate decisions.')}</span>
        {actions.map((action) => (
          <span key={String(action['rank'])}>
            Next: {String(action['action'] ?? '').replaceAll('_', ' ')} — {String(action['reason'] ?? '')}
          </span>
        ))}
        <span>Uncertainty: {String(recommendation['uncertainty'] ?? 'Not assessed.')}</span>
      </div>

      <form className="literature-search" onSubmit={(event) => { event.preventDefault(); void discover() }}>
        <label><span className="eyebrow">Search concepts</span><input className="field" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="double bottom forward returns" /></label>
        <label><span className="eyebrow">Unpaywall contact email</span><input className="field" type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="owner@example.com" /></label>
        <button className="btn primary" type="submit" disabled={!query.trim() || !email.trim() || busy !== null}>{busy === 'discover' ? 'Searching approved services…' : 'Search literature'}</button>
        <span className="muted">Budget: 20 candidates · 5 full texts · explicit click only</span>
      </form>
      {error ? <div className="workbench-notice" role="alert"><strong>LITERATURE ACTION FAILED</strong><span>{error}</span></div> : null}
      {discovery ? (
        <div className="literature-candidates" aria-label="Literature candidates">
          {discovery.candidates.map((candidate) => (
            <article key={candidate.candidate_id} className="literature-candidate">
              <span className="eyebrow">{candidate.provider} · {candidate.access_state} · {candidate.year ?? 'year unknown'}</span>
              {candidate.retracted ? <span className="chip fail">RETRACTED</span> : null}
              <h4>{candidate.title}</h4>
              <p>{candidate.relevance_explanation}</p>
              <p className="muted">{candidate.authors.join(', ') || 'Authors not returned.'} · {candidate.doi ?? 'No DOI'}</p>
              <button className="btn" type="button" disabled={candidate.access_state !== 'direct_pdf' || busy !== null} onClick={() => void acquire(candidate.candidate_id)}>{busy === candidate.candidate_id ? 'Validating and extracting…' : candidate.access_state === 'direct_pdf' ? 'Acquire open PDF' : 'No direct PDF'}</button>
            </article>
          ))}
        </div>
      ) : null}
      {acquisition ? (
        <div className="workbench-notice">
          <strong>EXTRACTION · {acquisition.document.status.toUpperCase()}</strong>
          <span>{acquisition.document.page_count} pages · {acquisition.document.character_count} characters · UNTRUSTED_SOURCE</span>
          {acquisition.document.warnings.map((warning) => <span key={warning}>{warning}</span>)}
        </div>
      ) : null}

      <label className="literature-owner-reason"><span className="eyebrow">Reason bound to each Touch ID action</span><textarea className="field" value={reason} onChange={(event) => setReason(event.target.value)} /></label>
      {claims.length === 0 ? (
        <Placeholder big="NO CLAIMS RECORDED">Drafts require method, sample, markets, limitations, and a verified text anchor for full-text sources.</Placeholder>
      ) : (
        <div className="research-findings" aria-label="Balanced claims map">
          {claims.map((claim) => {
            const claimId = String(claim['claim_id'] ?? '')
            const status = String(claim['status'] ?? 'draft')
            const anchor = claim['source_anchor'] as Record<string, unknown> | null
            return (
              <article key={claimId}>
                <span className="eyebrow">{String(claim['direction'] ?? '')} · {String(claim['strength'] ?? '')} · {String(claim['author_kind'] ?? '')}</span>
                <span className={status === 'screened' ? 'chip pass' : 'chip'}>{status === 'screened' ? 'SCREENED' : 'DRAFT — UNSCREENED'}</span>
                <p>{String(claim['claim_text'] ?? '')}</p>
                <dl className="literature-claim-detail">
                  <dt>Method</dt><dd>{String(claim['method_summary'] ?? 'Not recorded.')}</dd>
                  <dt>Sample</dt><dd>{String(claim['sample_summary'] ?? 'Not recorded.')}</dd>
                  <dt>Markets</dt><dd>{Array.isArray(claim['markets']) ? claim['markets'].join(', ') : 'Not recorded.'}</dd>
                  <dt>Limitations</dt><dd>{String(claim['limitations'] ?? 'Not recorded.')}</dd>
                </dl>
                <blockquote>{anchor ? `p. ${String(anchor['page'])}: ${String(anchor['excerpt'] ?? '')}` : String(claim['anchor_state'] ?? 'LEGACY — NO TEXT ANCHOR')}</blockquote>
                {status === 'draft' ? <div className="literature-claim-actions"><button className="btn primary" type="button" disabled={!reason.trim() || busy !== null || !anchor} onClick={() => void ownerAction('screen_source_claim', claimId)}>Touch ID · screen anchored claim</button><button className="btn" type="button" disabled={!reason.trim() || busy !== null} onClick={() => void ownerAction('reject_source_claim', claimId)}>Touch ID · reject</button></div> : null}
              </article>
            )
          })}
        </div>
      )}

      <div className="research-findings">
        {literature.sources.map((source) => (
          <label key={source.source_id} className="literature-source-row">
            <input type="checkbox" checked={selected.has(source.source_id)} onChange={(event) => setSelected((current) => { const next = new Set(current); if (event.target.checked) next.add(source.source_id); else next.delete(source.source_id); return next })} />
            <span><span className="eyebrow">{source.provider} · {source.access_mode} · {source.extraction_status ?? 'metadata only'}</span><strong>{source.title}</strong><span className="mono muted">{source.locator}</span></span>
          </label>
        ))}
      </div>
      <button className="btn primary" type="button" disabled={!selected.size || !reason.trim() || busy !== null} onClick={() => void freezePack()}>Touch ID · freeze selected source pack</button>
    </div>
  )
}

function SectionBody({
  section,
  sections,
  projectId,
  onRefresh,
}: {
  section: SectionId
  sections: ResearchEvidenceHubSections
  projectId: string
  onRefresh: () => void
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
      return <LiteratureSection literature={sections.literature} projectId={projectId} onRefresh={onRefresh} />
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
    case 'exploration': {
      const runs = sections.exploration.charts
        .map((chart) => chart['run_id'])
        .filter((runId): runId is string => typeof runId === 'string' && runId.length > 0)
      if (!runs.length) {
        return (
          <Placeholder big={sections.exploration.status}>
            Exploratory D1 chart and table artifacts appear here after the experiment engine
            records a completed discovery-share run.
          </Placeholder>
        )
      }
      return (
        <div className="research-figure-runs">
          {[...new Set(runs)].map((runId) => (
            <FigureReport key={runId} runId={runId} />
          ))}
        </div>
      )
    }
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

export function EvidenceHub(props: PanelHandleProps) {
  const params = (props.params ?? {}) as {
    initialSection?: unknown
    compactLiterature?: unknown
  }
  const initialSection = SECTION_ORDER.some((section) => section.id === params.initialSection)
    ? (params.initialSection as SectionId)
    : 'overview'
  const compactLiterature = params.compactLiterature === true
  const panelLink = usePanelLinked(props)
  const projectId = panelLink.linked.projectId
  const [hub, setHub] = useState<ResearchEvidenceHub | null>(null)
  const [scorecardOpen, setScorecardOpen] = useState(false)
  const [active, setActive] = useState<SectionId>(initialSection)
  const [error, setError] = useState<string | null>(null)
  const [refresh, setRefresh] = useState(0)

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
  }, [projectId, refresh])
  const visibleHub = hub?.project_id === projectId ? hub : null

  return (
    <div className="panel">
      <div className="panel-toolbar">
        <span className="title">{compactLiterature ? 'Literature' : 'Evidence'}</span>
        <span className="chip kind">READ-ONLY</span>
        <span className="muted">
          {compactLiterature
            ? 'sources · claims · screening state · pack membership'
            : 'for & against · equal prominence · nothing disappears'}
        </span>
        <span className="spacer" />
        {visibleHub ? (
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
        {projectId && !visibleHub && !error ? (
          <Placeholder big="LOADING EVIDENCE">
            Loading only the selected project's current evidence projection.
          </Placeholder>
        ) : null}
        {visibleHub && scorecardOpen ? (
          <ScorecardDetail scorecard={visibleHub.sections.overview.scorecard} />
        ) : null}
        {visibleHub && !scorecardOpen ? (
          <>
            {!compactLiterature ? <div className="scorecard-strip" aria-label="Headline evidence board">
              {headlineBoard(visibleHub.sections).map((category) => (
                <span
                  key={category.id}
                  className={stateChipClass(category.status.toLowerCase().replaceAll(' ', '_'))}
                  title={category.label}
                >
                  {category.label} · {category.status}
                </span>
              ))}
            </div> : null}
            {!compactLiterature ? <div className="evidence-hub-tabs" role="tablist" aria-label="Evidence sections">
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
            </div> : null}
            <div className="evidence-hub-body">
              <SectionBody section={active} sections={visibleHub.sections} projectId={visibleHub.project_id} onRefresh={() => setRefresh((value) => value + 1)} />
            </div>
          </>
        ) : null}
      </div>
    </div>
  )
}
