// The workstation table: headless TanStack core rendered as the same `.blotter` markup the
// hand-rolled tables use, plus click-to-sort headers, an optional text filter, and row
// virtualization past ~200 rows (so trade logs render uncapped).

import {
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
  type Row,
  type SortingState,
} from '@tanstack/react-table'
import { useVirtualizer } from '@tanstack/react-virtual'
import { useRef, useState, type ReactNode } from 'react'

const VIRTUALIZE_ABOVE = 200
const ROW_ESTIMATE = 27

// per-row lowercased haystack for the global filter, built once per row object (WeakMap keyed
// on the row datum) instead of stringifying every cell on every keystroke
const HAYSTACKS = new WeakMap<object, string>()

interface Props<T> {
  data: T[]
  columns: ColumnDef<T, unknown>[]
  /** Free-text filter value (matches any cell, case-insensitive); omit to disable. */
  globalFilter?: string
  onRowClick?: (row: T) => void
  onRowDoubleClick?: (row: T) => void
  onRowEnter?: (row: T) => void
  rowClass?: (row: T) => string
  rowCurrent?: (row: T) => boolean
  /** Rendered when the (filtered) table is empty. */
  empty?: ReactNode
  initialSorting?: SortingState
}

export function DataTable<T>({
  data,
  columns,
  globalFilter = '',
  onRowClick,
  onRowDoubleClick,
  onRowEnter,
  rowClass,
  rowCurrent,
  empty,
  initialSorting = [],
}: Props<T>) {
  const [sorting, setSorting] = useState<SortingState>(initialSorting)
  const scrollRef = useRef<HTMLDivElement>(null)

  const table = useReactTable({
    data,
    columns,
    state: { sorting, globalFilter },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    globalFilterFn: (row, _columnId, value: string) => {
      const key = row.original as object
      let hay = HAYSTACKS.get(key)
      if (hay === undefined) {
        hay = row
          .getAllCells()
          .map((c) => String(c.getValue() ?? ''))
          .join('\u0000')
          .toLowerCase()
        HAYSTACKS.set(key, hay)
      }
      return hay.includes(value.toLowerCase())
    },
  })

  const rows = table.getRowModel().rows
  const virtual = rows.length > VIRTUALIZE_ABOVE
  const virtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => ROW_ESTIMATE,
    overscan: 20,
    enabled: virtual,
  })

  const renderRow = (row: Row<T>, style?: React.CSSProperties) => (
    <tr
      key={row.id}
      style={style}
      className={rowClass?.(row.original) ?? ''}
      aria-current={rowCurrent?.(row.original) || undefined}
      tabIndex={onRowClick || onRowEnter ? 0 : undefined}
      onClick={onRowClick ? () => onRowClick(row.original) : undefined}
      onDoubleClick={onRowDoubleClick ? () => onRowDoubleClick(row.original) : undefined}
      onKeyDown={onRowEnter ? (e) => e.key === 'Enter' && onRowEnter(row.original) : undefined}
    >
      {row.getVisibleCells().map((cell) => (
        <td key={cell.id} className={(cell.column.columnDef.meta as { className?: string } | undefined)?.className ?? ''}>
          {flexRender(cell.column.columnDef.cell, cell.getContext())}
        </td>
      ))}
    </tr>
  )

  const header = (
    <thead>
      {table.getHeaderGroups().map((hg) => (
        <tr key={hg.id}>
          {hg.headers.map((h) => {
            const sorted = h.column.getIsSorted()
            return (
              <th
                key={h.id}
                className={`${(h.column.columnDef.meta as { className?: string } | undefined)?.className ?? ''} sortable`}
                onClick={h.column.getToggleSortingHandler()}
              >
                {flexRender(h.column.columnDef.header, h.getContext())}
                {sorted === 'asc' ? ' ▲' : sorted === 'desc' ? ' ▼' : ''}
              </th>
            )
          })}
        </tr>
      ))}
    </thead>
  )

  if (!rows.length) return <>{empty ?? <div className="muted panel-pad">no rows</div>}</>

  if (!virtual)
    return (
      <table className="blotter">
        {header}
        <tbody>{rows.map((r) => renderRow(r))}</tbody>
      </table>
    )

  const items = virtualizer.getVirtualItems()
  const padTop = items.length ? items[0].start : 0
  const padBottom = items.length ? virtualizer.getTotalSize() - items[items.length - 1].end : 0
  return (
    <div ref={scrollRef} className="table-scroll" tabIndex={0}>
      <table className="blotter">
        {header}
        <tbody>
          {padTop > 0 ? (
            <tr style={{ height: padTop }}>
              <td colSpan={columns.length} />
            </tr>
          ) : null}
          {items.map((vi) => renderRow(rows[vi.index]))}
          {padBottom > 0 ? (
            <tr style={{ height: padBottom }}>
              <td colSpan={columns.length} />
            </tr>
          ) : null}
        </tbody>
      </table>
    </div>
  )
}
