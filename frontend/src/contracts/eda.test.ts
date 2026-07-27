import { describe, expect, it } from 'vitest'
import {
  EdaComputeRequestSchema,
  EdaJobSummarySchema,
  EdaPanelStatusSchema,
  EdaPeriodKindSchema,
  EdaRunSummarySchema,
  EdaSectionNameSchema,
  EdaSectionResponseSchema,
} from './eda'
import {
  edaCompleteSections,
  edaFailedJob,
  edaFailedSection,
  edaNotEligibleSection,
  edaReadyMonthlyRun,
  edaRunningCustomJob,
} from '../mocks/fixtures/eda'

describe('B02-v3 EDA contracts', () => {
  it('accepts the exact period, section, and status vocabularies', () => {
    expect(EdaPeriodKindSchema.options).toEqual(['daily', 'weekly', 'monthly', 'custom', 'full_range'])
    expect(EdaPanelStatusSchema.options).toEqual(['complete', 'not_eligible', 'failed'])
    expect(EdaSectionNameSchema.options).toEqual([
      'quality_overview',
      'joint_density',
      'univariate',
      'quality_excerpt',
      'temporal_coverage',
      'temporal_distribution',
      'relationships',
      'stationarity',
      'change_points',
      'uncertainty',
      'audit_metadata',
    ])
  })

  it('parses ready, active, failed, and all eleven complete section fixtures', () => {
    expect(EdaRunSummarySchema.parse(edaReadyMonthlyRun)).toEqual(edaReadyMonthlyRun)
    expect(EdaJobSummarySchema.parse(edaRunningCustomJob).status).toBe('running')
    expect(EdaJobSummarySchema.parse(edaFailedJob).status).toBe('failed')
    expect(edaCompleteSections).toHaveLength(11)
    for (const section of edaCompleteSections) {
      expect(EdaSectionResponseSchema.parse(section)).toEqual(section)
    }
  })

  it('narrows unavailable sections and rejects analytic payloads on them', () => {
    const notEligible = EdaSectionResponseSchema.parse(edaNotEligibleSection)
    const failed = EdaSectionResponseSchema.parse(edaFailedSection)

    expect(notEligible.status).toBe('not_eligible')
    if (notEligible.status !== 'not_eligible') throw new Error('expected not_eligible section')
    expect(notEligible.detail).toBe('Median per jam belum cukup untuk analisis stasioneritas utama.')
    expect(notEligible.payload).toBeNull()
    expect(failed.status).toBe('failed')
    expect(failed.payload).toBeNull()
    expect(EdaSectionResponseSchema.safeParse({ ...edaNotEligibleSection, payload: {} }).success).toBe(false)
    expect(EdaSectionResponseSchema.safeParse({ ...edaFailedSection, payload_sha256: 'e'.repeat(64) }).success).toBe(false)
  })

  it('rejects legacy, unknown, and algorithm-less payloads', () => {
    const complete = edaCompleteSections[0]
    const completeWithoutAlgorithm: Record<string, unknown> = { ...complete }
    delete completeWithoutAlgorithm.algorithm_version

    expect(EdaRunSummarySchema.safeParse({
      ...edaReadyMonthlyRun,
      score_provenance: 'legacy',
    }).success).toBe(false)
    expect(EdaSectionResponseSchema.safeParse({
      ...complete,
      payload: {
        ...complete.payload,
        quality_metrics: { score_provenance: 'legacy' },
      },
    }).success).toBe(false)
    expect(EdaSectionResponseSchema.safeParse(completeWithoutAlgorithm).success).toBe(false)
    expect(EdaSectionResponseSchema.safeParse({
      ...complete,
      section: 'unknown_section',
    }).success).toBe(false)
  })

  it('keeps custom compute ranges half-open and second-precision', () => {
    const request = {
      device_id: 'b02f3872-39a2-4b6f-a4ec-045a287fde4b',
      time_zone: 'Asia/Jakarta',
      period_kind: 'custom',
      from: '2026-02-10T00:00:00',
      to: '2026-02-11T00:00:00',
    } as const
    expect(EdaComputeRequestSchema.parse(request)).toEqual(request)
    expect(EdaComputeRequestSchema.safeParse({ ...request, to: request.from }).success).toBe(false)
    expect(EdaComputeRequestSchema.safeParse({ ...request, from: '2026-02-10T00:00:00+07:00' }).success).toBe(false)
  })
})
