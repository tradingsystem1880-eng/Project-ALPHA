// MDI document state (spec 2026-09-01 §4.2 item 5): which documents are open, in which order,
// and which one is active. Pure and deterministic — the same action list always yields a
// deep-equal state — so the shell can replay it and tests can assert it without a DOM.

import type { WindowId } from './profiles'

/** `<window id>` or `<window id>:<instance>` (a report keyed by run, a chart keyed by symbol). */
export type DocumentKey = string

export interface OpenDocument {
  key: DocumentKey
  window: WindowId
  /** MDI tab text; the registry title unless the opener names the instance. */
  title: string
}

export interface MdiState {
  documents: readonly OpenDocument[]
  active: DocumentKey | null
}

export const EMPTY_MDI: MdiState = Object.freeze({ documents: Object.freeze([]), active: null })

export function windowOf(key: DocumentKey): WindowId {
  return key.split(':', 1)[0] as WindowId
}

/** Open (or re-activate) a document; opening an open key never duplicates it. */
export function openDocument(state: MdiState, key: DocumentKey, title: string): MdiState {
  if (state.documents.some((item) => item.key === key)) return { ...state, active: key }
  return {
    documents: [...state.documents, { key, window: windowOf(key), title }],
    active: key,
  }
}

export function activateDocument(state: MdiState, key: DocumentKey): MdiState {
  if (!state.documents.some((item) => item.key === key)) throw new Error(`unknown document ${key}`)
  return { ...state, active: key }
}

/** Close a document; closing the active one activates its previous neighbour (or the next). */
export function closeDocument(state: MdiState, key: DocumentKey): MdiState {
  const index = state.documents.findIndex((item) => item.key === key)
  if (index < 0) throw new Error(`unknown document ${key}`)
  const documents = state.documents.filter((item) => item.key !== key)
  if (state.active !== key) return { documents, active: state.active }
  const neighbour = documents[Math.max(0, index - 1)] ?? null
  return { documents, active: neighbour ? neighbour.key : null }
}
