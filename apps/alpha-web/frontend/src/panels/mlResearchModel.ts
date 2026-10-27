import type { MlCapabilities, MlExperimentSummary, MlModelName, MlModelParameters } from '../api/types'

export const ML_MODELS: { name: MlModelName; label: string }[] = [
  { name: 'lightgbm', label: 'LightGBM' },
  { name: 'linear', label: 'Linear' },
  { name: 'catboost', label: 'CatBoost' },
  { name: 'xgboost', label: 'XGBoost' },
  { name: 'double_ensemble', label: 'DoubleEnsemble' },
]

export function selectedModelCapability(capabilities: MlCapabilities | null, model: MlModelName) {
  return capabilities?.backends.find((backend) => backend.name === model) ?? null
}

/** Keeps the experiment's frozen recipe and schema; only a named model publishes an override. */
export const EXPERIMENT_RECIPE = 'experiment_recipe'
export type MlModelChoice = MlModelName | typeof EXPERIMENT_RECIPE

export function mlLaunchRequest(
  choice: MlModelChoice,
  estimator: 'ols' | 'ridge' | 'lasso' | 'nnls',
): { model?: MlModelName; parameters?: MlModelParameters } {
  if (choice === EXPERIMENT_RECIPE) return {}
  return { model: choice, parameters: choice === 'linear' ? { estimator } : {} }
}


export function mlExperimentEvidenceLabel(
  experiment: Pick<MlExperimentSummary, 'status' | 'replay_run_id' | 'counterfactual_refit'>,
): string {
  if (experiment.status === 'prepared') return 'INPUT PREPARED — MODEL NOT TRAINED'
  if (experiment.status !== 'trained' && experiment.status !== 'replay_handoff_prepared') {
    return 'MODEL NOT TRAINED — CANONICAL REPLAY NOT RECORDED'
  }
  if (experiment.replay_run_id) {
    return experiment.counterfactual_refit
      ? 'CANONICAL REPLAY AND COUNTERFACTUAL REFIT RECORDED'
      : 'CANONICAL REPLAY RECORDED — COUNTERFACTUAL REFIT PENDING'
  }
  return 'OOS PREDICTIONS — CANONICAL REPLAY PENDING'
}
