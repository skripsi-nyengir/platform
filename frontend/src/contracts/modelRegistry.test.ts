import { describe, expect, it } from 'vitest'
import { modelRegistryResponse } from '../mocks/fixtures/modelRegistry'
import { ModelRegistryResponseSchema } from './modelRegistry'

describe('model registry contract', () => {
  it('accepts all reported models with family-specific architecture values', () => {
    const parsed = ModelRegistryResponseSchema.parse(modelRegistryResponse)

    expect(parsed.items.map((item) => item.id)).toEqual([
      'conv1d_step5',
      'gru_step5',
      'lstm_step5',
      'rnn_step5',
      'transformer_step5',
    ])
    expect(parsed.items[0]?.architecture.latent_channels).toBe(16)
    expect(parsed.items[4]?.architecture.encoder_layers).toBe(2)
    expect(parsed.items.every((item) => item.window_size === 10)).toBe(true)
  })

  it('rejects a model hash that is not 64 lowercase hexadecimal characters', () => {
    const response = structuredClone(modelRegistryResponse)
    response.items[0].model_sha256 = 'INVALID'

    expect(ModelRegistryResponseSchema.safeParse(response).success).toBe(false)
  })
})
