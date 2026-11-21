// The small tag beside a price chart that says where the stored bars came from, in plain words.
// Only a real fault is red; a missing identity record is a neutral note with a hint.

import { venueLabel } from './venueNames'

export interface SourceTagInput {
  source: string
  venue: string | null
  timeframe: string
  quality_status: string
}

export interface SourceTag {
  text: string
  tone: 'kind' | 'pass'
  title: string
}

const BAR_SIZE: Readonly<Record<string, string>> = { '1D': 'daily', '1W': 'weekly', '1H': 'hourly' }

export function sourceTag(input: SourceTagInput): SourceTag {
  const name = venueLabel(input.source) ?? input.source
  const bars = `${name} ${BAR_SIZE[input.timeframe] ?? input.timeframe} bars`
  if (input.quality_status === 'legacy_unqualified') {
    return {
      text: `${bars} · identity not recorded`,
      tone: 'kind',
      title:
        'These bars were stored before ALPHA recorded the exact market and data identity. They are usable, but not provably the same series. '
        + `Source id: ${input.source}. Pulling the symbol again with "alpha data pull" stores it with its identity recorded.`,
    }
  }
  const venue = input.venue ? ` · ${input.venue}` : ''
  return { text: `${bars}${venue} · ${input.quality_status.replace(/_/g, ' ')}`, tone: 'pass', title: `Identity and quality are recorded for these bars. Source id: ${input.source}.` }
}
