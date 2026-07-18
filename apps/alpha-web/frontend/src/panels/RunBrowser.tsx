// Run Browser — the stored-run blotter, live: refetches whenever the activity stream reports a
// store change (whoever caused it — UI, CLI, Claude via MCP). Search + kind filter + sortable
// columns; click selects + broadcasts, Enter/double-click/⏎ button opens the run story.

import type { ColumnDef } from '@tanstack/react-table'
import type { IDockviewPanelProps } from 'dockview-react'
import { useEffect, useMemo, useState } from 'react'

import { api } from '../api/client'
import type { RunListItem } from '../api/types'
import { DataTable } from '../components/DataTable'
import { Placeholder } from '../components/Placeholder'
import { setLinked } from '../context/linked'
import { useActivity } from '../state/activity'
import { fmtTime, shortId } from '../util/format'
import { openRunDetail } from './actions'

const KINDS = ['all', 'runs', 'optim', 'portfolio', 'cross_sectional', 'propfirm', 'forecast']

export function RunBrowser(props: IDockviewPanelProps) {
  const [items, setItems] = useState<RunListItem[] | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [kind, setKind] = useState('all')
  const { runsVersion } = useActivity()

  useEffect(() => {
    let live = true
    // small debounce: bursts of store events collapse into one refetch
    const t = window.setTimeout(() => {
      api
        .runs('?limit=500')
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

  const filtered = useMemo(
    () => (items ?? []).filter((r) => kind === 'all' || r.kind === kind),
    [items, kind],
  )

  const columns = useMemo<ColumnDef<RunListItem, unknown>[]>(
    () => [
      {
        header: 'Run',
        accessorKey: 'run_id',
        cell: (c) => shortId(c.row.original.run_id),
        meta: { className: 'id' },
      },
      {
        header: 'Kind',
        accessorKey: 'kind',
        cell: (c) => <span className="chip kind">{c.row.original.kind}</span>,
      },
      {
        header: 'Command',
        accessorKey: 'command',
        cell: (c) => c.row.original.command ?? '—',
        meta: { className: 'mono' },
      },
      {
        header: 'Label',
        accessorKey: 'label',
        cell: (c) => c.row.original.label ?? '—',
        meta: { className: 'mono' },
      },
      {
        header: 'Verdict',
        accessorKey: 'verdict',
        cell: (c) =>
          c.row.original.verdict ? (
            <span className={`verdict g-${c.row.original.verdict}`}>{c.row.original.verdict}</span>
          ) : (
            <span className="muted">—</span>
          ),
      },
      {
        header: 'Result',
        accessorKey: 'passed',
        cell: (c) =>
          c.row.original.passed === null ? (
            <span className="muted">—</span>
          ) : (
            <span className={`chip ${c.row.original.passed ? 'pass' : 'fail'}`}>
              {c.row.original.passed ? 'PASS' : 'FAIL'}
            </span>
          ),
      },
      {
        header: 'Updated',
        accessorKey: 'mtime',
        cell: (c) => fmtTime(c.row.original.mtime),
        meta: { className: 'num' },
      },
      {
        id: 'open',
        header: '',
        cell: (c) => (
          <button
            className="btn"
            onClick={(e) => {
              e.stopPropagation()
              openRunDetail(props.containerApi, c.row.original.run_id)
            }}
          >
            open ⏎
          </button>
        ),
        enableSorting: false,
      },
    ],
    [props.containerApi],
  )

  function selectRow(run: RunListItem): void {
    setSelected(run.run_id)
    setLinked({ runId: run.run_id, ...(run.symbol ? { symbol: run.symbol } : {}) })
  }

  return (
    <div className="panel">
      <div className="panel-toolbar">
        <span className="title">Runs</span>
        {items ? <span className="count">{filtered.length}</span> : null}
        <input
          className="field toolbar-search"
          placeholder="search…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <select className="field" value={kind} onChange={(e) => setKind(e.target.value)}>
          {KINDS.map((k) => (
            <option key={k} value={k}>
              {k}
            </option>
          ))}
        </select>
      </div>
      <div className="panel-body">
        {error ? (
          <Placeholder big="error">{error}</Placeholder>
        ) : items === null ? (
          <Placeholder>loading…</Placeholder>
        ) : (
          <DataTable
            data={filtered}
            columns={columns}
            globalFilter={query}
            initialSorting={[{ id: 'mtime', desc: true }]}
            onRowClick={selectRow}
            onRowDoubleClick={(r) => openRunDetail(props.containerApi, r.run_id)}
            onRowEnter={(r) => openRunDetail(props.containerApi, r.run_id)}
            rowClass={(r) => (selected === r.run_id ? 'sel' : '')}
            empty={
              <Placeholder big="no runs yet">
                Launch one from the Strategy Lab or CLI, e.g. <code>alpha backtest run SPY</code>
              </Placeholder>
            }
          />
        )}
      </div>
    </div>
  )
}
