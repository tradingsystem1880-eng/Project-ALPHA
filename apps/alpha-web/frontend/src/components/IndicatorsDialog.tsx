import { useEffect, useRef } from 'react'
import { useSettings } from '../state/settings'
import { IndicatorPicker } from './IndicatorPicker'

export function IndicatorsDialog({ onClose }: { onClose: () => void }) {
  const { profile } = useSettings()
  const box = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null
    box.current?.querySelector<HTMLInputElement>('input')?.focus()
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { event.preventDefault(); onClose() }
      if (event.key === 'Tab') {
        const controls = Array.from(box.current?.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled), [tabindex="0"]') ?? [])
        const first = controls[0], last = controls.at(-1)
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus() }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus() }
      }
    }
    window.addEventListener('keydown', onKey)
    return () => { window.removeEventListener('keydown', onKey); previous?.focus() }
  }, [onClose])
  return <div className="figure-overlay" role="presentation" onClick={onClose}>
    <div ref={box} className="figure-overlay-box indicators-box" role="dialog" aria-modal="true" aria-label="Indicators" onClick={event => event.stopPropagation()}>
      <div className="figure-overlay-head doc-head"><span className="doc-head-title">Indicators — {profile} chart overlays</span><span className="spacer" /><button type="button" className="btn" onClick={onClose}>Done</button></div>
      <IndicatorPicker />
    </div>
  </div>
}
