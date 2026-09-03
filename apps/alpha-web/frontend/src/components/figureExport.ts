// Pure decisions behind the figure overlay: what a saved image is called, whether Copy can work,
// and whether the figure's prose is shown. The overlay only renders what this file decides.

export interface ExportNames {
  png: string
  svg: string
}

/** `<run prefix>-<figure>.<ext>` — the run prefix is what the Library rail shows for the run. */
export function exportNames(runId: string, figureId: string): ExportNames {
  const stem = `${runId.slice(0, 8)}-${figureId}`
  return { png: `${stem}.png`, svg: `${stem}.svg` }
}

export interface ClipboardEnvironment {
  secure: boolean
  clipboardWrite: boolean
  clipboardItem: boolean
}

export interface CopyCapability {
  enabled: boolean
  reason: string | null
}

export function copyCapability(env: ClipboardEnvironment): CopyCapability {
  if (!env.secure) return { enabled: false, reason: 'Copy needs a secure page (https or localhost)' }
  if (!env.clipboardWrite || !env.clipboardItem) {
    return { enabled: false, reason: 'This browser cannot copy images to the clipboard' }
  }
  return { enabled: true, reason: null }
}

/** Question, uncertainty and caveat are visible only as Notes (narrative mode). */
export function notesVisible(explain: string): boolean {
  return explain === 'narrative'
}
