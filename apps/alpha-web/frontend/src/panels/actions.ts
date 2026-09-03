// Navigation intents a panel can raise, without knowing what the shell is.
//
// Panels used to reach into the docking container and add windows, which meant every panel
// depended on the layout engine and on the ids other panels happened to use. They now state
// what they want -- show this run, open the lab with this command -- and the shell decides
// where that lands. Swapping the shell again would touch this file and nothing else.

import { setLinked } from '../context/linked'

export interface LabPrefill {
  command: string
  args: string
}

export interface Navigator {
  showRun(runId: string): void
  showStrategyLab(prefill?: LabPrefill): void
  showProjects(): void
  showResearchSources(): void
  showResearchData(): void
  /** Open the Data Manager and put the cursor in its symbol field. */
  showDataSymbol(): void
  showProviders(): void
  /** Open the Compare document (the selected run is ticked there). */
  showCompare(): void
}

/** Until the shell registers, intents are no-ops rather than crashes. */
let active: Navigator = {
  showRun: () => undefined,
  showStrategyLab: () => undefined,
  showProjects: () => undefined,
  showResearchSources: () => undefined,
  showResearchData: () => undefined,
  showDataSymbol: () => undefined,
  showProviders: () => undefined,
  showCompare: () => undefined,
}

let pendingPrefill: LabPrefill | null = null
const prefillListeners = new Set<() => void>()

export function registerNavigator(navigator: Navigator): void {
  active = navigator
}

/**
 * Show a run's report. The URL hash mirrors it (`#run=<id>`) so the address bar stays a
 * shareable deep link, which the shell reads at boot and on hashchange.
 */
export function openRunDetail(runId: string): void {
  setLinked({ runId })
  window.location.hash = `run=${runId}`
  active.showRun(runId)
}

/** The run id in the current URL hash (`#run=<16 hex>`), if any. */
export function runIdFromHash(): string | null {
  const match = /#run=([0-9a-f]{16})\b/.exec(window.location.hash)
  return match ? match[1] : null
}

/**
 * Open the Strategy Lab, optionally prefilled with a suggested command from the explanation
 * engine's next-step actions.
 *
 * The prefill is parked here rather than pushed as a panel parameter: the lab may not be
 * mounted yet when a suggestion is clicked from another screen, and dropping the suggestion
 * silently would be worse than holding it for one read. A mounted lab picks it up through
 * the subscription instead, since switching screens will not remount it.
 */
export function openStrategyLab(prefill?: LabPrefill): void {
  if (prefill) pendingPrefill = prefill
  active.showStrategyLab(prefill)
  if (prefill) for (const listener of [...prefillListeners]) listener()
}

/** Consume a queued prefill exactly once. */
export function takeLabPrefill(): LabPrefill | null {
  const value = pendingPrefill
  pendingPrefill = null
  return value
}

/**
 * Be told a prefill was queued. The listener is expected to call `takeLabPrefill`, so a
 * mounted lab consumes it and an unmounted one still finds it waiting at mount.
 */
export function onLabPrefill(listener: () => void): () => void {
  prefillListeners.add(listener)
  return () => {
    prefillListeners.delete(listener)
  }
}

/** Open the governed lifecycle surface used to resolve and launch a legacy trace rerun. */
export function openDevelopmentCenter(): void {
  active.showProjects()
}

export function openResearchSources(): void {
  active.showResearchSources()
}

export function openResearchData(): void {
  active.showResearchData()
}

export function openDataSymbol(): void {
  active.showDataSymbol()
}

export function openCompare(): void {
  active.showCompare()
}

export function openProviderCenter(): void {
  active.showProviders()
}
