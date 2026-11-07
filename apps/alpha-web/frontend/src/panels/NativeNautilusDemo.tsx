import { useEffect, useMemo, useState } from 'react'
import { CopyCommand } from '../components/CopyCommand'
import { MiniLine } from '../components/MiniLine'
import { Placeholder } from '../components/Placeholder'
import { CHART } from '../util/chartTheme'
import { fmtNum } from '../util/format'
import { Section } from './rundetail/common'
import { readNativeNautilusDemo, type NativeNautilusResult } from './nativeNautilusDemoModel'
import './nativeNautilusDemo.css'

const ARTIFACTS = `${import.meta.env.BASE_URL}demos/native-nautilus/`
const FILES = ['orders.csv', 'fills.csv', 'positions.csv', 'native-config.json', 'native-result.json', 'producer-result.json', 'provenance.json']
const utc = (value: string) => value.replace('T', ' ').replace('Z', ' UTC')

export function NativeNautilusDemo() {
  const [result, setResult] = useState<NativeNautilusResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [field, setField] = useState<'account_balance' | 'free_balance' | 'locked_balance'>('account_balance')
  useEffect(() => {
    const controller = new AbortController()
    fetch(`${ARTIFACTS}result.json`, { signal: controller.signal })
      .then(response => { if (!response.ok) throw new Error(`Recorded Nautilus file unavailable (${response.status})`); return response.json() })
      .then(value => { if (!controller.signal.aborted) setResult(readNativeNautilusDemo(value)) })
      .catch(reason => { if (!controller.signal.aborted) setError(String(reason)) })
    return () => controller.abort()
  }, [])
  const balances = useMemo(() => [{ label: field.replaceAll('_', ' '), colour: CHART.accent, points: result?.balances.map(row => [row.sequence, row[field]] as [number, number]) ?? [] }], [result, field])
  const fills = useMemo(() => [{ label: 'Native fill price', colour: CHART.gold, points: result?.fills.map((row, index) => [index + 1, Number(row.price)] as [number, number]) ?? [] }], [result])
  if (error) return <div className="panel"><div className="panel-body panel-pad"><p role="alert">{error}</p></div></div>
  if (!result) return <Placeholder>Reading the recorded native Nautilus demonstration…</Placeholder>
  const downloadAccountEvents = () => {
    const url = URL.createObjectURL(new Blob([result.account_events_csv], { type: 'text/csv;charset=utf-8' }))
    const anchor = document.createElement('a'); anchor.href = url; anchor.download = 'account-events.csv'
    document.body.append(anchor); anchor.click(); anchor.remove(); URL.revokeObjectURL(url)
  }
  return <div className="panel">
    <div className="panel-toolbar"><span className="title">Native Nautilus result</span><span className="chip kind">SYNTHETIC · NO LIVE TRADING</span></div>
    <div className="panel-body panel-pad workbench native-nautilus-demo" aria-label="Native Nautilus synthetic result">
      <div className="workbench-notice" role="note"><strong>Synthetic native execution demonstration</strong><span>Archived upstream EMACross / BacktestNode execution. No admitted research, validated returns, live routing or promotion approval. This run is separate from the Qlib demonstration.</span></div>
      <Section title="What ran">
        <p>NautilusTrader {result.version} · unmodified EMACross · {result.instrument}. Displaying <strong>{result.selected_run}</strong>; this view does not rerun the simulation.</p>
        <div className="ml-provenance-grid">
          <div><span>NATIVE EXECUTION</span><code>{result.orders.length} orders · {result.fills.length} fills · {result.positions.length} closed positions</code></div>
          <div><span>FABRICATED INPUT</span><code>{result.input_ticks} fresh ticks · {result.simulation_seconds} simulated seconds</code></div>
          <div><span>NATIVE RUN ID</span><code>{result.run_id}</code></div>
          <div><span>PRODUCER REPEAT CHECK</span><code>{result.producer_runs} runs / {result.producer_processes} processes · normalized reports agree</code></div>
        </div>
        <p>The producer used deliberately oscillating synthetic prices. Matching normalized reports demonstrate repeatable execution on that fixture, not a profitable strategy on market data. Raw IDs and execution metadata remain in the downloads.</p>
      </Section>
      <Section title="Native account-balance events — not equity">
        <p>All {result.balances.length} events are retained in native sequence, including equal UTC timestamps. These are recorded account balances in {result.currency}, not mark-to-market equity, unrealized P/L or investment returns.</p>
        <label className="eyebrow" htmlFor="native-nautilus-balance">Balance field</label>{' '}<select className="field" id="native-nautilus-balance" value={field} onChange={event => setField(event.target.value as typeof field)}><option value="account_balance">Total account balance</option><option value="free_balance">Free balance</option><option value="locked_balance">Locked balance</option></select>
        <div className="native-nautilus-balance"><p className="muted">{field === 'locked_balance' ? 'Axis amounts are USD.' : 'Axis labels use USD millions (M); the plotted values are native USD balances.'} Exact amounts remain in the table and CSV.</p><MiniLine series={balances} xLabel="Native event sequence · UTC timestamps in table" yLabel={`${field.replaceAll('_', ' ')} (${result.currency})`} formatY={value => field === 'locked_balance' ? fmtNum(value, 2) : `${(value / 1_000_000).toFixed(6)}M`} /></div>
        <details className="native-data-table"><summary>All 31 account events · equal timestamps preserved</summary><div style={{ overflowX: 'auto' }}><table className="blotter compact" aria-label="Native account balance events"><thead><tr><th>Seq</th><th>UTC timestamp</th><th className="r">Total USD</th><th className="r">Locked USD</th><th className="r">Free USD</th></tr></thead><tbody>{result.balances.map(row => <tr key={row.sequence}><td>{row.sequence}</td><td className="mono">{utc(row.timestamp)}</td><td className="num">{fmtNum(row.account_balance, 2)}</td><td className="num">{fmtNum(row.locked_balance, 2)}</td><td className="num">{fmtNum(row.free_balance, 2)}</td></tr>)}</tbody></table></div></details>
      </Section>
      <Section title="Chronological orders, fills and closed positions">
        <MiniLine series={fills} xLabel="Fill row · native chronological order, ties retained" yLabel="Native fill price (USD per EUR)" formatY={value => fmtNum(value, 5)} />
        <details className="native-data-table"><summary>Orders · 30 native rows</summary><div style={{ overflowX: 'auto' }}><table className="blotter compact" aria-label="Native Nautilus orders"><thead><tr><th>UTC initialized</th><th>Order ID</th><th>Side</th><th>Quantity</th><th>Native avg price</th><th>Status</th></tr></thead><tbody>{result.orders.map(row => <tr key={row.id}><td className="mono">{utc(row.timestamp)}</td><td className="mono">{row.id}</td><td>{row.side}</td><td>{row.quantity}</td><td>{row.price}</td><td>{row.status}</td></tr>)}</tbody></table></div></details>
        <details className="native-data-table"><summary>Fills · 30 native rows</summary><div style={{ overflowX: 'auto' }}><table className="blotter compact" aria-label="Native Nautilus fills"><thead><tr><th>UTC executed</th><th>Order ID</th><th>Side</th><th>Quantity</th><th>Price</th><th>Commission</th></tr></thead><tbody>{result.fills.map(row => <tr key={row.id}><td className="mono">{utc(row.timestamp)}</td><td className="mono">{row.order_id}</td><td>{row.side}</td><td>{row.quantity}</td><td>{row.price}</td><td>{row.commission}</td></tr>)}</tbody></table></div></details>
        <details className="native-data-table"><summary>Closed positions · 15 native rows</summary><div style={{ overflowX: 'auto' }}><table className="blotter compact" aria-label="Native Nautilus closed positions"><thead><tr><th>Position ID</th><th>Opened UTC</th><th>Closed UTC</th><th>Entry</th><th>Peak quantity</th><th>Open / close price</th><th>Native realized P/L</th></tr></thead><tbody>{result.positions.map(row => <tr key={row.id}><td>{row.id}</td><td className="mono">{utc(row.opened_at)}</td><td className="mono">{utc(row.closed_at)}</td><td>{row.entry}</td><td>{row.peak_quantity}</td><td>{row.open_price} / {row.close_price}</td><td>{row.realized_pnl}</td></tr>)}</tbody></table></div></details>
      </Section>
      <Section title="Native configuration, source and exact files">
        <p>Official source commit <code>{result.upstream_commit}</code>. Strategy <code>{result.strategy}</code>.</p>
        <details><summary>Archived native BacktestNode configuration</summary><pre className="repro">{JSON.stringify(result.native_config, null, 2)}</pre></details>
        <CopyCommand command={result.reproduction_template} why="Producer template only; requires the bundle and existing runtime. Archived paths are producer-local. Nothing is executed here." />
        <p><button className="btn" type="button" onClick={downloadAccountEvents}>account-events.csv</button>{FILES.map(name => <a className="btn" key={name} href={`${ARTIFACTS}${name}`} download>{name}</a>)}</p>
        <details><summary>Runtime and transferred-artifact provenance</summary><pre className="repro">{JSON.stringify({ version: result.version, run_id: result.run_id, config_id: result.config_id, strategy_sha256: result.strategy_sha256, normalized_reports_sha256: result.normalized_reports_sha256, transfer: result.transfer, artifact_sha256: result.artifact_sha256 }, null, 2)}</pre></details>
        <p className="muted">Read-only saved output. No native engine, canonical store, research consumption, trading connection or admission action is invoked by this view.</p>
      </Section>
    </div>
  </div>
}
