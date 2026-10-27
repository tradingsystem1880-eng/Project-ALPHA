import { describe, expect, it } from 'vitest'

import type { MlCapabilities } from '../api/types'
import {
  EXPERIMENT_RECIPE,
  ML_MODELS,
  mlExperimentEvidenceLabel,
  mlLaunchRequest,
  selectedModelCapability,
} from './mlResearchModel'

describe('ML model capability selection', () => {
  const capabilities: MlCapabilities = {
    schema_version: 1, qlib_version: '0.9.7',
    backends: [
      { name: 'linear', status: 'available', reason: null, versions: { pyqlib: '0.9.7' } },
      { name: 'catboost', status: 'missing_dependency', reason: 'catboost is not installed', versions: {} },
      { name: 'xgboost', status: 'incompatible_dependency', reason: 'unsupported version', versions: {} },
    ],
  }
  it('offers exactly the first wave and uses the selected worker evidence', () => {
    expect(ML_MODELS.map((model) => model.name)).toEqual([
      'lightgbm', 'linear', 'catboost', 'xgboost', 'double_ensemble',
    ])
    expect(selectedModelCapability(capabilities, 'linear')?.status).toBe('available')
    expect(selectedModelCapability(capabilities, 'catboost')?.reason).toBe('catboost is not installed')
    expect(selectedModelCapability(capabilities, 'xgboost')?.status).toBe('incompatible_dependency')
  })
  it('never infers backend readiness from an absent probe or another available backend', () => {
    expect(selectedModelCapability(null, 'linear')).toBeNull()
    expect(selectedModelCapability(capabilities, 'lightgbm')).toBeNull()
  })
  it('sends no model override unless a model is explicitly chosen', () => {
    expect(mlLaunchRequest(EXPERIMENT_RECIPE, 'lasso')).toEqual({})
    expect(mlLaunchRequest('lightgbm', 'lasso')).toEqual({ model: 'lightgbm', parameters: {} })
    expect(mlLaunchRequest('linear', 'lasso')).toEqual({ model: 'linear', parameters: { estimator: 'lasso' } })
  })
})


describe('ML experiment recorded evidence labels', () => {
  it.each([
    ['prepared', null, false, 'INPUT PREPARED — MODEL NOT TRAINED'],
    ['prepared', null, true, 'INPUT PREPARED — MODEL NOT TRAINED'],
    ['trained', null, false, 'OOS PREDICTIONS — CANONICAL REPLAY PENDING'],
    ['trained', null, true, 'OOS PREDICTIONS — CANONICAL REPLAY PENDING'],
    ['replay_handoff_prepared', null, false, 'OOS PREDICTIONS — CANONICAL REPLAY PENDING'],
    ['trained', '0123456789abcdef', false, 'CANONICAL REPLAY RECORDED — COUNTERFACTUAL REFIT PENDING'],
    ['replay_handoff_prepared', '0123456789abcdef', true, 'CANONICAL REPLAY AND COUNTERFACTUAL REFIT RECORDED'],
    ['empty', null, false, 'MODEL NOT TRAINED — CANONICAL REPLAY NOT RECORDED'],
    ['unknown', null, true, 'MODEL NOT TRAINED — CANONICAL REPLAY NOT RECORDED'],
    ['trained', undefined, false, 'OOS PREDICTIONS — CANONICAL REPLAY PENDING'],
    ['prepared', '0123456789abcdef', false, 'INPUT PREPARED — MODEL NOT TRAINED'],
  ] as const)('labels %s, replay %s, refit %s from recorded evidence', (status, replay_run_id, counterfactual_refit, expected) => {
    expect(mlExperimentEvidenceLabel({ status, replay_run_id, counterfactual_refit })).toBe(expected)
  })
})
