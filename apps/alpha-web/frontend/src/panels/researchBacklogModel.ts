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

export interface IdeaCardSummary {
  heading: string
  shown: { id: string; line: string }[]
  more: number
}

const IDEA_CARDS_SHOWN = 5

/** The front screen's idea-card block: the count, the first few cards with their claim and test status. */
export function ideaCardsSummary(cards: readonly { id: string; claim?: string | null; tested: boolean }[]): IdeaCardSummary {
  return {
    heading: `Idea cards (${cards.length})`,
    shown: cards.slice(0, IDEA_CARDS_SHOWN).map((card) => ({
      id: card.id,
      line: `${card.claim?.trim() || 'Claim not stated'} · ${card.tested ? 'test linked' : 'no test yet'}`,
    })),
    more: Math.max(0, cards.length - IDEA_CARDS_SHOWN),
  }
}
