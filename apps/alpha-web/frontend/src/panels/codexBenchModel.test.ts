import { describe, expect, it } from 'vitest'

import type { ResearchContextPacket, ResearchNote } from '../api/types'
import {
  NOTE_FENCE_BADGE,
  PACKET_KINDS,
  noteAuthorLabel,
  packetBuildCommand,
  packetHistoryRows,
  packetPayloadJson,
} from './codexBenchModel'

function packet(overrides: Partial<ResearchContextPacket> = {}): ResearchContextPacket {
  return {
    packet_id: `cp_${'a'.repeat(64)}`,
    project_id: 'project-1',
    packet_kind: 'research_case',
    protocol_id: 'new-idea-intake',
    protocol_content_hash: 'b'.repeat(64),
    payload: { packet_schema: 'ResearchContextPacketV1', b: 2, a: 1 },
    created_by: 'codex',
    created_at: '2026-08-09T00:00:00Z',
    ...overrides,
  }
}

describe('codex bench model', () => {
  it('prepares the exact owner-CLI recording command without executing anything', () => {
    expect(packetBuildCommand('project-1', 'research_case', 'new-idea-intake', null)).toBe(
      'alpha research context build project-1 --kind research_case '
        + '--protocol new-idea-intake --json',
    )
    expect(packetBuildCommand('project-1', 'asset', null, 'SPY')).toBe(
      'alpha research context build project-1 --kind asset --symbol SPY --json',
    )
    expect(PACKET_KINDS).toHaveLength(6)
  })

  it('renders the recorded payload deterministically with sorted keys', () => {
    const rendered = packetPayloadJson(packet())
    expect(rendered.indexOf('"a"')).toBeLessThan(rendered.indexOf('"b"'))
    expect(rendered).toContain('ResearchContextPacketV1')
  })

  it('summarises packet history without reshaping payloads', () => {
    const rows = packetHistoryRows([packet()])
    expect(rows).toEqual([
      {
        packet_id: `cp_${'a'.repeat(64)}`,
        packet_kind: 'research_case',
        protocol_id: 'new-idea-intake',
        created_at: '2026-08-09T00:00:00Z',
        payload_bytes: JSON.stringify(packet().payload).length,
      },
    ])
  })

  it('fences commentary as never-evidence with explicit authorship', () => {
    expect(NOTE_FENCE_BADGE).toBe('CODEX COMMENTARY — NOT EVIDENCE')
    const note: ResearchNote = {
      note_id: `rn_${'c'.repeat(64)}`,
      project_id: 'project-1',
      sequence: 1,
      note_kind: 'critique',
      body: 'x',
      author: 'codex',
      author_kind: 'agent',
      context_packet_id: null,
      created_at: '2026-08-09T00:00:00Z',
    }
    expect(noteAuthorLabel(note)).toBe('codex · agent')
    expect(noteAuthorLabel({ ...note, author: 'owner', author_kind: 'owner' })).toBe(
      'owner · owner',
    )
  })
})
