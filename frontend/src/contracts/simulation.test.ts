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
})
