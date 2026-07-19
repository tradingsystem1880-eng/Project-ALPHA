// Data Explorer — the symbols in the store (click to broadcast to the linked context) and a form to
// pull new data through the CLI.

import { useCallback, useEffect, useState } from 'react'

import { api } from '../api/client'
import type { ProviderDefinition } from '../api/types'
import { setLinked } from '../context/linked'
import { JobConsole } from '../components/JobConsole'
import { Placeholder } from '../components/Placeholder'
import {
  buildDataPullArgs,
  historicalProviders,
  providerOptionDefault,
} from './controlPlane'

export function DataExplorer() {
  const [symbols, setSymbols] = useState<string[] | null>(null)
  const [providers, setProviders] = useState<ProviderDefinition[] | null>(null)
  const [sym, setSym] = useState('AAPL')
  const [source, setSource] = useState('')
  const [exchange, setExchange] = useState('coinbase')
  const [start, setStart] = useState('2015-01-01')
  const [end, setEnd] = useState('2024-12-31')
  const [jobId, setJobId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    setError(null)
    void Promise.all([api.symbols(), api.providers()])
      .then(([stored, catalog]) => {
        setSymbols(stored.symbols)
        setProviders(catalog)
        const available = historicalProviders(catalog)
        setSource((current) => {
          if (available.some((provider) => provider.id === current)) return current
          return available[0]?.id ?? ''
        })
      })
      .catch((reason: unknown) => setError(String(reason)))
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const availableProviders = historicalProviders(providers ?? [])
  const activeProvider = availableProviders.find((provider) => provider.id === source)
  const exchangeOption = activeProvider?.options.exchange

  function chooseSource(id: string): void {
    setSource(id)
    const selected = availableProviders.find((provider) => provider.id === id)
    const venueDefault = providerOptionDefault(selected, 'exchange')
    if (venueDefault) setExchange(venueDefault)
  }

  function pull(): void {
    setError(null)
    const args = buildDataPullArgs({ symbol: sym, source, start, end, exchange })
    void api
      .launch('data pull', args)
      .then((result) => setJobId(result.job_id))
      .catch((reason: unknown) => setError(String(reason)))
  }

  return (
    <div className="panel">
      <div className="panel-toolbar">
        <span className="title">Data Explorer</span>
        {symbols ? <span className="count">{symbols.length}</span> : null}
        <div className="spacer" />
        <button className="btn" onClick={load}>
          refresh
        </button>
      </div>
      <div className="panel-body panel-pad de">
        {error ? <div className="leak">⚠ {error}</div> : null}
        <div className="rd-head">Stored symbols</div>
        {symbols === null ? (
          <Placeholder>loading…</Placeholder>
        ) : symbols.length === 0 ? (
          <div className="muted">No symbols stored yet — pull some below.</div>
        ) : (
          <div className="sym-chips">
            {symbols.map((s) => (
              <button key={s} className="sym-chip" onClick={() => setLinked({ symbol: s })}>
                {s}
              </button>
            ))}
          </div>
        )}

        <div className="rd-head de-pull">Pull data</div>
        <div className="lab-row">
          <label className="field-row">
            <span className="field-label">Symbol</span>
            <input className="field" value={sym} onChange={(e) => setSym(e.target.value)} />
          </label>
          <label className="field-row">
            <span className="field-label">Source</span>
            <select className="field" value={source} onChange={(e) => chooseSource(e.target.value)}>
              {availableProviders.map((provider) => (
                <option key={provider.id} value={provider.id}>
                  {provider.label}
                </option>
              ))}
            </select>
          </label>
          {exchangeOption ? (
            <label className="field-row">
              <span className="field-label">{exchangeOption.label}</span>
              <select className="field" value={exchange} onChange={(e) => setExchange(e.target.value)}>
                {exchangeOption.choices.map((choice) => (
                  <option key={choice} value={choice}>
                    {choice}
                  </option>
                ))}
              </select>
            </label>
          ) : null}
          <label className="field-row">
            <span className="field-label">Start</span>
            <input className="field" value={start} onChange={(e) => setStart(e.target.value)} />
          </label>
          <label className="field-row">
            <span className="field-label">End</span>
            <input className="field" value={end} onChange={(e) => setEnd(e.target.value)} />
          </label>
        </div>
        <div className="lab-actions">
          <button
            className="btn primary"
            onClick={pull}
            disabled={!activeProvider?.configured || !sym.trim() || !start || !end}
          >
            ⤓ Pull
          </button>
          <span className="muted mono">
            {providers === null
              ? 'loading providers…'
              : activeProvider?.network_required
                ? 'needs network'
                : 'local'}
          </span>
        </div>
        {activeProvider && !activeProvider.configured ? (
          <div className="leak">
            Provider is not configured. Missing:{' '}
            {activeProvider.credential_env
              .filter((credential) => !credential.present)
              .map((credential) => credential.name)
              .join(', ') || 'local package'}
          </div>
        ) : null}
        {activeProvider?.limitations.length ? (
          <div className="provider-limit muted">{activeProvider.limitations.join(' · ')}</div>
        ) : null}
        {jobId ? <JobConsole jobId={jobId} onDone={load} /> : null}
      </div>
    </div>
  )
}
