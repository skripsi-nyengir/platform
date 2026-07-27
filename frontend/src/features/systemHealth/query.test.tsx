import { describe, expect, it } from 'vitest'
import { systemStatus } from '../../mocks/fixtures/systemHealth'

describe('system status fixture', () => {
  it('separates telemetry import, preview worker, and artifact readiness', () => {
    const names = systemStatus.services.map((service) => service.name)
    expect(names).toEqual(expect.arrayContaining([
      'Import telemetri nyata',
      'Preview worker',
      'Artifact asli',
    ]))
  })
})
