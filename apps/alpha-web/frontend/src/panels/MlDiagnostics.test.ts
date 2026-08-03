import { describe, expect, it } from 'vitest'

import type { MlExperimentPage } from '../api/types'
import { mlExperimentPlaceholderLabel } from './mlTearsheetModel'

describe('mlExperimentPlaceholderLabel', () => {
  it('keeps loading, failure, and successful-empty experiment states distinct', () => {
    const empty = { items: [], limit: 50, offset: 0, has_more: false } as MlExperimentPage

    expect(mlExperimentPlaceholderLabel(null, null)).toBe('LOADING EXPERIMENTS…')
    expect(mlExperimentPlaceholderLabel(null, 'offline')).toBe('EXPERIMENT QUERY FAILED')
    expect(mlExperimentPlaceholderLabel(empty, null)).toBe('NO VALIDATED EXPERIMENT')
  })
})
