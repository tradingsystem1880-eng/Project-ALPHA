/**
 * A small line chart for *live* data — values computed on the fly, not read from a run.
 *
 * Everything derived from a stored run is now a server-rendered figure, which is why the
 * old chart library is gone. Two things are genuinely not run artifacts: the Black-Scholes
 * curve you are dragging a strike across, and ML diagnostics for a job still in flight.
 * Those need something interactive and immediate, so this stays — deliberately one small
 * component rather than a charting stack.
 *
 * It follows the same grammar as the figures: recessive axes, one saturated series, units
 * on the axis label, and a table alternative so the numbers are never colour-only.
 */

import { useId, useMemo } from 'react'

export interface MiniSeries {
  label: string
  colour: string
  points: [number, number][]
  dashed?: boolean
}

interface Props {
  series: MiniSeries[]
  xLabel: string
  yLabel: string
  height?: number
  /** Pre-formatted, because formatting depends on a unit this component does not know. */
  formatX?: (value: number) => string
  formatY?: (value: number) => string
}

const PAD = { top: 10, right: 14, bottom: 30, left: 54 }

export function MiniLine({
  series,
  xLabel,
  yLabel,
  height = 220,
  formatX = (value) => String(Math.round(value * 100) / 100),
  formatY = (value) => String(Math.round(value * 1000) / 1000),
}: Props) {
  const titleId = useId()
  const width = 640

  const bounds = useMemo(() => {
    const xs = series.flatMap((item) => item.points.map(([x]) => x))
    const ys = series.flatMap((item) => item.points.map(([, y]) => y))
    if (!xs.length) return null
    const xMin = Math.min(...xs)
    const xMax = Math.max(...xs)
    const yMin = Math.min(...ys)
    const yMax = Math.max(...ys)
    // A flat series has zero range; give it one so it draws a line rather than dividing by zero.
    return {
      xMin,
      xMax: xMax === xMin ? xMin + 1 : xMax,
      yMin: yMax === yMin ? yMin - 0.5 : yMin,
      yMax: yMax === yMin ? yMin + 0.5 : yMax,
    }
  }, [series])

  if (!bounds) return <p className="muted">Nothing to plot yet.</p>

  const sx = (x: number) =>
    PAD.left + ((x - bounds.xMin) / (bounds.xMax - bounds.xMin)) * (width - PAD.left - PAD.right)
  const sy = (y: number) =>
    height - PAD.bottom - ((y - bounds.yMin) / (bounds.yMax - bounds.yMin)) * (height - PAD.top - PAD.bottom)

  const ticksY = [bounds.yMin, (bounds.yMin + bounds.yMax) / 2, bounds.yMax]
  const ticksX = [bounds.xMin, (bounds.xMin + bounds.xMax) / 2, bounds.xMax]

  // The viewBox scales uniformly ("meet"): stretching x and y independently would shear the
  // tick text and make stroke weights depend on how wide the column happens to be.
  return (
    <figure className="miniline">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        preserveAspectRatio="xMidYMid meet"
        role="img"
        aria-labelledby={titleId}
        className="miniline-svg"
      >
        <title id={titleId}>
          {series.map((item) => item.label).join(', ')} against {xLabel}
        </title>
        {ticksY.map((value) => (
          <g key={`y${value}`}>
            <line
              x1={PAD.left}
              x2={width - PAD.right}
              y1={sy(value)}
              y2={sy(value)}
              className="miniline-grid"
            />
            <text x={PAD.left - 6} y={sy(value) + 3} className="miniline-tick" textAnchor="end">
              {formatY(value)}
            </text>
          </g>
        ))}
        {ticksX.map((value) => (
          <text
            key={`x${value}`}
            x={sx(value)}
            y={height - PAD.bottom + 14}
            className="miniline-tick"
            textAnchor="middle"
          >
            {formatX(value)}
          </text>
        ))}
        <text x={width / 2} y={height - 4} className="miniline-axis" textAnchor="middle">
          {xLabel}
        </text>
        <text
          x={12}
          y={height / 2}
          className="miniline-axis"
          textAnchor="middle"
          transform={`rotate(-90 12 ${height / 2})`}
        >
          {yLabel}
        </text>
        {series.map((item) => (
          <polyline
            key={item.label}
            className="miniline-series"
            points={item.points.map(([x, y]) => `${sx(x)},${sy(y)}`).join(' ')}
            stroke={item.colour}
            strokeDasharray={item.dashed ? '4 3' : undefined}
          />
        ))}
      </svg>
      <figcaption className="miniline-legend">
        {series.map((item) => (
          <span key={item.label}>
            <span className="miniline-swatch" style={{ background: item.colour }} />
            {item.label}
          </span>
        ))}
      </figcaption>
    </figure>
  )
}
