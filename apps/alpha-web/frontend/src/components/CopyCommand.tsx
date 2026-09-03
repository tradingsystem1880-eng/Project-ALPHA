// A step that an ADR keeps on the trusted CLI is still one click away: the exact command, a
// Copy button, and the one-line reason it is CLI-only. Nothing here runs anything.

import { useEffect, useState } from 'react'

export function CopyCommand({ command, why }: { command: string; why: string }) {
  const [state, setState] = useState<'idle' | 'copied' | 'failed'>('idle')
  useEffect(() => {
    if (state === 'idle') return
    const timer = window.setTimeout(() => setState('idle'), 2_000)
    return () => window.clearTimeout(timer)
  }, [state])
  const canCopy = typeof navigator !== 'undefined' && typeof navigator.clipboard?.writeText === 'function'
  return (
    <div className="copy-command" role="group" aria-label="Trusted CLI step">
      <code className="mono copy-command-text">{command}</code>
      <button
        type="button"
        className="btn"
        disabled={!canCopy}
        title={canCopy ? 'Copy this command to the clipboard' : 'Clipboard unavailable — select the command text instead'}
        onClick={() => {
          navigator.clipboard
            .writeText(command)
            .then(() => setState('copied'))
            .catch(() => setState('failed'))
        }}
      >
        {state === 'copied' ? 'Copied' : state === 'failed' ? 'Copy failed' : 'Copy command'}
      </button>
      <span className="muted copy-command-why">{why}</span>
    </div>
  )
}
