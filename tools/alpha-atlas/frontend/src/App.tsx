import { useEffect, useState } from 'react'

import { getJSON } from './api'
import type { AtlasGraph } from './model/types'
import { CodeExplorer } from './views/CodeExplorer'
import { ResearchLifecycle } from './views/ResearchLifecycle'
import { SystemMap } from './views/SystemMap'

interface Meta {
  stale: boolean
  node_count: number
  edge_count: number
}

const VIEWS = [
  { hash: 'lifecycle', label: 'Research Lifecycle' },
  { hash: 'system', label: 'System Map' },
  { hash: 'code', label: 'Code Explorer' },
] as const

function currentView(): string {
  const hash = window.location.hash.replace('#', '')
  return VIEWS.some((v) => v.hash === hash) ? hash : 'lifecycle'
}

export default function App() {
  const [graph, setGraph] = useState<AtlasGraph | null>(null)
  const [meta, setMeta] = useState<Meta | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [view, setView] = useState(currentView)

  useEffect(() => {
    getJSON<AtlasGraph>('/api/graph').then(setGraph, (e: Error) => setError(e.message))
    getJSON<Meta>('/api/meta').then(setMeta, () => undefined)
    const onHash = () => setView(currentView())
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  return (
    <div className="app">
      <header className="topbar">
        <h1>Alpha Atlas</h1>
        <nav className="nav">
          {VIEWS.map((v) => (
            <a key={v.hash} href={`#${v.hash}`} className={view === v.hash ? 'active' : ''}>
              {v.label}
            </a>
          ))}
        </nav>
        {meta?.stale && (
          <span className="stale">
            graph is stale — regenerate: uv run python -m alpha_atlas.generate
          </span>
        )}
      </header>
      <div className="main">
        {error && <div className="placeholder">Failed to load graph: {error}</div>}
        {!error && !graph && <div className="placeholder">Loading graph…</div>}
        {graph && view === 'lifecycle' && <ResearchLifecycle graph={graph} />}
        {graph && view === 'system' && <SystemMap graph={graph} />}
        {graph && view === 'code' && <CodeExplorer graph={graph} />}
      </div>
    </div>
  )
}
