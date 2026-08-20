import type {
  CryptoAcquisitionRequest,
  CryptoCapabilityItem,
  CryptoEstimate,
  CryptoFamily,
} from '../api/types'
import { fmtBytes } from '../util/format'
import { cryptoCoverageStateClass } from './researchDataModel'

export type CryptoFamilyRow = { family: CryptoFamily }

export function CryptoAcquisitionView({
  familyRows,
  provider,
  capability,
  family,
  instrument,
  base,
  quote,
  category,
  categoryChoices,
  frequency,
  frequencyChoices,
  days,
  period,
  network,
  poolAddress,
  metrics,
  start,
  end,
  caseBoundEvent,
  eventReason,
  eventCaptureReady,
  storageReady,
  estimate,
  busyAction,
  rangedBybitFamily,
  onFamilyChange,
  onInstrumentChange,
  onBaseChange,
  onQuoteChange,
  onCategoryChange,
  onFrequencyChange,
  onDaysChange,
  onPeriodChange,
  onNetworkChange,
  onPoolAddressChange,
  onMetricsChange,
  onStartChange,
  onEndChange,
  onEventReasonChange,
  onEstimate,
  onAcquire,
}: {
  familyRows: CryptoFamilyRow[]
  provider: CryptoAcquisitionRequest['provider'] | null
  capability: CryptoCapabilityItem | null
  family: CryptoFamily
  instrument: string
  base: string
  quote: string
  category: CryptoAcquisitionRequest['category']
  categoryChoices: CryptoAcquisitionRequest['category'][]
  frequency: CryptoAcquisitionRequest['frequency']
  frequencyChoices: CryptoAcquisitionRequest['frequency'][]
  days: number
  period: string
  network: string
  poolAddress: string
  metrics: string
  start: string
  end: string
  caseBoundEvent: boolean
  eventReason: string
  eventCaptureReady: boolean
  storageReady: boolean
  estimate: CryptoEstimate | null
  busyAction: string | null
  rangedBybitFamily: boolean
  onFamilyChange: (value: CryptoFamily) => void
  onInstrumentChange: (value: string) => void
  onBaseChange: (value: string) => void
  onQuoteChange: (value: string) => void
  onCategoryChange: (value: CryptoAcquisitionRequest['category']) => void
  onFrequencyChange: (value: CryptoAcquisitionRequest['frequency']) => void
  onDaysChange: (value: number) => void
  onPeriodChange: (value: string) => void
  onNetworkChange: (value: string) => void
  onPoolAddressChange: (value: string) => void
  onMetricsChange: (value: string) => void
  onStartChange: (value: string) => void
  onEndChange: (value: string) => void
  onEventReasonChange: (value: string) => void
  onEstimate: () => void
  onAcquire: () => void
}) {
  if (familyRows.length === 0) return null
  const showRange =
    (provider === 'coinmetrics' && family === 'onchain_metrics')
    || provider === 'ccxt:coinbase'
    || (provider === 'bybit' && rangedBybitFamily)

  return (
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
            <span className={cryptoCoverageStateClass(capability.qualification_state)}>
              {capability.qualification_state.toUpperCase()}
            </span>
          </span>
          <span>Stored coverage: {capability.earliest ?? 'none'} → {capability.latest ?? 'none'}</span>
          <span className="advanced-only">Supported frequencies: {capability.frequencies.join(' · ')}</span>
          <span className="advanced-only">Limits: {capability.limits.join(' · ')}</span>
        </div>
      ) : null}
      <div className="crypto-form-grid">
        <label><span className="eyebrow">Dataset family</span><select className="field" value={family} onChange={(event) => onFamilyChange(event.target.value as CryptoFamily)}>{familyRows.map((row) => <option key={row.family} value={row.family}>{row.family.replaceAll('_', ' ')}</option>)}</select></label>
        <label><span className="eyebrow">Instrument</span><input className="field mono" value={instrument} onChange={(event) => onInstrumentChange(event.target.value)} /></label>
        <label><span className="eyebrow">Base asset</span><input className="field mono" value={base} onChange={(event) => onBaseChange(event.target.value.toUpperCase())} /></label>
        <label><span className="eyebrow">Quote asset</span><input className="field mono" value={quote} onChange={(event) => onQuoteChange(event.target.value.toUpperCase())} /></label>
        <label><span className="eyebrow">Market</span><select className="field" value={category} onChange={(event) => onCategoryChange(event.target.value as CryptoAcquisitionRequest['category'])}>{categoryChoices.map((item) => <option key={item} value={item}>{item}</option>)}</select></label>
        <label><span className="eyebrow">Frequency</span><select className="field" value={frequency} onChange={(event) => onFrequencyChange(event.target.value as CryptoAcquisitionRequest['frequency'])}>{frequencyChoices.map((item) => <option key={item} value={item}>{item === '1d' ? 'daily' : item === '1h' ? 'hourly' : item}</option>)}</select></label>
        <label><span className="eyebrow">Estimate days</span><input className="field" type="number" min={1} max={3650} value={days} onChange={(event) => onDaysChange(Number(event.target.value))} /></label>
        {provider === 'binance' ? <label><span className="eyebrow">Archive month</span><input className="field mono" type="month" value={period} onChange={(event) => onPeriodChange(event.target.value)} /></label> : null}
        {provider === 'geckoterminal' ? <><label><span className="eyebrow">Network</span><input className="field mono" value={network} onChange={(event) => onNetworkChange(event.target.value)} /></label><label><span className="eyebrow">Pool address</span><input className="field mono" value={poolAddress} onChange={(event) => onPoolAddressChange(event.target.value)} /></label></> : null}
        {provider === 'coinmetrics' && family === 'onchain_metrics' ? <label><span className="eyebrow">Metrics</span><input className="field mono" value={metrics} onChange={(event) => onMetricsChange(event.target.value)} /></label> : null}
        {showRange ? <><label><span className="eyebrow">Start UTC</span><input className="field mono" value={start} onChange={(event) => onStartChange(event.target.value)} /></label><label><span className="eyebrow">End UTC</span><input className="field mono" value={end} onChange={(event) => onEndChange(event.target.value)} /></label></> : null}
        {caseBoundEvent ? <label><span className="eyebrow">Event-capture reason</span><input className="field" value={eventReason} onChange={(event) => onEventReasonChange(event.target.value)} /></label> : null}
      </div>
      <div className="crypto-actions">
        <button className="btn" type="button" disabled={busyAction !== null} onClick={onEstimate}>{busyAction === 'estimate' ? 'Estimating…' : 'Estimate storage'}</button>
        <button className="btn primary" type="button" disabled={!storageReady || !provider || busyAction !== null || !eventCaptureReady} onClick={onAcquire}>{busyAction === 'acquire' ? 'Starting…' : 'Acquire & qualify'}</button>
        {estimate ? <span className="muted">{estimate.estimated_rows.toLocaleString()} rows · about {fmtBytes(estimate.estimated_bytes)}</span> : null}
      </div>
      {caseBoundEvent && !eventCaptureReady ? <div className="workbench-notice" role="note"><strong>SELECT A RESEARCH CASE</strong><span>Derivative trades and books must be bound to the current case revision before any provider request.</span></div> : null}
      <p className="mono muted advanced-only">alpha crypto-data acquire {provider} {family} {instrument} --base {base} --quote {quote} …</p>
    </section>
  )
}
