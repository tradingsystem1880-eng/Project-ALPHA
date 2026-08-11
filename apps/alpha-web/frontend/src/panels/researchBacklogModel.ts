// Pure grouping model for the ResearchBacklog panel: serves the already-tested
// bucket/sort/progress model in researchCockpitModel.ts against the new list route.

import {
  researchBucketLabel,
  researchCaseBucket,
  sortResearchCases,
  type ResearchCaseBucket,
  type ResearchCaseSummary,
} from './researchCockpitModel'

const BUCKET_RENDER_ORDER: readonly ResearchCaseBucket[] = [
  'needs_owner',
  'running',
  'ready',
  'blocked',
  'closed',
]

export interface ResearchBacklogGroup {
  bucket: ResearchCaseBucket
  label: string
  cases: ResearchCaseSummary[]
}

export function groupResearchBacklog(rows: ResearchCaseSummary[]): ResearchBacklogGroup[] {
  const sorted = sortResearchCases(rows)
  return BUCKET_RENDER_ORDER.flatMap((bucket) => {
    const cases = sorted.filter((row) => researchCaseBucket(row) === bucket)
    if (cases.length === 0) return []
    return [{ bucket, label: researchBucketLabel(bucket), cases }]
  })
}
