// Options — Black-Scholes greeks calculator + a price/delta-vs-spot curve. Inputs debounce into the
// CLI's `alpha options` analytics; nothing here reaches market data (it's a pure calculator).

import { useEffect, useMemo, useState } from 'react'
import type uPlot from 'uplot'

import { api } from '../api/client'
import type { OptionCurvePoint, OptionGreeks as Greeks } from '../api/types'
import { AXIS, CHART } from '../util/chartTheme'
import { fmtNum } from '../util/format'
import { UplotChart } from '../components/UplotChart'

function curveOptions(): Omit<uPlot.Options, 'width' | 'height'> {
  return {
    scales: { x: { time: false }, price: {}, delta: { range: [-1, 1] } },
    axes: [
      { ...AXIS },
      { ...AXIS, scale: 'price' },
      { ...AXIS, scale: 'delta', side: 1, grid: { show: false } },
    ],
    series: [
      {},
      { label: 'Price', scale: 'price', stroke: CHART.accent, width: 1.5, points: { show: false } },
      { label: 'Delta', scale: 'delta', stroke: CHART.gold, width: 1.5, points: { show: false } },
    ],
    legend: { show: false },
    cursor: { points: { show: false } },
  }
}

const GREEK_ROWS: [keyof Greeks, string, number][] = [
  ['price', 'Price', 4],
  ['delta', 'Delta', 4],
  ['gamma', 'Gamma', 5],
  ['vega', 'Vega (1%)', 4],
  ['theta', 'Theta (day)', 4],
  ['rho', 'Rho (1%)', 4],
]

export function OptionsGreeks() {
  const [spot, setSpot] = useState('100')
  const [strike, setStrike] = useState('100')
  const [vol, setVol] = useState('0.20')
  const [days, setDays] = useState('30')
  const [rate, setRate] = useState('0.05')
  const [kind, setKind] = useState('call')
  const [greeks, setGreeks] = useState<Greeks | null>(null)
  const [curve, setCurve] = useState<OptionCurvePoint[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  // greeks depend on spot — refetch on any input
  useEffect(() => {
    let live = true
    const timer = setTimeout(() => {
      setError(null)
      const q = new URLSearchParams({ spot, strike, vol, days, rate, kind })
      api
        .optionsGreeks(q.toString())
        .then((r) => live && setGreeks(r))
        .catch((e: unknown) => live && setError(String(e)))
    }, 180)
    return () => {
      live = false
      clearTimeout(timer)
    }
  }, [spot, strike, vol, days, rate, kind])

  // the curve is spot-independent — only refetch when its inputs change
  useEffect(() => {
    let live = true
    const timer = setTimeout(() => {
      const q = new URLSearchParams({ strike, vol, days, rate, kind, points: '61' })
      api
        .optionsCurve(q.toString())
        .then((r) => live && setCurve(r.points))
        .catch(() => live && setCurve(null))
    }, 180)
    return () => {
      live = false
      clearTimeout(timer)
    }
  }, [strike, vol, days, rate, kind])

  const data = useMemo<uPlot.AlignedData | null>(
    () =>
      curve && curve.length
        ? [curve.map((p) => p.spot), curve.map((p) => p.price), curve.map((p) => p.delta)]
        : null,
    [curve],
  )
  const options = useMemo(curveOptions, [])

  const field = (
    label: string,
    value: string,
    set: (v: string) => void,
  ): React.ReactNode => (
    <label className="field-row">
      <span className="field-label">{label}</span>
      <input className="field" value={value} onChange={(e) => set(e.target.value)} spellCheck={false} />
    </label>
  )

  return (
    <div className="panel">
      <div className="panel-toolbar">
        <span className="title">Options · Black-Scholes</span>
      </div>
      <div className="panel-body panel-pad lab">
        <div className="lab-row">
          {field('Spot', spot, setSpot)}
          {field('Strike', strike, setStrike)}
          {field('Vol', vol, setVol)}
          {field('Days', days, setDays)}
          {field('Rate', rate, setRate)}
          <label className="field-row">
            <span className="field-label">Kind</span>
            <select className="field" value={kind} onChange={(e) => setKind(e.target.value)}>
              <option value="call">call</option>
              <option value="put">put</option>
            </select>
          </label>
        </div>

        {error ? <div className="leak">⚠ {error}</div> : null}

        {greeks ? (
          <div className="metric-grid">
            {GREEK_ROWS.map(([key, label, digits]) => (
              <div className="metric" key={key}>
                <span className="eyebrow">{label}</span>
                <span className="metric-val num">{fmtNum(greeks[key], digits)}</span>
              </div>
            ))}
          </div>
        ) : null}

        {data ? (
          <div>
            <div className="rd-head">Price &amp; delta vs spot</div>
            <UplotChart data={data} options={options} height={240} />
          </div>
        ) : null}
      </div>
    </div>
  )
}
