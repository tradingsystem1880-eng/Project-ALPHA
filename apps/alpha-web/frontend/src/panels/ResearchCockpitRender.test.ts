import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import type { ResearchCase, ResearchStudyStatusV1, VerifiedBlindSemanticReadV1 } from '../api/types'
import { StudyStatusSection } from './ResearchCockpit'

const hash = 'a'.repeat(64)
// A closed case: the study status renders with no owner step to offer.
const closedCase = {
  project_id: 'project-1',
  active_contract_id: `rc_${hash}`,
  phase: 'closed',
  execution_state: 'idle',
  responsibility: 'owner',
  exploration_review: { state: 'approved', event: null },
  confirmation_review: { state: 'approved', event: null },
  source_pack_id: null,
  next_action: 'Research Case is closed.',
} as unknown as ResearchCase
const noop = () => undefined

describe('Research Cockpit study status', () => {
  it('renders only the server-masked points and preserves owner-only D1 authority', () => {
    const status: ResearchStudyStatusV1 = {
      schema: 'ResearchStudyStatusV1',
      schema_version: 1,
      authority: 'none',
      project_id: 'project-1',
      active_contract_id: `rc_${hash}`,
      semantic: {
        state: 'review_required',
        source_state: 'current',
        case_contract_id: `rc_${hash}`,
        case_revision: hash,
        verified_read_sha256: hash,
        projection_sha256: hash,
        run_id: '0123456789abcdef',
        cutoff_confirmed_at: '2026-08-30T00:00:00Z',
        event_count: 1,
        head_sha256: hash,
        definition: {
          event_id: `se_${hash}`,
          artifact_id: `sd_${hash}`,
          receipt_id: 'receipt-1',
          actor: 'owner',
          reason: 'define observed shape',
          recorded_at: '2026-08-30T00:00:01Z',
          payload: {
            event_type: 'definition',
            definition_label: 'bounded reversal',
            definition_text: 'Describe only the visible pre-cutoff structure.',
          },
        },
        review: null,
        freeze: null,
        next_owner_action: 'Review with fresh Touch ID.',
      },
      d1: {
        launch_authority: 'owner_cli_only',
        status: 'not_started',
        attempts: [],
        elapsed_budget: { variants: 3 },
        remaining_budget: { variants: 61 },
      },
      promotion: {
        packet_id: null,
        readiness: { state: 'blocked', blockers: [] },
      },
      next_action: 'Launch through owner CLI only.',
      responsibility: 'owner',
    }
    const semanticRead: VerifiedBlindSemanticReadV1 = {
      schema: 'VerifiedBlindSemanticReadV1',
      schema_version: 1,
      source_verification: 'verified_completed_d0_recomputation',
      authority: 'none',
      run_id: '0123456789abcdef',
      projection: {
        schema: 'BlindSemanticProjectionV1',
        schema_version: 1,
        run_id: '0123456789abcdef',
        acceptance_artifact_sha256: hash,
        events_artifact_sha256: hash,
        chart_data_artifact_sha256: hash,
        cutoff_confirmed_at: '2026-08-30T00:00:00Z',
        points: [{ point_id: 'visible-1', available_at: '2026-08-29T23:00:00Z', value: 1 }],
        masked_count: 7,
        authority: 'none',
        cutoff_source: 'd0_acceptance_measurement_reference',
        lineage_verification: 'not_checked',
        semantic_status: 'unfrozen',
        content_sha256: hash,
      },
      content_sha256: hash,
    }

    const html = renderToStaticMarkup(createElement(StudyStatusSection, {
      status,
      semanticRead,
      semanticError: null,
      researchCase: closedCase,
      onRefresh: noop,
    }))

    expect(html).toContain('aria-label="Verified semantic study status"')
    expect(html).toContain('visible-1')
    expect(html).toContain('Masked future points')
    expect(html).toContain('>7<')
    expect(html).toContain('OWNER ONLY')
    expect(html).not.toContain('Touch ID · launch D1')
    expect(html).toContain('bounded reversal')
    expect(html).toContain('Describe only the visible pre-cutoff structure.')
    expect(html).toContain('Touch ID receipt receipt-1')
    expect(html).not.toContain('future-point-value')

    const staleHtml = renderToStaticMarkup(createElement(StudyStatusSection, {
      status: {
        ...status,
        semantic: {
          ...status.semantic,
          state: 'stale',
          source_state: 'stale',
          verified_read_sha256: 'b'.repeat(64),
          definition: null,
          review: null,
          freeze: null,
          next_owner_action: 'Refresh and obtain owner review.',
        },
      },
      semanticRead,
      semanticError: null,
      researchCase: closedCase,
      onRefresh: noop,
    }))
    expect(staleHtml).toContain('STALE')
    expect(staleHtml).toContain('MASKED D0 PROJECTION UNAVAILABLE')
    expect(staleHtml).not.toContain('visible-1')
    expect(staleHtml).not.toContain('bounded reversal')
  })
})
