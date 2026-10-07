import { useSyncExternalStore } from 'react'
type Selection = { id: string; hash: string | null }
const STORAGE_KEY = 'alpha.desk-rule.v1'
function restore(): Selection {
  try {
    const value = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? 'null')
    if (value && typeof value.id === 'string' && (value.hash === null || typeof value.hash === 'string')) return { id: value.id, hash: value.hash }
  } catch { /* Presentation history is optional. */ }
  return { id: '', hash: null }
}
let selected: Selection = restore()
const listeners = new Set<() => void>()
export function selectDeskRule(id: string, hash: string | null = null) {
  selected = { id, hash }
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(selected)) } catch { /* Selection still works in memory. */ }
  listeners.forEach(listener => listener())
}
export function useDeskRule() {
  return useSyncExternalStore(listener => { listeners.add(listener); return () => listeners.delete(listener) }, () => selected)
}
