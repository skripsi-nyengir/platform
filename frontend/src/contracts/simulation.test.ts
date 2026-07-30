import { describe, expect, it } from 'vitest'
import { simulationMetricsResponse } from '../mocks/fixtures/simulation'
import { SimulationMetricsResponseSchema } from './simulation'

describe('SimulationMetricsResponseSchema', () => {
  it('accepts all three server research scopes and the operational event list', () => {
    const payload = simulationMetricsResponse('artifact-transformer-v3')

    expect(SimulationMetricsResponseSchema.parse(payload)).toEqual(payload)
  })

  it('rejects an operational count that disagrees with the server event list', () => {
    const payload = simulationMetricsResponse('artifact-transformer-v3')

    expect(SimulationMetricsResponseSchema.safeParse({
      ...payload,
      operational_event_count: payload.operational_event_count + 1,
    }).success).toBe(false)
  })

  it('accepts a continuous operational bucket breakdown', () => {
    const payload = {
      ...simulationMetricsResponse('artifact-transformer-v3'),
      bucket_hours: 24,
      operational_buckets: [
        {
          bucket_start: '2026-04-19T00:00:00',
          bucket_end: '2026-04-20T00:00:00',
          event_count: 2,
        },
        {
          bucket_start: '2026-04-20T00:00:00',
          bucket_end: '2026-04-21T00:00:00',
          event_count: 0,
        },
      ],
    }

    expect(SimulationMetricsResponseSchema.parse(payload)).toEqual(payload)
  })

  it('rejects non-positive bucket intervals', () => {
    const payload = {
      ...simulationMetricsResponse('artifact-transformer-v3'),
      bucket_hours: 0,
      operational_buckets: [],
    }

    expect(SimulationMetricsResponseSchema.safeParse(payload).success).toBe(false)
  })
})
