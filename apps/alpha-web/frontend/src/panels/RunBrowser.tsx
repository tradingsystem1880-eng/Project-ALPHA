// Run Browser — the stored-run blotter. Newest-first, click a row to broadcast its symbol to the
// linked context (and, once Run Detail lands, to open it).

import type { IDockviewPanelProps } from 'dockview-react'
import { useEffect, useState } from 'react'

import { api } from '../api/client'
import type { RunListItem } from '../api/types'
import { setLinked } from '../context/linked'
import { fmtTime, shortId } from '../util/format'
import { Placeholder } from '../components/Placeholder'
import { openRunDetail } from './actions'

export function RunBrowser(props: IDockviewPanelProps) {
  const [items, setItems] = useState<RunListItem[] | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let live = true
    api
      .runs()
      .then((r) => live && setItems(r.items))
      .catch((e: unknown) => live && setError(String(e)))
    return () => {
      live = false
    }
  }, [])

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
                  onClick={() => selectRow(r)}
                  onDoubleClick={() => openDetail(r)}
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
