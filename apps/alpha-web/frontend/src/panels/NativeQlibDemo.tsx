import { useEffect, useMemo, useState } from 'react'
import { CopyCommand } from '../components/CopyCommand'
import { Placeholder } from '../components/Placeholder'
import { RecordedSeries } from '../components/RecordedSeries'
import { fmtNum } from '../util/format'
import { Section } from './rundetail/common'
import { readNativeQlibDemo, type NativeQlibResult } from './nativeQlibDemoModel'

const ARTIFACTS = `${import.meta.env.BASE_URL}demos/native-qlib/`

export function NativeQlibDemo() {
  const [result, setResult] = useState<NativeQlibResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [symbol, setSymbol] = useState('SYN00')
  const [diagnostic, setDiagnostic] = useState<'ic' | 'rank_ic'>('ic')
  useEffect(() => {
    const controller = new AbortController()
    fetch(`${ARTIFACTS}result.json`, { signal: controller.signal })
      .then(response => { if (!response.ok) throw new Error(`Recorded demo file unavailable (${response.status})`); return response.json() })
      .then(value => { if (!controller.signal.aborted) setResult(readNativeQlibDemo(value)) })
      .catch(reason => { if (!controller.signal.aborted) setError(String(reason)) })
    return () => controller.abort()
  }, [])
  const rows = useMemo(() => result?.predictions.filter(row => row.symbol === symbol) ?? [], [result, symbol])
  const scores = useMemo(() => rows.map(row => ({ time: Date.parse(row.session_ts) / 1000, value: row.score })), [rows])
  const diagnostics = useMemo(() => result?.diagnostics.map(row => ({ time: Date.parse(row.session_ts) / 1000, value: row[diagnostic] })) ?? [], [result, diagnostic])
  if (error) return <div className="panel"><div className="panel-body panel-pad"><p role="alert">{error}</p></div></div>
  if (!result) return <Placeholder>Reading the recorded native Qlib demonstration…</Placeholder>
  const symbols = [...new Set(result.predictions.map(row => row.symbol))]
  const downloadConfig = () => {
    const url = URL.createObjectURL(new Blob([result.config], { type: 'application/yaml;charset=utf-8' }))
    const anchor = document.createElement('a')
    anchor.href = url; anchor.download = 'native-qlib-workflow.yaml'
    document.body.append(anchor); anchor.click(); anchor.remove(); URL.revokeObjectURL(url)
  }
  return <div className="panel">
    <div className="panel-toolbar"><span className="title">Native Qlib result</span><span className="chip kind">SYNTHETIC · READ ONLY</span></div>
    <div className="panel-body panel-pad workbench" aria-label="Native Qlib synthetic result">
      <div className="workbench-notice" role="note"><strong>Synthetic engineering demonstration</strong><span>Real upstream qrun execution; generated data. No admitted experiment, research consumption, trading result or promotion approval.</span></div>
      <Section title="What ran">
        <p>Qlib {result.qlib_version} · {result.model} · recorder <strong>{result.status}</strong>. One native fit generated all {result.test_rows} test predictions.</p>
        <div className="ml-provenance-grid">
          <div><span>TRAIN / VALIDATION / TEST</span><code>{result.train_rows} / {result.valid_rows} / {result.test_rows} rows</code></div>
          <div><span>BOUNDED EXECUTION</span><code>{result.threads} CPU thread · {result.rounds} rounds · {fmtNum(result.wall_seconds, 2)} seconds</code></div>
          <div><span>NATIVE RECORDER ID</span><code>{result.run_id}</code></div>
          <div><span>GENERATED INPUT</span><code>{result.sessions} dates · {result.symbols} symbols · {result.features} features · seed {result.seed}</code></div>
        </div>
        <p>The first 48 dates trained the model; the next 16 selected its state; the final 16 produced the scores below. The target was constructed from the inputs: <span className="mono">{result.target_description}</span>.</p>
      </Section>
      <Section title="Chronological test scores">
        <label className="eyebrow" htmlFor="native-demo-symbol">Synthetic symbol</label>{' '}
        <select className="field" id="native-demo-symbol" value={symbol} onChange={event => setSymbol(event.target.value)}>{symbols.map(name => <option key={name}>{name}</option>)}</select>
        <p>These are the native recorder’s scores in date order, not equity or returns. Select a symbol to inspect its complete 16-date test series.</p>
        <RecordedSeries points={scores} label={`Native score · ${symbol}`} unit="synthetic target units" panelId={`native-qlib-score-${symbol}`} />
        <details className="native-data-table"><summary>Scores and constructed targets · {rows.length} rows</summary><table className="blotter compact" aria-label="Native scores and synthetic targets"><thead><tr><th>Session UTC</th><th>Symbol</th><th className="r">Native score</th><th className="r">Synthetic target</th></tr></thead><tbody>{rows.map(row => <tr key={row.session_ts}><td className="mono">{row.session_ts.slice(0, 10)}</td><td>{row.symbol}</td><td className="num">{fmtNum(row.score, 6)}</td><td className="num">{fmtNum(row.synthetic_target, 6)}</td></tr>)}</tbody></table></details>
      </Section>
      <Section title="Native signal diagnostics">
        <p>Mean IC <strong>{fmtNum(result.metrics.ic, 4)}</strong> · mean rank IC <strong>{fmtNum(result.metrics.rank_ic, 4)}</strong>. Each daily correlation compares scores with constructed targets across eight synthetic symbols. High correlation here shows that the planted signal was learned; it does not establish a trading edge.</p>
        <label className="eyebrow" htmlFor="native-demo-diagnostic">Recorded diagnostic</label>{' '}
        <select className="field" id="native-demo-diagnostic" value={diagnostic} onChange={event => setDiagnostic(event.target.value as 'ic' | 'rank_ic')}><option value="ic">IC</option><option value="rank_ic">Rank IC</option></select>
        <RecordedSeries points={diagnostics} label={diagnostic === 'ic' ? 'Native daily IC' : 'Native daily rank IC'} unit="correlation" panelId={`native-qlib-${diagnostic}`} />
      </Section>
      <Section title="Recorded command, config and files">
        <CopyCommand command={result.command} why="Recorded upstream command; copying does not execute or admit research." />
        <details><summary>Native workflow YAML (machine paths shown as $OUTPUT; config_sha256 is of the executed original)</summary><pre className="repro">{result.config}</pre></details>
        <p><a className="btn" href={`${ARTIFACTS}native_predictions.csv`} download>All 128 scores CSV</a>{' '}<a className="btn" href={`${ARTIFACTS}daily_signal_diagnostics.csv`} download>Daily diagnostics CSV</a>{' '}<button className="btn" type="button" onClick={downloadConfig}>Native workflow YAML</button></p>
        <details><summary>Artifact provenance</summary><pre className="repro">{JSON.stringify({ run_id: result.run_id, input_sha256: result.input_sha256, config_sha256: result.config_sha256, qrun_source_sha256: result.qrun_source_sha256, artifact_sha256: result.artifact_sha256 }, null, 2)}</pre></details>
        <p className="muted">Fixed packaged demo files only. Native model/dataset pickles stay outside this UI. Canonical exchange admission, research history and promotion state are unchanged.</p>
      </Section>
    </div>
  </div>
}
