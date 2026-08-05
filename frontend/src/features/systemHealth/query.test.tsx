import { describe, expect, it } from 'vitest'
import { systemStatus } from '../../mocks/fixtures/systemHealth'

describe('system status fixture', () => {
  it('matches the five runtime health services in API order', () => {
    const names = systemStatus.services.map((service) => service.name)
    expect(names).toEqual([
      'api',
      'database',
      'live-subscriber',
      'preview-worker',
      'active-selection',
    ])
  })
})
