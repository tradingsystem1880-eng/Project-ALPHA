// Options — Black-Scholes greeks calculator + a price/delta-vs-spot curve. Inputs debounce into the
// CLI's `alpha options` analytics; nothing here reaches market data (it's a pure calculator).

import { useEffect, useMemo, useState } from 'react'

import { api } from '../api/client'
import type { OptionCurvePoint, OptionGreeks as Greeks } from '../api/types'
import { CHART } from '../util/chartTheme'
import { fmtNum } from '../util/format'
import { MiniLine } from '../components/MiniLine'


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
    setGreeks(null)
    setError(null)
    const timer = setTimeout(() => {
      const q = new URLSearchParams({ spot, strike, vol, days, rate, kind })
      api
        .optionsGreeks(q.toString())
        .then((r) => {
          if (!live) return
          setGreeks(r)
          setError(null)
        })
        .catch((e: unknown) => {
          if (!live) return
          setGreeks(null)
          setError(String(e))
        })
    }, 180)
    return () => {
      live = false
      clearTimeout(timer)
    }
  }, [spot, strike, vol, days, rate, kind])

  // the curve is spot-independent — only refetch when its inputs change
  useEffect(() => {
    let live = true
    setCurve(null)
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

  // Price and delta live on different scales, so they are two figures rather than one
  // chart with two y-axes -- the same rule the server-rendered figures follow.
  const priceSeries = useMemo(
    () =>
      curve?.length
        ? [{ label: 'Price', colour: CHART.accent, points: curve.map((p) => [p.spot, p.price] as [number, number]) }]
        : null,
    [curve],
  )
  const deltaSeries = useMemo(
    () =>
      curve?.length
        ? [{ label: 'Delta', colour: CHART.gold, points: curve.map((p) => [p.spot, p.delta] as [number, number]) }]
        : null,
    [curve],
  )

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

        {priceSeries && deltaSeries ? (
          <div className="options-curves">
            <div>
              <div className="rd-head">Option price vs spot</div>
              <MiniLine
                series={priceSeries}
                xLabel="Spot (price)"
                yLabel="Option price"
                height={200}
              />
            </div>
            <div>
              <div className="rd-head">Delta vs spot</div>
              <MiniLine series={deltaSeries} xLabel="Spot (price)" yLabel="Delta" height={200} />
            </div>
          </div>
        ) : null}
      </div>
    </div>
  )
}
