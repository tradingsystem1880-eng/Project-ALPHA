import './FollowToday.css'
// Today: what is active among the ideas the owner follows forward on paper. A display, not a
// research result and never an order. The server sends every decision and number
// (`GET /api/follow/today`, `GET /api/follow/{id}`); this file lays them out.

import { useEffect, useState } from 'react'

import { api } from '../api/client'
import type { FollowRow, FollowShow, FollowToday as Today } from '../api/types'
import { CopyCommand } from '../components/CopyCommand'
import { Timestamp } from '../util/formatTime'
import { openStoredMarket } from './actions'
import {
  NOTICE, behindLine, closedSessionLine, detailFacts, equityGeometry, equityPoints, groupSections, paperLine, rankMark, readingPairs,
  replayLine, rowMarker, sessionLine, tableRows, type Section,
} from './followTodayModel'
import { fmtPct } from './marketModel'

const CHART_W = 640
const CHART_H = 220
const LEFT = 64
const BOTTOM = 28

export interface FollowTodayViewProps {
  data: Today | null
  error: string | null
  loading: boolean
  selected: string | null
  detail: FollowShow | null
  detailError: string | null
  detailLoading: boolean
  onSelect(id: string): void
  onRefresh(): void
  onOpenChart(asset: string): void
}

function Card({ row, open, onSelect }: { row: FollowRow; open: boolean; onSelect(id: string): void }) {
  const marker = rowMarker(row)
  const paper = paperLine(row)
  const pairs = readingPairs(row)
  return (
    <button type="button" className="follow-card" data-id={row.follow_id} data-flag={marker ? 'true' : undefined} aria-pressed={open}
      onClick={() => onSelect(row.follow_id)}>
      <span className="follow-card-name">{row.name}</span>
      <span className="muted follow-card-meta">{`${row.asset || 'no asset'} · follow ${row.follow_id}`}</span>
      <span className="follow-card-decision">{row.decision}</span>
      {pairs.length ? (
        <span className="follow-readings">
          {pairs.map(([label, value]) => <span key={label} className="follow-reading">{`${label}: `}<b className="num">{value}</b></span>)}
        </span>
      ) : null}
      {row.exits.length ? <span className="muted follow-card-exits">{`Exits: ${row.exits.join('; ')}`}</span> : null}
      <span className="follow-card-paper">{paper.position}</span>
      <span className="follow-card-change" data-dir={paper.dir}>
        <span aria-hidden="true">{`${rankMark(paper.dir)} `}</span>{`${paper.change} since the start`}
      </span>
      <span className="muted follow-card-session">{sessionLine(row)}</span>
      {marker ? <span className="follow-marker"><span aria-hidden="true">{`${marker.icon} `}</span>{marker.words}</span> : null}
    </button>
  )
}

function GroupBlock({ section, selected, onSelect }: { section: Section; selected: string | null; onSelect(id: string): void }) {
  const head = `${section.title} (${section.rows.length})`
  if (!section.rows.length) return <p className="muted follow-group-empty">{`${head}: none`}</p>
  return (
    <section aria-label={head} className="follow-group" data-group={section.key}>
      <h3>{head}</h3>
      <div className="follow-grid">
        {section.rows.map(row => <Card key={row.follow_id} row={row} open={row.follow_id === selected} onSelect={onSelect} />)}
      </div>
    </section>
  )
}

function EquityChart({ show }: { show: FollowShow }) {
  const points = equityPoints(show)
  if (!points.length) return <p className="muted">No paper equity values are recorded in the entries shown.</p>
  const geo = equityGeometry(points, CHART_W - LEFT - 12, CHART_H - BOTTOM - 4)
  const summary = points.map(p => `${p.session} ${fmtPct(p.pct)}`).join(', ')
  const ends = geo.labels.length === 1 ? [0] : [0, geo.labels.length - 1]
  return (
    <svg viewBox={`0 0 ${CHART_W} ${CHART_H}`} className="follow-chart" role="img"
      aria-label={`Paper equity since the start, percent, by session. ${summary}. The table below has the entries.`}>
      <g transform={`translate(${LEFT} 4)`}>
        {geo.ticks.map(tick => <text key={tick.text} x={-8} y={tick.y + 4} textAnchor="end" className="follow-axis">{tick.text}</text>)}
        <line x1={0} x2={CHART_W - LEFT - 12} y1={geo.zeroY} y2={geo.zeroY} className="follow-zero" />
        <polyline points={geo.points} className="follow-line" />
        {geo.dots.map(dot => <circle key={dot.session} cx={dot.x} cy={dot.y} r={3.5} className="follow-dot" />)}
        {ends.map(index => (
          <text key={geo.labels[index].text} x={geo.labels[index].x} y={CHART_H - BOTTOM + 18} className="follow-axis"
            textAnchor={ends.length === 1 ? 'middle' : index === 0 ? 'start' : 'end'}>{geo.labels[index].text}</text>
        ))}
      </g>
    </svg>
  )
}

function Detail({ row, show, onOpenChart }: { row: FollowRow | null; show: FollowShow; onOpenChart(asset: string): void }) {
  const rows = tableRows(show)
  const asset = show.record.assets[0] ?? row?.asset ?? ''
  return (
    <div className="follow-detail-body">
      <div>
        <h4>Paper equity path</h4>
        <p className="muted">Percent since the start, one point per entry shown. The dashed line is zero.</p>
        <EquityChart show={show} />
        <p className="follow-replay">{replayLine(show)}</p>
        {asset ? <button type="button" className="btn follow-chart-link" onClick={() => onOpenChart(asset)}>{`Open the chart for ${asset}`}</button> : null}
      </div>
      <div>
        <h4>{`Last entries (${rows.length})`}</h4>
        <div className="follow-table-wrap">
          <table className="blotter follow-table" aria-label="Last journal entries">
            <thead><tr><th scope="col">Session</th><th scope="col">Kind</th><th scope="col">Decision</th><th scope="col" className="r">Equity</th></tr></thead>
            <tbody>
              {rows.map(entry => (
                <tr key={`${entry.session}-${entry.kind}`} data-entry={entry.session}>
                  <td>{entry.session}</td><td>{entry.kind}</td><td>{entry.words}</td><td className="num r">{entry.equity}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <h4>Facts fixed when it started</h4>
        <dl className="follow-facts">
          {detailFacts(show).map(([label, value]) => <div key={label}><dt className="muted">{label}</dt><dd>{value}</dd></div>)}
        </dl>
      </div>
    </div>
  )
}

function Empty() {
  return (
    <section className="follow-start" aria-label="Start a follow">
      <p><strong>Nothing is followed yet.</strong> A follow watches one finished rule test forward, on paper, one session at a time.</p>
      <CopyCommand command="alpha follow start --test <run id>" why="Starting a follow is an owner step in the terminal. This screen only shows." />
      <p>Find a run id with: <code className="mono">alpha results list</code></p>
    </section>
  )
}

export function FollowTodayView(props: FollowTodayViewProps) {
  const { data, error, loading, selected, detail, detailError, detailLoading, onSelect, onRefresh, onOpenChart } = props
  const row = data?.rows.find(item => item.follow_id === selected) ?? null
  return (
    <div className="follow-today" style={{ background: 'var(--panel)', color: 'var(--ink)', padding: 'var(--pad)' }}>
      <div className="follow-head">
        <h2>Followed on paper</h2>
        {data ? <span>As of <Timestamp value={data.as_of} /></span> : null}
        <button type="button" className="btn" onClick={onRefresh}>Refresh</button>
      </div>
      {data ? (
        <p className="follow-lede"><strong>{closedSessionLine(data)}</strong>{' · '}<span>{behindLine(data)}</span></p>
      ) : null}
      <p className="muted follow-notice">{NOTICE}</p>
      {error ? <p role="alert" className="follow-error">{error}</p> : null}
      {loading && !data && !error ? <p className="muted" role="status">Loading the followed ideas…</p> : null}
      {data && data.rows.length === 0 ? <Empty /> : null}
      {data && data.rows.length ? (
        <div className="follow-groups">
          {groupSections(data).map(section => <GroupBlock key={section.key} section={section} selected={selected} onSelect={onSelect} />)}
        </div>
      ) : null}
      {selected ? (
        <section className="follow-detail" aria-label="Detail of the selected follow">
          <h3>{row ? row.name : `Follow ${selected}`}</h3>
          {detailError ? <p role="alert" className="follow-error">{detailError}</p> : null}
          {detailLoading && !detail && !detailError ? <p className="muted" role="status">Loading this follow…</p> : null}
          {detail ? <Detail row={row} show={detail} onOpenChart={onOpenChart} /> : null}
        </section>
      ) : null}
    </div>
  )
}

const words = (cause: unknown): string => (cause instanceof Error ? cause.message : String(cause))

export function FollowToday() {
  const [data, setData] = useState<Today | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const [shown, setShown] = useState<{ id: string; show: FollowShow } | null>(null)
  const [detailError, setDetailError] = useState<{ id: string; text: string } | null>(null)
  const [round, setRound] = useState(0)
  useEffect(() => {
    let live = true
    setError(null)
    api.followToday().then(
      result => { if (live) setData(result) },
      (cause: unknown) => { if (live) { setData(null); setError(words(cause)) } },
    )
    return () => { live = false }
  }, [round])
  useEffect(() => {
    if (!selected) return
    let live = true
    api.followShow(selected).then(
      result => { if (live) { setShown({ id: selected, show: result }); setDetailError(null) } },
      (cause: unknown) => { if (live) setDetailError({ id: selected, text: words(cause) }) },
    )
    return () => { live = false }
  }, [selected, round])
  const detail = shown && shown.id === selected ? shown.show : null
  const failed = detailError && detailError.id === selected ? detailError.text : null
  return (
    <FollowTodayView data={data} error={error} loading={!error && data === null} selected={selected} detail={detail} detailError={failed}
      detailLoading={!detail && !failed} onSelect={id => setSelected(current => (current === id ? null : id))}
      onRefresh={() => setRound(value => value + 1)} onOpenChart={openStoredMarket} />
  )
}
