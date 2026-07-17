// Trades tab: the realized trade log. (Virtualized, uncapped rendering arrives with the
// DataTable upgrade; until then the render caps at 800 rows with an explicit notice.)

import type { TradeRow } from '../../api/types'
import { fmtNum } from '../../util/format'
import { Section } from './common'

const COLS = [
  'instrument_id',
  'side',
  'quantity',
  'entry_price',
  'exit_price',
  'entry_ts',
  'exit_ts',
  'realized_pnl',
  'realized_return',
] as const

const CAP = 800

export function TradesTab({ trades }: { trades: TradeRow[] }) {
  if (!trades.length)
    return (
      <Section title="Trades">
        <div className="muted">
          No discrete trades recorded — position-level strategies rebalance holdings rather than
          opening/closing round trips; read the equity curve instead.
        </div>
      </Section>
    )
  const rows = trades.slice(0, CAP)
  return (
    <Section
      title={`Trades · ${trades.length}`}
      right={trades.length > CAP ? <span className="muted">showing first {CAP}</span> : undefined}
    >
      <table className="blotter">
        <thead>
          <tr>
            {COLS.map((c) => (
              <th key={c} className={c === 'instrument_id' || c === 'side' || c.endsWith('_ts') ? '' : 'r'}>
                {c.replace(/_/g, ' ')}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              {COLS.map((c) => {
                const v = r[c]
                const numeric = typeof v === 'number'
                const neg = numeric && v < 0 && (c === 'realized_pnl' || c === 'realized_return')
                return (
                  <td key={c} className={numeric ? `num${neg ? ' neg' : ''}` : 'mono'}>
                    {numeric
                      ? fmtNum(v, c === 'realized_return' ? 4 : 2)
                      : String(v ?? '—').slice(0, 16)}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </Section>
  )
}
