/** Selection and parameters only: Python owns every indicator value. */
import { useEffect, useState } from 'react'
import { INDICATOR_PRESETS, PATTERNS, PATTERN_LABEL, parseIndicatorSpec, toggleIndicator, togglePattern } from '../panels/chartOverlaysModel'
import { getSettings, setSettings, useSettings } from '../state/settings'
import { readFavorites, replaceIndicator } from './indicatorPickerModel'
import './researchTools.css'

const FAVORITES_KEY = 'alpha.indicator-favorites.v1'
export function IndicatorPicker({ inline = false }: { inline?: boolean }) {
  const { profile, overlays } = useSettings()
  const config = overlays[profile]
  const [query, setQuery] = useState('')
  const [favoritesOnly, setFavoritesOnly] = useState(false)
  const [favorites, setFavorites] = useState<string[]>(() => {
    try { return readFavorites(JSON.parse(localStorage.getItem(FAVORITES_KEY) ?? '[]')) }
    catch { return [] }
  })
  const [custom, setCustom] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [editing, setEditing] = useState<string | null>(null)
  const [parameters, setParameters] = useState<string[]>([])
  useEffect(() => { setEditing(null); setError(null) }, [profile])
  useEffect(() => {
    try { localStorage.setItem(FAVORITES_KEY, JSON.stringify(favorites)) }
    catch { /* The selection still works without browser persistence. */ }
  }, [favorites])
  const update = (next: typeof config) => setSettings({ overlays: { ...getSettings().overlays, [profile]: next } })
  const options = [...INDICATOR_PRESETS, ...[...new Set([...config.indicators, ...favorites])].filter(spec => !INDICATOR_PRESETS.some(item => item.id === spec)).map(id => ({ id, label: id }))]
  const visible = options.filter(item => `${item.label} ${item.id}`.toLowerCase().includes(query.toLowerCase()) && (!favoritesOnly || favorites.includes(item.id)))
  const apply = () => {
    try {
      if (editing) update(replaceIndicator(config, editing, [editing.split(':')[0], ...parameters].join(':')))
      else { const spec = parseIndicatorSpec(custom); if (!config.indicators.includes(spec)) update(toggleIndicator(config, spec)); setCustom('') }
      setEditing(null); setError(null)
    } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)) }
  }
  return <div className={`indicators-body indicator-picker${inline ? ' indicator-picker-inline' : ''}`}>
    <input className="field" aria-label="Search indicators" placeholder="Search indicators…" value={query} onChange={event => setQuery(event.target.value)} />
    <button className="btn" aria-pressed={favoritesOnly} onClick={() => setFavoritesOnly(value => !value)}>Favourites</button>
    <fieldset className="indicators-group"><legend>Indicators</legend>
      {visible.map(item => <div className="indicator-choice" key={item.id}>
        <label className="settings-row indicators-row"><input type="checkbox" checked={config.indicators.includes(item.id)} onChange={() => { update(toggleIndicator(config, item.id)); if (editing === item.id) setEditing(null) }} /><span>{item.label}</span>{item.label !== item.id ? <span className="mono muted">{item.id}</span> : null}</label>
        <button className="btn" aria-label={`Favourite ${item.id}`} aria-pressed={favorites.includes(item.id)} onClick={() => setFavorites(values => values.includes(item.id) ? values.filter(value => value !== item.id) : [...values, item.id])}>{favorites.includes(item.id) ? '★' : '☆'}</button>
        {config.indicators.includes(item.id) ? <button className="btn" aria-label={`Edit ${item.id} parameters`} onClick={() => { setEditing(item.id); setParameters(item.id.split(':').slice(1)); setError(null) }}>Edit</button> : null}
      </div>)}
      {!visible.length ? <p>No matching indicators.</p> : null}
      {editing ? <form className="indicator-parameters" aria-label={`Parameters for ${editing}`} onSubmit={event => { event.preventDefault(); apply() }}>
        <strong>{editing.split(':')[0].toUpperCase()}</strong>
        {parameters.map((value, index) => {
          const name = editing.startsWith('macd:') ? ['Fast window', 'Slow window', 'Signal window'][index] : index === 0 ? 'Window' : 'Width'
          return <label key={index}>{name}<input className="field" type="number" step={name === 'Width' ? 'any' : '1'} value={value} onChange={event => setParameters(values => values.map((entry, position) => position === index ? event.target.value : entry))} /></label>
        })}
        <button className="btn" type="submit">Apply parameters</button><button className="btn" type="button" onClick={() => { setEditing(null); setError(null) }}>Cancel edit</button>
      </form> : null}
      <form className="indicators-custom" aria-label="Add a custom indicator" onSubmit={event => { event.preventDefault(); if (!editing) apply() }}>
        <input className="field mono" value={custom} placeholder="custom, e.g. ema:100 or bbands:30:2.5" aria-label="Custom indicator spec" aria-invalid={error !== null} spellCheck={false} onChange={event => { setCustom(event.target.value); setError(null) }} />
        <button type="submit" className="btn" disabled={!custom.trim() || editing !== null}>Add</button>
      </form>
      {error ? <p className="indicators-error" role="alert">{error}</p> : null}
    </fieldset>
    <fieldset className="indicators-group"><legend>Patterns</legend>{PATTERNS.map(pattern => <label key={pattern} className="settings-row indicators-row"><input type="checkbox" checked={config.patterns.includes(pattern)} onChange={() => update(togglePattern(config, pattern))} /><span>{PATTERN_LABEL[pattern]}</span></label>)}</fieldset>
    <p className="muted indicators-note">Values come from Python via <span className="mono">alpha chart overlays</span>. Warm-up bars remain blank; confirmed patterns appear only when knowable. Overlays do not establish a trading edge.</p>
  </div>
}
