// The one topbar status chip. Priority: the selected run's research-gate watermark (a server
// string relayed verbatim), then the linked project's open research gate, then the standing
// truth that nothing here routes live capital. The chip opens Governance; it derives nothing.

import type { StrategyGateLock } from '../panels/researchGateModel'

export interface StatusChip {
  text: string
  tone: 'kind' | 'warn' | 'fail'
  title: string
}

export function statusChip(input: {
  watermark: string | null
  gateLock: StrategyGateLock | null
}): StatusChip {
  if (input.watermark) {
    return {
      text: input.watermark,
      tone: 'fail',
      title: `${input.watermark} — the selected run was launched under an owner research-gate override and is permanently watermarked.`,
    }
  }
  if (input.gateLock) return { text: 'Research gate open', tone: 'warn', title: input.gateLock.reason }
  return {
    text: 'Paper only',
    tone: 'kind',
    title: 'No live-capital routing exists; every session is paper. Open Governance for authority and gates.',
  }
}
