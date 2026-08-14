import { useCallback, useEffect, useMemo, useState } from 'react'

import { api } from '../api/client'
import type {
  CryptoAcquisitionRequest,
  CryptoAssetIdentity,
  CryptoCatalog,
  CryptoCapabilities,
  CryptoCoverage,
  CryptoCoverageItem,
  CryptoEstimate,
  CryptoFamily,
  CryptoQuality,
  CryptoSnapshotCreate,
  CryptoSnapshotRegister,
  CryptoSnapshotVerify,
  CryptoStorage,
  CryptoStorageInventory,
  CryptoStorageVerify,
  CryptoCacheClean,
} from '../api/types'
import { JobConsole } from '../components/JobConsole'
import { shortId } from '../util/format'
import {
  cryptoCanonicalAction,
  cryptoSectionForFamily,
  latestCryptoManifestIds,
  type CryptoDataSection,
} from './researchDataModel'

const SECTIONS: { id: CryptoDataSection; label: string }[] = [
  { id: 'assets', label: 'Assets & Contracts' },
  { id: 'cex', label: 'CEX History' },
  { id: 'derivatives', label: 'Derivatives & Funding' },
  { id: 'options', label: 'Options & Volatility' },
  { id: 'onchain', label: 'On-chain Metrics' },
  { id: 'dex', label: 'DEX Pools & Liquidity' },
  { id: 'quality', label: 'Coverage & Quality' },
  { id: 'storage', label: 'Storage & Jobs' },
]

const PROVIDERS = new Set(['binance', 'bybit', 'coingecko', 'geckoterminal', 'coinmetrics'])

function acquisitionProvider(value: string): CryptoAcquisitionRequest['provider'] | null {
  if (PROVIDERS.has(value)) return value as CryptoAcquisitionRequest['provider']
  return null
}

function defaultInstrument(family: CryptoFamily): string {
  if (family === 'asset_metadata' || family === 'market_reference') return 'bitcoin'
  if (family === 'onchain_metrics') return 'btc'
  if (family.startsWith('option_') || family === 'historical_volatility') return 'BTC'
  return 'BTCUSDT'
}

function stateClass(state: CryptoCoverageItem['state']): string {
  if (state === 'qualified') return 'chip pass'
  if (state === 'quarantined' || state === 'unavailable') return 'chip fail'
  return 'chip'
}

function bytesLabel(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let size = value
  let unit = 0
  while (size >= 1000 && unit < units.length - 1) {
    size /= 1000
    unit += 1
  }
  return `${size.toFixed(unit < 2 ? 0 : 1)} ${units[unit]}`
}

export function CryptoDataCenter({ onRegistered }: { onRegistered?: () => void }) {
  const [section, setSection] = useState<CryptoDataSection>('derivatives')
  const [catalog, setCatalog] = useState<CryptoCatalog | null>(null)
  const [capabilities, setCapabilities] = useState<CryptoCapabilities | null>(null)
  const [storage, setStorage] = useState<CryptoStorage | null>(null)
  const [coverage, setCoverage] = useState<CryptoCoverage | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [family, setFamily] = useState<CryptoFamily>('funding')
  const [instrument, setInstrument] = useState('BTCUSDT')
  const [base, setBase] = useState('BTC')
  const [quote, setQuote] = useState('USDT')
  const [category, setCategory] = useState<CryptoAcquisitionRequest['category']>('linear')
  const [frequency, setFrequency] = useState<CryptoAcquisitionRequest['frequency']>('1h')
  const [period, setPeriod] = useState('2026-07')
  const [network, setNetwork] = useState('eth')
  const [poolAddress, setPoolAddress] = useState('')
  const [metrics, setMetrics] = useState('AdrActCnt,TxCnt,FeeTotNtv')
  const [start, setStart] = useState('2025-01-01T00:00:00Z')
  const [end, setEnd] = useState('2026-01-01T00:00:00Z')
  const [days, setDays] = useState(30)
  const [estimate, setEstimate] = useState<CryptoEstimate | null>(null)
  const [asset, setAsset] = useState<CryptoAssetIdentity | null>(null)
  const [quality, setQuality] = useState<CryptoQuality | null>(null)
  const [selected, setSelected] = useState<Set<string>>(() => new Set())
  const [jobId, setJobId] = useState<string | null>(null)
  const [jobFinished, setJobFinished] = useState(false)
  const [snapshot, setSnapshot] = useState<CryptoSnapshotCreate | null>(null)
  const [verification, setVerification] = useState<CryptoSnapshotVerify | null>(null)
  const [registration, setRegistration] = useState<CryptoSnapshotRegister | null>(null)
  const [storageInventory, setStorageInventory] = useState<CryptoStorageInventory | null>(null)
  const [storageVerification, setStorageVerification] = useState<CryptoStorageVerify | null>(null)
  const [cacheResult, setCacheResult] = useState<CryptoCacheClean | null>(null)
  const [cleanupArmed, setCleanupArmed] = useState(false)
  const [busyAction, setBusyAction] = useState<string | null>(null)

  const load = useCallback(async (refresh = false) => {
    if (refresh) setRefreshing(true)
    else setLoading(true)
    try {
      const [nextCatalog, nextCapabilities, nextStorage, nextCoverage] = await Promise.all([
        api.cryptoCatalog(),
        api.cryptoCapabilities(),
        api.cryptoStorage(),
        api.cryptoCoverage(),
      ])
      setCatalog(nextCatalog)
      setCapabilities(nextCapabilities)
      setStorage(nextStorage)
      setCoverage(nextCoverage)
      setSelected((current) => {
        const admitted = new Set(
          nextCoverage.items
            .filter((item) => item.state === 'qualified')
            .map((item) => item.manifest_id),
        )
        return new Set([...current].filter((id) => admitted.has(id)))
      })
      setError(null)
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : String(reason))
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const familyRows = useMemo(
    () => (catalog?.families ?? []).filter((row) => {
      const provider = acquisitionProvider(row.provider)
      return provider !== null && cryptoSectionForFamily(row.family) === section
    }),
    [catalog, section],
  )

  useEffect(() => {
    if (familyRows.length === 0 || familyRows.some((row) => row.family === family)) return
    const next = familyRows[0].family
    setFamily(next)
    setInstrument(defaultInstrument(next))
  }, [family, familyRows])

  useEffect(() => {
    setEstimate(null)
    setSnapshot(null)
    setVerification(null)
    setRegistration(null)
  }, [family, instrument, base, quote, category, frequency, days])

  const provider = acquisitionProvider(
    catalog?.families.find((row) => row.family === family)?.provider ?? '',
  )
  const capability = capabilities?.items.find((item) => item.family === family) ?? null
  const qualifiedCount = coverage?.items.filter((item) => item.state === 'qualified').length ?? 0
  const action = cryptoCanonicalAction({
    loading,
    storageState: storage?.state,
    storageBlocker: storage?.blocker,
    qualifiedCount,
    selectedCount: selected.size,
  })
  const visibleCoverage = (coverage?.items ?? []).filter((item) => {
    if (section === 'quality' || section === 'storage') return true
    return cryptoSectionForFamily(item.family) === section
  })
  const latestManifestIds = latestCryptoManifestIds(visibleCoverage)
  const selectedBaseAssets = new Set(
    (coverage?.items ?? [])
      .filter((item) => selected.has(item.manifest_id) && item.base_asset)
      .map((item) => item.base_asset as string),
  )

  async function estimateAcquisition(): Promise<void> {
    setBusyAction('estimate')
    setError(null)
    try {
      setEstimate(await api.cryptoEstimate({ family, instruments: 1, days, frequency }))
    } catch (reason: unknown) {
      setEstimate(null)
      setError(reason instanceof Error ? reason.message : String(reason))
    } finally {
      setBusyAction(null)
    }
  }

  async function inspectAsset(): Promise<void> {
    setBusyAction('asset')
    setError(null)
    try {
      setAsset(await api.cryptoAsset(base, new Date().toISOString()))
    } catch (reason: unknown) {
      setAsset(null)
      setError(reason instanceof Error ? reason.message : String(reason))
    } finally {
      setBusyAction(null)
    }
  }

  async function acquire(): Promise<void> {
    if (!provider) return
    setBusyAction('acquire')
    setError(null)
    try {
      const request: CryptoAcquisitionRequest = {
        provider,
        family,
        instrument,
        base,
        quote,
        category,
        frequency,
        period: provider === 'binance' ? period : null,
        network: provider === 'geckoterminal' ? network : null,
        pool_address: provider === 'geckoterminal' && poolAddress ? poolAddress : null,
        metrics: provider === 'coinmetrics'
          ? metrics.split(',').map((item) => item.trim()).filter(Boolean)
          : [],
        start: provider === 'coinmetrics' ? start : null,
        end: provider === 'coinmetrics' ? end : null,
      }
      const accepted = await api.cryptoAcquire(request)
      setJobId(accepted.job_id)
      setJobFinished(false)
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : String(reason))
    } finally {
      setBusyAction(null)
    }
  }

  async function freezeSnapshot(): Promise<void> {
    setBusyAction('snapshot')
    setError(null)
    try {
      const created = await api.cryptoSnapshotCreate([...selected])
      setSnapshot(created)
      setVerification(null)
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : String(reason))
    } finally {
      setBusyAction(null)
    }
  }

  async function verifySnapshot(): Promise<void> {
    if (!snapshot) return
    setBusyAction('verify')
    setError(null)
    try {
      setVerification(await api.cryptoSnapshotVerify(snapshot.snapshot_id, {
        required_families: snapshot.families,
        purpose: 'research',
      }))
    } catch (reason: unknown) {
      setVerification(null)
      setError(reason instanceof Error ? reason.message : String(reason))
    } finally {
      setBusyAction(null)
    }
  }

  async function registerSnapshot(): Promise<void> {
    if (!snapshot || !verification?.eligible || selectedBaseAssets.size !== 1) return
    setBusyAction('register')
    setError(null)
    try {
      setRegistration(
        await api.cryptoSnapshotRegister(snapshot.snapshot_id, [...selectedBaseAssets][0]),
      )
      onRegistered?.()
    } catch (reason: unknown) {
      setRegistration(null)
      setError(reason instanceof Error ? reason.message : String(reason))
    } finally {
      setBusyAction(null)
    }
  }

  async function inspectQuality(item: CryptoCoverageItem): Promise<void> {
    setBusyAction(`quality:${item.manifest_id}`)
    setError(null)
    try {
      setQuality(await api.cryptoQuality(item.manifest_id))
      setSection('quality')
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : String(reason))
    } finally {
      setBusyAction(null)
    }
  }

  async function inspectStorage(): Promise<void> {
    setBusyAction('storage-inventory')
    setError(null)
    try {
      setStorageInventory(await api.cryptoStorageInventory())
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : String(reason))
    } finally {
      setBusyAction(null)
    }
  }

  async function verifyStorage(): Promise<void> {
    setBusyAction('storage-verify')
    setError(null)
    try {
      setStorageVerification(await api.cryptoStorageVerify())
    } catch (reason: unknown) {
      setStorageVerification(null)
      setError(reason instanceof Error ? reason.message : String(reason))
    } finally {
      setBusyAction(null)
    }
  }

  async function cleanCache(): Promise<void> {
    if (!cleanupArmed) {
      setCleanupArmed(true)
      return
    }
    setBusyAction('cache-clean')
    setError(null)
    try {
      setCacheResult(await api.cryptoCacheClean())
      setCleanupArmed(false)
      await load(true)
      await inspectStorage()
    } catch (reason: unknown) {
      setCacheResult(null)
      setError(reason instanceof Error ? reason.message : String(reason))
    } finally {
      setBusyAction(null)
    }
  }

  function toggleManifest(item: CryptoCoverageItem): void {
    if (item.state !== 'qualified') return
    setSelected((current) => {
      const next = new Set(current)
      if (next.has(item.manifest_id)) next.delete(item.manifest_id)
      else next.add(item.manifest_id)
      return next
    })
    setSnapshot(null)
    setVerification(null)
  }

  return (
    <section className="crypto-center" aria-label="Crypto Data Center">
      <div className="crypto-center-head">
        <div>
          <div className="title">Crypto Data Center</div>
          <p className="muted">Provider-native public data · exact units · no automatic fallback · no execution authority</p>
        </div>
        <button className="btn" type="button" disabled={refreshing} onClick={() => void load(true)}>
          {refreshing ? 'Refreshing…' : 'Refresh'}
        </button>
      </div>

      <div className={`crypto-next ${action.state}`} role="status">
        <span className="eyebrow">Canonical next action</span>
        <strong>{action.label}</strong>
      </div>
      {error ? <div className="workbench-notice" role="alert"><strong>ACTION BLOCKED</strong><span>{error}</span></div> : null}

      <nav className="crypto-tabs" role="tablist" aria-label="Crypto data families">
        {SECTIONS.map((item) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            aria-selected={section === item.id}
            className={`area-tab${section === item.id ? ' active' : ''}`}
            onClick={() => setSection(item.id)}
          >
            {item.label}
          </button>
        ))}
      </nav>

      {section === 'assets' ? (
        <div className="crypto-card-grid">
          <section className="provider-card">
            <div className="rd-head">Reviewed native identity</div>
            <div className="crypto-form-grid">
              <label><span className="eyebrow">Asset</span><input className="field mono" value={base} onChange={(event) => { setBase(event.target.value.toUpperCase()); setAsset(null) }} /></label>
              <button className="btn" type="button" disabled={busyAction === 'asset'} onClick={() => void inspectAsset()}>{busyAction === 'asset' ? 'Checking…' : 'Inspect lineage'}</button>
            </div>
            {asset ? (
              <div className="crypto-detail">
                <strong>{asset.coingecko_id}</strong>
                <span>{asset.network} · {asset.native_asset ? 'reviewed native asset' : 'contract asset'}</span>
                <span className="mono advanced-only">{asset.provider_symbols.map(([key, value]) => `${key}:${value}`).join(' · ')}</span>
              </div>
            ) : <p className="muted">Ticker-only contract joins are prohibited. Native BTC and ETH use reviewed mappings.</p>}
          </section>
        </div>
      ) : null}

      {familyRows.length > 0 ? (
        <section className="crypto-acquire provider-card" aria-label="Bounded acquisition">
          <div className="provider-card-head">
            <div className="rd-head">Bounded acquisition</div>
            <span className="chip kind">{provider ?? 'NO AUTHORITY'}</span>
          </div>
          {capability ? (
            <div className="crypto-detail" aria-label="Provider dataset capability">
              <span>
                <span className="chip kind">SUPPORTED</span>{' '}
                <span className={capability.verification_state === 'receipt_verified' ? 'chip pass' : 'chip'}>
                  {capability.verification_state === 'receipt_verified' ? 'RECEIPT VERIFIED' : 'NOT VERIFIED'}
                </span>{' '}
                <span className={stateClass(capability.qualification_state)}>
                  {capability.qualification_state.toUpperCase()}
                </span>
              </span>
              <span>
                Stored coverage: {capability.earliest ?? 'none'} → {capability.latest ?? 'none'}
              </span>
              <span className="advanced-only">Supported frequencies: {capability.frequencies.join(' · ')}</span>
              <span className="advanced-only">Limits: {capability.limits.join(' · ')}</span>
            </div>
          ) : null}
          <div className="crypto-form-grid">
            <label><span className="eyebrow">Dataset family</span><select className="field" value={family} onChange={(event) => { const next = event.target.value as CryptoFamily; setFamily(next); setInstrument(defaultInstrument(next)) }}>{familyRows.map((row) => <option key={row.family} value={row.family}>{row.family.replaceAll('_', ' ')}</option>)}</select></label>
            <label><span className="eyebrow">Instrument</span><input className="field mono" value={instrument} onChange={(event) => setInstrument(event.target.value)} /></label>
            <label><span className="eyebrow">Base asset</span><input className="field mono" value={base} onChange={(event) => setBase(event.target.value.toUpperCase())} /></label>
            <label><span className="eyebrow">Quote asset</span><input className="field mono" value={quote} onChange={(event) => setQuote(event.target.value.toUpperCase())} /></label>
            <label><span className="eyebrow">Market</span><select className="field" value={category} onChange={(event) => setCategory(event.target.value as CryptoAcquisitionRequest['category'])}><option value="spot">spot</option><option value="linear">linear</option><option value="inverse">inverse</option></select></label>
            <label><span className="eyebrow">Frequency</span><select className="field" value={frequency} onChange={(event) => setFrequency(event.target.value as CryptoAcquisitionRequest['frequency'])}><option value="1d">daily</option><option value="1h">hourly</option><option value="5m">5 minutes</option><option value="1m">1 minute</option></select></label>
            <label><span className="eyebrow">Estimate days</span><input className="field" type="number" min={1} max={3650} value={days} onChange={(event) => setDays(Number(event.target.value))} /></label>
            {provider === 'binance' ? <label><span className="eyebrow">Archive month</span><input className="field mono" type="month" value={period} onChange={(event) => setPeriod(event.target.value)} /></label> : null}
            {provider === 'geckoterminal' ? <><label><span className="eyebrow">Network</span><input className="field mono" value={network} onChange={(event) => setNetwork(event.target.value)} /></label><label><span className="eyebrow">Pool address</span><input className="field mono" value={poolAddress} onChange={(event) => setPoolAddress(event.target.value)} /></label></> : null}
            {provider === 'coinmetrics' ? <><label><span className="eyebrow">Metrics</span><input className="field mono" value={metrics} onChange={(event) => setMetrics(event.target.value)} /></label><label><span className="eyebrow">Start UTC</span><input className="field mono" value={start} onChange={(event) => setStart(event.target.value)} /></label><label><span className="eyebrow">End UTC</span><input className="field mono" value={end} onChange={(event) => setEnd(event.target.value)} /></label></> : null}
          </div>
          <div className="crypto-actions">
            <button className="btn" type="button" disabled={busyAction !== null} onClick={() => void estimateAcquisition()}>{busyAction === 'estimate' ? 'Estimating…' : 'Estimate storage'}</button>
            <button className="btn primary" type="button" disabled={storage?.state !== 'ready' || !provider || busyAction !== null} onClick={() => void acquire()}>{busyAction === 'acquire' ? 'Starting…' : 'Acquire & qualify'}</button>
            {estimate ? <span className="muted">{estimate.estimated_rows.toLocaleString()} rows · about {bytesLabel(estimate.estimated_bytes)}</span> : null}
          </div>
          <p className="mono muted advanced-only">alpha crypto-data acquire {provider} {family} {instrument} --base {base} --quote {quote} …</p>
        </section>
      ) : null}

      {jobId ? <section className="crypto-job"><div className="rd-head">Acquisition job</div><div className="workbench-notice" role="status"><strong>{jobFinished ? 'FINISHED' : 'RUNNING'}</strong><span>{jobFinished ? 'Coverage refreshed. Review the new mechanical qualification below.' : 'Fetching one bounded provider response and freezing its exact bytes.'}</span></div><div className="advanced-only"><JobConsole jobId={jobId} onDone={() => { setJobFinished(true); void load(true) }} /></div></section> : null}

      <section aria-label="Crypto coverage">
        <div className="rd-head">{section === 'quality' ? 'All coverage and quality' : 'Available coverage'} · {latestManifestIds.size} current <span className="advanced-only">· {visibleCoverage.length} immutable versions</span></div>
        {loading ? <p className="muted">Loading exact manifests and qualification reports…</p> : null}
        {!loading && visibleCoverage.length === 0 ? <p className="muted">No dataset in this family has been acquired yet. Estimate one bounded acquisition above.</p> : null}
        <div className="crypto-coverage-list">
          {visibleCoverage.map((item) => (
            <article className={`crypto-dataset ${selected.has(item.manifest_id) ? 'selected' : ''}${latestManifestIds.has(item.manifest_id) ? '' : ' advanced-only'}`} key={item.manifest_id}>
              <label className="crypto-dataset-select">
                <input
                  type="checkbox"
                  checked={selected.has(item.manifest_id)}
                  disabled={item.state !== 'qualified'}
                  onChange={() => toggleManifest(item)}
                  aria-label={`Select ${item.state} ${item.family} ${item.instrument} ${item.quote_asset ?? 'no quote asset'}`}
                />
                <span><strong>{item.instrument}</strong><span>{item.family.replaceAll('_', ' ')} · {item.provider}/{item.venue}</span></span>
              </label>
              <span className={stateClass(item.state)}>{item.state.toUpperCase()}</span>
              <span className="mono">{item.row_count.toLocaleString()} rows · {item.frequency}</span>
              <span className="muted">{item.quote_asset ?? 'no quote'} · {item.units}{item.fetched_at ? ` · fetched ${new Date(item.fetched_at).toLocaleString()}` : ' · legacy receipt time unavailable'}</span>
              <button className="btn" type="button" disabled={busyAction === `quality:${item.manifest_id}`} onClick={() => void inspectQuality(item)}>Quality</button>
              <span className="mono muted advanced-only">manifest {shortId(item.manifest_id)} · artifact {shortId(item.artifact_sha256)} · {item.method_version}</span>
            </article>
          ))}
        </div>
      </section>

      {quality ? (
        <section className="provider-card" aria-label="Selected quality report">
          <div className="rd-head">Mechanical quality · {quality.dataset.instrument} · {quality.dataset.family.replaceAll('_', ' ')}</div>
          <div className="crypto-detail"><span className={stateClass(quality.quality.state)}>{quality.quality.state.toUpperCase()}</span><span>{quality.quality.row_count.toLocaleString()} rows · {quality.quality.observed_start ?? 'no start'} → {quality.quality.observed_end ?? 'no end'}</span><span>{quality.next_action}</span>{quality.quality.failures.length ? <strong>Failures: {quality.quality.failures.join(', ')}</strong> : null}{quality.quality.warnings.length ? <span>Warnings: {quality.quality.warnings.join(', ')}</span> : null}<span className="mono muted advanced-only">{quality.quality.dataset_sha256} · {quality.quality.method_version}</span></div>
        </section>
      ) : null}

      <section className="crypto-snapshot provider-card" aria-label="Frozen crypto snapshot">
        <div className="provider-card-head"><div className="rd-head">Research snapshot</div><span className="chip kind">{selected.size} selected</span></div>
        <p className="muted">Only mechanically qualified datasets can be selected. Provider, venue, quote, units, timestamps, and hashes remain separate.</p>
        <div className="crypto-actions">
          <button className="btn primary" type="button" disabled={selected.size === 0 || busyAction !== null} onClick={() => void freezeSnapshot()}>{busyAction === 'snapshot' ? 'Freezing…' : 'Freeze selected snapshot'}</button>
          {snapshot ? <button className="btn" type="button" disabled={busyAction !== null} onClick={() => void verifySnapshot()}>{busyAction === 'verify' ? 'Verifying…' : 'Verify for research'}</button> : null}
        </div>
        {snapshot ? <div className="crypto-detail"><strong>Frozen · {snapshot.member_count} members</strong><span>{snapshot.families.map((item) => item.replaceAll('_', ' ')).join(' · ')}</span><span className="mono muted advanced-only">snapshot {snapshot.snapshot_id}</span></div> : null}
        {verification ? <div className={`workbench-notice ${verification.eligible ? '' : 'fail'}`} role="status"><strong>{verification.eligible ? 'ELIGIBLE' : 'BLOCKED'}</strong><span>{verification.eligible ? 'Register this immutable snapshot for compatible research proposals.' : `${verification.next_action}${verification.blockers.length ? ` ${verification.blockers.join('; ')}` : ''}`}</span></div> : null}
        {verification?.eligible ? <div className="crypto-actions"><button className="btn primary" type="button" disabled={busyAction !== null || selectedBaseAssets.size !== 1 || registration !== null} onClick={() => void registerSnapshot()}>{busyAction === 'register' ? 'Registering…' : registration ? 'Registered for research' : 'Register research-only dataset'}</button>{selectedBaseAssets.size !== 1 ? <span className="muted">Select datasets for exactly one base asset before registration.</span> : null}</div> : null}
        {registration ? <div className="workbench-notice" role="status"><strong>REGISTERED · RESEARCH ONLY</strong><span>Available to compatible proposal operators; registration does not make an incompatible case executable.</span><span className="mono muted advanced-only">{registration.ref_id}</span></div> : null}
      </section>

      {section === 'storage' && storage ? (
        <section className="provider-card">
          <div className="rd-head">Expansion storage</div>
          <div className="crypto-storage-stats"><span className={storage.state === 'ready' ? 'chip pass' : 'chip fail'}>{storage.state.toUpperCase()}</span><span>{bytesLabel(storage.free_bytes)} free of {bytesLabel(storage.total_bytes)}</span><span>{storage.manifest_count} immutable manifests</span><span>{bytesLabel(storage.cache_bytes)} removable cache</span><span>Reserve {storage.reserve_fraction == null ? '—' : `${Math.round(storage.reserve_fraction * 100)}%`} · minimum {bytesLabel(storage.minimum_free_bytes)}</span></div>
          <p className="muted">The browser receives only the volume label and capacity—not the private absolute path. Missing or substituted media fails closed.</p>
          <div className="crypto-actions"><button className="btn" type="button" disabled={busyAction !== null} onClick={() => void inspectStorage()}>{busyAction === 'storage-inventory' ? 'Inspecting…' : 'Inspect storage inventory'}</button><button className="btn" type="button" disabled={busyAction !== null} onClick={() => void verifyStorage()}>{busyAction === 'storage-verify' ? 'Verifying every artifact…' : 'Verify all immutable data'}</button><button className={cleanupArmed ? 'btn danger' : 'btn'} type="button" disabled={busyAction !== null || storage.cache_bytes === 0} onClick={() => void cleanCache()}>{busyAction === 'cache-clean' ? 'Cleaning cache…' : cleanupArmed ? 'Confirm clean removable cache' : 'Review cache cleanup'}</button></div>
          {cleanupArmed ? <div className="workbench-notice fail" role="alert"><strong>CONFIRM CACHE CLEANUP</strong><span>Only {bytesLabel(storage.cache_bytes)} under the disposable cache tree will be deleted. Raw, normalized, staged, snapshot, and control artifacts are excluded.</span></div> : null}
          {storageInventory ? <div className="crypto-detail"><strong>INVENTORY</strong><span>{storageInventory.manifest_count} manifests · {storageInventory.snapshot_count} snapshots · {storageInventory.staging_count} staged downloads</span><span>{bytesLabel(storageInventory.cache_bytes)} removable cache</span><span className="mono muted advanced-only">{JSON.stringify(storageInventory.counts_by_kind)}</span></div> : null}
          {storageVerification ? <div className="workbench-notice" role="status"><strong>VERIFIED</strong><span>{storageVerification.manifest_count} manifests and {storageVerification.snapshot_count} snapshots re-hashed · {storageVerification.research_eligible_snapshot_count} research eligible</span></div> : null}
          {cacheResult ? <div className="workbench-notice" role="status"><strong>CACHE CLEANED</strong><span>{bytesLabel(cacheResult.removed_bytes)} removed · immutable artifacts removed: 0</span></div> : null}
        </section>
      ) : null}
    </section>
  )
}
