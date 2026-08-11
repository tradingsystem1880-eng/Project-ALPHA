// Pure model for the CodexBench: exact recording commands, byte-identical packet
// display, and the epistemic fence around Codex commentary. The bench is a workbench,
// not a chat — packets are recorded through the owner's CLI or Codex's MCP seam, and
// this model only prepares and displays; it never records anything itself.

import type { ResearchContextPacket, ResearchNote } from '../api/types'

export const PACKET_KINDS = [
  'research_case',
  'asset',
  'experiment',
  'chart',
  'validation',
  'strategy_promotion',
] as const

export type PacketKind = typeof PACKET_KINDS[number]

export const NOTE_FENCE_BADGE = 'CODEX COMMENTARY — NOT EVIDENCE'

/** The exact owner-CLI command that records this packet; shown, copied, never executed. */
export function packetBuildCommand(
  projectId: string,
  kind: PacketKind,
  protocolId: string | null,
  symbol: string | null,
): string {
  const parts = ['alpha', 'research', 'context', 'build', projectId, '--kind', kind]
  if (kind === 'asset' && symbol) parts.push('--symbol', symbol)
  if (protocolId) parts.push('--protocol', protocolId)
  parts.push('--json')
  return parts.join(' ')
}

/** Byte-identical display: canonical JSON of the recorded payload, never re-shaped. */
export function packetPayloadJson(packet: ResearchContextPacket): string {
  return JSON.stringify(packet.payload, Object.keys(packet.payload).sort(), 2)
}

export interface PacketHistoryRow {
  packet_id: string
  packet_kind: string
  protocol_id: string | null
  created_at: string
  payload_bytes: number
}

export function packetHistoryRows(packets: ResearchContextPacket[]): PacketHistoryRow[] {
  return packets.map((packet) => ({
    packet_id: packet.packet_id,
    packet_kind: packet.packet_kind,
    protocol_id: packet.protocol_id,
    created_at: packet.created_at,
    payload_bytes: JSON.stringify(packet.payload).length,
  }))
}

export function noteAuthorLabel(note: ResearchNote): string {
  return note.author_kind === 'agent' ? `${note.author} · agent` : `${note.author} · owner`
}
