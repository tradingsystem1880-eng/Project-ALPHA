import { useEffect, useState } from 'react'
import { getJSON } from '../api/client'
import { SetupReadingBlock } from '../components/ReadingBlock'
import type { components } from '../api/generated'
import { Timestamp } from '../util/formatTime'
import { healthLine } from './ruleTestModel'
import { curveRows, FIELD_LABELS, object, shown, stored, timelineMarks } from './setupLabModel'

type Schema = components['schemas']
export type SetupDetail = Schema['SetupRunDetail']
type RunList = Schema['SetupRunList']
type Outcome = Schema['SetupOutcome']
type Row = Record<string, unknown>
type Column = readonly [string, string]

function Value({ value, name = '' }: { value: unknown; name?: string }) {
  if (typeof value === 'number') {
    if (name === 'net_return' || name === 'risk_fraction') {
      return <span title={`${shown(value)} as a fraction`}>{(100 * value).toFixed(2)}%</span>
    }
    if (name === 'r_multiple') return <>{value.toFixed(2)} R</>
  }
  return typeof value === 'string' && (name.endsWith('_ts') || name.endsWith('_bar'))
    ? <Timestamp value={value} /> : <>{shown(value)}</>
}

function Labels({ labels, explanations }: { labels: string[]; explanations: Record<string, string> }) {
  return <ul aria-label="Recorded labels">{labels.map(label => <li key={label}>
    <strong>{label}</strong>: {explanations[label] ?? 'Plain explanation not recorded for this label.'}
  </li>)}</ul>
}

function TrialLabels({ labels, explanations, shownAbove = [] }: { labels: SetupDetail['trial_labels']; explanations: Record<string, string>; shownAbove?: string[] }) {
  return <>{Object.entries(labels ?? {}).filter(([, values]) => values.join() !== shownAbove.join()).map(([index, values]) => <div key={index}>
    <p>Recorded trial {index}</p><Labels labels={values} explanations={explanations} />
  </div>)}</>
}

function Fields({ value, explanations }: { value: unknown; explanations: Record<string, string> }) {
  if (value === null || value === undefined) return <p>not recorded</p>
  if (Array.isArray(value)) return <ul>{value.map((item, index) => <li key={index}><Fields value={item} explanations={explanations} /></li>)}</ul>
  if (typeof value !== 'object') return <>{shown(value)}</>
  return <dl>{Object.entries(value).map(([name, child]) => <div key={name}>
    <dt>{FIELD_LABELS[name] ?? name.replaceAll('_', ' ')}</dt><dd>
      {name === 'labels' && Array.isArray(child) ? <Labels labels={child} explanations={explanations} />
        : name.endsWith('_ts') || name.endsWith('_bar') ? <Value name={name} value={child} />
        : <Fields value={child} explanations={explanations} />}
    </dd>
  </div>)}</dl>
}

function Table({ caption, columns, rows }: { caption: string; columns: readonly Column[]; rows: Row[] }) {
  return <div style={{ overflowX: 'auto' }}><table className="blotter">
    <caption>{caption}</caption><thead><tr>{columns.map(([key, title]) => <th scope="col" key={key}>{title}</th>)}</tr></thead>
    <tbody>{rows.map((row, index) => <tr key={index} style={row.status === 'rejected' ? { color: 'var(--muted)' } : undefined}>
      {columns.map(([key]) => <td key={key}><Value value={row[key]} name={key} /></td>)}
    </tr>)}</tbody>
  </table></div>
}

/** A match sheet the detail left out to stay small; it is read when the owner opens the section. */
function LazySheet({ findId, sheet }: { findId: string; sheet: Schema['SetupFigure'] }) {
  const [loaded, setLoaded] = useState<Schema['SetupFigure'] | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    const [, kind, number] = /^sheets\/(accepted|rejected)-(\d{3})\.png$/.exec(sheet.name) ?? []
    if (!kind) { setError('The sheet name is not valid.'); return }
    let live = true
    getJSON<Schema['SetupFigure']>(`/api/setup/runs/${findId}/sheets/${kind}/${number}`)
      .then(value => { if (live) setLoaded(value) })
      .catch((cause: unknown) => { if (live) setError(String(cause)) })
    return () => { live = false }
  }, [findId, sheet.name])
  if (error) return <p role="alert">{error}</p>
  return loaded ? <Figure figure={loaded} title={`Recorded match sheet · ${sheet.name}`} /> : <p role="status">Loading sheet…</p>
}

function Figure({ figure, title }: { figure: Schema['SetupFigure']; title: string }) {
  return <figure className="figure-card"><figcaption>{title}</figcaption>
    {figure.png ? <img src={`data:image/png;base64,${figure.png}`} alt={`${title}. Recorded values and limitations appear in the adjacent tables.`} style={{ width: '100%', height: 'auto' }} />
      : <p>Figure: not recorded</p>}
  </figure>
}

function MatchTimeline({ candidates, trades }: { candidates: Row[]; trades: Outcome[] }) {
  const marks = timelineMarks(candidates)
  if (!marks.length) return <p>Match timeline: no dated matches recorded</p>
  const symbols = [...new Set(marks.map(mark => mark.symbol))]
  const first = Math.min(...marks.map(mark => mark.at))
  const span = Math.max(...marks.map(mark => mark.at)) - first || 1
  const x = (at: number) => 60 + ((at - first) / span) * 860
  const traded = new Set(trades.flatMap(outcome => (outcome.rows ?? []).filter(row => row.complete === true).map(row => `${String(row.asset)}|${String(row.candidate_id)}`)))
  const year = (at: number) => new Date(at).getUTCFullYear()
  return <figure className="figure-card"><figcaption>Where each stored match falls in time (bright: accepted; grey: rejected; ringed: a completed trade was recorded)</figcaption>
    <svg viewBox={`0 0 940 ${symbols.length * 44 + 30}`} role="img" aria-label="Timeline of stored matches by instrument" style={{ width: '100%', height: 'auto' }}>
      {symbols.map((symbol, row) => <g key={symbol}>
        <text x="4" y={row * 44 + 30} fill="var(--ink)" fontSize="12">{symbol}</text>
        <line x1="60" x2="920" y1={row * 44 + 26} y2={row * 44 + 26} stroke="var(--line-strong)" />
        {marks.filter(mark => mark.symbol === symbol).map((mark, index) => <circle key={index} cx={x(mark.at)} cy={row * 44 + 26} r={mark.rejected ? 3 : 5} fill={mark.rejected ? 'var(--muted)' : 'var(--accent)'} fillOpacity={mark.rejected ? 0.5 : 0.9} />)}
        {candidates.filter(c => String(c.symbol) === symbol && traded.has(`${symbol}|${String(c.candidate_id)}`) && typeof c.event_ts === 'string').map(c => <circle key={String(c.candidate_id)} cx={x(Date.parse(String(c.event_ts)))} cy={row * 44 + 26} r={9} fill="none" stroke="var(--ink)" />)}
      </g>)}
      <text x="60" y={symbols.length * 44 + 20} fill="var(--ink)" fontSize="12">{year(first)}</text>
      <text x="920" y={symbols.length * 44 + 20} fill="var(--ink)" fontSize="12" textAnchor="end">{year(first + span)}</text>
    </svg></figure>
}

const MATCH_COLUMNS: readonly Column[] = [
  ['symbol', 'Instrument'], ['candidate_id', 'Match identifier'], ['event_ts', 'Pattern known at'],
  ['status', 'Recorded status'], ['reason', 'Rejection reason'], ['trigger_ts', 'Trigger close'],
  ['entry_ts', 'Entry date'], ['entry_price', 'Entry price'], ['cluster_id', 'Separate occurrence group'],
  ['cluster_first', 'First accepted day in group'],
]
const TRADE_COLUMNS: readonly Column[] = [
  ['asset', 'Instrument'], ['candidate_id', 'Match identifier'], ['entry_ts', 'Entry date'],
  ['direction', 'Direction'], ['entry_price', 'Entry price'], ['stop', 'Stop price'], ['target', 'Target price'],
  ['exit_ts', 'Exit date'], ['exit_price', 'Exit price'], ['reason', 'Exit reason'],
  ['risk_fraction', 'Initial risk (%)'], ['net_return', 'Result after costs (%)'], ['r_multiple', 'R multiple'], ['complete', 'Completed'],
]

function DataHealth({ summary }: { summary: Row }) {
  const line = healthLine(object(summary.data_health))
  return line && <p>{line}</p>
}

/** The stored summary without its old outcome word: the evidence word above replaces it on this screen. */
function withoutOutcome(summary: Row): Row {
  return Object.fromEntries(Object.entries(summary).filter(([name]) => name !== 'outcome'))
}

function OutcomeReading({ outcome, kind, summary }: { outcome: Outcome; kind: 'study' | 'trade'; summary: Row }) {
  const found = outcome.reading
  const sentence = typeof summary.reading === 'string' ? summary.reading : null
  return <SetupReadingBlock kind={kind} sentence={sentence} evidence={found?.evidence ?? null} oldWording={found?.old_wording ?? false}
    position={found?.family_position ?? null} count={found?.family_count ?? null} />
}

function Study({ outcome, detail }: { outcome: Outcome; detail: SetupDetail }) {
  const summary = object(outcome.summary)
  const rows = curveRows(summary.curve)
  return <section aria-label="Recorded event study">
    <h3>Average path after a match · {stored(summary.occurrences)} separate occurrences</h3>
    <DataHealth summary={summary} />
    <Labels labels={outcome.labels} explanations={detail.label_explanations} />
    <p>Study identifier: {outcome.run_id} · Trial indices: {stored(outcome.trial_indices)}</p>
    <TrialLabels labels={outcome.trial_labels} explanations={detail.label_explanations} shownAbove={outcome.labels} />
    <p>Rule version: {stored(outcome.rule_version)}</p>
    <OutcomeReading outcome={outcome} kind="study" summary={summary} />
    <Figure figure={outcome.figure} title="Average path after a match against the stored baseline" />
    <p>Returns are fractions after costs. The baseline is the recorded ordinary-date comparison; the band is the recorded random-date range.</p>
    {rows.length ? <details><summary>Values behind the figure (every bar)</summary><Table caption="Recorded average path and comparison values" rows={rows} columns={[
      ['bar', 'Bars after entry'], ['mean', 'Average path'], ['drift', 'Stored baseline'],
      ['lower', 'Random dates, lower bound'], ['upper', 'Random dates, upper bound'],
    ]} /></details> : <p>Average path and baseline: not recorded</p>}
    <details><summary>Stored study summary, horizons and limitations</summary><Fields value={withoutOutcome(summary)} explanations={detail.label_explanations} /></details>
  </section>
}

function Trades({ outcome, detail }: { outcome: Outcome; detail: SetupDetail }) {
  const summary = object(outcome.summary)
  const pooled = object(summary.pooled)
  return <section aria-label="Recorded setup trades">
    <h3>Trades after costs</h3>
    <DataHealth summary={summary} />
    <Labels labels={outcome.labels} explanations={detail.label_explanations} />
    <p>Trade run identifier: {outcome.run_id} · Trial indices: {stored(outcome.trial_indices)}</p>
    <TrialLabels labels={outcome.trial_labels} explanations={detail.label_explanations} shownAbove={outcome.labels} />
    <p>Rule version: {stored(outcome.rule_version)}</p>
    <p>{stored(summary.basis)}</p>
    <OutcomeReading outcome={outcome} kind="trade" summary={summary} />
    <p>Stop: the protective exit. Target: the declared exit level in the trade’s favour. Time: the holding limit. Other recorded exit reasons stay visible.</p>
    {outcome.rows === null ? <p>Trade rows: not recorded</p> : outcome.rows.length === 0 ? <p>No trades recorded.</p>
      : <Table caption="Every recorded trade, including skipped and unfinished entries" columns={TRADE_COLUMNS} rows={outcome.rows} />}
    <p aria-label="Recorded trade totals">Total completed trades: {stored(pooled.trades)} · Mean return after costs: <Value name="net_return" value={pooled.mean} /> · Total return: not recorded</p>
    <h4>Cost rule</h4><p>Basis points (bps) are hundredths of one percent. Values below are the recorded per-asset cost assumptions.</p>
    <Fields value={summary.costs} explanations={detail.label_explanations} />
    <Figure figure={outcome.figure} title="Recorded trade results and random-date comparison" />
    <details><summary>Stored trade summary and limitations</summary><Fields value={withoutOutcome(summary)} explanations={detail.label_explanations} /></details>
  </section>
}

function Detail({ detail }: { detail: SetupDetail }) {
  return <>
    <h2>{detail.run.description ?? 'Setup description: not recorded'}</h2>
    <DataHealth summary={object(detail.summary)} />
    <Labels labels={detail.run.labels} explanations={detail.label_explanations} />
    <p>Find identifier: {detail.run.find_id} · Trial indices: {stored(detail.trial_indices)}</p>
    <TrialLabels labels={detail.trial_labels} explanations={detail.label_explanations} shownAbove={detail.run.labels} />
    <h3>Instruments and recorded date span</h3>
    {detail.run.assets === null ? <p>Instruments: not recorded</p> : <Table caption="Stored data coverage" columns={[
      ['asset', 'Instrument'], ['first_bar', 'First bar'], ['last_bar', 'Last bar'], ['error', 'Recorded data error'],
    ]} rows={detail.run.assets} />}
    <h3>Matches and rejected candidates</h3>
    {object(object(detail.summary).totals).accepted === 0 && <p>No accepted matches recorded. Rejected or pending candidates remain below.</p>}
    <p>{detail.price_bars_reason} Entry, stop, target and exit levels are listed with each recorded trade below.</p>
    {detail.candidates === null ? <p>Matches: not recorded</p> : detail.candidates.length === 0 ? <p>No matches recorded.</p>
      : <><MatchTimeline candidates={detail.candidates} trades={detail.trades} />
        <div style={{ maxHeight: 420, overflow: 'auto' }}><Table caption="Every recorded candidate; rejected rows are grey and keep their reason" columns={MATCH_COLUMNS} rows={detail.candidates} /></div></>}
    {detail.sheets === null ? <p>Sheets: not recorded</p> : <>
      {detail.sheets.slice(0, 1).map(sheet => <Figure key={sheet.name} figure={sheet} title={`Recorded match sheet · ${sheet.name}`} />)}
      {detail.sheets.length > 1 && <details><summary>{detail.sheets.length - 1} more recorded match sheets</summary>
        {detail.sheets.slice(1).map(sheet => sheet.deferred ? <LazySheet key={sheet.name} findId={detail.run.find_id} sheet={sheet} /> : <Figure key={sheet.name} figure={sheet} title={`Recorded match sheet · ${sheet.name}`} />)}</details>}</>}
    <details><summary>Stored find counts and specification</summary><Fields value={detail.summary} explanations={detail.label_explanations} /><Fields value={detail.spec} explanations={detail.label_explanations} /></details>
    {!detail.studies.length && <p>Study: not recorded</p>}
    {detail.studies.map(outcome => <Study key={outcome.run_id} outcome={outcome} detail={detail} />)}
    {!detail.trades.length && <p>Trades: not recorded</p>}
    {detail.trades.map(outcome => <Trades key={outcome.run_id} outcome={outcome} detail={detail} />)}
    <aside aria-label="What this cannot tell you" style={{ border: '1px solid var(--line-strong)', padding: 12 }}>
      <h3>What this cannot tell you</h3><p>Limits from Setup find, Setup study and Setup trade:</p>
      {detail.limits.map(limit => <blockquote key={limit}>{limit}</blockquote>)}
    </aside>
  </>
}

/** What the list already knows about the selected setup, shown while its full record loads. */
function Skeleton({ run, selected }: { run: Schema['SetupRun'] | null; selected: string | null }) {
  if (!run) return <p role="status">{selected ? 'Loading selected setup…' : 'Select a setup run.'}</p>
  return <>
    <h2>{run.description ?? 'Setup description: not recorded'}</h2>
    <p role="status">Loading selected setup… The matches, trades and figures follow.</p>
    <p>Find identifier: {run.find_id}</p>
    {run.assets ? <Table caption="Stored data coverage" columns={[
      ['asset', 'Instrument'], ['first_bar', 'First bar'], ['last_bar', 'Last bar'], ['error', 'Recorded data error'],
    ]} rows={run.assets} /> : null}
  </>
}

export function SetupLabView({ list, selected, detail, error, onSelect }: {
  list: RunList | null; selected: string | null; detail: SetupDetail | null;
  error: string | null; onSelect: (id: string) => void
}) {
  return <div className="panel"><div className="panel-body" tabIndex={0} style={{ background: 'var(--panel)', color: 'var(--ink)', padding: 12 }}>
    <h1>Setup Lab</h1><p>Recorded exploratory results. These observations do not confirm an edge.</p>
    {error && <p role="alert">{error}</p>}
    {!list && !error && <p role="status">Loading setup runs…</p>}
    {list?.items.length === 0 && <p>No setup runs. No completed setup find has been recorded in this store.</p>}
    {list && list.items.length > 0 && <>
      <label>Recorded setup run (newest first) <select aria-label="Recorded setup run" value={selected ?? ''} onChange={event => onSelect(event.target.value)}>
        <option value="" disabled>Select a setup run</option>
        {list.items.map(run => <option key={run.find_id} value={run.find_id}>{run.description ?? 'Description not recorded'} · {run.find_id}</option>)}
      </select></label>
      <div aria-live="polite">{!error && (detail?.run.find_id === selected ? <Detail detail={detail} />
        : <Skeleton run={list.items.find(item => item.find_id === selected) ?? null} selected={selected} />)}</div>
    </>}
  </div></div>
}

export function SetupLabPanel() {
  const [list, setList] = useState<RunList | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const [detail, setDetail] = useState<SetupDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    let live = true
    getJSON<RunList>('/api/setup/runs').then(value => {
      if (live) { setList(value); setSelected(value.items[0]?.find_id ?? null) }
    }).catch((cause: unknown) => { if (live) setError(String(cause)) })
    return () => { live = false }
  }, [])
  useEffect(() => {
    let live = true
    if (selected) getJSON<SetupDetail>(`/api/setup/runs/${encodeURIComponent(selected)}`).then(value => {
      if (value.run.find_id !== selected) throw new Error('The stored result belongs to another setup.')
      if (live) { setDetail(value); setError(null) }
    }).catch((cause: unknown) => { if (live) setError(String(cause)) })
    return () => { live = false }
  }, [selected])
  return <SetupLabView list={list} selected={selected} detail={detail} error={error} onSelect={id => { setDetail(null); setError(null); setSelected(id) }} />
}
