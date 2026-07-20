import type { ControlJob, ControlJobDetail } from '../api/types'

const ACTIVE_STATUSES = new Set<ControlJob['status']>(['queued', 'running'])

export function isActiveControlJob(job: ControlJob): boolean {
  return ACTIVE_STATUSES.has(job.status)
}

export interface DurableJobRefresh {
  jobs: ControlJob[]
  activeJobIds: string[]
  completedJobIds: string[]
  detailErrors: string[]
}

const JOB_PAGE_LIMIT = 100
const MAX_JOB_PAGES = 50

/** Rehydrate every active summary through its durable detail resource after a reload. */
export async function refreshDurableJobs(
  listJobs: (
    limit: number,
    offset: number,
  ) => Promise<{ items: ControlJob[]; has_more?: boolean }>,
  getJobDetail: (jobId: string) => Promise<ControlJobDetail>,
): Promise<DurableJobRefresh> {
  const summaries: ControlJob[] = []
  for (let pageIndex = 0; pageIndex < MAX_JOB_PAGES; pageIndex += 1) {
    const page = await listJobs(JOB_PAGE_LIMIT, summaries.length)
    summaries.push(...page.items)
    if (!page.has_more) break
    if (page.items.length === 0) throw new Error('durable job pagination did not advance')
    if (pageIndex === MAX_JOB_PAGES - 1) {
      throw new Error(`durable job recovery exceeded ${MAX_JOB_PAGES * JOB_PAGE_LIMIT} records`)
    }
  }

  const activeSummaries = summaries.filter(isActiveControlJob)
  const results = await Promise.allSettled(
    activeSummaries.map((job) => getJobDetail(job.job_id)),
  )
  const details = new Map<string, ControlJob>()
  const detailErrors: string[] = []

  results.forEach((result, index) => {
    const jobId = activeSummaries[index].job_id
    if (result.status === 'fulfilled') details.set(jobId, result.value)
    else detailErrors.push(`${jobId}: ${String(result.reason)}`)
  })

  const jobs = summaries.map((job) => details.get(job.job_id) ?? job)
  const activeJobIds = jobs.filter(isActiveControlJob).map((job) => job.job_id)
  const completedJobIds = activeSummaries
    .filter((job) => !isActiveControlJob(details.get(job.job_id) ?? job))
    .map((job) => job.job_id)

  return { jobs, activeJobIds, completedJobIds, detailErrors }
}
