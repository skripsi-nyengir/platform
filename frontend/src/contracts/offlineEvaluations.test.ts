import { describe, expect, it } from 'vitest'
import { offlineEvaluationsResponse } from '../mocks/fixtures/offlineEvaluations'
import {
  OfflineEvaluationsResponseSchema,
  type OfflineEvaluationsResponse,
} from './offlineEvaluations'

describe('offline evaluations contract', () => {
  it('accepts all five trained model families and free-form event families', () => {
    const response: OfflineEvaluationsResponse = structuredClone(offlineEvaluationsResponse)
    response.items[0]!.metrics.event_hit_by_family.rare_family = 0.25

    const parsed = OfflineEvaluationsResponseSchema.parse(response)

    expect(parsed.items.map((item) => item.model_family)).toEqual([
      'conv1d',
      'gru',
      'lstm',
      'rnn',
      'transformer',
    ])
    expect(parsed.items[0]?.metrics.event_hit_by_family.rare_family).toBe(0.25)
  })

  it('rejects a non-numeric event-family hit rate', () => {
    const response = structuredClone(offlineEvaluationsResponse)
    const eventHitByFamily: Record<string, unknown> =
      response.items[0].metrics.event_hit_by_family
    eventHitByFamily.spike = 'invalid'

    expect(OfflineEvaluationsResponseSchema.safeParse(response).success).toBe(false)
  })
})
