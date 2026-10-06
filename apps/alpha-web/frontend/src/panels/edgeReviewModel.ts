/** Recorded projections only: never infer a return, benchmark, fee total or verdict. */
import type { NativeTearSheetProjection } from '../api/types'
const object = (value: unknown): Record<string, unknown> => value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
const number = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value)
const display = (value: unknown, unit = '') => number(value) ? `${value}${unit}` : typeof value === 'string' && value ? value : 'Not recorded'
const percent = (value: unknown) => number(value) ? `${(value * 100).toFixed(2)}%` : 'Not recorded'

export function edgeReviewRows(manifest: Record<string, unknown>, native: NativeTearSheetProjection | null): { label: string; value: string }[] {
  const oos = object(manifest.oos_metrics)
  const hasOos = Object.keys(oos).length > 0
  const metrics = hasOos ? oos : object(manifest.metrics)
  const params = object(manifest.params)
  const trade = native?.trade_statistics.find(item => item.metric === 'trade_count')
  const pnl = native?.trade_statistics.find(item => item.metric === 'total_realized_pnl')
  const benchmark = native?.benchmark.at(-1)
  return [
    { label: hasOos ? 'OOS portfolio return' : 'Portfolio return', value: percent(metrics.total_return) },
    { label: hasOos ? 'OOS maximum drawdown' : 'Maximum drawdown', value: percent(metrics.max_drawdown) },
    { label: 'Sharpe', value: display(metrics.sharpe) },
    { label: 'Fee assumption', value: display(params.fee_bps, ' bps') },
    { label: 'Slippage assumption', value: display(params.slippage_bps, ' bps') },
    { label: 'Total realized costs', value: 'Not recorded' },
    { label: 'Realized trade P&L', value: pnl?.available ? display(pnl.value, ` ${pnl.unit}`) : pnl?.unavailable_reason ?? 'Not recorded' },
    { label: 'Trade count', value: number(manifest.n_trades) ? display(manifest.n_trades) : trade?.available ? display(trade.value) : trade?.unavailable_reason ?? 'Not recorded' },
    { label: 'Benchmark', value: native?.benchmark_available && benchmark?.available ? display(benchmark.benchmark_kind) : benchmark?.unavailable_reason ?? 'Not recorded' },
    { label: 'Benchmark final normalized equity', value: native?.benchmark_available && benchmark?.available ? display(benchmark.benchmark_equity) : 'Not recorded' },
    { label: 'Validation verdict', value: display(object(manifest.verdict).overall ?? manifest.verdict) },
    { label: 'Recorded gate result', value: typeof manifest.passed === 'boolean' ? manifest.passed ? 'Passed' : 'Failed' : 'Not recorded' },
    { label: 'Deflated Sharpe', value: display(number(manifest.dsr) ? manifest.dsr : object(manifest.dsr).dsr) },
  ]
}
