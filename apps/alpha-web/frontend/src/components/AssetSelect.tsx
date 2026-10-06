import { useEffect, useId, useRef, useState } from 'react'
import { assetGroups, type AssetChoice, type AssetGroup } from './assetChoices'
import type { ArchiveChartDataset } from '../api/client'
import { api } from '../api/client'
import { useAreaVersion } from '../state/activity'
import { useSettings } from '../state/settings'
import { symbolFitsProfile } from '../shell/profiles'
import { setStoredVenue } from '../context/storedQuotes'

/** Stored inventory, with opt-in exact archive navigation. Manual entries are unverified. */
export function AssetSelect({ value, onChange, id, label = 'Asset', allowManual = false, includeBinanceSpot = false, onListedSelect, onArchiveSelect }: {
  value: string; onChange: (value: string) => void; id?: string; label?: string; allowManual?: boolean; includeBinanceSpot?: boolean; onListedSelect?: (pair: string) => void; onArchiveSelect?: (dataset: ArchiveChartDataset) => void
}) {
  const generated = useId()
  const listId = `${generated}-assets`
  const wrap = useRef<HTMLDivElement>(null)
  const input = useRef<HTMLInputElement>(null)
  const restoringFocus = useRef(false)
  const { profile } = useSettings()
  const revision = useAreaVersion('bars')
  const [symbols, setSymbols] = useState<string[]>([])
  const [archives, setArchives] = useState<ArchiveChartDataset[]>([])
  const [archiveError, setArchiveError] = useState<string | null>(null)
  const [archiveLoading, setArchiveLoading] = useState(false)
  const [expanded, setExpanded] = useState<string | null>(null)
  const includeArchive = Boolean(onArchiveSelect) && profile === 'crypto'
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [active, setActive] = useState(0)
  const [retry, setRetry] = useState(0)
  const [detail, setDetail] = useState<{ symbol: string; text: string } | null>(null)
  const [listedMarkets, setListedMarkets] = useState<{ pair: string; provider_symbol: string; quote_asset: string }[]>([])
  const [listedAsOf, setListedAsOf] = useState<string | null>(null)
  const [listedStale, setListedStale] = useState(false)
  const [listedLoading, setListedLoading] = useState(false)
  const [listedError, setListedError] = useState<string | null>(null)
  useEffect(() => {
    if (!open) return
    const outside = (event: MouseEvent) => {
      if (!wrap.current?.contains(event.target as Node)) setOpen(false)
    }
    // Close after the destination's click, so collapsing suggestions cannot move a button
    // between pointer-down and pointer-up and silently swallow the user's action.
    document.addEventListener('click', outside)
    return () => document.removeEventListener('click', outside)
  }, [open])
  useEffect(() => {
    let live = true
    setLoading(true); setError(null)
    api.symbols().then(result => { if (live) setSymbols(result.symbols) })
      .catch(cause => { if (live) setError(String(cause)) })
      .finally(() => { if (live) setLoading(false) })
    return () => { live = false }
  }, [revision, retry])
  useEffect(() => {
    if (!includeArchive || !open) return
    let live = true
    setArchiveLoading(true); setArchiveError(null)
    api.chartDatasets().then(result => { if (live) setArchives(result.datasets) })
      .catch(cause => { if (live) { setArchives([]); setArchiveError(String(cause)) } })
      .finally(() => { if (live) setArchiveLoading(false) })
    return () => { live = false }
  }, [includeArchive, open, revision, retry])
  const groups = assetGroups(symbols.filter(symbol => symbolFitsProfile(profile, symbol)), includeArchive ? archives : [])
  const options = groups.filter(group => `${group.label} ${group.choices.map(choice => choice.description).join(' ')}`.toLowerCase().includes(query.toLowerCase()))
  useEffect(() => {
    if (!includeBinanceSpot || !open || query.trim().length < 2) { setListedMarkets([]); return }
    let live = true
    const timer = window.setTimeout(() => {
      setListedLoading(true)
      setListedError(null)
      api.cryptoMarketCatalog(query.trim(), 25).then(result => {
        if (!live) return
        setListedMarkets(result.markets.map(item => ({ pair: item.pair, provider_symbol: item.provider_symbol, quote_asset: item.quote_asset })))
        setListedAsOf(result.as_of)
        setListedStale(result.stale)
      }).catch(cause => { if (live) { setListedMarkets([]); setListedError(String(cause)) } }).finally(() => { if (live) setListedLoading(false) })
    }, 250)
    return () => { live = false; window.clearTimeout(timer) }
  }, [includeBinanceSpot, open, query, retry])
  const candidate = open ? options[active]?.choices[0] : undefined
  const focused = candidate?.kind === 'stored' ? candidate.symbol : undefined
  useEffect(() => {
    let live = true
    setDetail(null)
    if (!focused) return
    const timer = window.setTimeout(() => {
      api.candles(focused, '?tail=1').then(result => {
        if (!live) return
        const provenance = result.provenance
        setStoredVenue(focused, provenance.venue)
        setDetail({ symbol: focused, text: `${provenance.source} · ${provenance.venue ?? 'venue not recorded'} · ${provenance.quality_status}` })
      }).catch(() => { if (live) setDetail({ symbol: focused, text: 'Stored asset · provenance unavailable' }) })
    }, 250)
    return () => { live = false; window.clearTimeout(timer) }
  }, [focused, revision])
  const choose = (symbol: string) => { onChange(symbol); setOpen(false); setQuery(''); setActive(0); setExpanded(null) }
  const chooseSource = (choice: AssetChoice) => {
    if (choice.kind === 'stored') choose(choice.symbol)
    else { onArchiveSelect?.(choice.dataset); setOpen(false); setQuery(''); setExpanded(null) }
  }
  const chooseGroup = (group: AssetGroup) => {
    if (group.choices.length === 1) chooseSource(group.choices[0])
    else setExpanded(value => value === group.label ? null : group.label)
  }
  useEffect(() => {
    if (expanded) wrap.current?.querySelector<HTMLButtonElement>('[data-source-choice]')?.focus()
  }, [expanded])
  return <div className="asset-select" ref={wrap} onKeyDown={event => {
    if (event.key !== 'Escape') return
    event.preventDefault(); event.stopPropagation(); setOpen(false); setExpanded(null)
    restoringFocus.current = true; input.current?.focus(); restoringFocus.current = false
  }}>
    <div className="asset-select-control"><input ref={input} id={id} className="field" role="combobox" aria-label={label} aria-autocomplete="list" aria-expanded={open} aria-controls={listId} aria-activedescendant={open && options[active] ? `${listId}-${active}` : undefined}
      value={open ? query : value} placeholder={value || 'Search stored assets…'} autoComplete="off"
      onFocus={() => { if (restoringFocus.current) return; setOpen(true); setQuery(''); setActive(0); setExpanded(null) }}
      onClick={() => { if (!open) { setOpen(true); setQuery(''); setActive(0); setExpanded(null) } }}
      onChange={event => { setQuery(event.target.value); setExpanded(null); if (allowManual) onChange(event.target.value.toUpperCase()); setActive(0); setOpen(true) }}
      onKeyDown={event => {
        if (event.key === 'Tab') { setOpen(false); return }
        if (event.key === 'ArrowDown' || event.key === 'ArrowUp') { event.preventDefault(); setOpen(true); setActive(index => Math.max(0, Math.min(options.length - 1, index + (event.key === 'ArrowDown' ? 1 : -1)))) }
        if (event.key === 'Enter' && open) { event.preventDefault(); if (options[active]) chooseGroup(options[active]); else if (allowManual && query.trim()) choose(query.trim().toUpperCase()) }
      }} />
      <button type="button" className="btn" aria-label={`Show ${label.toLowerCase()} choices`} onMouseDown={event => event.preventDefault()} onClick={() => { setOpen(!open); setQuery(''); setActive(0); setExpanded(null) }}>▾</button></div>
    {open ? <div className="asset-select-popup">
      <div className="asset-select-caption">{includeArchive ? 'Available assets' : 'Stored assets'} · {profile} · {groups.length} pairs</div>
      {loading ? <p role="status">Loading assets…</p> : null}
      {archiveLoading ? <p role="status">Loading external-drive markets…</p> : null}
      {archiveError ? <p role="alert">Archive discovery failed: {archiveError} <button type="button" className="btn" onClick={() => setRetry(value => value + 1)}>Retry archive</button></p> : null}
      {error ? <div role="alert">{error}<button type="button" className="btn" onClick={() => setRetry(value => value + 1)}>Retry assets</button></div> : null}
      <div id={listId} role="listbox" aria-label="Stored assets">{options.map((group, index) => <div key={group.label}>
        <button type="button" role="option" aria-selected={index === active} id={`${listId}-${index}`} onMouseEnter={() => setActive(index)} onMouseDown={event => event.preventDefault()} onClick={() => chooseGroup(group)}><strong>{group.label}</strong><span>{group.choices.length > 1 ? `${group.choices.length} available sources / intervals · choose one` : group.choices[0].kind === 'archive' ? group.choices[0].description : detail?.symbol === group.choices[0].symbol ? detail.text : 'Stored daily bars'}</span></button>
      </div>)}</div>
      {options.filter(group => group.label === expanded).map(group => <div key={group.label} className="asset-source-choices" role="group" aria-label={`Sources for ${group.label}`}>{group.choices.map(choice => <button type="button" className="btn" data-source-choice key={choice.id} aria-label={`Open ${group.label} · ${choice.description}`} onClick={() => chooseSource(choice)}>{choice.description}</button>)}</div>)}
      {!loading && !error && options.length === 0 ? <p>No matching stored assets. Download data to make an asset available.</p> : null}
      {includeBinanceSpot && query.trim().length >= 2 ? <div className="asset-select-market-catalog">
        <div className="asset-select-caption">Binance spot listings · {listedStale ? 'stale catalog · ' : 'verified catalog · '}{listedAsOf?.slice(0, 10) ?? 'date unavailable'}</div>
        {listedLoading ? <p role="status">Searching listed pairs…</p> : null}
        {listedError ? <p role="alert">Spot catalog unavailable: {listedError} <button type="button" className="btn" onMouseDown={event => event.preventDefault()} onClick={() => setRetry(value => value + 1)}>Retry</button></p> : null}
        {listedMarkets.map(item => <button type="button" className="btn" key={item.provider_symbol} onMouseDown={event => event.preventDefault()} onClick={() => { choose(item.pair); onListedSelect?.(item.pair) }}><strong>{item.pair}</strong> · Listed spot pair · history not checked</button>)}
        {!listedLoading && !listedError && listedMarkets.length === 0 ? <p>No Binance spot listing match in the latest catalog.</p> : null}
      </div> : null}
      {allowManual && query.trim() && !symbols.includes(query.trim().toUpperCase()) ? <button type="button" className="btn" onMouseDown={event => event.preventDefault()} onClick={() => choose(query.trim().toUpperCase())}>Use {query.trim().toUpperCase()} · availability not verified</button> : null}
    </div> : null}
  </div>
}
