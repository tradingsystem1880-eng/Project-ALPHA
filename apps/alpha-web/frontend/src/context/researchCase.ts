// One-shot "follow this research case" signal from a gated strategy surface (Development
// Center / Strategy Lab / Validation Workflow) to the shell. The shell links the project,
// switches to the research desk, and focuses the Research Cockpit so the owner lands on the
// case that is holding the gate. Mirrors context/newIdea.ts: focus intent only, no mutation.

type Listener = (projectId: string) => void

const listeners = new Set<Listener>()

export function requestResearchCase(projectId: string): void {
  for (const listener of listeners) listener(projectId)
}

export function onResearchCase(listener: Listener): () => void {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}
