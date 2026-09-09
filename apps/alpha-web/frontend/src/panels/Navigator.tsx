// Navigator dock (spec 2026-09-01 §4.2 item 4): one tree of Strategies · Backtests · Research
// cases · Data · Scripts · Paper sandbox, filed by the server's `market` field. Replaces the
// Library rail. Clicking a backtest opens its report document; a strategy or research case sets
// the linked project.

import { useEffect, useState } from 'react'

import { api } from '../api/client'
import type { CryptoStorage, PaperSession, ProjectSummary, RunListItem, StrategyDef } from '../api/types'
import { setLinked } from '../context/linked'
import { pairsByVenue, useStoredVenues } from '../context/storedQuotes'
import { dockOf } from '../shell/documents'
import { Icon } from '../shell/icons'
import { useActivityField, useAreaVersion } from '../state/activity'
import { useSettings } from '../state/settings'
import { storageRow } from './dataManagerModel'
import { MARKET_UNKNOWN_LABEL, navigatorTree, type NavigatorLeaf } from './navigatorModel'

export function Navigator({ onOpenRun }: { onOpenRun: (runId: string, title: string) => void }) {
  const { profile } = useSettings()
  const venues = useStoredVenues()
  const [showAll, setShowAll] = useState(false)
  const [tab, setTab] = useState<string>('Common')
  const [runs, setRuns] = useState<RunListItem[]>([])
  const [projects, setProjects] = useState<ProjectSummary[]>([])
  const [strategies, setStrategies] = useState<StrategyDef[]>([])
  const [sessions, setSessions] = useState<PaperSession[]>([])
  const [storage, setStorage] = useState<CryptoStorage | null>(null)
  const [error, setError] = useState<string | null>(null)
  const storeRevision = useActivityField('runsVersion')
  const controlVersion = useAreaVersion('control')
  const paperVersion = useAreaVersion('paper')

  useEffect(() => {
    let live = true
    setError(null)
    Promise.all([
      api.runs('?limit=500'),
      api.projects(100, 0),
      api.strategies(),
      api.paperSessions(),
      api.cryptoStorage().catch(() => null),
    ])
      .then(([runList, projectPage, strategyList, sessionList, storageStatus]) => {
        if (!live) return
        setRuns(runList.items)
        setProjects(projectPage.items as ProjectSummary[])
        setStrategies(strategyList)
        setSessions(sessionList)
        setStorage(storageStatus)
      })
      .catch((cause) => live && setError(String(cause)))
    return () => {
      live = false
    }
  }, [storeRevision, controlVersion, paperVersion])

  const groups = navigatorTree({
    profile,
    showAll,
    runs,
    projects,
    strategies,
    sessions,
    storage: storageRow(storage),
    pairsByVenue: pairsByVenue(venues),
  })

  const activate = (leaf: NavigatorLeaf) => {
    if (leaf.action.kind === 'run') onOpenRun(leaf.action.runId, leaf.label)
    else if (leaf.action.kind === 'project') setLinked({ projectId: leaf.action.projectId })
    else if (leaf.action.kind === 'symbol') setLinked({ symbol: leaf.action.symbol })
  }

  const leafButton = (leaf: NavigatorLeaf) => (
    <li key={leaf.id} role="treeitem" aria-selected={false} className={`tone-${leaf.tone}`}>
      <button
        type="button"
        className="tree-leaf"
        onClick={() => activate(leaf)}
        disabled={leaf.action.kind === 'none'}
        title={leaf.sub ? `${leaf.label} · ${leaf.sub}` : leaf.label}
      >
        <Icon name="doc" size={12} />
        <span className="tree-leaf-label">{leaf.label}</span>
        {leaf.sub ? <span className="tree-leaf-sub mono">{leaf.sub}</span> : null}
      </button>
    </li>
  )

  return (
    <div className="dock-panel navigator">
      <div className="dock-toolbar">
        <label className="settings-row">
          <input type="checkbox" checked={showAll} onChange={(event) => setShowAll(event.target.checked)} />
          <span>Show all markets</span>
        </label>
      </div>
      {error ? <p className="muted">{error}</p> : null}
      <nav className="report-tree navigator-tree" tabIndex={0}>
        <ul role="tree" aria-label="Navigator">
          {groups.map((group) => (
            <li key={group.label} role="treeitem" aria-expanded="true" className="tree-group">
              <span className="tree-group-label">
                <span className="tree-caret" aria-hidden="true">▾</span>
                <Icon name="folder" size={12} />
                {group.label}
              </span>
              <ul role="group">
                {group.leaves.length === 0 && group.unknown.length === 0 ? (
                  <li role="treeitem" aria-selected={false} className="tree-leaf empty">
                    none
                  </li>
                ) : null}
                {group.leaves.map(leafButton)}
                {group.unknown.length ? (
                  <li role="treeitem" aria-expanded="true" className="tree-group">
                    <span className="tree-group-label">
                      <span className="tree-caret" aria-hidden="true">▾</span>
                      <Icon name="folder" size={12} />
                      {MARKET_UNKNOWN_LABEL}
                    </span>
                    <ul role="group">{group.unknown.map(leafButton)}</ul>
                  </li>
                ) : null}
              </ul>
            </li>
          ))}
        </ul>
      </nav>
      <nav className="rd-tabs dock-tabs" role="tablist" aria-label="Navigator tabs">
        {dockOf('Navigator').tabs.map((item) => (
          <button
            key={item}
            type="button"
            role="tab"
            aria-selected={tab === item}
            className={`rd-tab${tab === item ? ' active' : ''}`}
            disabled={item === 'Favorites'}
            title={item === 'Favorites' ? 'Favorites are not stored anywhere yet' : 'Everything the store holds, filed by market'}
            onClick={() => setTab(item)}
          >
            {item}
          </button>
        ))}
      </nav>
    </div>
  )
}
