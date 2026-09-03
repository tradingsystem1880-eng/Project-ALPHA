/**
 * A figure maximised (artboard 3-Chart-maximised): a header line `<figure> — <run> (maximised)`,
 * a toolbar with Save PNG, Save SVG, Copy, Close and zoom, and `Esc restores · run … · UTC` on
 * the right. A fixed overlay with role=dialog and a focus trap on its controls, following the
 * App.tsx palette precedent — the SPA has no dialog dependency. The image bytes are the
 * existing server-rendered ones (zoom scales the SVG in the browser, it draws nothing); Copy
 * fetches the PNG endpoint and hands the blob to the Clipboard API, and says why when that API
 * is not available.
 */

import { useEffect, useRef, useState } from 'react'

import { api } from '../api/client'
import type { FigureMetadata } from '../api/types'
import { Icon } from '../shell/icons'
import { useSettings } from '../state/settings'
import { copyCapability, exportNames, notesVisible } from './figureExport'

interface Props {
  runId: string
  /** The run's display name; the header falls back to the short id. */
  runName?: string
  meta: FigureMetadata
  onClose: () => void
}

const ZOOMS = [1, 1.25, 1.5, 2, 3] as const

function clipboardEnvironment() {
  const nav = typeof navigator === 'undefined' ? undefined : navigator
  return {
    secure: typeof window !== 'undefined' && window.isSecureContext,
    clipboardWrite: typeof nav?.clipboard?.write === 'function',
    clipboardItem: typeof ClipboardItem !== 'undefined',
  }
}

type CopyState = 'idle' | 'copying' | 'copied' | 'failed'

export function FigureOverlay({ runId, runName, meta, onClose }: Props) {
  const { explain } = useSettings()
  const box = useRef<HTMLDivElement>(null)
  const [zoom, setZoom] = useState(0)
  const [copy, setCopy] = useState<CopyState>('idle')
  const [copyError, setCopyError] = useState<string | null>(null)
  const capability = copyCapability(clipboardEnvironment())
  const names = exportNames(runId, meta.figure_id)
  const svg = api.figureImageUrl(runId, meta.figure_id, meta.cache_key, 'svg')
  const png = api.figureImageUrl(runId, meta.figure_id, meta.cache_key, 'png')

  useEffect(() => {
    const root = box.current
    if (!root) return
    const controls = () =>
      [...root.querySelectorAll<HTMLElement>('a[href], button:not([disabled])')]
    controls()[0]?.focus()
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        onClose()
        return
      }
      if (event.key !== 'Tab') return
      const items = controls()
      if (!items.length) return
      const first = items[0]
      const last = items[items.length - 1]
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
      }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  const doCopy = async () => {
    setCopy('copying')
    setCopyError(null)
    try {
      const blob = await fetch(png).then((response) => {
        if (!response.ok) throw new Error(`PNG fetch failed: ${response.status}`)
        return response.blob()
      })
      await navigator.clipboard.write([new ClipboardItem({ 'image/png': blob })])
      setCopy('copied')
    } catch (cause: unknown) {
      setCopy('failed')
      setCopyError(String(cause))
    }
  }

  const copyLabel = copy === 'copying' ? 'Copying…' : copy === 'copied' ? 'Copied' : 'Copy'
  const copyTitle = capability.reason ?? copyError ?? 'Copy the PNG to the clipboard'

  return (
    <div className="figure-overlay" role="presentation" onClick={onClose}>
      <div
        ref={box}
        className="figure-overlay-box"
        role="dialog"
        aria-modal="true"
        aria-label={meta.title}
        onClick={(event) => event.stopPropagation()}
      >
        <div className="figure-overlay-head doc-head">
          <span className="doc-head-title">
            {meta.title} — {runName ?? `run ${runId.slice(0, 8)}`} (maximised)
          </span>
          <span className="spacer" />
          <span className="muted figure-overlay-sub">{meta.subtitle}</span>
        </div>
        <div className="figure-overlay-bar" role="toolbar" aria-label="Figure toolbar">
          <div className="figure-actions">
            <a className="btn" href={png} download={names.png}>
              Save PNG
            </a>
            <a className="btn" href={svg} download={names.svg}>
              Save SVG
            </a>
            <button
              type="button"
              className="btn"
              disabled={!capability.enabled || copy === 'copying'}
              title={copyTitle}
              onClick={() => void doCopy()}
            >
              {copyLabel}
            </button>
            <button type="button" className="btn" onClick={onClose}>
              Close
            </button>
            <span className="toolbar-sep" />
            <button type="button" className="btn glyph" aria-label="Zoom in" disabled={zoom >= ZOOMS.length - 1} onClick={() => setZoom((value) => Math.min(ZOOMS.length - 1, value + 1))}>
              <Icon name="zoom-in" />
            </button>
            <button type="button" className="btn glyph" aria-label="Zoom out" disabled={zoom === 0} onClick={() => setZoom((value) => Math.max(0, value - 1))}>
              <Icon name="zoom-out" />
            </button>
            <button type="button" className="btn glyph" aria-label="Fit" title="Fit the figure to the window" disabled={zoom === 0} onClick={() => setZoom(0)}>
              <Icon name="crosshair" />
            </button>
          </div>
          <span className="spacer" />
          <span className="muted figure-overlay-context">Esc restores · run {runId.slice(0, 8)} · UTC</span>
        </div>
        {copy === 'failed' && copyError ? <p className="figure-copy-error">{copyError}</p> : null}
        <div className="figure-overlay-scroll">
          <img
            className="figure-overlay-image"
            src={svg}
            alt={meta.alt_text}
            style={zoom ? { width: `${ZOOMS[zoom] * 100}%`, maxHeight: 'none' } : undefined}
          />
        </div>
        <div className={notesVisible(explain) ? 'figure-explain' : 'figure-explain sr-only'}>
          <p className="figure-question">
            <span className="eyebrow">What this answers</span>
            {meta.question}
          </p>
          <p className="figure-caveat">
            <span className="eyebrow">How sure</span>
            {meta.uncertainty}
          </p>
          <p className="figure-caveat">
            <span className="eyebrow">Read with care</span>
            {meta.caveat}
          </p>
        </div>
      </div>
    </div>
  )
}
