import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { RunInvestigation } from '../../src/panels/RunInvestigation'
import { investigations } from '../../src/api/investigations'

const runId = 'run-fixture'
const parentId = 'parent-investigation'
const childId = 'child-investigation'
const createdId = 'created-investigation'

function investigation(id: string, status: 'completed' | 'ready' = 'completed') {
  return {
    id, run_id: runId, question: id, cutoff: '2020-01-02', parent_id: null,
    status, error: null, active_job_id: null, requests_remaining: 9, turns_remaining: 3,
    can_resume: false, can_followup: false, comparison_draft: null,
    acquisition_status: 'not_started', comparison_child_id: null,
    progress: [], receipts: [], report: null,
  }
}

const parent = investigation(parentId)
const child = investigation(childId, 'ready')
const created = investigation(createdId, 'ready')
const cases = new Map([[parentId, parent], [childId, child], [createdId, created]])
const held = new Set<string>([parentId])
const heldPolls = new Set<string>()
const heldShows = new Map<string, Array<Promise<unknown>>>()
const pending = new Map<string, Array<(response: Response) => void>>()
let root: Root | null = null

// Capture only: return the real API promise without adding a reaction ahead of poll's await.
const show = investigations.show
investigations.show = id => {
  const isHeld = held.has(id) || heldPolls.has(id)
  const request = show(id)
  if (isHeld) {
    const requests = heldShows.get(id) ?? []
    requests.push(request)
    heldShows.set(id, requests)
  }
  return request
}

function json(value: unknown): Response {
  return new Response(JSON.stringify(value), {headers: {'Content-Type': 'application/json'}})
}

function waitFor(key: string): Promise<Response> {
  return new Promise(resolve => {
    const resolvers = pending.get(key) ?? []
    resolvers.push(resolve)
    pending.set(key, resolvers)
  })
}

function resolve(key: string, outcome: 'success' | 'error' = 'success'): void {
  const resolver = pending.get(key)?.shift()
  if (!resolver) throw new Error(`No held ${key} request to resolve`)
  if (outcome === 'error') resolver(new Response('stale parent poll failure', {status: 503}))
  else resolver(json(key === 'turn' ? {job_id: 'new-job', status: 'running'} : key === 'create' ? created : cases.get(key) ?? parent))
}

async function resolvePoll(key: string, outcome: 'success' | 'error' = 'success'): Promise<void> {
  const request = heldShows.get(key)?.shift()
  if (!request) throw new Error(`No held ${key} poll request to settle`)
  resolve(key, outcome)
  // Registered after poll's await; this fixture's obsolete poll continuation is synchronous.
  await request.then(() => undefined, () => undefined)
}

function responseForKey(key: string): Promise<Response> {
  if (heldPolls.has(key) || held.delete(key)) return waitFor(key)
  if (key === 'eligibility') return Promise.resolve(json({run_id: runId, eligible: true, cutoff: '2020-01-02', reason: null}))
  if (key === 'list') return Promise.resolve(json([parent, child]))
  if (key === 'turn') return Promise.resolve(json({job_id: 'new-job', status: 'running'}))
  return Promise.resolve(json(cases.get(key) ?? parent))
}

window.fetch = ((input: RequestInfo | URL, init?: RequestInit) => {
  const url = new URL(typeof input === 'string' ? input : input instanceof Request ? input.url : input.href, 'http://localhost')
  const method = init?.method ?? 'GET'
  const path = url.pathname
  if (path.includes('/eligibility/')) return responseForKey('eligibility')
  if (path === '/api/investigations' && method === 'GET') return responseForKey('list')
  if (path === '/api/investigations' && method === 'POST') return responseForKey('create')
  if (path.endsWith('/turns')) return responseForKey('turn')
  const id = path.split('/').at(-1) ?? ''
  return responseForKey(id)
}) as typeof fetch

declare global {
  interface Window {
    IS_REACT_ACT_ENVIRONMENT: boolean
    __panelRace: {
      ready: boolean
      ids: {parent: string; child: string; created: string}
      holdNext(key: string): void
      holdPolls(id: string): void
      pendingCount(key: string): number
      select(id: string): Promise<void>
      selectAndResolve(id: string, key: string, outcome?: 'success' | 'error'): Promise<void>
      resolve(key: string, outcome?: 'success' | 'error'): Promise<void>
      startAndResolve(key: string, outcome?: 'success' | 'error'): Promise<void>
      unmountAndResolve(key: string): Promise<void>
    }
  }
}

window.IS_REACT_ACT_ENVIRONMENT = true
const container = document.createElement('div')
document.body.append(container)
root = createRoot(container)
window.__panelRace = {
  ready: false,
  ids: {parent: parentId, child: childId, created: createdId},
  holdNext(key) { held.add(key) },
  holdPolls(id) { heldPolls.add(id) },
  pendingCount(key) { return pending.get(key)?.length ?? 0 },
  async select(id) {
    await act(async () => {
      const select = document.querySelector<HTMLSelectElement>('[aria-label="Saved investigations"]')
      if (!select) throw new Error('Saved investigations selector is not mounted')
      select.value = id
      select.dispatchEvent(new Event('change', {bubbles: true}))
    })
  },
  async selectAndResolve(id, key, outcome = 'success') {
    await act(async () => {
      const select = document.querySelector<HTMLSelectElement>('[aria-label="Saved investigations"]')
      if (!select) throw new Error('Saved investigations selector is not mounted')
      select.value = id
      select.dispatchEvent(new Event('change', {bubbles: true}))
      await resolvePoll(key, outcome)
    })
  },
  async resolve(key, outcome = 'success') {
    await act(async () => {
      await resolvePoll(key, outcome)
    })
  },
  async startAndResolve(key, outcome = 'success') {
    await act(async () => {
      const button = [...document.querySelectorAll('button')].find(item => item.textContent?.trim() === 'Start new investigation')
      if (!button) throw new Error('Start new investigation button is not mounted')
      button.click()
      resolve('create')
      await Promise.resolve()
      await Promise.resolve()
      await resolvePoll(key, outcome)
    })
  },
  async unmountAndResolve(key) {
    await act(async () => {
      root?.unmount()
      root = null
      await resolvePoll(key)
    })
  },
}

act(() => { root?.render(<RunInvestigation runId={runId} />) })
window.__panelRace.ready = true
