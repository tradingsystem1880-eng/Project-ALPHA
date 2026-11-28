// Market Watch: a failed `candles(symbol, '?tail=2')` read must not look like an asset with no data.
// The panel stores a failed read as a small marker `{ failed: true, reason }` in its quotes state and
// watchRow words that row "read failed" with the plain reason (shown in the row title).
import { describe, expect, it } from 'vitest'

import { watchRow } from './marketWatchModel'

const NOW = Date.UTC(2026, 10, 28)
const REASON = 'stored bars for SOL/USDT could not be parsed'

function text(row: unknown): string {
  return JSON.stringify(row).toLowerCase()
}

describe('Market Watch failed quote read', () => {
  it('a Market Watch row whose bars could not be read says the read failed and gives the reason', () => {
    const failed = watchRow('SOL/USDT', { failed: true, reason: REASON } as never, NOW)
    const missing = watchRow('SOL/USDT', null, NOW)
    expect(text(failed)).toContain('read failed')
    expect(text(failed)).toContain(REASON.toLowerCase())
    expect(text(failed)).toContain('sol/usdt')
    expect(failed).not.toEqual(missing)
  })

  it('a Market Watch row with no stored bars keeps its no-data wording and does not claim a failed read', () => {
    const missing = watchRow('SOL/USDT', null, NOW)
    expect(missing).toMatchObject({ last: '—', tone: 'none' })
    expect(text(missing)).not.toContain('read failed')
  })
})
