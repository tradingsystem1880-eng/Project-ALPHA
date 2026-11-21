import { useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../../api/client'
import type { RunSeries } from '../../api/types'
import { useSettings } from '../../state/settings'
import { useChartPalette } from '../../theme/themeState'
import { ariaSummary, buildStack, priceReason, readoutAt, type Readout } from './tearSheetModel'
import type { TearSheetMount } from './tearSheetPlot'

const num = (value: number | null, digits: number) => value === null ? '—' : value.toFixed(digits)
const pct = (value: number | null) => value === null ? '—' : `${(value * 100).toFixed(1)}%`

function ReadoutLine({ readout }: { readout: Readout | null }) {
  if (!readout) return <span className="muted">Move over the charts to read one day.</span>
  return <span className="mono">
    {readout.date} · Close {num(readout.close, 2)} · Equity {num(readout.equity, 3)} · Buy and hold {num(readout.benchmark, 3)} · Drawdown {pct(readout.drawdown)} · In market {readout.inMarket ? 'yes' : 'no'}
  </span>
}

/** Interactive price, equity and drawdown of one run, drawn from its stored series. Readings only. */
export function TearSheetStack({ runId }: { runId: string }) {
  const [series, setSeries] = useState<RunSeries | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [log, setLog] = useState(false)
  const [readout, setReadout] = useState<Readout | null>(null)
  const [drawError, setDrawError] = useState<string | null>(null)
  const host = useRef<HTMLDivElement>(null)
  const mount = useRef<TearSheetMount | null>(null)
  const window = useRef<[number, number] | null>(null)
  const { chartStyle } = useSettings()
  const palette = useChartPalette()
  const stack = useMemo(() => series && series.ts.length ? buildStack(series, log) : null, [series, log])
  const latest = useRef(series); latest.current = series

  useEffect(() => {
    let live = true
    setSeries(null); setError(null)
    api.runSeries(runId).then(body => { if (live) setSeries(body) }).catch(reason => { if (live) setError(String(reason instanceof Error ? reason.message : reason)) })
    return () => { live = false }
  }, [runId])

  useEffect(() => {
    if (!stack || !host.current) return
    const node = host.current
    let live = true
    setDrawError(null)
    import('./tearSheetPlot').then(async ({ mountTearSheet }) => {
      const next = await mountTearSheet(node, stack, chartStyle, palette, seconds => {
        const current = latest.current
        setReadout(seconds === null || !current ? null : readoutAt(current, seconds))
      }, window.current)
      if (!live) { next.destroy(); return }
      mount.current = next
    }).catch(reason => { if (live) setDrawError(String(reason)) })
    return () => {
      live = false
      if (mount.current) { window.current = mount.current.window(); mount.current.destroy(); mount.current = null }
    }
  }, [stack, chartStyle, palette])

  const reason = series ? priceReason(series.price?.status ?? 'none') : null
  return <section className="tear-sheet-stack" aria-label="Interactive equity, drawdown and price chart" data-testid="tear-sheet-stack">
    <div className="tear-sheet-head">
      <h3>Price, equity and drawdown</h3>
      <label title="Show equity on a log scale. Values are the stored ones."><input type="checkbox" checked={log} disabled={!series} onChange={event => setLog(event.target.checked)} /> Log</label>
    </div>
    {error ? <p role="alert">Could not load the chart series. {error}</p>
      : !series ? <p role="status">Loading the chart…</p>
      : !stack ? <p className="muted">This run stored no equity series, so there is nothing to draw.</p>
      : <>
        {reason && <p className="muted" data-testid="tear-sheet-price-reason">{reason}</p>}
        <p className="tear-sheet-readout" aria-live="off"><ReadoutLine readout={readout} /></p>
        {drawError && <p role="alert">Could not draw the chart. {drawError}</p>}
        <div ref={host} className="tear-sheet-host" role="img" aria-label={ariaSummary(series)} />
        {stack.bands.length > 0 && <ul className="tear-sheet-bands muted" aria-label="Shaded periods">
          {stack.bands.map(band => <li key={`${band.kind}-${band.label}`}>{band.label}</li>)}
        </ul>}
        {series.bounds.trades.truncated && <p className="muted">Showing the first {series.bounds.trades.cap} of {series.bounds.trades.original} trades.</p>}
        {series.bounds.points.truncated && <p className="muted">Showing {series.bounds.points.returned} of {series.bounds.points.original} days, evenly spaced, both ends kept.</p>}
      </>}
  </section>
}
