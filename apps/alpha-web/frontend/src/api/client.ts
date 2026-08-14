// Thin typed client over the FastAPI JSON layer. Same-origin (loopback), so no base URL.

import type {
  ActiveResearchGateOverride,
  AgentBrief,
  Candles,
  ChartBundle,
  CommandDef,
  ControlJob,
  ControlJobDetail,
  CryptoAcquisitionRequest,
  CryptoAssetIdentity,
  CryptoAssetMaster,
  CryptoAssetMasters,
  CryptoCatalog,
  CryptoCapabilities,
  CryptoCoverage,
  CryptoEstimate,
  CryptoEstimateRequest,
  CryptoQuality,
  CryptoSnapshotCreate,
  CryptoSnapshotRegister,
  CryptoSnapshotVerify,
  CryptoSnapshotVerifyRequest,
  CryptoStorage,
  CryptoStorageInventory,
  CryptoStorageVerify,
  CryptoCacheClean,
  DecisionPacket,
  EvidencePage,
  EquitySeries,
  ExperimentSpec,
  ForecastOrigins,
  ForecastPaths,
  ForecastSeries,
  JobDetail,
  MlExperimentPage,
  MlExperimentPreflight,
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
  ProviderCheckReceipt,
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
  ResearchDatasetPage,
  ResearchDecisionView,
  ResearchEvidenceHub,
  ResearchNotePage,
  ResearchProtocolLibrary,
  ResearchScorecard,
  ResearchLaunchResponse,
  ResearchProposalRequest,
  ResearchProposalOptionsV1,
  ResearchProposalResponse,
  ResearchReport,
  FigureCatalogue,
  RunComparison,
  FigureMetadata,
  RiskReport,
  RunContextV1,
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

export function runContextForProject(projectId: string | null): RunContextV1 {
  return projectId
    ? { schema_version: 1, kind: 'governed_project', project_id: projectId }
    : { schema_version: 1, kind: 'standalone_sandbox' }
}

async function getJSON<T>(url: string): Promise<T> {
  const res = await fetch(url)
  if (!res.ok) throw await responseError(res)
  return (await res.json()) as T
}

async function responseError(res: Response): Promise<Error> {
  let message = 'The Workstation request failed.'
  let recovery = ''
  let fields = ''
  let requestId = res.headers.get('x-request-id') ?? ''
  try {
    const parsed: unknown = await res.json()
    if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
      const error = parsed as Record<string, unknown>
      if (typeof error.message === 'string' && error.message) message = error.message
      if (typeof error.recovery_action === 'string') recovery = error.recovery_action
      if (typeof error.request_id === 'string') requestId = error.request_id
      if (Array.isArray(error.field_errors)) {
        fields = error.field_errors
          .flatMap((item) => {
            if (!item || typeof item !== 'object' || Array.isArray(item)) return []
            const field = (item as Record<string, unknown>).field
            const fieldMessage = (item as Record<string, unknown>).message
            return typeof field === 'string' && typeof fieldMessage === 'string'
              ? [`${field}: ${fieldMessage}`]
              : []
          })
          .join('; ')
      }
    }
  } catch {
    // The stable API contract was unavailable; never relay an untrusted raw response to the DOM.
  }
  const status = `${res.status}${res.statusText ? ` ${res.statusText}` : ''}`
  return new Error(
    `${status} — ${message}${fields ? ` Fields: ${fields}.` : ''}${recovery ? ` ${recovery}` : ''}${requestId ? ` [request ${requestId}]` : ''}`,
  )
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

export type OwnerActionType =
  | 'screen_source_claim'
  | 'reject_source_claim'
  | 'revise_source_claim'
  | 'freeze_source_pack'
  | 'approve_exploration'
  | 'reject_exploration'
  | 'revise_exploration'
  | 'launch_d1'
  | 'approve_confirmation'
  | 'reject_confirmation'
  | 'launch_d2'
  | 'record_final_disposition'

export interface OwnerCredentialOptions {
  challenge_id: string
  expires_at: string
  binding?: Record<string, unknown>
  public_key: Record<string, unknown>
}

export interface OwnerActionChallengeRequest {
  action_type: OwnerActionType
  project_id: string
  artifact_hash: string
  expected_case_revision: string
  consequence_summary: string
  reason: string
  payload: Record<string, unknown>
}

export interface OwnerActionResult {
  authorization: Record<string, unknown>
  result: Record<string, unknown>
}

export interface LiteratureCandidate {
  candidate_id: string
  title: string
  provider: string
  doi: string | null
  year: number | null
  authors: string[]
  open_access_url: string | null
  access_state: 'direct_pdf' | 'landing_page' | 'metadata_only' | 'unavailable'
  relevance_explanation: string
  matched_concepts: string[]
  retracted: boolean | null
}

export interface LiteratureDiscoveryResult {
  discovery_id: string
  query: string
  candidates: LiteratureCandidate[]
  receipt: Record<string, unknown>
}

export interface LiteratureAcquisitionResult {
  source: Record<string, unknown>
  document: {
    extraction_id: string
    status: 'extracted' | 'encrypted' | 'image_only' | 'truncated' | 'parser_failed'
    page_count: number
    character_count: number
    warnings: string[]
    artifact: Record<string, unknown>
  }
  acquisition: Record<string, unknown>
}

async function postJSON<T>(url: string, body: unknown): Promise<T> {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw await responseError(res)
  return (await res.json()) as T
}

export const api = {
  ownerRegistrationOptions: (token: string): Promise<OwnerCredentialOptions> =>
    postJSON('/api/owner-auth/enrollment/options', { token }),
  ownerRegistrationFinish: (
    token: string,
    challengeId: string,
    credential: Record<string, unknown>,
  ): Promise<Record<string, unknown>> =>
    postJSON('/api/owner-auth/enrollment/finish', {
      token,
      challenge_id: challengeId,
      credential,
    }),
  ownerActionChallenge: (
    body: OwnerActionChallengeRequest,
  ): Promise<OwnerCredentialOptions> => postJSON('/api/owner-auth/actions/challenge', body),
  ownerActionPerform: (
    challengeId: string,
    credential: Record<string, unknown>,
    payload: Record<string, unknown>,
  ): Promise<OwnerActionResult> => postJSON('/api/owner-auth/actions/perform', {
    challenge_id: challengeId,
    credential,
    payload,
  }),
  runs: (query = ''): Promise<RunList> => getJSON(`/api/runs${query}`),
  run: (id: string): Promise<RunDetail> => getImmutableJSON(`/api/runs/${id}`),
  chartBundle(id: string, limit = 2_000, start?: string | null, end?: string | null): Promise<ChartBundle> {
    const params = new URLSearchParams({ limit: String(limit) })
    if (start) params.set('start', start)
    if (end) params.set('end', end)
    return getImmutableJSON(`/api/runs/${id}/chart-bundle?${params.toString()}`)
  },
  compareRuns: (runIds: string[]): Promise<RunComparison> =>
    postJSON('/api/v3/runs/compare', { run_ids: runIds }),
  figures: (id: string): Promise<FigureCatalogue> => getJSON(`/api/runs/${id}/figures`),
  figureMetadata: (id: string, figureId: string, fmt: 'svg' | 'png' = 'svg'): Promise<FigureMetadata> =>
    getJSON(`/api/runs/${id}/figures/${figureId}?fmt=${fmt}`),
  // Content-addressed: the key makes the URL immutable, so the browser caches it for good.
  figureImageUrl: (id: string, figureId: string, key: string, fmt: 'svg' | 'png' = 'svg'): string =>
    `/api/runs/${id}/figures/${figureId}/image?fmt=${fmt}&key=${key}`,
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
  cryptoCatalog: (): Promise<CryptoCatalog> => getJSON('/api/crypto-data/catalog'),
  cryptoCapabilities: (): Promise<CryptoCapabilities> =>
    getJSON('/api/crypto-data/capabilities'),
  cryptoStorage: (): Promise<CryptoStorage> => getJSON('/api/crypto-data/storage'),
  cryptoStorageInventory: (): Promise<CryptoStorageInventory> =>
    getJSON('/api/crypto-data/storage/inventory'),
  cryptoStorageVerify: (): Promise<CryptoStorageVerify> =>
    postJSON('/api/crypto-data/storage/verify', {}),
  cryptoCacheClean: (): Promise<CryptoCacheClean> =>
    postJSON('/api/crypto-data/storage/cache/clean', { confirm: true }),
  cryptoCoverage: (): Promise<CryptoCoverage> => getJSON('/api/crypto-data/coverage'),
  cryptoAsset: (symbol: string, asOf: string): Promise<CryptoAssetIdentity> => {
    const params = new URLSearchParams({ as_of: asOf })
    return getJSON(`/api/crypto-data/assets/${encodeURIComponent(symbol)}?${params.toString()}`)
  },
  cryptoAssetContract: (
    network: string,
    contractAddress: string,
    assetMasterVersion: string,
    asOf: string,
  ): Promise<CryptoAssetIdentity> => {
    const params = new URLSearchParams({
      asset_master_version: assetMasterVersion,
      as_of: asOf,
    })
    return getJSON(
      `/api/crypto-data/assets/contracts/${encodeURIComponent(network)}/${encodeURIComponent(contractAddress)}?${params.toString()}`,
    )
  },
  cryptoAssetMasters: (): Promise<CryptoAssetMasters> =>
    getJSON('/api/crypto-data/asset-masters'),
  cryptoAssetMasterCreate: (
    coingeckoManifestId: string,
    geckoterminalManifestIds: string[],
  ): Promise<CryptoAssetMaster> =>
    postJSON('/api/crypto-data/asset-masters', {
      coingecko_manifest_id: coingeckoManifestId,
      geckoterminal_manifest_ids: geckoterminalManifestIds,
    }),
  cryptoAssetMasterVerify: (version: string): Promise<CryptoAssetMaster> =>
    postJSON(`/api/crypto-data/asset-masters/${encodeURIComponent(version)}/verify`, {}),
  cryptoQuality: (manifestId: string): Promise<CryptoQuality> =>
    getJSON(`/api/crypto-data/quality/${encodeURIComponent(manifestId)}`),
  cryptoEstimate: (body: CryptoEstimateRequest): Promise<CryptoEstimate> =>
    postJSON('/api/crypto-data/estimate', body),
  cryptoAcquire: (
    body: CryptoAcquisitionRequest,
  ): Promise<{ job_id: string; status: string; session_id?: string | null }> =>
    postJSON('/api/crypto-data/acquisitions', body),
  cryptoSnapshotCreate: (
    manifestIds: string[],
    assetMasterVersion = 'reviewed-native-v1',
  ): Promise<CryptoSnapshotCreate> =>
    postJSON('/api/crypto-data/snapshots', {
      manifest_ids: manifestIds,
      asset_master_version: assetMasterVersion,
    }),
  cryptoSnapshotVerify: (
    snapshotId: string,
    body: CryptoSnapshotVerifyRequest,
  ): Promise<CryptoSnapshotVerify> =>
    postJSON(`/api/crypto-data/snapshots/${encodeURIComponent(snapshotId)}/verify`, body),
  cryptoSnapshotRegister: (
    snapshotId: string,
    symbol: string,
  ): Promise<CryptoSnapshotRegister> =>
    postJSON(`/api/crypto-data/snapshots/${encodeURIComponent(snapshotId)}/register`, { symbol }),
  providerCheck: (providerId: string): Promise<ProviderCheckReceipt> =>
    postJSON(`/api/providers/${encodeURIComponent(providerId)}/check`, {}),
  system: (): Promise<SystemStatus> => getJSON('/api/system'),
  jobs: (): Promise<PaperJobSummary[]> => getJSON('/api/jobs'),
  job: (id: string): Promise<JobDetail> => getJSON(`/api/jobs/${id}`),
  async launch(
    command: string,
    args: string,
    runContext?: RunContextV1,
  ): Promise<{ job_id: string; status: string; session_id?: string | null }> {
    const res = await fetch('/api/jobs', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ command, args, ...(runContext ? { run_context: runContext } : {}) }),
    })
    if (!res.ok) throw await responseError(res)
    return (await res.json()) as { job_id: string; status: string; session_id?: string | null }
  },
  cancel: (id: string): Promise<Response> => fetch(`/api/jobs/${id}`, { method: 'DELETE' }),
  streamUrl: (id: string): string => `/api/jobs/${id}/stream`,
  workspaces: (): Promise<WorkspaceMeta[]> => getJSON('/api/workspaces'),
  getWorkspace: (slug: string): Promise<WorkspaceDoc> => getJSON(`/api/workspaces/${slug}`),
  // The slug is derived server-side from the name, so there is nothing to pass here.
  async saveWorkspace(body: {
    name: string
    linked_context: unknown
  }): Promise<{ slug: string; name: string }> {
    const res = await fetch('/api/workspaces', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body),
    })
    if (!res.ok) throw await responseError(res)
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
  researchCompare: (symbol: string, runContext: RunContextV1): Promise<ResearchReport> => {
    const params = new URLSearchParams({
      symbol,
      context_kind: runContext.kind,
    })
    if (runContext.kind === 'governed_project') params.set('project_id', runContext.project_id)
    return getJSON(`/api/research/compare?${params.toString()}`)
  },
  researchCapture: (body: ResearchCaptureRequest): Promise<ResearchCaptureResponse> =>
    postJSON('/api/research/cases', body),
  researchCase: (projectId: string): Promise<ResearchCase> =>
    getJSON(`/api/research/cases/${encodeURIComponent(projectId)}`),
  researchProposalOptions: (projectId: string): Promise<ResearchProposalOptionsV1> =>
    getJSON(`/api/research/cases/${encodeURIComponent(projectId)}/proposal-options`),
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
  researchLiteratureDiscover: (
    projectId: string,
    body: {
      query: string
      unpaywall_email: string
      max_candidates?: number
      max_full_texts?: number
    },
  ): Promise<LiteratureDiscoveryResult> =>
    postJSON(`/api/research/cases/${encodeURIComponent(projectId)}/literature/discover`, body),
  researchLiteratureAcquire: (
    projectId: string,
    body: { discovery_id: string; candidate_id: string },
  ): Promise<LiteratureAcquisitionResult> =>
    postJSON(`/api/research/cases/${encodeURIComponent(projectId)}/literature/acquire`, body),
  researchScorecard: (projectId: string): Promise<ResearchScorecard> =>
    getJSON(`/api/research/cases/${encodeURIComponent(projectId)}/scorecard`),
  researchDecisionView: (projectId: string): Promise<ResearchDecisionView> =>
    getJSON(`/api/research/cases/${encodeURIComponent(projectId)}/decision-view`),
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
  researchDatasets: (
    query: { symbol?: string; limit?: number; offset?: number } = {},
  ): Promise<ResearchDatasetPage> => {
    const params = new URLSearchParams({
      limit: String(query.limit ?? 100),
      offset: String(query.offset ?? 0),
    })
    if (query.symbol) params.set('symbol', query.symbol)
    return getJSON(`/api/research/datasets?${params.toString()}`)
  },
  researchGateOverrides: (): Promise<ActiveResearchGateOverride[]> =>
    getJSON('/api/research-gate-overrides'),
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
    if (!res.ok) throw await responseError(res)
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
  mlExperimentPreflight: (projectId: string): Promise<MlExperimentPreflight> =>
    getJSON(`/api/ml/experiments/preflight?project_id=${encodeURIComponent(projectId)}`),
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
