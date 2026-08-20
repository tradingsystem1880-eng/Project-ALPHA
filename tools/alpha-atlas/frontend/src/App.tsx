import { useEffect, useState } from 'react'

import { getJSON } from './api'
import type { AtlasGraph } from './model/types'
import { ResearchLifecycle } from './views/ResearchLifecycle'

interface Meta {
  stale: boolean
  node_count: number
  edge_count: number
}

export default function App() {
  const [graph, setGraph] = useState<AtlasGraph | null>(null)
  const [meta, setMeta] = useState<Meta | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getJSON<AtlasGraph>('/api/graph').then(setGraph, (e: Error) => setError(e.message))
    getJSON<Meta>('/api/meta').then(setMeta, () => undefined)
  }, [])

  return (
    <div className="app">
      <header className="topbar">
        <h1>Alpha Atlas</h1>
        <span className="hint">Research Lifecycle — click a node for its explanation</span>
        {meta?.stale && (
          <span className="stale">
            graph is stale — regenerate: uv run python -m alpha_atlas.generate
          </span>
        )}
      </header>
      <div className="main">
        {error && <div className="placeholder">Failed to load graph: {error}</div>}
        {!error && !graph && <div className="placeholder">Loading graph…</div>}
        {graph && <ResearchLifecycle graph={graph} />}
      </div>
    </div>
  )
}
