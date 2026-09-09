// Insert › Indicators… (spec 2026-09-01 §4.2 Phase 5 S3): pick the indicator series and pattern
// layers the price chart asks `alpha chart overlays` for. The selection is per profile and
// persisted in settings; the chart re-requests on every change. Nothing here computes a value —
// a custom spec is only checked against the CLI's grammar so a typo is caught before the request.

import { useEffect, useRef, useState } from 'react'

import {
  INDICATOR_PRESETS,
  PATTERNS,
  PATTERN_LABEL,
  parseIndicatorSpec,
  toggleIndicator,
  togglePattern,
} from '../panels/chartOverlaysModel'
import { setSettings, useSettings } from '../state/settings'

export function IndicatorsDialog({ onClose }: { onClose: () => void }) {
  const { profile, overlays } = useSettings()
  const config = overlays[profile]
  const [custom, setCustom] = useState('')
  const [customError, setCustomError] = useState<string | null>(null)
  const box = useRef<HTMLDivElement>(null)

  useEffect(() => {
    box.current?.querySelector<HTMLInputElement>('input')?.focus()
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const update = (next: typeof config) => setSettings({ overlays: { ...overlays, [profile]: next } })
  const extras = config.indicators.filter((spec) => !INDICATOR_PRESETS.some((preset) => preset.id === spec))

  const addCustom = () => {
    try {
      const spec = parseIndicatorSpec(custom)
      if (!config.indicators.includes(spec)) update(toggleIndicator(config, spec))
      setCustom('')
      setCustomError(null)
    } catch (cause) {
      setCustomError(cause instanceof Error ? cause.message : String(cause))
    }
  }

  return (
    <div className="figure-overlay" role="presentation" onClick={onClose}>
      <div
        ref={box}
        className="figure-overlay-box indicators-box"
        role="dialog"
        aria-modal="true"
        aria-label="Indicators"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="figure-overlay-head doc-head">
          <span className="doc-head-title">Indicators — {profile} chart overlays</span>
          <span className="spacer" />
          <button type="button" className="btn" onClick={onClose}>
            Done
          </button>
        </div>
        <div className="indicators-body">
          <fieldset className="indicators-group">
            <legend>Indicators</legend>
            {INDICATOR_PRESETS.map((preset) => (
              <label key={preset.id} className="settings-row indicators-row">
                <input
                  type="checkbox"
                  checked={config.indicators.includes(preset.id)}
                  onChange={() => update(toggleIndicator(config, preset.id))}
                />
                <span>{preset.label}</span>
                <span className="mono muted">{preset.id}</span>
              </label>
            ))}
            {extras.map((spec) => (
              <label key={spec} className="settings-row indicators-row">
                <input type="checkbox" checked onChange={() => update(toggleIndicator(config, spec))} />
                <span className="mono">{spec}</span>
              </label>
            ))}
            <form
              className="indicators-custom"
              aria-label="Add a custom indicator"
              onSubmit={(event) => {
                event.preventDefault()
                addCustom()
              }}
            >
              <input
                className="field mono"
                value={custom}
                placeholder="custom, e.g. ema:100 or bbands:30:2.5"
                aria-label="Custom indicator spec"
                aria-invalid={customError !== null}
                spellCheck={false}
                onChange={(event) => {
                  setCustom(event.target.value)
                  setCustomError(null)
                }}
              />
              <button type="submit" className="btn" disabled={!custom.trim()}>
                Add
              </button>
            </form>
            {customError ? (
              <p className="indicators-error" role="alert">
                {customError}
              </p>
            ) : null}
          </fieldset>
          <fieldset className="indicators-group">
            <legend>Patterns</legend>
            {PATTERNS.map((pattern) => (
              <label key={pattern} className="settings-row indicators-row">
                <input
                  type="checkbox"
                  checked={config.patterns.includes(pattern)}
                  onChange={() => update(togglePattern(config, pattern))}
                />
                <span>{PATTERN_LABEL[pattern]}</span>
              </label>
            ))}
          </fieldset>
          <p className="muted indicators-note">
            Every value is computed in Python by <span className="mono">alpha chart overlays</span> over the same
            point-in-time window as the candles: warm-up bars are blank, and a swing, trendline or level is drawn
            only once it was knowable on the last bar.
          </p>
        </div>
      </div>
    </div>
  )
}
