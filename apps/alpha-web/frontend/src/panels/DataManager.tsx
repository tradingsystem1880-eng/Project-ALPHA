// Data Manager — one home for getting data into ALPHA: pull OHLC bars through the CLI (the
// profile picks the defaults, the venue's first listed bar sizes the request and names the retry
// start), the stored pairs, the Expansion SSD research datasets and the reviewed crypto assets.
// The second tab keeps the governed Research Data explorer (Crypto Data Center + research dataset
// bindings) intact. Every read is a CLI projection; nothing here holds authority.

import { useCallback, useEffect, useState } from 'react'

import { api } from '../api/client'
import { useAreaVersion } from '../state/activity'
import type { CryptoCoverage, CryptoStorage, DataSnapshots, DataSourceStatus, ProviderDefinition } from '../api/types'
import { CopyCommand } from '../components/CopyCommand'
import { JobConsole } from '../components/JobConsole'
import { Placeholder } from '../components/Placeholder'
import { setLinked, useLinked } from '../context/linked'
import type { PanelHandleProps } from '../context/panelHandle'
import { dockOf } from '../shell/documents'
import type { Profile } from '../state/settings'
import { useSettings } from '../state/settings'
import { buildDataPullArgs, historicalProviders, providerOptionDefault } from './controlPlane'
import type { ListingHint } from './dataManagerModel'
import {
  listingHint,
  pullDefaults,
  retryStartFrom,
  starterSymbols,
  storageRow,
  validateDates,
} from './dataManagerModel'
import { CLI_ONLY } from './researchCockpitModel'
import { ResearchDataExplorer } from './ResearchDataExplorer'

type Tab = 'Pull' | 'Snapshots' | 'Quality' | 'Storage'
const TAB_HELP: Readonly<Record<Tab, string>> = {
  Pull: 'Pull OHLC into the store and see the stored pairs',
  Snapshots: 'Every immutable data snapshot (alpha data snapshots), verify one, or freeze a new one',
  Quality: 'The governed Research Data explorer: datasets, quality checks, snapshots',
  Storage: 'Expansion SSD research datasets and the reviewed crypto assets',
}
const REVIEWED_ASSETS = ['BTC', 'ETH', 'XRP', 'SOL']
const ASSET_MASTER_RECIPE = [
  '# 1. Extend with_reviewed_native_assets() in alpha_data.crypto.asset_master (ADR-0032 review).',
  '# 2. Regenerate the receipted cross-provider asset master:',
  'uv run alpha crypto-data asset-master-create \\',
  '  --coingecko-manifest-id <qualified asset_metadata manifest> \\',
  '  --geckoterminal-manifest-id <qualified DEX pool catalog manifest> --json',
].join('\n')

function today(): string {
  return new Date().toISOString().slice(0, 10)
}

export function DataManager(props: PanelHandleProps) {
  const { profile } = useSettings()
  const [tab, setTab] = useState<Tab>('Pull')
  // Read inside the component: this module is itself imported by the registry.
  const tabs = dockOf('DataManager').tabs as readonly Tab[]
  return (
    <div className="panel data-manager">
      {tab === 'Quality' ? (
        <>
          <SourceStatusCard />
          <ResearchDataExplorer {...props} embedded />
        </>
      ) : tab === 'Snapshots' ? (
        <SnapshotsTab profile={profile} />
      ) : (
        <PullAndStore profile={profile} section={tab === 'Storage' ? 'storage' : 'pull'} />
      )}
      <nav className="rd-tabs dock-tabs" role="tablist" aria-label="Data Manager sections">
        {tabs.map((item) => (
          <button
            key={item}
            type="button"
            role="tab"
            aria-selected={tab === item}
            className={`rd-tab${tab === item ? ' active' : ''}`}
            title={TAB_HELP[item]}
            onClick={() => setTab(item)}
          >
            {item}
          </button>
        ))}
      </nav>
    </div>
  )
}

function PullAndStore({ profile, section }: { profile: Profile; section: 'pull' | 'storage' }) {
  const defaults = pullDefaults(profile)
  const [symbols, setSymbols] = useState<string[] | null>(null)
  const [providers, setProviders] = useState<ProviderDefinition[] | null>(null)
  const [storage, setStorage] = useState<CryptoStorage | null>(null)
  const [coverage, setCoverage] = useState<CryptoCoverage | null>(null)
  const [sym, setSym] = useState(defaults.symbol)
  const [source, setSource] = useState(defaults.source)
  const [exchange, setExchange] = useState(defaults.exchange)
  const [start, setStart] = useState('2015-01-01')
  const [end, setEnd] = useState(today)
  const [jobId, setJobId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [hint, setHint] = useState<ListingHint | null>(null)
  const [retryFrom, setRetryFrom] = useState<string | null>(null)
  const [assets, setAssets] = useState<Record<string, string> | null>(null)

  const load = useCallback(() => {
    setError(null)
    void Promise.all([api.symbols(), api.providers(), api.cryptoStorage(), api.cryptoCoverage()])
      .then(([stored, catalog, storageStatus, datasets]) => {
        setSymbols(stored.symbols)
        setProviders(catalog)
        setStorage(storageStatus)
        setCoverage(datasets)
        const available = historicalProviders(catalog)
        setSource((current) => {
          if (available.some((provider) => provider.id === current)) return current
          return available[0]?.id ?? ''
        })
      })
      .catch((reason: unknown) => setError(String(reason)))
  }, [])

  const barsVersion = useAreaVersion('bars')
  useEffect(() => {
    load()
  }, [load, barsVersion])

  // Switching profile re-seeds the form; the provider list then re-validates the source.
  useEffect(() => {
    setSym(defaults.symbol)
    setSource(defaults.source)
    setExchange(defaults.exchange)
    setHint(null)
    setRetryFrom(null)
  }, [defaults.symbol, defaults.source, defaults.exchange])

  const availableProviders = historicalProviders(providers ?? [])
  const activeProvider = availableProviders.find((provider) => provider.id === source)
  const exchangeOption = activeProvider?.options.exchange
  const symbol = sym.trim()

  function chooseSource(id: string): void {
    setSource(id)
    const selected = availableProviders.find((provider) => provider.id === id)
    const venueDefault = providerOptionDefault(selected, 'exchange')
    if (venueDefault) setExchange(venueDefault)
  }

  function estimate(): void {
    setError(null)
    setHint(null)
    setRetryFrom(null)
    const problem = validateDates(start, end)
    if (problem) {
      setError(problem)
      return
    }
    void api
      .firstBar(symbol, exchange)
      .then((first) => {
        const next = listingHint(first, start, end)
        setHint(next)
        setRetryFrom(next.retryFrom)
      })
      .catch((reason: unknown) => setError(String(reason)))
  }

  function pull(from: string): void {
    const problem = validateDates(from, end)
    if (problem) {
      setError(problem)
      return
    }
    setError(null)
    setRetryFrom(null)
    setStart(from)
    const args = buildDataPullArgs({ symbol, source, start: from, end, exchange })
    void api
      .launch('data pull', args)
      .then((result) => setJobId(result.job_id))
      .catch((reason: unknown) => setError(String(reason)))
  }

  function finished(id: string): void {
    load()
    void api.job(id).then((job) => {
      if (job.status === 'failed') setRetryFrom(retryStartFrom(job.current_step))
    })
  }

  function checkAssets(): void {
    const asOf = today()
    void Promise.all(
      REVIEWED_ASSETS.map((asset) =>
        api
          .cryptoAsset(asset, asOf)
          .then((identity) => [asset, identity.coingecko_id] as const)
          .catch(() => [asset, 'not reviewed'] as const),
      ),
    ).then((rows) => setAssets(Object.fromEntries(rows)))
  }

  const ssd = storageRow(storage)
  return (
    <div className="panel-body panel-pad de">
      {error ? <div className="leak">⚠ {error}</div> : null}
      {section === 'pull' ? (
        <>
      <div className="rd-head">Pull OHLC (backtest data)</div>
      <div className="lab-row">
        <label className="field-row">
          <span className="field-label">Symbol</span>
          <input
            id="data-manager-symbol"
            className="field"
            list="data-manager-symbols"
            value={sym}
            onChange={(e) => setSym(e.target.value)}
          />
          <datalist id="data-manager-symbols">
            {[...new Set([...starterSymbols(profile), ...(symbols ?? [])])].map((candidate) => (
              <option key={candidate} value={candidate} />
            ))}
          </datalist>
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
          <span className="field-label">From</span>
          <input className="field" type="date" value={start} onChange={(e) => setStart(e.target.value)} />
        </label>
        <label className="field-row">
          <span className="field-label">To</span>
          <input className="field" type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
        </label>
      </div>
      <div className="lab-actions">
        <button
          className="btn primary"
          onClick={() => pull(start)}
          disabled={!activeProvider?.configured || !symbol || !start || !end}
        >
          ⤓ Pull
        </button>
        <button className="btn" onClick={estimate} disabled={source !== 'ccxt' || !symbol}>
          Estimate
        </button>
        {retryFrom ? (
          <button className="btn" onClick={() => pull(retryFrom)}>
            Start there ({retryFrom})
          </button>
        ) : null}
        <span className="muted mono">
          {hint
            ? `listed ${hint.listed} · ~${hint.bars} bars`
            : providers === null
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
      {jobId ? <JobConsole jobId={jobId} onDone={() => finished(jobId)} /> : null}

      <div className="rd-head de-pull">Stored pairs</div>
      {symbols === null ? (
        <Placeholder>loading…</Placeholder>
      ) : symbols.length === 0 ? (
        <div className="muted">No pairs stored yet — pull one above.</div>
      ) : (
        <div className="sym-chips">
          {symbols.map((stored) => (
            <button key={stored} className="sym-chip" onClick={() => setLinked({ symbol: stored })}>
              {stored}
            </button>
          ))}
        </div>
      )}

        </>
      ) : (
        <>
      <div className="rd-head de-pull">Expansion SSD — research datasets</div>
      <div className="lab-row">
        <span className={`chip ${ssd.tone === 'ok' ? 'pass' : 'warn'}`}>{ssd.label}</span>
        <span className="muted mono">{ssd.detail}</span>
        <button className="btn" onClick={load}>
          refresh
        </button>
      </div>
      {storage?.state === 'ready' && coverage ? (
        coverage.items.length === 0 ? (
          <div className="muted">No qualified datasets yet.</div>
        ) : (
          <div className="table-scroll" tabIndex={0}>
            <table className="blotter">
              <thead>
                <tr>
                  <th>family</th>
                  <th>source</th>
                  <th>instrument</th>
                  <th>state</th>
                  <th className="r">rows</th>
                  <th>to</th>
                </tr>
              </thead>
              <tbody>
                {coverage.items.map((item) => (
                  <tr key={item.manifest_id}>
                    <td>{item.family}</td>
                    <td>
                      {item.provider} · {item.venue}
                    </td>
                    <td>{item.instrument}</td>
                    <td>{item.state}</td>
                    <td className="r">{item.row_count}</td>
                    <td>{item.observed_end?.slice(0, 10) ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      ) : null}

      <div className="rd-head de-pull">Reviewed crypto assets</div>
      <div className="lab-row">
        {REVIEWED_ASSETS.map((asset) => {
          const status = assets?.[asset]
          const tone = status === undefined ? 'kind' : status === 'not reviewed' ? 'warn' : 'pass'
          return (
            <span key={asset} className={`chip ${tone}`}>
              {status === undefined ? asset : `${asset} · ${status}`}
            </span>
          )
        })}
        <button className="btn" onClick={checkAssets}>
          check
        </button>
      </div>
      <details>
        <summary className="muted">Add a reviewed asset — CLI recipe (nothing is changed here)</summary>
        <pre className="mono">{ASSET_MASTER_RECIPE}</pre>
        <CopyCommand command={ASSET_MASTER_RECIPE.split('\n').filter((line) => !line.startsWith('#')).join(' ')} why={CLI_ONLY.assetMaster.why} />
      </details>
        </>
      )}
    </div>
  )
}

/** Canonical provenance and pending candidate/quarantine receipts for the linked symbol, with
 *  the audit of each receipt one click away (`alpha data audit PROVIDER RECEIPT`, a safe job). */
function SourceStatusCard() {
  const linked = useLinked()
  const barsVersion = useAreaVersion('bars')
  const [status, setStatus] = useState<DataSourceStatus | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [jobId, setJobId] = useState<string | null>(null)
  const symbol = linked.symbol
  useEffect(() => {
    if (!symbol) return
    let live = true
    setError(null)
    api
      .dataSourceStatus(symbol)
      .then((next) => live && setStatus(next))
      .catch((reason: unknown) => live && setError(reason instanceof Error ? reason.message : String(reason)))
    return () => {
      live = false
    }
  }, [symbol, barsVersion])
  if (!symbol) return null
  const audit = (receipt: string) => {
    const [provider, receiptId] = receipt.split(':', 2)
    api
      .launch('data', `audit ${provider} ${receiptId}`)
      .then((job) => setJobId(job.job_id))
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : String(reason)))
  }
  return (
    <section className="source-status" aria-label="Source status">
      <div className="rd-head">Source status · {symbol}</div>
      {error ? <span className="leak">⚠ {error}</span> : null}
      {status ? (
        <dl className="market-watch-details">
          <dt>Provenance</dt>
          <dd className="mono">{status.provenance ? JSON.stringify(status.provenance) : 'none recorded'}</dd>
          <dt>Promotion</dt>
          <dd className="mono">{status.promotion_pending ? 'PENDING' : 'settled'}</dd>
          <dt>Candidates</dt>
          <dd>{status.candidates.length ? status.candidates.map((receipt) => <button key={receipt} className="btn" type="button" onClick={() => audit(receipt)}>Audit {receipt}</button>) : <span className="muted">none</span>}</dd>
          <dt>Quarantined</dt>
          <dd>{status.quarantined.length ? status.quarantined.map((receipt) => <button key={receipt} className="btn" type="button" onClick={() => audit(receipt)}>Audit {receipt}</button>) : <span className="muted">none</span>}</dd>
        </dl>
      ) : null}
      {jobId ? <span className="muted">audit job {jobId} started — see the Toolbox Data pulls tab</span> : null}
    </section>
  )
}

/** Every immutable snapshot, verified or frozen on demand — each is a safe `alpha data` job. */
function SnapshotsTab({ profile }: { profile: Profile }) {
  const linked = useLinked()
  const barsVersion = useAreaVersion('bars')
  const [list, setList] = useState<DataSnapshots | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const defaults = pullDefaults(profile)
  const [snapshotId, setSnapshotId] = useState(() => `snap-${today().replaceAll('-', '')}`)
  const [symbols, setSymbols] = useState(linked.symbol ?? defaults.symbol)
  useEffect(() => {
    let live = true
    api
      .dataSnapshots()
      .then((next) => live && setList(next))
      .catch((reason: unknown) => live && setError(reason instanceof Error ? reason.message : String(reason)))
    return () => {
      live = false
    }
  }, [barsVersion])
  const run = (args: string, label: string) => {
    setError(null)
    api
      .launch('data', args)
      .then((job) => setNotice(`${label} started as job ${job.job_id} — see the Toolbox Data pulls tab`))
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : String(reason)))
  }
  return (
    <div className="dock-panel snapshots-tab">
      <div className="rd-head">Immutable snapshots</div>
      {error ? <span className="leak">⚠ {error}</span> : null}
      {notice ? <span className="muted">{notice}</span> : null}
      {list === null ? null : list.snapshots.length === 0 ? (
        <p className="muted">No snapshots yet. A snapshot freezes exactly the stored bars a run reads.</p>
      ) : (
        <table className="blotter" aria-label="Snapshots">
          <thead><tr><th>Snapshot</th><th>Source</th><th>Symbols</th><th>Created</th><th /></tr></thead>
          <tbody>
            {list.snapshots.map((row) => (
              <tr key={row.snapshot_id ?? row.manifest_sha256}>
                <td className="mono">{row.snapshot_id ?? '—'}</td>
                <td>{row.source ?? '—'}</td>
                <td className="mono">{row.symbols.join(' ')}</td>
                <td className="mono">{row.created_at ?? '—'}</td>
                <td><button className="btn" type="button" onClick={() => run(`verify ${row.snapshot_id ?? ''}`, `verify ${row.snapshot_id ?? ''}`)} disabled={!row.snapshot_id}>Verify</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <form
        className="snapshot-form"
        aria-label="Freeze snapshot"
        onSubmit={(event) => {
          event.preventDefault()
          const source = defaults.source
          const exchange = defaults.exchange ? ` --exchange ${defaults.exchange}` : ''
          run(`snapshot ${snapshotId.trim()} ${symbols.trim()} --source ${source}${exchange}`, `snapshot ${snapshotId.trim()}`)
        }}
      >
        <label className="field-row"><span className="field-label">Snapshot id</span><input className="field" value={snapshotId} onChange={(e) => setSnapshotId(e.target.value)} /></label>
        <label className="field-row"><span className="field-label">Symbols (space-separated)</span><input className="field" value={symbols} onChange={(e) => setSymbols(e.target.value)} /></label>
        <button className="btn primary" type="submit" disabled={!snapshotId.trim() || !symbols.trim()}>Freeze snapshot · {defaults.source}{defaults.exchange ? ` · ${defaults.exchange}` : ''}</button>
      </form>
    </div>
  )
}
