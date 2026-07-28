import { describe, expect, it } from 'vitest'
import { modelRegistryResponse } from '../mocks/fixtures/modelRegistry'
import { ModelRegistryResponseSchema } from './modelRegistry'

describe('model registry contract', () => {
  it('accepts all reported models with family-specific architecture values', () => {
    const parsed = ModelRegistryResponseSchema.parse(modelRegistryResponse)

    expect(parsed.items.map((item) => item.id)).toEqual([
      'transformer_step5',
      'conv1d_step5',
      'lstm_step5',
    ])
    expect(parsed.items[1]?.architecture.channels).toEqual([16, 32])
  })

  it('rejects a model hash that is not 64 lowercase hexadecimal characters', () => {
    const response = structuredClone(modelRegistryResponse)
    response.items[0].model_sha256 = 'INVALID'

    expect(ModelRegistryResponseSchema.safeParse(response).success).toBe(false)
  })
})
