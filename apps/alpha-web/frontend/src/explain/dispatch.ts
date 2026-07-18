// The one kind→suggestion-engine mapping. Every surface that wants "next steps for this run"
// (Run Detail, Pipeline) routes through here — a new run kind is added once, not per panel.

import { forecastSuggestions } from './forecast'
import { optimSuggestions } from './optim'
import { portfolioSuggestions } from './portfolio'
import { propfirmSuggestions } from './propfirm'
import { suggestions } from './suggestions'
import type {
  ForecastManifest,
  OptimManifest,
  PortfolioManifest,
  PropfirmManifest,
  Suggestion,
  ValidateManifest,
} from './types'

export function suggestionsFor(kind: string, manifest: Record<string, unknown>): Suggestion[] {
  switch (kind) {
    case 'optim':
      return optimSuggestions(manifest as OptimManifest)
    case 'portfolio':
    case 'cross_sectional':
      return portfolioSuggestions(manifest as PortfolioManifest)
    case 'propfirm':
      return propfirmSuggestions(manifest as PropfirmManifest)
    case 'forecast':
      return forecastSuggestions(manifest as ForecastManifest)
    default: {
      // runs/: the gauntlet engine only speaks about validated runs — a plain backtest has no
      // gates to narrate, so it gets no (rather than confidently wrong) suggestions.
      const vm = manifest as ValidateManifest
      return vm.verdict ? suggestions(vm) : []
    }
  }
}
