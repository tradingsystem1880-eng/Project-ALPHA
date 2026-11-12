import { useEffect, useRef, useState } from 'react'
import { inspectRetainedCoverage, type RetainedCoverageResponse } from '../api/retainedCoverage'
import type { CryptoQuality } from '../api/types'

type Outcome = { state: 'idle' | 'loading' | 'cancelled' }
  | { state: 'error'; message: string }
  | { state: 'complete'; report: RetainedCoverageResponse }

export function RetainedBarCoverage({ quality }: { quality: CryptoQuality }) {
  const [start, setStart] = useState('')
  const [end, setEnd] = useState('')
  const [cutoff, setCutoff] = useState('')
  const [hashCap, setHashCap] = useState('')
  const [outcome, setOutcome] = useState<Outcome>({ state: 'idle' })
  const active = useRef<AbortController | null>(null)
  const epoch = useRef(0)
  useEffect(() => () => { epoch.current++; active.current?.abort() }, [])
  const dataset = quality.dataset
  const supported = dataset.provider === 'binance' && dataset.venue === 'binance'
    && dataset.market_type === 'spot' && dataset.family === 'market_bars'
    && dataset.frequency === '1d' && dataset.units === 'provider_native_ohlcv'
    && dataset.timestamp_convention === 'interval_start_utc'
  const loading = outcome.state === 'loading'

  function clearResult() { setOutcome({ state: 'idle' }) }
  async function inspect() {
    const current = ++epoch.current
    active.current?.abort()
    const controller = new AbortController()
    active.current = controller
    setOutcome({ state: 'loading' })
    try {
      const report = await inspectRetainedCoverage(quality.manifest_id, {
        coverage_start: start, coverage_end: end, as_of: cutoff,
        expected_cadence_seconds: 86400, max_verify_artifact_bytes: Number(hashCap),
      }, controller.signal)
      if (current === epoch.current) setOutcome({ state: 'complete', report })
    } catch (cause) {
      if (current === epoch.current && !controller.signal.aborted) {
        setOutcome({ state: 'error', message: cause instanceof Error ? cause.message : 'Retained coverage unavailable.' })
      }
    }
  }
  const report = outcome.state === 'complete' ? outcome.report : null
  const rows = report?.audit_state === 'inspected' ? report.row_audit : null
  return <section className="provider-card" aria-label="Retained daily bar coverage">
    <h3>Inspect retained daily bar coverage</h3>
    <p>Read-only diagnostics for this selected manifest. Binance spot native 1d bars only;
      cadence 86,400 seconds. Declare the grid explicitly. No data is fetched or repaired.</p>
    <p>Missing grid slots do not prove missing trades or complete provider history.
      The cutoff is a period-closure check, not publication availability or PIT eligibility.
      This inspection grants no admission or execution authority.</p>
    {!supported ? <p role="status">Unavailable for this dataset: select Binance spot native daily market bars.</p> :
      <form onSubmit={event => { event.preventDefault(); void inspect() }}>
        <fieldset className="crypto-form-grid" disabled={loading}>
          <legend>Caller-declared UTC grid · end exclusive</legend>
          <label>Coverage start (ISO UTC)<input className="field mono" aria-label="Coverage start (ISO UTC)" required value={start}
            placeholder="2024-01-01T00:00:00Z" onChange={event => { setStart(event.target.value); clearResult() }} /></label>
          <label>Coverage end exclusive (ISO UTC)<input className="field mono" aria-label="Coverage end exclusive (ISO UTC)" required value={end}
            placeholder="2024-01-05T00:00:00Z" onChange={event => { setEnd(event.target.value); clearResult() }} /></label>
          <label>Closure cutoff as_of (ISO UTC)<input className="field mono" aria-label="Closure cutoff as_of (ISO UTC)" required value={cutoff}
            placeholder="2024-01-05T00:00:00Z" onChange={event => { setCutoff(event.target.value); clearResult() }} /></label>
          <label>Maximum artifact hash bytes<input className="field mono" aria-label="Maximum artifact hash bytes" type="number" required
            min="1" max="9007199254740991" step="1" value={hashCap}
            onChange={event => { setHashCap(event.target.value); clearResult() }} /></label>
          <button className="btn primary" type="submit">Inspect retained grid</button>
        </fieldset>
        <p className="muted">Inspection ceilings: 32 MiB normalized input, 32 MiB metadata,
          50,000 returned rows and 1,000 missing ranges. Hash reads have the explicit cap above;
          payload reads have a separate 32 MiB + 1 byte ceiling. Decoder peak memory and wall time
          are not covered by these counters. The server command has a 60-second timeout.</p>
      </form>}
    {loading ? <div role="status">Inspecting retained evidence… <button className="btn" type="button" onClick={() => {
      ++epoch.current; active.current?.abort(); setOutcome({ state: 'cancelled' })
    }}>Stop waiting</button></div> : null}
    {outcome.state === 'cancelled' ? <p role="status">Stopped waiting; the server inspection may still finish within its timeout. No acquisition was started.</p> : null}
    {outcome.state === 'error' ? <p role="alert">{outcome.message}</p> : null}
    {report?.audit_state === 'unavailable' ? <p role="status">Retained evidence unavailable or unverifiable within the declared limits. No complete grid result is available. Review storage, evidence and bounds before retrying.</p> : null}
    {rows ? <div aria-label="Retained grid result">
      <p role="status">{rows.declared_grid_satisfied ? 'Declared grid satisfied' : 'Declared grid has findings'}</p>
      <p>Requested: {rows.start} → {rows.end_exclusive} (exclusive); cutoff {rows.as_of}.</p>
      <p>{rows.covered_slots} covered / {rows.expected_slots} expected slots · {rows.missing_slots} missing slots.</p>
      <p>{rows.row_count} retained rows · {rows.in_window_rows} in window · {rows.outside_window_rows} outside window.</p>
      <p>Duplicate groups: {rows.duplicate_timestamp_groups}; extra rows: {rows.duplicate_extra_rows};
        identical groups: {rows.identical_duplicate_groups}; conflicting groups: {rows.conflicting_duplicate_groups}.</p>
      <p>Invalid timestamps: {rows.invalid_timestamp_rows}; invalid close timestamps: {rows.invalid_close_timestamp_rows};
        off grid: {rows.off_grid_rows}; invalid numeric rows: {rows.invalid_numeric_rows}.</p>
      <p>Failures: {rows.failures.join(', ') || 'none'} · Warnings: {rows.warnings.join(', ') || 'none'}.</p>
      <p>Stored quality remains {report?.stored_quality?.state}; it has not been rewritten.</p>
      {report?.source_retrieved_after_as_of ? <p>Source evidence was retrieved after the requested cutoff. Historical publication availability is unproven.</p> : null}
      <p>{rows.missing_range_count} missing ranges{rows.missing_ranges_truncated ? ' · output truncated; exact missing totals retained' : ''}.</p>
      {rows.missing_ranges.length ? <table className="blotter compact" aria-label="Missing declared daily intervals">
        <thead><tr><th>Start (UTC)</th><th>End exclusive (UTC)</th><th>Missing slots</th></tr></thead>
        <tbody>{rows.missing_ranges.map(range => <tr key={range.start}><td>{range.start}</td><td>{range.end}</td><td>{range.slots}</td></tr>)}</tbody>
      </table> : null}
    </div> : null}
    {report ? <p>Inspection read {report.hash_bytes_read ?? 'unknown'} artifact hash bytes and {report.metadata_bytes_read ?? 'unknown'} metadata bytes.
      Provider calls: 0. Provider-history completeness and PIT eligibility: unproven.</p> : null}
  </section>
}
