import { describe, expect, it } from 'vitest'
import { formatProvenance } from '../components/data/provenance'

describe('shared provenance presentation', () => {
  it('formats both supported provenance values without a default fallback', () => {
    expect(formatProvenance('simulated_preview')).toBe('Simulasi preview')
    expect(formatProvenance('artifact_backed')).toBe('Artifact asli')
  })
})
