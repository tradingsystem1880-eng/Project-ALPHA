import type { JobSummary } from '../api/types'

export interface JobProgressView {
  elapsedSeconds: number
  elapsedLabel: string
  etaLabel: string
  estimateBasis: string
  fraction: number | null
  currentStep: string
  commandPath: string
}

export function formatJobDuration(seconds: number): string {
  const whole = Math.max(0, Math.floor(seconds))
  if (whole < 60) return `${whole}s`
  const minutes = Math.floor(whole / 60)
  const remainder = whole % 60
  if (minutes < 60) return `${minutes}m ${String(remainder).padStart(2, '0')}s`
  const hours = Math.floor(minutes / 60)
  return `${hours}h ${String(minutes % 60).padStart(2, '0')}m`
}

export function jobProgressView(job: JobSummary, nowSeconds: number): JobProgressView {
  const commandPath = job.command_path || job.command.split(' ').slice(0, 2).join(' ')
  const running = job.status === 'running'
  const hasRecordedElapsed = Number.isFinite(job.elapsed_seconds)
  const elapsedSeconds = running
    ? Math.max(0, nowSeconds - job.created_at)
    : Math.max(0, hasRecordedElapsed ? job.elapsed_seconds : 0)
  const estimatedTotal =
    job.progress_mode === 'estimated' && job.eta_seconds !== null
      ? Math.max(job.elapsed_seconds + job.eta_seconds, 0.001)
      : null
  const remaining = estimatedTotal === null ? null : Math.max(0, estimatedTotal - elapsedSeconds)
  const fraction =
    !running || job.progress_mode === 'terminal'
      ? 1
      : estimatedTotal === null
        ? null
        : Math.min(elapsedSeconds / estimatedTotal, 0.95)

  let etaLabel = 'estimating…'
  if (!running) etaLabel = 'complete'
  else if (remaining !== null && remaining <= 0) etaLabel = 'finishing…'
  else if (remaining !== null && remaining < 60) etaLabel = '<1 min'
  else if (remaining !== null) etaLabel = `~${Math.ceil(remaining / 60)} min`

  return {
    elapsedSeconds,
    elapsedLabel: !running && !hasRecordedElapsed ? 'not recorded' : formatJobDuration(elapsedSeconds),
    etaLabel,
    estimateBasis:
      job.eta_sample_count > 0
        ? `median of ${job.eta_sample_count} completed ${commandPath} job${job.eta_sample_count === 1 ? '' : 's'} this session`
        : 'waiting for the first comparable completed run',
    fraction,
    currentStep:
      job.current_step ||
      `${running ? 'Running' : job.status === 'done' ? 'Completed' : `Exited ${job.status}`} alpha ${commandPath}`,
    commandPath,
  }
}
