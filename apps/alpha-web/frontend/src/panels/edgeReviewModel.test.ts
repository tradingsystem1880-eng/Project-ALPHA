import { describe, expect, it } from 'vitest'
import { edgeReviewRows } from './edgeReviewModel'

describe('recorded edge review', () => {
  it('keeps OOS separate, preserves zero costs, and does not estimate missing costs or trades', () => {
    const rows = edgeReviewRows({ oos_metrics: { total_return: 0.12, max_drawdown: -0.2 }, metrics: { total_return: 0.9 }, params: { fee_bps: 0, slippage_bps: 2 } }, null)
    expect(rows.find(row => row.label === 'OOS portfolio return')?.value).toBe('12.00%')
    expect(rows.find(row => row.label === 'Fee assumption')?.value).toBe('0 bps')
    expect(rows.find(row => row.label === 'Total realized costs')?.value).toBe('Not recorded')
    expect(rows.find(row => row.label === 'Trade count')?.value).toBe('Not recorded')
  })
  it.each([0.72, { dsr: 0.72 }])('reads scalar and nested recorded DSR: %j', dsr => {
    expect(edgeReviewRows({ dsr }, null).find(row => row.label === 'Deflated Sharpe')?.value).toBe('0.72')
  })
  it('does not convert missing or nonfinite metrics into zero or verdicts', () => {
    const rows = edgeReviewRows({ metrics: { total_return: Infinity } }, null)
    expect(rows.find(row => row.label === 'Portfolio return')?.value).toBe('Not recorded')
    expect(rows.find(row => row.label === 'Validation verdict')?.value).toBe('Not recorded')
  })
})
