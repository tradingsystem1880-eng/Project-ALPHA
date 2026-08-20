import { useEffect, useState } from 'react'

import { getJSON } from '../api'
import { levelColor, levelHint } from '../model/evidence'
import type { NodeDetail } from '../model/types'

interface Excerpt {
  path: string
  start: number
  end: number
  lines: string[]
}

interface Anchor {
  path: string
  symbol: string
  line: number
}

function asList(value: unknown): string[] {
  return Array.isArray(value) ? value.map(String) : []
}

export interface StepNav {
  steps: Array<{ id: string; label: string }>
  onSelect: (id: string) => void
}

export function NodePanel({ nodeId, nav }: { nodeId: string; nav?: StepNav }) {
  const [detail, setDetail] = useState<NodeDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [excerpt, setExcerpt] = useState<Excerpt | null>(null)
  const [pack, setPack] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    setDetail(null)
    setExcerpt(null)
    setPack(null)
    setCopied(false)
    setError(null)
    getJSON<NodeDetail>(`/api/node/${encodeURIComponent(nodeId).replaceAll('%2F', '/')}`).then(
      setDetail,
      (e: Error) => setError(e.message),
    )
  }, [nodeId])

  if (error) return <div className="placeholder">{error}</div>
  if (!detail) return <div className="placeholder">Loading…</div>

  const { node, edges, neighbors } = detail
  const meta = node.meta ?? {}
  const stepIndex = nav ? nav.steps.findIndex((s) => s.id === node.id) : -1
  const anchors = (meta['verified_anchors'] as Anchor[] | undefined) ?? []
  const docs = edges.filter((e) => e.type === 'defines' && e.target === node.id)
  const tests = edges.filter((e) => e.type === 'validates' && e.target === node.id)
  const produces = edges.filter((e) => e.type === 'produces' && e.source === node.id)
  const dependsOn = edges.filter((e) => e.type === 'depends_on' && e.source === node.id)

  const showExcerpt = (anchor: Anchor) => {
    const start = Math.max(anchor.line - 2, 1)
    getJSON<Excerpt>(
      `/api/excerpt?path=${encodeURIComponent(anchor.path)}&start=${start}&end=${anchor.line + 18}`,
    ).then(setExcerpt, (e: Error) => setError(e.message))
  }

  const generateContext = async () => {
    setCopied(false)
    const response = await fetch('/api/prompt-pack', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ node_ids: [node.id] }),
    })
    if (!response.ok) {
      setError(`prompt pack failed: ${response.status}`)
      return
    }
    const payload = (await response.json()) as { markdown: string }
    setPack(payload.markdown)
  }

  const copyPack = async () => {
    if (pack) {
      await navigator.clipboard.writeText(pack)
      setCopied(true)
    }
  }

  return (
    <div>
      <h2>{node.label}</h2>
      <div>
        <span className="kind">{node.kind}</span>
        <span
          className="badge"
          style={{ background: levelColor(node.evidence.level) }}
          title={levelHint(node.evidence.level)}
        >
          {node.evidence.level}
        </span>
        {meta['needs_reverification'] === true && (
          <span className="warn"> needs re-verification</span>
        )}
        <p className="level-hint">{levelHint(node.evidence.level)}</p>
      </div>

      {stepIndex >= 0 && nav && (
        <div className="step-nav">
          <button
            className="cta secondary"
            disabled={stepIndex === 0}
            onClick={() => nav.onSelect(nav.steps[stepIndex - 1].id)}
          >
            ← Previous
          </button>
          <button
            className="cta secondary"
            disabled={stepIndex === nav.steps.length - 1}
            onClick={() => nav.onSelect(nav.steps[stepIndex + 1].id)}
          >
            Next →
          </button>
          <span className="count">
            step {stepIndex + 1} of {nav.steps.length}
          </span>
        </div>
      )}

      {typeof meta['purpose'] === 'string' && (
        <>
          <h3>Purpose</h3>
          <p>{meta['purpose']}</p>
        </>
      )}

      {anchors.length > 0 && (
        <>
          <h3>Implementing files</h3>
          <ul>
            {anchors.map((anchor) => (
              <li key={`${anchor.path}:${anchor.symbol}`} className="prov">
                <button onClick={() => showExcerpt(anchor)}>
                  {anchor.path}:{anchor.line}
                </button>
                {anchor.symbol ? ` — ${anchor.symbol}` : ''}
              </li>
            ))}
          </ul>
        </>
      )}

      {excerpt && (
        <>
          <h3>
            {excerpt.path} lines {excerpt.start}–{excerpt.end}
          </h3>
          <div className="excerpt">
            {excerpt.lines.map((line, i) => `${excerpt.start + i}  ${line}`).join('\n')}
          </div>
        </>
      )}

      {docs.length > 0 && (
        <>
          <h3>Defined by</h3>
          <ul>
            {docs.map((e) => (
              <li key={e.id}>{neighbors[e.source]?.label ?? e.source}</li>
            ))}
          </ul>
        </>
      )}

      {tests.length > 0 && (
        <>
          <h3>Verified by {tests.length} test file(s)</h3>
          <ul>
            {tests.slice(0, 12).map((e) => (
              <li key={e.id} className="prov">
                {e.source.replace('test:', '')}
              </li>
            ))}
            {tests.length > 12 && <li>… and {tests.length - 12} more</li>}
          </ul>
        </>
      )}

      {(produces.length > 0 || dependsOn.length > 0) && (
        <>
          <h3>Produces / depends on</h3>
          <ul>
            {produces.map((e) => (
              <li key={e.id}>produces → {neighbors[e.target]?.label ?? e.target}</li>
            ))}
            {dependsOn.map((e) => (
              <li key={e.id}>depends on → {neighbors[e.target]?.label ?? e.target}</li>
            ))}
          </ul>
        </>
      )}

      {asList(meta['limitations']).length > 0 && (
        <>
          <h3>Limitations</h3>
          <ul>
            {asList(meta['limitations']).map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </>
      )}

      {asList(meta['safe_change']).length > 0 && (
        <>
          <h3>Safe change area</h3>
          <ul>
            {asList(meta['safe_change']).map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </>
      )}

      <h3>AI context</h3>
      <p>
        <button className="cta" onClick={generateContext}>
          Generate AI Context
        </button>{' '}
        {pack && (
          <button className="cta" onClick={copyPack}>
            {copied ? 'Copied ✓' : 'Copy for Codex / Claude'}
          </button>
        )}
      </p>
      {pack && <div className="excerpt">{pack}</div>}

      <div className="meta-footer">
        {typeof meta['owner'] === 'string' && <div>curated by: {meta['owner']}</div>}
        {typeof meta['confidence'] === 'string' && (
          <div>documentation confidence: {meta['confidence']} (provenance quality, not correctness)</div>
        )}
        {typeof meta['last_verified_commit'] === 'string' && (
          <div>last verified: {meta['last_verified_commit']}</div>
        )}
        <div>
          evidence provenance:
          <ul>
            {node.evidence.provenance.slice(0, 8).map((p, i) => (
              <li key={i} className="prov">
                {p.extractor}: {p.source}
                {p.line ? `:${p.line}` : ''} — {p.detail}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  )
}
