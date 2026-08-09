// Thin typed client over the FastAPI JSON layer. Same-origin (loopback), so no base URL.

import type {
  AgentBrief,
  Candles,
  ChartBundle,
  CommandDef,
  ControlJob,
  ControlJobDetail,
  DecisionPacket,
  EvidencePage,
  EquitySeries,
  ExperimentSpec,
  ForecastOrigins,
  ForecastPaths,
  ForecastSeries,
  JobDetail,
  MlExperimentPage,
  MlExperimentJobAccepted,
  MlServiceStatus,
  MlTearSheetProjection,
  NativeTearSheetProjection,
  NullTiers,
  OptimTrials,
  PaperEvent,
  PaperJobSummary,
  PaperReadinessReport,
  PaperSession,
  PortfolioAnalyticsProjection,
  PropfirmPaths,
  OptionCurve,
  OptionGreeks,
  ProviderDefinition,
  ProjectDetail,
  ProjectPage,
  ProjectSummary,
  ResearchCaptureRequest,
  ResearchCaptureResponse,
  ResearchCase,
  ResearchCasePage,
  ResearchCaseReport,
  ResearchContextPacket,
  ResearchContextPacketPage,
  ResearchEvidenceHub,
  ResearchNotePage,
  ResearchProtocolLibrary,
  ResearchScorecard,
  ResearchLaunchResponse,
  ResearchProposalRequest,
  ResearchProposalResponse,
  ResearchReport,
  RiskReport,
  RunDetail,
  RunList,
  ScreenerNews,
  ScreenerQuote,
  StrategyDef,
  StrategyVersion,
  SystemStatus,
  SuiteAction,
  SuiteCancelResponse,
  SuiteLaunch,
  SuitePlan,
  TradeRow,
  WorkspaceDoc,
  WorkspaceMeta,
} from './types'

async function getJSON<T>(url: string): Promise<T> {
  const res = await fetch(url)
  if (!res.ok) {
    const body = await res.text().catch(() => '')
    let detail = body
    try {
      const parsed: unknown = JSON.parse(body)
      if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
        const value = (parsed as Record<string, unknown>).detail
        if (typeof value === 'string') detail = value
      }
    } catch {
      // Plain-text failures are valid for infrastructure endpoints.
    }
    detail = detail
      .split('\n')
      .map((line) => line.replace(/^[│┃]\s?/, '').trim())
      .filter((line) => line && !/^usage:/i.test(line) && !/^try ['`]/i.test(line) && !/^[╭╰─━┄┅┈┉]+/.test(line))
      .join(' ')
    const status = `${res.status}${res.statusText ? ` ${res.statusText}` : ''}`
    throw new Error(`${status}${detail ? ` — ${detail}` : ''}`)
  }
  return (await res.json()) as T
}

const IMMUTABLE_CACHE_LIMIT = 128
const immutableCache = new Map<string, Promise<unknown>>()

function getImmutableJSON<T>(url: string): Promise<T> {
  const existing = immutableCache.get(url)
  if (existing) {
    immutableCache.delete(url)
    immutableCache.set(url, existing)
    return existing as Promise<T>
  }
  const request = getJSON<T>(url).catch((error: unknown) => {
    immutableCache.delete(url)
    throw error
  })
  immutableCache.set(url, request)
  if (immutableCache.size > IMMUTABLE_CACHE_LIMIT) {
    const oldest = immutableCache.keys().next().value
    if (oldest !== undefined) immutableCache.delete(oldest)
  }
  return request
}

export function clearImmutableApiCache(): void {
  immutableCache.clear()
}

async function postJSON<T>(url: string, body: unknown): Promise<T> {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const detail = await res.text().catch(() => '')
    throw new Error(`${res.status} ${res.statusText}${detail ? ` — ${detail}` : ''}`)
  }
  return (await res.json()) as T
}

export const api = {
  runs: (query = ''): Promise<RunList> => getJSON(`/api/runs${query}`),
  run: (id: string): Promise<RunDetail> => getImmutableJSON(`/api/runs/${id}`),
  chartBundle(id: string, limit = 2_000, start?: string | null, end?: string | null): Promise<ChartBundle> {
    const params = new URLSearchParams({ limit: String(limit) })
    if (start) params.set('start', start)
    if (end) params.set('end', end)
    return getImmutableJSON(`/api/runs/${id}/chart-bundle?${params.toString()}`)
  },
  equity: (id: string): Promise<EquitySeries> => getImmutableJSON(`/api/runs/${id}/equity`),
  trades: (id: string): Promise<TradeRow[]> => getImmutableJSON(`/api/runs/${id}/trades`),
  forecast: (id: string): Promise<ForecastSeries> => getImmutableJSON(`/api/runs/${id}/forecast`),
  forecastPaths: (id: string, n = 20): Promise<ForecastPaths> =>
    getImmutableJSON(`/api/runs/${id}/forecast/paths?n=${n}`),
  nulls: (id: string): Promise<NullTiers> => getImmutableJSON(`/api/runs/${id}/nulls`),
  trials: (id: string): Promise<OptimTrials> => getImmutableJSON(`/api/runs/${id}/trials`),
  propfirmPaths: (id: string): Promise<PropfirmPaths> => getImmutableJSON(`/api/runs/${id}/propfirm-paths`),
  origins: (id: string): Promise<ForecastOrigins> => getImmutableJSON(`/api/runs/${id}/origins`),
  nativeTearsheet: (id: string, pointLimit = 750): Promise<NativeTearSheetProjection> =>
    getImmutableJSON(`/api/runs/${id}/native-tearsheet?point_limit=${pointLimit}`),
  portfolioAnalytics: (
    id: string,
    timestampLimit = 2000,
    symbolLimit = 50,
  ): Promise<PortfolioAnalyticsProjection> =>
    getImmutableJSON(
      `/api/runs/${id}/portfolio-analytics?timestamp_limit=${timestampLimit}&symbol_limit=${symbolLimit}`,
    ),
  tearsheetUrl: (id: string): string => `/api/runs/${id}/tearsheet`,
  candles: (symbol: string, query = ''): Promise<Candles> =>
    getJSON(`/api/candles/${encodeURIComponent(symbol)}${query}`),
  strategies: (): Promise<StrategyDef[]> => getJSON('/api/strategies'),
  commands: (): Promise<CommandDef[]> => getJSON('/api/commands'),
  symbols: (): Promise<{ symbols: string[] }> => getJSON('/api/symbols'),
  providers: (): Promise<ProviderDefinition[]> => getJSON('/api/providers'),
  system: (): Promise<SystemStatus> => getJSON('/api/system'),
  jobs: (): Promise<PaperJobSummary[]> => getJSON('/api/jobs'),
  job: (id: string): Promise<JobDetail> => getJSON(`/api/jobs/${id}`),
  async launch(
    command: string,
    args: string,
  ): Promise<{ job_id: string; status: string; session_id?: string | null }> {
    const res = await fetch('/api/jobs', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ command, args }),
    })
    if (!res.ok) throw new Error(await res.text())
    return (await res.json()) as { job_id: string; status: string; session_id?: string | null }
  },
  cancel: (id: string): Promise<Response> => fetch(`/api/jobs/${id}`, { method: 'DELETE' }),
  streamUrl: (id: string): string => `/api/jobs/${id}/stream`,
  workspaces: (): Promise<WorkspaceMeta[]> => getJSON('/api/workspaces'),
  getWorkspace: (slug: string): Promise<WorkspaceDoc> => getJSON(`/api/workspaces/${slug}`),
  async saveWorkspace(body: {
    name: string
    linked_context: unknown
    dockview: unknown
  }): Promise<{ slug: string; name: string }> {
    const res = await fetch('/api/workspaces', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body),
    })
    if (!res.ok) throw new Error(await res.text())
    return (await res.json()) as { slug: string; name: string }
  },
  deleteWorkspace: (slug: string): Promise<Response> =>
    fetch(`/api/workspaces/${slug}`, { method: 'DELETE' }),
  optionsGreeks: (query: string): Promise<OptionGreeks> => getJSON(`/api/options/greeks?${query}`),
  optionsCurve: (query: string): Promise<OptionCurve> => getJSON(`/api/options/curve?${query}`),
  riskScenario: (runId: string, confidence = 0.95): Promise<RiskReport> =>
    getJSON(`/api/risk/scenario?run_id=${encodeURIComponent(runId)}&confidence=${confidence}`),
  screenerQuote: (symbol: string): Promise<ScreenerQuote> =>
    getJSON(`/api/screener/quote?symbol=${encodeURIComponent(symbol)}`),
  screenerNews: (symbol: string, days = 7, limit = 20): Promise<ScreenerNews> =>
    getJSON(`/api/screener/news?symbol=${encodeURIComponent(symbol)}&days=${days}&limit=${limit}`),
  researchCompare: (symbol: string): Promise<ResearchReport> =>
    getJSON(`/api/research/compare?symbol=${encodeURIComponent(symbol)}`),
  researchCapture: (body: ResearchCaptureRequest): Promise<ResearchCaptureResponse> =>
    postJSON('/api/research/cases', body),
  researchCase: (projectId: string): Promise<ResearchCase> =>
    getJSON(`/api/research/cases/${encodeURIComponent(projectId)}`),
  researchProposal: (
    projectId: string,
    body: ResearchProposalRequest,
  ): Promise<ResearchProposalResponse> =>
    postJSON(`/api/research/cases/${encodeURIComponent(projectId)}/proposal`, body),
  researchPilot: (projectId: string): Promise<ResearchLaunchResponse> =>
    postJSON(`/api/research/cases/${encodeURIComponent(projectId)}/launch`, { stage: 'pilot' }),
  researchStatus: (projectId: string): Promise<ResearchCase> =>
    getJSON(`/api/research/cases/${encodeURIComponent(projectId)}/status`),
  researchProgressReport: (projectId: string): Promise<ResearchCaseReport> =>
    getJSON(`/api/research/cases/${encodeURIComponent(projectId)}/report`),
  researchCases: (query: { limit?: number; offset?: number } = {}): Promise<ResearchCasePage> =>
    getJSON(`/api/research/cases?limit=${query.limit ?? 50}&offset=${query.offset ?? 0}`),
  researchEvidenceHub: (projectId: string): Promise<ResearchEvidenceHub> =>
    getJSON(`/api/research/cases/${encodeURIComponent(projectId)}/evidence-hub`),
  researchScorecard: (projectId: string): Promise<ResearchScorecard> =>
    getJSON(`/api/research/cases/${encodeURIComponent(projectId)}/scorecard`),
  researchContextPackets: (
    projectId: string,
    query: { limit?: number; offset?: number } = {},
  ): Promise<ResearchContextPacketPage> =>
    getJSON(
      `/api/research/cases/${encodeURIComponent(projectId)}/context-packets`
        + `?limit=${query.limit ?? 50}&offset=${query.offset ?? 0}`,
    ),
  researchContextPacket: (packetId: string): Promise<ResearchContextPacket> =>
    getJSON(`/api/research/context-packets/${encodeURIComponent(packetId)}`),
  researchNotes: (
    projectId: string,
    query: { limit?: number; offset?: number } = {},
  ): Promise<ResearchNotePage> =>
    getJSON(
      `/api/research/cases/${encodeURIComponent(projectId)}/notes`
        + `?limit=${query.limit ?? 100}&offset=${query.offset ?? 0}`,
    ),
  researchProtocols: (): Promise<ResearchProtocolLibrary> => getJSON('/api/research/protocols'),
  projects: (limit = 50, offset = 0): Promise<ProjectPage> =>
    getJSON(`/api/projects?limit=${limit}&offset=${offset}`),
  project: (id: string, lineageLimit = 100): Promise<ProjectDetail> =>
    getJSON(`/api/projects/${encodeURIComponent(id)}?lineage_limit=${lineageLimit}`),
  createProject: (body: {
    name: string
    hypothesis: string
    falsification_criterion: string
  }): Promise<ProjectSummary> => postJSON('/api/projects', body),
  createStrategyVersion: (
    projectId: string,
    body: {
      strategy_name: string
      source_fingerprint: string
      definition: Record<string, unknown>
      parameter_space: Record<string, unknown>
    },
  ): Promise<StrategyVersion> => postJSON(`/api/projects/${encodeURIComponent(projectId)}/versions`, body),
  createExperiment: (
    projectId: string,
    body: {
      version_id: string
      snapshot_id: string
      universe: string[]
      split_policy: Record<string, unknown>
      costs: Record<string, unknown>
      seeds: Record<string, unknown>
      stage_config: Record<string, unknown>
    },
  ): Promise<ExperimentSpec> => postJSON(`/api/projects/${encodeURIComponent(projectId)}/experiments`, body),
  developmentJobs: (limit = 50, offset = 0): Promise<{ items: ControlJob[]; limit: number; offset: number; has_more: boolean }> =>
    getJSON(`/api/development/jobs?limit=${limit}&offset=${offset}`),
  suitePlan: (projectId: string, experimentId: string, action: SuiteAction): Promise<SuitePlan> =>
    getJSON(`/api/projects/${encodeURIComponent(projectId)}/experiments/${encodeURIComponent(experimentId)}/suite/${encodeURIComponent(action)}/plan`),
  runSuite: (
    projectId: string,
    experimentId: string,
    action: SuiteAction,
    body: { owner_actor?: string; owner_reason?: string },
  ): Promise<SuiteLaunch> =>
    postJSON(`/api/projects/${encodeURIComponent(projectId)}/experiments/${encodeURIComponent(experimentId)}/suite/${encodeURIComponent(action)}/run`, body),
  suiteJob: (jobId: string): Promise<ControlJobDetail> =>
    getJSON(`/api/development/suite-jobs/${encodeURIComponent(jobId)}?event_tail=true`),
  async cancelDevelopmentJob(jobId: string): Promise<SuiteCancelResponse> {
    const res = await fetch(`/api/development/jobs/${encodeURIComponent(jobId)}`, { method: 'DELETE' })
    if (!res.ok) throw new Error(await res.text())
    return (await res.json()) as SuiteCancelResponse
  },
  sealHoldout: (
    projectId: string,
    body: {
      experiment_id: string
      actor: string
      reason: string
      start_date: string
      end_date: string
    },
  ) => postJSON(`/api/projects/${encodeURIComponent(projectId)}/holdouts/seal`, body),
  transitionExperimentStage: (
    projectId: string,
    experimentId: string,
    stage: string,
    body: {
      state: 'ready' | 'queued' | 'running' | 'pass' | 'warning' | 'fail' | 'stale'
      reason: string
    },
  ) => postJSON(`/api/projects/${encodeURIComponent(projectId)}/experiments/${encodeURIComponent(experimentId)}/stages/${encodeURIComponent(stage)}/state`, body),
  freezeDecision: (
    projectId: string,
    experimentId: string,
    body: {
      verdict: 'accept' | 'reject' | 'revise'
      actor: string
      reason: string
      negative_results_acknowledged: true
    },
  ): Promise<DecisionPacket> =>
    postJSON(`/api/projects/${encodeURIComponent(projectId)}/experiments/${encodeURIComponent(experimentId)}/decision`, body),
  agentBrief: (projectId: string, evidenceLimit = 50): Promise<AgentBrief> =>
    getJSON(`/api/projects/${encodeURIComponent(projectId)}/agent-brief?evidence_limit=${evidenceLimit}`),
  evidence: (query: {
    asset?: string | null
    projectId?: string | null
    status?: 'draft' | 'corroborated' | 'rejected' | 'superseded' | null
    asOf?: string | null
    limit?: number
    offset?: number
  } = {}): Promise<EvidencePage> => {
    const params = new URLSearchParams()
    if (query.asset) params.set('asset', query.asset)
    if (query.projectId) params.set('project_id', query.projectId)
    if (query.status) params.set('status', query.status)
    if (query.asOf) params.set('as_of', query.asOf)
    params.set('limit', String(query.limit ?? 50))
    params.set('offset', String(query.offset ?? 0))
    return getJSON(`/api/evidence?${params.toString()}`)
  },
  developmentJob: (jobId: string): Promise<ControlJobDetail> =>
    getJSON(`/api/development/jobs/${encodeURIComponent(jobId)}?event_tail=true`),
  mlStatus: (): Promise<MlServiceStatus> => getJSON('/api/ml/status'),
  mlExperiments: (projectId?: string | null): Promise<MlExperimentPage> => {
    const query = projectId ? `?project_id=${encodeURIComponent(projectId)}` : ''
    return getJSON(`/api/ml/experiments${query}`)
  },
  mlTearsheet(exchangeId: string, timelineOffset = 0): Promise<MlTearSheetProjection> {
    if (!Number.isInteger(timelineOffset) || timelineOffset < 0 || timelineOffset > 1_000_000) {
      throw new RangeError('ML tear-sheet timeline offset must be an integer from 0 to 1,000,000')
    }
    const params = new URLSearchParams({
      feature_limit: '50',
      timeline_limit: '500',
      timeline_offset: String(timelineOffset),
      history_limit: '200',
    })
    return getJSON(
      `/api/ml/exchanges/${encodeURIComponent(exchangeId)}/tear-sheet?${params.toString()}`,
    )
  },
  createMlExperiment: (projectId: string): Promise<MlExperimentJobAccepted> =>
    postJSON('/api/ml/experiments', { project_id: projectId }),
  paperSessions: (): Promise<PaperSession[]> => getJSON('/api/paper/sessions'),
  paperReadiness: (): Promise<PaperReadinessReport> => getJSON('/api/paper/readiness'),
  paperSession: (id: string): Promise<PaperSession> =>
    getJSON(`/api/paper/sessions/${encodeURIComponent(id)}`),
  paperEvents: (id: string, after = 0): Promise<PaperEvent[]> =>
    getJSON(`/api/paper/sessions/${encodeURIComponent(id)}/events?after=${after}`),
}
