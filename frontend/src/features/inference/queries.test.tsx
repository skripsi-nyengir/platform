import { describe, expect, it } from 'vitest'
import { normalInferencePoints } from '../../mocks/fixtures/inference'

describe('inference fixture contract', () => {
  it('carries provenance on every score result', () => {
    expect(normalInferencePoints).not.toHaveLength(0)
    expect(normalInferencePoints.every((point) => point.score_provenance === 'simulated_preview')).toBe(true)
  })
})
