import { useEffect, useMemo, useState } from 'react'

import { api } from '../api/client'
import type {
  ControlJob,
  EvidencePage,
  MlExperimentPage,
  MlExperimentPreflight,
  MlServiceStatus,
  ProjectDetail,
  ProjectSummary,
  SuiteAction,
  SuitePlan,
} from '../api/types'
import { Placeholder } from '../components/Placeholder'
import { ResearchGateLockNotice } from '../components/ResearchGateLockNotice'
import { setLinked, useLinked } from '../context/linked'
import { fmtPct, shortId } from '../util/format'
import { isActiveControlJob, refreshDurableJobs } from './durableJobs'
import { strategyGateLock } from './researchGateModel'
import { projectStageRows } from './v3Models'

function ContextLine() {
  const linked = useLinked()
  return (
    <div className="workbench-context mono">
      <span>GROUP {linked.linkGroup}</span>
      <span>PROJECT {linked.projectId ?? '—'}</span>
      <span>VERSION {linked.versionId ?? '—'}</span>
      <span>SYMBOL {linked.symbol ?? '—'}</span>
      <span>UNIVERSE {linked.universe ?? '—'}</span>
      <span>TIMEFRAME {linked.timeframe}</span>
      <span>AS-OF {linked.end ?? 'LATEST'}</span>
      <span>SNAPSHOT {linked.snapshotId ?? '—'}</span>
      <span>RUN {linked.runId ? shortId(linked.runId) : '—'}</span>
    </div>
  )
}

const STAGE_ACTIONS: { id: SuiteAction; label: string }[] = [
  { id: 'baseline', label: 'Run baseline' },
  { id: 'inner_oos', label: 'Run inner OOS' },
  { id: 'three_null_families', label: 'Run three null families' },
  { id: 'monte_carlo', label: 'Run four-family Monte Carlo' },
  { id: 'optimize_grid', label: 'Optimize deterministic grid' },
  { id: 'fixed_stress', label: 'Run fixed stress scenarios' },
  { id: 'portfolio_cross_asset', label: 'Run portfolio / cross-asset' },
  { id: 'qlib', label: 'Generate / train Qlib' },
  { id: 'kronos', label: 'Run / evaluate Kronos' },
  { id: 'holdout_reveal', label: 'Reveal final holdout' },
  { id: 'paper_preflight', label: 'Paper preflight' },
] as const

function ProjectCreate({ onCreated }: { onCreated: (project: ProjectSummary) => void }) {
  const [name, setName] = useState('')
  const [hypothesis, setHypothesis] = useState('')
  const [falsification, setFalsification] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const valid = name.trim() && hypothesis.trim() && falsification.trim()
  async function submit() {
    if (!valid) return
    setBusy(true)
    setError(null)
    try {
      const project = await api.createProject({
        name: name.trim(),
        hypothesis: hypothesis.trim(),
        falsification_criterion: falsification.trim(),
      })
      onCreated(project)
      setName(''); setHypothesis(''); setFalsification('')
    } catch (reason) {
      setError(String(reason))
    } finally {
      setBusy(false)
    }
  }
  return (
    <details className="project-create">
      <summary>New strategy project</summary>
      <div className="project-create-grid">
        <label><span className="eyebrow">Name</span><input className="field" value={name} onChange={(event) => setName(event.target.value)} /></label>
        <label><span className="eyebrow">Hypothesis</span><textarea className="field" value={hypothesis} onChange={(event) => setHypothesis(event.target.value)} /></label>
        <label><span className="eyebrow">Falsification criterion</span><textarea className="field" value={falsification} onChange={(event) => setFalsification(event.target.value)} /></label>
        <button className="btn primary" disabled={!valid || busy} onClick={submit}>{busy ? 'creating…' : 'Create project'}</button>
        {error ? <span className="neg mono">{error}</span> : null}
      </div>
    </details>
  )
}

function parseObject(value: string, label: string): Record<string, unknown> {
  const parsed: unknown = JSON.parse(value)
  if (!parsed || Array.isArray(parsed) || typeof parsed !== 'object') throw new Error(`${label} must be a JSON object`)
  return parsed as Record<string, unknown>
}

function ImmutableSetup({ project, onUpdated, locked }: { project: ProjectDetail; onUpdated: () => Promise<void>; locked: boolean }) {
  const [strategy, setStrategy] = useState('ts_momentum')
  const [source, setSource] = useState('')
  const [definition, setDefinition] = useState('{"lookback":252,"skip":21,"vol_window":63,"target_vol":0.15,"rebalance_every":21,"max_leverage":1,"account_type":"CASH"}')
  const [parameterSpace, setParameterSpace] = useState('{"lookback":[126,252,378],"target_vol":[0.1,0.15,0.2]}')
  const [snapshot, setSnapshot] = useState('')
  const [universe, setUniverse] = useState('')
  const [splitPolicy, setSplitPolicy] = useState('{"train":504,"test":63,"embargo":5,"anchored":false}')
  const [costs, setCosts] = useState('{"fee_bps":1,"slippage_bps":2}')
  const [seeds, setSeeds] = useState('{"master":7}')
  const [stageConfig, setStageConfig] = useState('{"tier1_paths":1000,"tier2_paths":64,"n_resamples":2000,"holdout_min_sharpe":0,"kronos_model":"fake"}')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function createVersion() {
    if (!source.trim() || !strategy.trim()) return
    setBusy(true); setError(null)
    try {
      await api.createStrategyVersion(project.project_id, {
        strategy_name: strategy.trim(),
        source_fingerprint: source.trim(),
        definition: parseObject(definition, 'definition'),
        parameter_space: parseObject(parameterSpace, 'parameter space'),
      })
      await onUpdated()
    } catch (reason) {
      setError(String(reason))
    } finally {
      setBusy(false)
    }
  }

  async function createExperiment() {
    if (!project.current_version_id || !snapshot.trim() || !universe.trim()) return
    setBusy(true); setError(null)
    try {
      await api.createExperiment(project.project_id, {
        version_id: project.current_version_id,
        snapshot_id: snapshot.trim(),
        universe: universe.split(',').map((symbol) => symbol.trim().toUpperCase()).filter(Boolean),
        split_policy: parseObject(splitPolicy, 'split policy'),
        costs: parseObject(costs, 'costs'),
        seeds: parseObject(seeds, 'seeds'),
        stage_config: parseObject(stageConfig, 'stage configuration'),
      })
      await onUpdated()
    } catch (reason) {
      setError(String(reason))
    } finally {
      setBusy(false)
    }
  }

  return (
    <details className="project-create immutable-setup" open={!project.current_experiment_id}>
      <summary>Immutable strategy & experiment setup</summary>
      <div className="immutable-setup-grid">
        <section>
          <div className="rd-head">Strategy version · content addressed</div>
          <div className="governance-form">
            <label><span className="eyebrow">Registered strategy</span><input className="field mono" value={strategy} onChange={(event) => setStrategy(event.target.value)} /></label>
            <label><span className="eyebrow">Clean source fingerprint</span><input className="field mono" placeholder="git:<commit>" value={source} onChange={(event) => setSource(event.target.value)} /></label>
            <label className="span-two"><span className="eyebrow">Resolved definition JSON</span><textarea className="field mono" value={definition} onChange={(event) => setDefinition(event.target.value)} /></label>
            <label className="span-two"><span className="eyebrow">Declared parameter space JSON</span><textarea className="field mono" value={parameterSpace} onChange={(event) => setParameterSpace(event.target.value)} /></label>
            <button className="btn primary span-two" disabled={locked || busy || !source.trim() || !strategy.trim()} title={locked ? 'Research gate open — close the research case first' : undefined} onClick={createVersion}>Create immutable version</button>
          </div>
        </section>
        <section>
          <div className="rd-head">Experiment specification · frozen inputs</div>
          <div className="governance-form">
            <label><span className="eyebrow">Snapshot ID</span><input className="field mono" value={snapshot} onChange={(event) => setSnapshot(event.target.value)} /></label>
            <label><span className="eyebrow">Frozen universe</span><input className="field mono" placeholder="AAPL,MSFT,SPY" value={universe} onChange={(event) => setUniverse(event.target.value)} /></label>
            <label><span className="eyebrow">Split policy JSON</span><textarea className="field mono" value={splitPolicy} onChange={(event) => setSplitPolicy(event.target.value)} /></label>
            <label><span className="eyebrow">Costs JSON</span><textarea className="field mono" value={costs} onChange={(event) => setCosts(event.target.value)} /></label>
            <label><span className="eyebrow">Semantic seeds JSON</span><textarea className="field mono" value={seeds} onChange={(event) => setSeeds(event.target.value)} /></label>
            <label><span className="eyebrow">Stage configuration JSON</span><textarea className="field mono" value={stageConfig} onChange={(event) => setStageConfig(event.target.value)} /></label>
            <button className="btn primary span-two" disabled={locked || busy || !project.current_version_id || !snapshot.trim() || !universe.trim()} title={locked ? 'Research gate open — close the research case first' : undefined} onClick={createExperiment}>Freeze experiment specification</button>
          </div>
        </section>
      </div>
      {error ? <span className="neg mono">{error}</span> : null}
    </details>
  )
}

function ExperimentSummary({ project }: { project: ProjectDetail }) {
  const experiment = project.experiments.find((row) => row.experiment_id === project.current_experiment_id)
  const holdout = project.holdouts.find((row) => row.experiment_id === project.current_experiment_id)
  return (
    <div className="development-spec">
      <div><span className="eyebrow">Hypothesis</span><p>{project.hypothesis}</p></div>
      <div><span className="eyebrow">Falsification</span><p>{project.falsification_criterion}</p></div>
      <div><span className="eyebrow">Current immutable version</span><span className="mono">{project.current_version_id ?? 'NOT CREATED'}</span></div>
      <div><span className="eyebrow">Experiment</span><span className="mono">{project.current_experiment_id ?? 'NOT CREATED'}</span></div>
      <div><span className="eyebrow">Snapshot</span><span className="mono">{experiment?.snapshot_id ?? 'NOT FROZEN'}</span></div>
      <div><span className="eyebrow">Frozen universe</span><span className="mono">{experiment?.universe.join(' · ') ?? 'NOT FROZEN'}</span></div>
      <div><span className="eyebrow">Final holdout</span><span className={`mono ${holdout?.contaminated_at ? 'neg' : ''}`}>{holdout ? holdout.contaminated_at ? 'CONTAMINATED' : holdout.revealed_at ? 'REVEALED' : 'SEALED' : 'NOT SEALED'}</span></div>
      <div><span className="eyebrow">Attempts recorded</span><span className="mono">{project.attempts.length} total · {project.attempts.filter((row) => ['failed', 'pruned', 'rejected'].includes(row.status)).length} negative</span></div>
    </div>
  )
}

export function DevelopmentCenter() {
  const linked = useLinked()
  const [projects, setProjects] = useState<ProjectSummary[]>([])
  const [projectHasMore, setProjectHasMore] = useState(false)
  const [projectsLoading, setProjectsLoading] = useState(false)
  const [selectedId, setSelectedId] = useState(linked.projectId ?? '')
  const [detail, setDetail] = useState<ProjectDetail | null>(null)
  const [jobs, setJobs] = useState<ControlJob[]>([])
  const [error, setError] = useState<string | null>(null)
  const [plans, setPlans] = useState<Partial<Record<SuiteAction, SuitePlan>>>({})
  const [planErrors, setPlanErrors] = useState<Partial<Record<SuiteAction, string>>>({})
  const [selectedAction, setSelectedAction] = useState<SuiteAction>('baseline')
  const [plansLoading, setPlansLoading] = useState(false)
  const [launching, setLaunching] = useState(false)
  const [jobsReady, setJobsReady] = useState(false)
  const [jobPollError, setJobPollError] = useState<string | null>(null)
  const [jobRefresh, setJobRefresh] = useState(0)
  const [ownerActor, setOwnerActor] = useState('owner')
  const [ownerReason, setOwnerReason] = useState('Candidate frozen; owner approved one-shot holdout reveal.')
  const [governanceBusy, setGovernanceBusy] = useState(false)
  const [holdoutStart, setHoldoutStart] = useState('')
  const [holdoutEnd, setHoldoutEnd] = useState('')
  const [holdoutReason, setHoldoutReason] = useState('Final evaluation window reserved before model selection.')
  const [decisionVerdict, setDecisionVerdict] = useState<'accept' | 'reject' | 'revise'>('revise')
  const [decisionReason, setDecisionReason] = useState('')
  const [negativeAcknowledged, setNegativeAcknowledged] = useState(false)
  const [briefBusy, setBriefBusy] = useState(false)
  const [briefStatus, setBriefStatus] = useState<string | null>(null)

  const refreshProjects = () => {
    api.projects(100, 0).then((page) => {
      setProjects(page.items)
      setProjectHasMore(page.has_more)
      setSelectedId((current) => current || linked.projectId || page.items[0]?.project_id || '')
    }).catch((reason: unknown) => setError(String(reason)))
  }

  useEffect(() => {
    refreshProjects()
    // Initial bounded projections; user mutations refresh explicitly.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    setSelectedId(linked.projectId ?? '')
  }, [linked.projectId])

  async function loadMoreProjects(): Promise<void> {
    if (projectsLoading || !projectHasMore) return
    setProjectsLoading(true)
    try {
      const page = await api.projects(100, projects.length)
      setProjects((current) => [...current, ...page.items])
      setProjectHasMore(page.has_more)
    } catch (reason) {
      setError(String(reason))
    } finally {
      setProjectsLoading(false)
    }
  }

  useEffect(() => {
    if (!selectedId) {
      setDetail(null)
      return
    }
    let live = true
    setDetail(null)
    api.project(selectedId).then((project) => {
      if (!live) return
      setDetail(project)
      const experiment = project.experiments.find((row) => row.experiment_id === project.current_experiment_id)
      setLinked({
        projectId: project.project_id,
        versionId: project.current_version_id,
        snapshotId: experiment?.snapshot_id ?? null,
        universe: experiment?.universe.join(',') ?? null,
      })
    }).catch((reason: unknown) => live && setError(String(reason)))
    return () => { live = false }
  }, [selectedId])

  useEffect(() => {
    const experimentId = detail?.current_experiment_id
    if (!detail || !experimentId) {
      setPlans({})
      setPlanErrors({})
      return
    }
    let live = true
    setPlansLoading(true)
    Promise.allSettled(STAGE_ACTIONS.map(async ({ id }) => [id, await api.suitePlan(detail.project_id, experimentId, id)] as const))
      .then((results) => {
        if (!live) return
        const next: Partial<Record<SuiteAction, SuitePlan>> = {}
        const failures: Partial<Record<SuiteAction, string>> = {}
        results.forEach((result, index) => {
          const action = STAGE_ACTIONS[index].id
          if (result.status === 'fulfilled') next[action] = result.value[1]
          else failures[action] = String(result.reason)
        })
        setPlans(next)
        setPlanErrors(failures)
        const firstReady = STAGE_ACTIONS.find(({ id }) => next[id]?.ready)?.id
        if (firstReady) setSelectedAction((current) => next[current] ? current : firstReady)
      })
      .finally(() => live && setPlansLoading(false))
    return () => { live = false }
  }, [detail])

  useEffect(() => {
    let live = true
    let timer: number | undefined
    setJobsReady(false)

    const poll = async (): Promise<void> => {
      try {
        const refreshed = await refreshDurableJobs(api.developmentJobs, api.developmentJob)
        if (!live) return
        setJobs(refreshed.jobs)
        setJobsReady(true)
        setJobPollError(
          refreshed.detailErrors.length
            ? `DURABLE JOB DETAIL RETRY · ${refreshed.detailErrors.join(' · ')}`
            : null,
        )
        setLaunching(
          refreshed.jobs.some(
            (job) => isActiveControlJob(job) && (!selectedId || job.project_id === selectedId),
          ),
        )

        const completedSelectedProject = refreshed.jobs.some(
          (job) =>
            refreshed.completedJobIds.includes(job.job_id) && job.project_id === selectedId,
        )
        if (completedSelectedProject && selectedId) {
          api.project(selectedId)
            .then((project) => live && setDetail(project))
            .catch((reason: unknown) => live && setJobPollError(String(reason)))
        }
        timer = window.setTimeout(poll, refreshed.activeJobIds.length ? 1000 : 5000)
      } catch (reason) {
        if (!live) return
        setJobsReady(false)
        setJobPollError(`DURABLE JOB POLL RETRY · ${String(reason)}`)
        timer = window.setTimeout(poll, 2000)
      }
    }

    void poll()
    return () => {
      live = false
      if (timer !== undefined) window.clearTimeout(timer)
    }
  }, [jobRefresh, selectedId])

  const stages = useMemo(() => projectStageRows(detail), [detail])
  // R6h (spec §15): an open research-required gate disables every strategy-creation and
  // optimisation affordance below; the notice carries the reason and the case link.
  const gateLock = strategyGateLock(detail?.research_gate_state)
  const projectJobs = jobs.filter((job) => !selectedId || job.project_id === selectedId)
  const selectedPlan = plans[selectedAction]
  const experimentId = detail?.current_experiment_id ?? null
  const holdout = detail?.holdouts.find((row) => row.experiment_id === experimentId)
  const decision = detail?.decision_packets.find((row) => row.experiment_id === experimentId)
  const monteCarloReview = detail?.monte_carlo_reviews.find((row) => row.experiment_id === experimentId)
  const monteCarloStage = detail?.stage_states.find((row) => row.experiment_id === experimentId && row.stage === 'monte_carlo')
  const candidate = detail?.stage_states.find((row) => row.experiment_id === experimentId && row.stage === 'candidate')
  const candidatePrerequisites = ['baseline', 'oos', 'robustness', 'optimization', 'portfolio']
  const monteCarloReady = monteCarloStage?.state === 'pass' || (monteCarloStage?.state === 'warning' && monteCarloReview?.decision === 'continue')
  const candidateReady = monteCarloReady && candidatePrerequisites.every((stage) => detail?.stage_states.some((row) => row.experiment_id === experimentId && row.stage === stage && ['pass', 'warning'].includes(row.state)))

  async function reloadDetail() {
    if (!selectedId) return
    const next = await api.project(selectedId)
    setDetail(next)
    const experiment = next.experiments.find((row) => row.experiment_id === next.current_experiment_id)
    setLinked({
      projectId: next.project_id,
      versionId: next.current_version_id,
      snapshotId: experiment?.snapshot_id ?? null,
      universe: experiment?.universe.join(',') ?? null,
    })
  }

  async function prepareCodexTask() {
    if (!detail) return
    setBriefBusy(true); setBriefStatus(null); setError(null)
    try {
      const brief = await api.agentBrief(detail.project_id)
      if (!navigator.clipboard?.writeText) {
        throw new Error('Clipboard API is unavailable in this browser context')
      }
      await navigator.clipboard.writeText(JSON.stringify(brief, null, 2))
      setBriefStatus(`COPIED · ${brief.evidence.length} EVIDENCE · ${brief.required_tests.length} REQUIRED TESTS`)
    } catch (reason) {
      setError(String(reason))
    } finally {
      setBriefBusy(false)
    }
  }

  async function launchSelected() {
    if (gateLock || !detail?.current_experiment_id || !selectedPlan?.ready) return
    setLaunching(true)
    setError(null)
    try {
      const owner = selectedAction === 'holdout_reveal'
        ? { owner_actor: ownerActor.trim(), owner_reason: ownerReason.trim() }
        : {}
      await api.runSuite(
        detail.project_id,
        detail.current_experiment_id,
        selectedAction,
        owner,
      )
      setJobRefresh((value) => value + 1)
    } catch (reason) {
      setError(String(reason))
      setLaunching(false)
    }
  }

  async function cancelJob(jobId: string) {
    try {
      await api.cancelDevelopmentJob(jobId)
      setJobRefresh((value) => value + 1)
    } catch (reason) {
      setError(String(reason))
    }
  }

  async function sealFinalHoldout() {
    if (!detail || !experimentId || !holdoutStart || !holdoutEnd || !holdoutReason.trim() || !ownerActor.trim()) return
    setGovernanceBusy(true); setError(null)
    try {
      await api.sealHoldout(detail.project_id, {
        experiment_id: experimentId,
        actor: ownerActor.trim(),
        reason: holdoutReason.trim(),
        start_date: holdoutStart,
        end_date: holdoutEnd,
      })
      await reloadDetail()
    } catch (reason) {
      setError(String(reason))
    } finally {
      setGovernanceBusy(false)
    }
  }

  async function freezeCandidate() {
    if (!detail || !experimentId || !candidateReady || !candidate || ['pass', 'warning'].includes(candidate.state)) return
    setGovernanceBusy(true); setError(null)
    try {
      const states = ['ready', 'queued', 'running', 'pass'] as const
      const current = states.indexOf(candidate.state as typeof states[number])
      for (const state of states.slice(current + 1)) {
        await api.transitionExperimentStage(detail.project_id, experimentId, 'candidate', {
          state,
          reason: 'Owner froze the candidate after reviewing all pre-holdout research evidence.',
        })
      }
      await reloadDetail()
    } catch (reason) {
      setError(String(reason))
    } finally {
      setGovernanceBusy(false)
    }
  }

  async function freezeDecision() {
    if (!detail || !experimentId || !negativeAcknowledged || !decisionReason.trim() || !ownerActor.trim()) return
    setGovernanceBusy(true); setError(null)
    try {
      await api.freezeDecision(detail.project_id, experimentId, {
        verdict: decisionVerdict,
        actor: ownerActor.trim(),
        reason: decisionReason.trim(),
        negative_results_acknowledged: true,
      })
      await reloadDetail()
    } catch (reason) {
      setError(String(reason))
    } finally {
      setGovernanceBusy(false)
    }
  }

  return (
    <div className="panel">
      <div className="panel-toolbar">
        <span className="title">Development Center</span>
        <span className="chip kind">PROJECT CONTROL</span>
        <select className="field project-select" value={selectedId} onChange={(event) => setSelectedId(event.target.value)} aria-label="Strategy project">
          <option value="">NO PROJECT</option>
          {projects.map((project) => <option key={project.project_id} value={project.project_id}>{project.name}</option>)}
        </select>
        <span className="spacer" />
        {projectHasMore ? <button className="btn" disabled={projectsLoading} onClick={() => void loadMoreProjects()}>{projectsLoading ? 'Loading…' : 'Load more'}</button> : null}
        <span className="mono muted">{projects.length} PROJECTS</span>
      </div>
      <div className="panel-body panel-pad workbench">
        <ContextLine />
        <ProjectCreate onCreated={(project) => { setProjects((rows) => [project, ...rows]); setSelectedId(project.project_id) }} />
        {error ? <div className="workbench-notice"><strong>PROJECTION ERROR</strong><span>{error}</span></div> : null}
        {jobPollError ? <div className="workbench-notice" role="alert"><strong>JOB JOURNAL</strong><span>{jobPollError}</span></div> : null}
        {!selectedId ? <Placeholder big="NO PROJECT">Create or select a project to inspect immutable strategy-development lineage.</Placeholder> : !detail ? <div className="skeleton" style={{ height: 300 }} /> : (
          <>
            <ExperimentSummary project={detail} />
            {gateLock ? <ResearchGateLockNotice lock={gateLock} projectId={detail.project_id} projectName={detail.name} /> : null}
            <div className="agent-brief-bar">
              <div><span className="eyebrow">Typed AgentBrief</span><span>Current hypothesis, allowed scope, cited evidence, stage state, warnings, and required tests.</span></div>
              {briefStatus ? <span className="mono pos">{briefStatus}</span> : null}
              <button className="btn primary" disabled={briefBusy} onClick={prepareCodexTask}>{briefBusy ? 'Preparing…' : 'Prepare Codex task'}</button>
            </div>
            <ImmutableSetup project={detail} onUpdated={reloadDetail} locked={Boolean(gateLock)} />
            <div className="development-grid">
              <section>
                <div className="rd-head">Lifecycle stages</div>
                <div className="dev-stage-list">
                  {stages.map((stage, index) => (
                    <button
                      className={`dev-stage dev-stage-button state-${stage.state}`}
                      key={stage.id}
                      disabled={!stage.runId}
                      onClick={() => stage.runId && setLinked({ runId: stage.runId })}
                      title={stage.runId ? `Select cited run ${stage.runId}` : 'No canonical run linked'}
                    >
                      <span className="dev-index mono">{String(index + 1).padStart(2, '0')}</span>
                      <span>{stage.label}</span>
                      <span className="spacer" />
                      {stage.runId ? <span className="mono">{shortId(stage.runId)}</span> : null}
                      <span className={`dev-state chip ${stage.state === 'pass' ? 'pass' : stage.state === 'fail' ? 'fail' : ''}`}>{stage.state.replace('_', ' ')}</span>
                    </button>
                  ))}
                </div>
              </section>
              <section>
                <div className="rd-head">Resolved actions</div>
                {plansLoading ? <div className="workbench-notice"><strong>RESOLVING</strong><span>Checking immutable inputs, prerequisites, and workload through alpha_cli.</span></div> : null}
                <div className="stage-actions">
                  {STAGE_ACTIONS.map((action) => {
                    const plan = plans[action.id]
                    const title = plan?.ready ? `Preview ${plan.steps.length} allowlisted command${plan.steps.length === 1 ? '' : 's'}` : plan?.blockers.join('; ') || planErrors[action.id] || 'No current immutable experiment'
                    return <button className={`btn ${selectedAction === action.id ? 'primary' : ''}`} disabled={Boolean(gateLock) || !plan?.ready || launching || !jobsReady} key={action.id} title={gateLock ? gateLock.reason : title} onClick={() => setSelectedAction(action.id)}>{action.label}</button>
                  })}
                </div>
                {selectedPlan ? (
                  <div className="suite-preview">
                    <div className="suite-preview-head"><span className="chip kind">{selectedPlan.action}</span><span className={`chip ${selectedPlan.ready ? 'pass' : 'fail'}`}>{selectedPlan.ready ? 'READY' : 'BLOCKED'}</span><span className="spacer" /><span className="mono muted">{String(selectedPlan.estimated_workload.class).toUpperCase()}</span></div>
                    <div className="suite-resolved mono">
                      <span>EXPERIMENT {shortId(selectedPlan.experiment_id)}</span>
                      <span>STAGE {selectedPlan.stage} · {selectedPlan.current_stage_state}</span>
                      <span>SNAPSHOT {selectedPlan.resolved_experiment.snapshot_id}</span>
                      <span>UNIVERSE {selectedPlan.resolved_experiment.universe.join(' · ')}</span>
                      <span>SPLIT {JSON.stringify(selectedPlan.resolved_experiment.split_policy)}</span>
                      <span>COSTS {JSON.stringify(selectedPlan.resolved_experiment.costs)}</span>
                    </div>
                    <p className="muted">{String(selectedPlan.estimated_workload.description)}</p>
                    <ol className="suite-command-list">
                      {selectedPlan.steps.map((step) => <li key={step.index}><span>{step.label}</span><code>{step.command.join(' ')}</code><small>{step.evidence_role.replaceAll('_', ' ')}</small></li>)}
                    </ol>
                    {selectedAction === 'holdout_reveal' ? <div className="suite-owner-confirm"><label><span className="eyebrow">Owner</span><input className="field" value={ownerActor} onChange={(event) => setOwnerActor(event.target.value)} /></label><label><span className="eyebrow">Permanent audit reason</span><textarea className="field" value={ownerReason} onChange={(event) => setOwnerReason(event.target.value)} /></label></div> : null}
                    <button className="btn primary" disabled={Boolean(gateLock) || !selectedPlan.ready || launching || !jobsReady || (selectedAction === 'holdout_reveal' && (!ownerActor.trim() || !ownerReason.trim()))} title={gateLock?.reason} onClick={launchSelected}>{!jobsReady ? 'Recovering jobs…' : launching ? 'Running…' : `Launch ${selectedPlan.steps.length} step${selectedPlan.steps.length === 1 ? '' : 's'}`}</button>
                  </div>
                ) : null}
                <div className="rd-head">Durable development journals</div>
                {projectJobs.length ? <div className="control-job-list">{projectJobs.slice(0, 12).map((job) => <div key={job.job_id}><span className={`chip ${job.status === 'succeeded' ? 'pass' : job.status === 'failed' ? 'fail' : ''}`}>{job.status}</span><span>{job.kind}</span><span className="mono muted">{shortId(job.job_id)}</span>{['queued', 'running'].includes(job.status) ? <button className="btn danger" aria-label={`Cancel ${job.kind} job ${shortId(job.job_id)}`} onClick={() => cancelJob(job.job_id)}>Cancel</button> : null}</div>)}</div> : <span className="muted">No journal entries for this project.</span>}
              </section>
            </div>
            <section className="owner-governance">
              <div className="rd-head">Owner governance · irreversible records</div>
              <div className="governance-grid">
                <div className="governance-block">
                  <div className="governance-title"><span>Final holdout</span><span className={`chip ${holdout?.contaminated_at ? 'fail' : holdout ? 'pass' : ''}`}>{holdout ? holdout.contaminated_at ? 'CONTAMINATED' : holdout.revealed_at ? 'REVEALED' : 'SEALED' : 'NOT SEALED'}</span></div>
                  {holdout ? <><span className="mono muted">SPEC {holdout.holdout_spec_hash ? shortId(holdout.holdout_spec_hash) : 'WINDOW NOT DEFINED'}</span><p>{holdout.revealed_at ? `${holdout.start_date} → ${holdout.end_date}` : 'Date boundaries remain redacted until the audited reveal.'}</p></> : <div className="governance-form"><label><span className="eyebrow">Start</span><input className="field" type="date" value={holdoutStart} onChange={(event) => setHoldoutStart(event.target.value)} /></label><label><span className="eyebrow">End</span><input className="field" type="date" value={holdoutEnd} onChange={(event) => setHoldoutEnd(event.target.value)} /></label><label className="span-two"><span className="eyebrow">Seal reason</span><textarea className="field" value={holdoutReason} onChange={(event) => setHoldoutReason(event.target.value)} /></label><button className="btn primary span-two" disabled={governanceBusy || !holdoutStart || !holdoutEnd || !ownerActor.trim() || !holdoutReason.trim()} onClick={sealFinalHoldout}>Seal immutable holdout</button></div>}
                </div>
                <div className="governance-block">
                  <div className="governance-title"><span>Candidate freeze</span><span className={`chip ${candidate?.state === 'pass' ? 'pass' : ''}`}>{candidate?.state ?? 'NOT STARTED'}</span></div>
                  <p>Freezes the current strategy and experiment only after baseline, OOS, robustness, four-family Monte Carlo, optimization, and portfolio research clear.</p>
                  <button className="btn primary" disabled={governanceBusy || !candidateReady || candidate?.state === 'pass'} onClick={freezeCandidate}>{candidate?.state === 'pass' ? 'Candidate frozen' : 'Freeze candidate'}</button>
                </div>
                <div className="governance-block">
                  <div className="governance-title"><span>Monte Carlo review</span><span className={`chip ${monteCarloReview?.decision === 'continue' ? 'pass' : monteCarloReview ? 'fail' : ''}`}>{monteCarloReview?.decision.toUpperCase() ?? (monteCarloStage?.state === 'warning' ? 'OWNER REVIEW REQUIRED' : monteCarloStage?.state?.toUpperCase() ?? 'NOT STARTED')}</span></div>
                  {monteCarloReview ? <><span className="mono">{shortId(monteCarloReview.review_id)} · {monteCarloReview.actor}</span><p>{monteCarloReview.rationale}</p><span className="mono muted">{monteCarloReview.evidence_hashes.length} EXACT RUN HASHES · CLI-ONLY AUTHORITY</span></> : <p>Warnings pause here. Record continue, revise, or reject with <code>alpha project review-monte-carlo</code>; the Workstation and MCP are read-only for this owner decision.</p>}
                </div>
                <div className="governance-block">
                  <div className="governance-title"><span>Decision packet</span><span className={`chip ${decision?.verdict === 'accept' ? 'pass' : decision?.verdict === 'reject' ? 'fail' : ''}`}>{decision?.verdict?.toUpperCase() ?? 'OPEN'}</span></div>
                  {decision ? <><span className="mono">{shortId(decision.packet_id)}</span><p>{decision.reason}</p><span className="mono muted">{decision.negative_result_attempt_ids.length} NEGATIVE RESULTS ACKNOWLEDGED · SANDBOX ONLY</span></> : <div className="governance-form"><label><span className="eyebrow">Owner</span><input className="field" value={ownerActor} onChange={(event) => setOwnerActor(event.target.value)} /></label><label><span className="eyebrow">Verdict</span><select className="field" value={decisionVerdict} onChange={(event) => setDecisionVerdict(event.target.value as 'accept' | 'reject' | 'revise')}><option value="revise">Revise</option><option value="reject">Reject</option><option value="accept">Accept · sandbox</option></select></label><label className="span-two"><span className="eyebrow">Decision rationale</span><textarea className="field" value={decisionReason} onChange={(event) => setDecisionReason(event.target.value)} /></label><label className="governance-ack span-two"><input type="checkbox" checked={negativeAcknowledged} onChange={(event) => setNegativeAcknowledged(event.target.checked)} /><span>I reviewed all failed, pruned, rejected, and cancelled attempts.</span></label><button className="btn primary span-two" disabled={governanceBusy || !negativeAcknowledged || !decisionReason.trim() || !ownerActor.trim()} onClick={freezeDecision}>Freeze {decisionVerdict} packet · sandbox only</button></div>}
                </div>
              </div>
            </section>
          </>
        )}
      </div>
    </div>
  )
}

export function MlResearch() {
  const linked = useLinked()
  const [status, setStatus] = useState<MlServiceStatus | null>(null)
  const [experiments, setExperiments] = useState<MlExperimentPage | null>(null)
  const [preflight, setPreflight] = useState<MlExperimentPreflight | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [activeJobId, setActiveJobId] = useState<string | null>(null)
  const [jobState, setJobState] = useState<ControlJob['status'] | null>(null)

  useEffect(() => {
    let live = true
    setStatus(null); setExperiments(null); setPreflight(null); setError(null)
    api.mlStatus().then(async (next) => {
      if (!live) return
      setStatus(next)
      if (next.active_job_id) {
        setActiveJobId(next.active_job_id)
        setBusy(true)
      }
      if (next.available) {
        const [page, checks] = await Promise.all([
          api.mlExperiments(linked.projectId),
          linked.projectId ? api.mlExperimentPreflight(linked.projectId) : Promise.resolve(null),
        ])
        if (live) {
          setExperiments(page)
          setPreflight(checks)
        }
      }
    }).catch((reason: unknown) => live && setError(String(reason)))
    return () => { live = false }
  }, [linked.projectId])

  useEffect(() => {
    if (!activeJobId) return
    let live = true
    let timer: number | undefined
    const projectId = linked.projectId
    const poll = async () => {
      try {
        const job = await api.developmentJob(activeJobId)
        if (!live) return
        setJobState(job.status)
        if (['succeeded', 'failed', 'cancelled'].includes(job.status)) {
          setBusy(false)
          if (job.status !== 'succeeded') {
            setError(job.terminal_error || `ML experiment job ${job.status}`)
          }
          const [nextExperiments, nextStatus, nextPreflight] = await Promise.all([
            api.mlExperiments(projectId),
            api.mlStatus(),
            projectId ? api.mlExperimentPreflight(projectId) : Promise.resolve(null),
          ])
          if (live) {
            setExperiments(nextExperiments)
            setStatus(nextStatus)
            setPreflight(nextPreflight)
            setActiveJobId(null)
          }
          return
        }
        timer = window.setTimeout(poll, 1000)
      } catch (reason) {
        if (!live) return
        setError(`Durable ML job poll retrying: ${String(reason)}`)
        timer = window.setTimeout(poll, 2000)
      }
    }
    void poll()
    return () => {
      live = false
      if (timer !== undefined) window.clearTimeout(timer)
    }
  }, [activeJobId, linked.projectId])

  const ready = preflight?.ready === true && linked.projectId !== null
  async function createExperiment() {
    if (!ready || !linked.projectId) return
    setBusy(true)
    setError(null)
    try {
      const accepted = await api.createMlExperiment(linked.projectId)
      setActiveJobId(accepted.job_id)
      setJobState(accepted.status)
    } catch (reason) {
      setError(String(reason))
      setBusy(false)
    }
  }
  return (
    <div className="panel">
      <div className="panel-toolbar"><span className="title">ML Research</span><span className="chip kind">QLIB ISOLATED WORKER</span><span className="spacer" />{status ? <span className={`chip ${status.worker_ready ? 'pass' : 'fail'}`}>{status.worker_ready ? 'WORKER READY' : 'WORKER BLOCKED'}</span> : null}</div>
      <div className="panel-body panel-pad workbench" tabIndex={0} aria-label="ML research control content">
        <ContextLine />
        {error ? <div className="workbench-notice"><strong>ML CONTROL ERROR</strong><span>{error}</span></div> : status?.message ? <div className="workbench-notice"><strong>{status.worker_ready ? 'READY' : 'BLOCKED'}</strong><span>{status.message}</span></div> : null}
        {activeJobId ? <div className="durable-job-banner"><span className={`chip ${jobState === 'failed' ? 'fail' : ''}`}>{jobState ?? 'queued'}</span><span>Durable ML journal</span><span className="mono">{shortId(activeJobId)}</span><span className="spacer" /><span className="muted mono">SAFE TO LEAVE THIS PANEL · POLLING CONTROL DB</span></div> : null}
        {preflight ? (
          <section className="ml-preflight" aria-label="ML experiment preflight">
            <div className="rd-head">Server-verified launch preflight</div>
            {preflight.checks.map((check) => (
              <div className="governance-title" key={check.check_id}>
                <span>{check.check_id.replaceAll('_', ' ')}</span>
                <span className={`chip ${check.state === 'pass' ? 'pass' : 'fail'}`}>
                  {check.state.toUpperCase()}
                </span>
                <span>{check.message}</span>
                {check.recovery_action ? <span className="muted">{check.recovery_action}</span> : null}
              </div>
            ))}
          </section>
        ) : null}
        <div className="ml-spec-grid">
          <div><span className="eyebrow">Recipe</span><span>Alpha158-style</span></div>
          <div><span className="eyebrow">Model</span><span>LightGBM · CPU</span></div>
          <div><span className="eyebrow">Target</span><span>next-session open → open</span></div>
          <div><span className="eyebrow">Replay</span><span>long-only top quintile · equal weight</span></div>
          <div><span className="eyebrow">Minimum universe</span><span className="mono">{status?.min_symbols ?? 20} symbols</span></div>
          <div><span className="eyebrow">Minimum history</span><span className="mono">{status?.min_aligned_sessions ?? 756} aligned sessions</span></div>
          <div><span className="eyebrow">Isolation</span><span className="mono">{status?.isolation ?? 'separate worker lock'}</span></div>
          <div><span className="eyebrow">Heavy concurrency</span><span className="mono">{status?.concurrency_limit ?? 1}</span></div>
        </div>
        {experiments === null ? null : experiments.items.length ? (
          <div className="ml-experiment-list">
            {experiments.items.map((experiment) => (
              <div className="ml-experiment" key={experiment.experiment_id}>
                <div><span className="chip kind">{experiment.status}</span><span className="mono">{shortId(experiment.experiment_id)}</span></div>
                <div className="ml-experiment-metrics">
                  <span>IC <b className="mono">{experiment.metrics.ic ?? '—'}</b></span>
                  <span>RankIC <b className="mono">{experiment.metrics.rank_ic ?? '—'}</b></span>
                  <span>Turnover <b className="mono">{fmtPct(experiment.metrics.turnover)}</b></span>
                  <span>Costed <b className="mono">{fmtPct(experiment.metrics.costed_return)}</b></span>
                </div>
                <div className="mono muted">{experiment.universe_size} symbols · {experiment.aligned_sessions} sessions · {experiment.folds} folds</div>
                <div className="ml-validation-label">{experiment.counterfactual_refit ? 'COUNTERFACTUAL REFIT VALIDATED' : 'OOS REPLAY VALIDATED — MODEL NOT RECOMPUTED UNDER COUNTERFACTUAL'}</div>
              </div>
            ))}
          </div>
        ) : (
          <div className="tear-analysis-grid">
            <div className="tear-gap"><div className="tear-gap-title">Fold boundaries</div><div className="tear-gap-state mono">NO VALIDATED ML ARTIFACT</div></div>
            <div className="tear-gap"><div className="tear-gap-title">IC / RankIC</div><div className="tear-gap-state mono">NO VALIDATED ML ARTIFACT</div></div>
            <div className="tear-gap"><div className="tear-gap-title">Feature importance</div><div className="tear-gap-state mono">NO VALIDATED ML ARTIFACT</div></div>
          </div>
        )}
        <button className="btn primary" disabled={!ready || busy} onClick={createExperiment} title={ready ? 'Generate the exact preflighted experiment through the isolated worker service' : 'Every server-verified preflight check must pass'}>{busy ? `ML job ${jobState ?? 'queued'}…` : 'Generate preflighted ML experiment'}</button>
        {status === null && !error ? <span className="muted mono">CHECKING ISOLATED WORKER READINESS…</span> : null}
        {status && !status.available ? <span className="muted mono">BUTTON DISABLED · {status.message ?? 'isolated worker service unavailable'}</span> : null}
        {status?.available && status.worker_ready && !linked.projectId ? <span className="muted mono">SELECT OR CREATE A STRATEGY PROJECT IN DEVELOPMENT CENTER TO ENABLE TRAINING</span> : null}
      </div>
    </div>
  )
}

type EvidenceFilter = '' | 'draft' | 'corroborated' | 'rejected' | 'superseded'

function evidenceMetric(record: EvidencePage['items'][number]): string | null {
  if (record.metric_name === null || record.metric_value === null) return null
  return `${record.metric_name} ${record.metric_value.toLocaleString(undefined, { maximumSignificantDigits: 6 })}${record.metric_unit ? ` ${record.metric_unit}` : ''}`
}

export function AssetMemory() {
  const linked = useLinked()
  const [assetInput, setAssetInput] = useState(linked.symbol ?? '')
  const [asset, setAsset] = useState(linked.symbol ?? '')
  const [projectOnly, setProjectOnly] = useState(false)
  const [statusFilter, setStatusFilter] = useState<EvidenceFilter>('')
  const [page, setPage] = useState<EvidencePage | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [refresh, setRefresh] = useState(0)

  useEffect(() => {
    setAssetInput(linked.symbol ?? '')
    setAsset(linked.symbol ?? '')
  }, [linked.symbol])

  useEffect(() => {
    if (!linked.projectId) setProjectOnly(false)
  }, [linked.projectId])

  useEffect(() => {
    const normalizedAsset = asset.trim().toUpperCase()
    const projectId = projectOnly ? linked.projectId : null
    if (!normalizedAsset && !projectId) {
      setPage(null)
      return
    }
    let live = true
    setLoading(true); setError(null); setPage(null)
    api.evidence({
      asset: normalizedAsset || null,
      projectId,
      status: statusFilter || null,
      asOf: linked.end,
      limit: 50,
    }).then((next) => {
      if (live) setPage(next)
    }).catch((reason: unknown) => {
      if (live) setError(String(reason))
    }).finally(() => {
      if (live) setLoading(false)
    })
    return () => { live = false }
  }, [asset, linked.end, linked.projectId, projectOnly, refresh, statusFilter])

  const relatedAssets = useMemo(() => {
    const selected = asset.trim().toUpperCase()
    return [...new Set((page?.items ?? []).flatMap((record) => record.assets))]
      .filter((candidate) => candidate !== selected)
      .slice(0, 12)
  }, [asset, page])
  const methods = useMemo(
    () => [...new Set((page?.items ?? []).map((record) => record.method))].slice(0, 8),
    [page],
  )
  const negativeCount = (page?.items ?? []).filter(
    (record) => record.status === 'rejected' || record.counterevidence.length > 0,
  ).length

  return (
    <div className="panel">
      <div className="panel-toolbar"><span className="title">Asset Memory</span><span className="chip kind">CITED EVIDENCE LEDGER</span><span className="spacer" /><span className="mono muted">{page?.items.length ?? 0} FINDINGS</span></div>
      <div className="panel-body panel-pad workbench asset-memory">
        <ContextLine />
        <form className="asset-memory-filters" onSubmit={(event) => { event.preventDefault(); setAsset(assetInput) }}>
          <label><span className="eyebrow">Asset</span><input className="field mono" placeholder="AAPL" value={assetInput} onChange={(event) => setAssetInput(event.target.value.toUpperCase())} /></label>
          <label><span className="eyebrow">Revision status</span><select className="field" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value as EvidenceFilter)}><option value="">All latest revisions</option><option value="corroborated">Corroborated</option><option value="draft">Draft</option><option value="rejected">Rejected</option><option value="superseded">Superseded</option></select></label>
          <label className="asset-memory-check"><input type="checkbox" checked={projectOnly} disabled={!linked.projectId} onChange={(event) => setProjectOnly(event.target.checked)} /><span>Linked project only</span></label>
          <button className="btn primary" type="submit">Search ledger</button>
          <button className="btn" type="button" onClick={() => setRefresh((value) => value + 1)}>Refresh</button>
        </form>
        {error ? <div className="workbench-notice"><strong>EVIDENCE ERROR</strong><span>{error}</span></div> : null}
        {!asset && !projectOnly ? <Placeholder big="SELECT SCOPE">Set an active symbol or restrict the ledger to the linked project.</Placeholder> : loading && !page ? <div className="skeleton" style={{ height: 220 }} /> : (
          <>
            <div className="asset-memory-summary">
              <div><span className="eyebrow">Knowledge cutoff</span><span className="mono">{linked.end ?? 'LATEST AVAILABLE'}</span></div>
              <div><span className="eyebrow">Negative / counterevidence</span><span className="mono">{negativeCount}</span></div>
              <div><span className="eyebrow">Related assets</span><span className="mono">{relatedAssets.join(' · ') || '—'}</span></div>
              <div><span className="eyebrow">Methods represented</span><span className="mono">{methods.join(' · ') || '—'}</span></div>
            </div>
            {page?.items.length ? <div className="asset-memory-list">{page.items.map((record) => {
              const metric = evidenceMetric(record)
              return (
                <article className="asset-memory-record" key={`${record.evidence_id}:${record.revision}`}>
                  <div className="asset-memory-record-head">
                    <span className={`chip ${record.status === 'corroborated' ? 'pass' : record.status === 'rejected' ? 'fail' : ''}`}>{record.status}</span>
                    <span className="mono muted">REV {record.revision}</span>
                    <span>{record.method}</span>
                    <span className="spacer" />
                    <span className="mono muted">KNOWN {record.knowledge_at}</span>
                  </div>
                  <p>{record.claim}</p>
                  <div className="asset-memory-tags mono"><span>{record.assets.join(' · ')}</span><span>{record.timeframe}</span>{metric ? <span>{metric}</span> : null}{record.interpretation_label ? <span className="asset-association-label">{record.interpretation_label.toUpperCase()}</span> : null}</div>
                  {record.counterevidence.length ? <div className="asset-counterevidence"><strong>COUNTEREVIDENCE</strong><span>{record.counterevidence.join(' · ')}</span></div> : null}
                  <div className="asset-source-row"><button className="btn" onClick={() => setLinked({ runId: record.source_run_id })}>Open run {shortId(record.source_run_id)}</button><code>{record.source_artifact} · {record.source_field} · {JSON.stringify(record.row_selector)}</code></div>
                </article>
              )
            })}</div> : <Placeholder big="NO CITED FINDINGS">No latest evidence revisions match this asset, project, status, and as-of scope.</Placeholder>}
          </>
        )}
      </div>
    </div>
  )
}
