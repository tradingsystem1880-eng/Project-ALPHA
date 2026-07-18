// Run Browser — the stored-run blotter, live: refetches whenever the activity stream reports a
// store change (whoever caused it — UI, CLI, Claude via MCP). Click selects + broadcasts; Enter
// or double-click opens the run story.

import type { IDockviewPanelProps } from 'dockview-react'
import { useEffect, useState } from 'react'

import { api } from '../api/client'
import type { RunListItem } from '../api/types'
import { setLinked } from '../context/linked'
import { useActivity } from '../state/activity'
import { fmtTime, shortId } from '../util/format'
import { Placeholder } from '../components/Placeholder'
import { openRunDetail } from './actions'

export function RunBrowser(props: IDockviewPanelProps) {
  const [items, setItems] = useState<RunListItem[] | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const { runsVersion } = useActivity()

  useEffect(() => {
    let live = true
    // small debounce: bursts of store events collapse into one refetch
    const t = window.setTimeout(() => {
      api
        .runs()
        .then((r) => {
          if (!live) return
          setItems(r.items)
          setError(null)
        })
        .catch((e: unknown) => live && setError(String(e)))
    }, 150)
    return () => {
      live = false
      window.clearTimeout(t)
    }
  }, [runsVersion])

  function selectRow(run: RunListItem): void {
    setSelected(run.run_id)
    setLinked({ runId: run.run_id, ...(run.symbol ? { symbol: run.symbol } : {}) })
  }

  function openDetail(run: RunListItem): void {
    openRunDetail(props.containerApi, run.run_id)
  }

  return (
    <div className="panel">
      <div className="panel-toolbar">
        <span className="title">Runs</span>
        {items ? <span className="count">{items.length}</span> : null}
      </div>
      <div className="panel-body">
        {error ? (
          <Placeholder big="error">{error}</Placeholder>
        ) : items === null ? (
          <Placeholder>loading…</Placeholder>
        ) : items.length === 0 ? (
          <Placeholder big="no runs yet">
            Launch one from the console or CLI, e.g. <code>alpha backtest run SPY</code>
          </Placeholder>
        ) : (
          <table className="blotter">
            <thead>
              <tr>
                <th>Run</th>
                <th>Kind</th>
                <th>Command</th>
                <th>Label</th>
                <th>Verdict</th>
                <th>Result</th>
                <th className="r">Updated</th>
              </tr>
            </thead>
            <tbody>
              {items.map((r) => (
                <tr
                  key={r.run_id}
                  className={selected === r.run_id ? 'sel' : ''}
                  tabIndex={0}
                  onClick={() => selectRow(r)}
                  onDoubleClick={() => openDetail(r)}
                  onKeyDown={(e) => e.key === 'Enter' && openDetail(r)}
                >
                  <td className="id">{shortId(r.run_id)}</td>
                  <td>
                    <span className="chip kind">{r.kind}</span>
                  </td>
                  <td className="mono">{r.command ?? '—'}</td>
                  <td className="mono">{r.label ?? '—'}</td>
                  <td>
                    {r.verdict ? (
                      <span className={`verdict g-${r.verdict}`}>{r.verdict}</span>
                    ) : (
                      <span className="muted">—</span>
                    )}
                  </td>
                  <td>
                    {r.passed === null ? (
                      <span className="muted">—</span>
                    ) : (
                      <span className={`chip ${r.passed ? 'pass' : 'fail'}`}>
                        {r.passed ? 'PASS' : 'FAIL'}
                      </span>
                    )}
                  </td>
                  <td className="num">{fmtTime(r.mtime)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
