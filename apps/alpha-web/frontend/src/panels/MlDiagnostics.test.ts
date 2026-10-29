import { describe, expect, it } from 'vitest'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'

import type { MlExperimentPage, MlTearSheetProjection } from '../api/types'
import { mlExperimentPlaceholderLabel } from './mlTearsheetModel'
import { MlDiagnosticsBody } from './MlDiagnostics'

describe('mlExperimentPlaceholderLabel', () => {
  it('keeps loading, failure, and successful-empty experiment states distinct', () => {
    const empty = { items: [], limit: 50, offset: 0, has_more: false } as MlExperimentPage

    expect(mlExperimentPlaceholderLabel(null, null)).toBe('LOADING EXPERIMENTS…')
    expect(mlExperimentPlaceholderLabel(null, 'offline')).toBe('EXPERIMENT QUERY FAILED')
    expect(mlExperimentPlaceholderLabel(empty, null)).toBe('NO VALIDATED EXPERIMENT')
  })
})


describe('tabular diagnostic display', () => {
  it('renders absent linear importance and economics without inventing tree gain', () => {
    const sheet: MlTearSheetProjection = {
      available: true, exchange_id: 'a'.repeat(32), authority: 'qlib_diagnostic_only',
      label: 'Predictive diagnostics only', membership_status: 'current_membership_warning',
      counterfactual_refit: false, model_backend: 'linear', versions: null,
      feature_recipe: null, label_recipe: null, score_distribution: null, ic: null,
      quantile_returns: [], portfolio: null, feature_importance: [],
      feature_importance_truncated: false, folds: [], timeline_total: 0,
      timeline_offset: 0, timeline_limit: 500, timeline_has_more: false,
    }
    const html = renderToStaticMarkup(createElement(MlDiagnosticsBody, { sheet, summary: null }))
    expect(html).toContain('FEATURE IMPORTANCE NOT EMITTED')
    expect(html).toContain('DIAGNOSTIC PORTFOLIO NOT EMITTED')
    expect(html).toContain('Canonical ALPHA replay')
    expect(html).not.toContain('mean gain')
    expect(html).not.toContain('relative gain')
    expect(html).not.toContain('LightGBM')
    expect(html).not.toContain('Model score diagnostic state')
    for (const score_status of ['degenerate', 'ties_present'] as const) {
      const reason = score_status === 'degenerate'
        ? 'All scores are identical; quantile grouping is unavailable.'
        : 'Tied cross-sections are omitted from quantile grouping.'
      const stateHtml = renderToStaticMarkup(createElement(MlDiagnosticsBody, {
        sheet: { ...sheet, diagnostic_state: {
          score_status, reason, degenerate_cross_sections: 1,
          tied_cross_sections: 2, quantile_cross_sections: 0,
        } }, summary: null,
      }))
      expect(stateHtml).toContain(reason)
      expect(stateHtml).toContain('Model score diagnostic state')
      expect(stateHtml).toContain('QUANTILE RETURNS NOT EMITTED')
    }
  })
})
