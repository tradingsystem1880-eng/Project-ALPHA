let pending: Record<string, unknown> | null = null
const listeners = new Set<() => void>()
export function publishRuleDraft(spec: Record<string, unknown>) {
  pending = spec; listeners.forEach(listener => listener())
}
export function consumeRuleDraft() { const draft = pending; pending = null; return draft }
export function onRuleDraft(listener: () => void) { listeners.add(listener); return () => { listeners.delete(listener) } }
