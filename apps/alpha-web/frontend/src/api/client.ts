// Thin typed client over the FastAPI JSON layer. Same-origin (loopback), so no base URL.

import type {
  AppsManifest,
  Candles,
  CommandDef,
  EquitySeries,
  ForecastSeries,
  JobDetail,
  JobSummary,
  OptionCurve,
  OptionGreeks,
  RunDetail,
  RunList,
  StrategyDef,
  TradeRow,
  WorkspaceDoc,
  WorkspaceMeta,
} from './types'

async function getJSON<T>(url: string): Promise<T> {
  const res = await fetch(url)
  if (!res.ok) {
    const detail = await res.text().catch(() => '')
    throw new Error(`${res.status} ${res.statusText}${detail ? ` — ${detail}` : ''}`)
  }
  return (await res.json()) as T
}

export const api = {
  runs: (query = ''): Promise<RunList> => getJSON(`/api/runs${query}`),
  run: (id: string): Promise<RunDetail> => getJSON(`/api/runs/${id}`),
  equity: (id: string): Promise<EquitySeries> => getJSON(`/api/runs/${id}/equity`),
  trades: (id: string): Promise<TradeRow[]> => getJSON(`/api/runs/${id}/trades`),
  forecast: (id: string): Promise<ForecastSeries> => getJSON(`/api/runs/${id}/forecast`),
  tearsheetUrl: (id: string): string => `/api/runs/${id}/tearsheet`,
  candles: (symbol: string, query = ''): Promise<Candles> =>
    getJSON(`/api/candles/${encodeURIComponent(symbol)}${query}`),
  strategies: (): Promise<StrategyDef[]> => getJSON('/api/strategies'),
  commands: (): Promise<CommandDef[]> => getJSON('/api/commands'),
  symbols: (): Promise<{ symbols: string[] }> => getJSON('/api/symbols'),
  apps: (): Promise<AppsManifest> => getJSON('/api/apps'),
  jobs: (): Promise<JobSummary[]> => getJSON('/api/jobs'),
  job: (id: string): Promise<JobDetail> => getJSON(`/api/jobs/${id}`),
  async launch(command: string, args: string): Promise<{ job_id: string; status: string }> {
    const res = await fetch('/api/jobs', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ command, args }),
    })
    if (!res.ok) throw new Error(await res.text())
    return (await res.json()) as { job_id: string; status: string }
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
}
