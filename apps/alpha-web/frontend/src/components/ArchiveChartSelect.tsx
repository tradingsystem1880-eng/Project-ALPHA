/** Archive identity stays separate from the canonical linked strategy symbol. */
import { useEffect, useState } from 'react'
import { api, type ArchiveChartDataset } from '../api/client'

export function ArchiveChartSelect({ onSelect, onClose, initialQuery = '', initialTimeframe = 'all' }: { onSelect: (item: ArchiveChartDataset) => void; onClose: () => void; initialQuery?: string; initialTimeframe?: string }) {
  const [items, setItems] = useState<ArchiveChartDataset[] | null>(null)
  const [query, setQuery] = useState(initialQuery)
  const [timeframe, setTimeframe] = useState(initialTimeframe)
  const [error, setError] = useState<string | null>(null)
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    let alive = true
    setError(null)
    setItems(null)
    api.chartDatasets().then(result => alive && setItems(result.datasets)).catch(cause => alive && setError(String(cause)))
    return () => { alive = false }
  }, [attempt])
  const matches = (items ?? []).filter(item => (timeframe === 'all' || item.frequency === timeframe) && `${item.instrument} ${item.venue} ${item.market_type} ${item.frequency}`.toLowerCase().includes(query.toLowerCase()))
  return <section className="archive-chart-picker" aria-label="External archive datasets">
    <header><strong>External archive — select an exact dataset</strong><button className="btn" onClick={onClose}>Close archive picker</button></header>
    <div className="lab-row">
      <input className="field" aria-label="Search archive datasets" placeholder="Search symbol, venue or market type" value={query} onChange={event => setQuery(event.target.value)} />
      <label className="field-row"><span className="field-label">Native timeframe</span><select className="field" aria-label="Filter archive timeframe" value={timeframe} onChange={event => setTimeframe(event.target.value)}>
        <option value="all">All intervals</option>{['1m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '8h', '12h', '1d', '3d', '1w'].map(value => <option key={value} value={value}>{value}</option>)}
      </select></label>
    </div>
    {error ? <div role="alert">{error}<button className="btn" onClick={() => setAttempt(value => value + 1)}>Retry archive discovery</button></div> : items === null ? <p role="status">Reading archive metadata…</p> : <>
      <p>{matches.length} matching chart series · {new Set(matches.map(item => item.instrument)).size} instruments. Monthly segments join only when venue, pair, market and native interval match; artifact bytes and raw lineage are verified when opened.</p>
      {matches.length ? <div className="archive-chart-results"><table className="blotter"><thead><tr><th>Instrument</th><th>Venue / market</th><th>Interval</th><th>Coverage</th><th>Source rows</th><th>Dataset</th></tr></thead><tbody>{matches.slice(0, 200).map(item => <tr key={item.manifest_id}>
        <td><button className="btn" onClick={() => onSelect(item)}>Open {item.instrument}</button></td><td>{item.venue} · {item.market_type}</td><td>{item.frequency}</td><td>{item.start?.slice(0, 16)} → {item.end?.slice(0, 16)}</td><td>{item.row_count}</td><td title={item.manifest_ids.join('\n')}>{item.manifest_count} segments · {item.manifest_id.slice(0, 10)}</td>
      </tr>)}</tbody></table></div> : <p>No compatible datasets found. Check the mounted drive or adjust the search.</p>}
      {matches.length > 200 ? <p>Showing the first 200 matches. Narrow the search to find a specific instrument or interval.</p> : null}
    </>}
  </section>
}
