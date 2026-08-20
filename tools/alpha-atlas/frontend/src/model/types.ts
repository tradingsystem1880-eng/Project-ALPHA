// Mirrors architecture/atlas/schema/atlas-schema.json (the schema is the authority).

export interface Provenance {
  extractor: string
  source: string
  detail: string
  line?: number
}

export type EvidenceLevel =
  | 'unknown'
  | 'declared'
  | 'implemented'
  | 'connected'
  | 'tested'
  | 'observed'

export interface Evidence {
  level: EvidenceLevel
  provenance: Provenance[]
}

export interface AtlasNode {
  id: string
  kind: string
  label: string
  path?: string
  component?: string
  evidence: Evidence
  meta?: Record<string, unknown>
}

export interface AtlasEdge {
  id: string
  type: string
  source: string
  target: string
  evidence: Evidence
}

export interface AtlasGraph {
  schema_version: number
  inputs_hash: string
  nodes: AtlasNode[]
  edges: AtlasEdge[]
  stats: Record<string, unknown>
}

export interface NodeDetail {
  node: AtlasNode
  edges: AtlasEdge[]
  neighbors: Record<string, { label: string; kind: string; level: EvidenceLevel }>
}
