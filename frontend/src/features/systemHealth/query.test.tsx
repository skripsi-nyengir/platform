import { describe, expect, it } from 'vitest'
import { systemStatus } from '../../mocks/fixtures/systemHealth'

describe('system status fixture', () => {
  it('matches the seven canonical backend services in API order', () => {
    const names = systemStatus.services.map((service) => service.name)
    expect(names).toEqual([
      'api',
      'database',
      'live-subscriber',
      'telemetry-import',
      'preview-worker',
      'active-selection',
      'artifact-readiness',
    ])
  })
})
