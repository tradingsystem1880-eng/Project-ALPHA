import { useEffect, useState } from 'react'

import { getJSON } from './api'
import { LEVELS, levelColor, levelHint } from './model/evidence'
import type { AtlasGraph } from './model/types'
import { ChangeImpact } from './views/ChangeImpact'
import { CodeExplorer } from './views/CodeExplorer'
import { DataLineage } from './views/DataLineage'
import { ResearchLifecycle } from './views/ResearchLifecycle'
import { SystemMap } from './views/SystemMap'

interface Meta {
  stale: boolean
  node_count: number
  edge_count: number
}

const VIEWS = [
  {
    hash: 'lifecycle',
    label: 'Research Lifecycle',
    hint: 'Follow the numbered steps Idea → Promotion; click a step for its files, docs, tests, and AI context.',
  },
  {
    hash: 'system',
    label: 'System Map',
    hint: 'Components with aggregated import arrows; click one to expand its modules, click again to collapse.',
  },
  {
    hash: 'code',
    label: 'Code Explorer',
    hint: 'One component’s internal module graph; ✓n = validating test files.',
  },
  {
    hash: 'lineage',
    label: 'Data Lineage',
    hint: 'The research-entity chain and the artifacts each step produces.',
  },
  {
    hash: 'impact',
    label: 'Change Impact',
    hint: 'Pick a node to see everything that depends on it and which tests exercise a change.',
  },
] as const

function currentView(): string {
  const hash = window.location.hash.replace('#', '')
  return VIEWS.some((v) => v.hash === hash) ? hash : 'lifecycle'
}

function EvidenceLegend() {
  return (
    <div className="legend">
      <span className="legend-title">evidence:</span>
      {LEVELS.filter((level) => level !== 'observed').map((level) => (
        <span key={level} className="legend-chip" title={levelHint(level)}>
          <span className="legend-dot" style={{ background: levelColor(level) }} />
          {level}
        </span>
      ))}
    </div>
  )
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

  const active = VIEWS.find((v) => v.hash === view) ?? VIEWS[0]

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
        {meta && !meta.stale && (
          <span className="counts">
            {meta.node_count.toLocaleString()} nodes · {meta.edge_count.toLocaleString()} edges
          </span>
        )}
        {meta?.stale && (
          <span className="stale">
            graph is stale — regenerate: uv run python -m alpha_atlas.generate
          </span>
        )}
      </header>
      <div className="subbar">
        <span className="hint">{active.hint}</span>
        <EvidenceLegend />
      </div>
      <div className="main">
        {error && <div className="placeholder">Failed to load graph: {error}</div>}
        {!error && !graph && <div className="placeholder">Loading graph…</div>}
        {graph && view === 'lifecycle' && <ResearchLifecycle graph={graph} />}
        {graph && view === 'system' && <SystemMap graph={graph} />}
        {graph && view === 'code' && <CodeExplorer graph={graph} />}
        {graph && view === 'lineage' && <DataLineage graph={graph} />}
        {graph && view === 'impact' && <ChangeImpact graph={graph} />}
      </div>
    </div>
  )
}
