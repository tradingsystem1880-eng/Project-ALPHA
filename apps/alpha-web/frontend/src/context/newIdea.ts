// One-shot "New Idea" signal from the shell (topbar button / palette) to the Research
// Cockpit's capture form. Deliberately not part of linked context: it carries no data,
// only focus intent, and it never creates anything — capture stays an explicit POST.

type Listener = () => void

const listeners = new Set<Listener>()

export function requestNewIdea(): void {
  for (const listener of listeners) listener()
}

export function onNewIdea(listener: Listener): () => void {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}
