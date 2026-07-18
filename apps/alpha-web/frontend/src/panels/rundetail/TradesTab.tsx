// Trades tab: the realized trade log, uncapped — sortable and virtualized past ~200 rows.

import type { ColumnDef } from '@tanstack/react-table'
import { useMemo, useState } from 'react'

import type { TradeRow } from '../../api/types'
import { DataTable } from '../../components/DataTable'
import { fmtNum } from '../../util/format'
import { Section } from './common'

const NUM_COLS = ['quantity', 'entry_price', 'exit_price', 'realized_pnl', 'realized_return']

export function TradesTab({ trades }: { trades: TradeRow[] }) {
  const [query, setQuery] = useState('')

  const columns = useMemo<ColumnDef<TradeRow, unknown>[]>(() => {
    const cols: ColumnDef<TradeRow, unknown>[] = [
      { header: 'instrument', accessorKey: 'instrument_id', meta: { className: 'mono' } },
      { header: 'side', accessorKey: 'side', meta: { className: 'mono' } },
    ]
    for (const key of NUM_COLS) {
      cols.push({
        header: key.replace(/_/g, ' '),
        accessorKey: key,
        cell: (c) => {
          const v = c.row.original[key]
          if (typeof v !== 'number') return '—'
          const neg = v < 0 && (key === 'realized_pnl' || key === 'realized_return')
          return <span className={neg ? 'neg' : ''}>{fmtNum(v, key === 'realized_return' ? 4 : 2)}</span>
        },
        meta: { className: 'num' },
      })
    }
    cols.push(
      {
        header: 'entry',
        accessorKey: 'entry_ts',
        cell: (c) => String(c.row.original.entry_ts ?? '—').slice(0, 10),
        meta: { className: 'mono' },
      },
      {
        header: 'exit',
        accessorKey: 'exit_ts',
        cell: (c) => String(c.row.original.exit_ts ?? '—').slice(0, 10),
        meta: { className: 'mono' },
      },
    )
    return cols
  }, [])

  if (!trades.length)
    return (
      <Section title="Trades">
        <div className="muted">
          No discrete trades recorded — position-level strategies rebalance holdings rather than
          opening/closing round trips; read the equity curve instead.
        </div>
      </Section>
    )

  return (
    <Section
      title={`Trades · ${trades.length}`}
      right={
        <input
          className="field toolbar-search"
          placeholder="filter…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      }
    >
      <DataTable data={trades} columns={columns} globalFilter={query} />
    </Section>
  )
}
