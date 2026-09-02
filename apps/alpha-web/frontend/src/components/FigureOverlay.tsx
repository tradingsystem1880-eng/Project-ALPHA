/**
 * A figure at full size, with the four things a trader does with it: Save PNG, Save SVG, Copy,
 * Close. A fixed overlay with role=dialog and a focus trap on its controls, following the
 * App.tsx palette precedent — the SPA has no dialog dependency. The image bytes are the
 * existing server-rendered ones; Copy fetches the PNG endpoint and hands the blob to the
 * Clipboard API, and says why when that API is not available.
 */

import { useEffect, useRef, useState } from 'react'

import { api } from '../api/client'
import type { FigureMetadata } from '../api/types'
import { useSettings } from '../state/settings'
import { copyCapability, exportNames, notesVisible } from './figureExport'

interface Props {
  runId: string
  meta: FigureMetadata
  onClose: () => void
}

function clipboardEnvironment() {
  const nav = typeof navigator === 'undefined' ? undefined : navigator
  return {
    secure: typeof window !== 'undefined' && window.isSecureContext,
    clipboardWrite: typeof nav?.clipboard?.write === 'function',
    clipboardItem: typeof ClipboardItem !== 'undefined',
  }
}

type CopyState = 'idle' | 'copying' | 'copied' | 'failed'

export function FigureOverlay({ runId, meta, onClose }: Props) {
  const { explain } = useSettings()
  const box = useRef<HTMLDivElement>(null)
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
        <div className="figure-overlay-head">
          <div className="figure-overlay-title">
            <b>{meta.title}</b>
            <span className="muted">{meta.subtitle}</span>
          </div>
          <div className="figure-actions">
            <a className="btn ghost" href={png} download={names.png}>
              Save PNG
            </a>
            <a className="btn ghost" href={svg} download={names.svg}>
              Save SVG
            </a>
            <button
              type="button"
              className="btn ghost"
              disabled={!capability.enabled || copy === 'copying'}
              title={copyTitle}
              onClick={() => void doCopy()}
            >
              {copyLabel}
            </button>
            <button type="button" className="btn ghost" onClick={onClose}>
              Close
            </button>
          </div>
        </div>
        {copy === 'failed' && copyError ? <p className="figure-copy-error">{copyError}</p> : null}
        <img className="figure-overlay-image" src={svg} alt={meta.alt_text} />
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
