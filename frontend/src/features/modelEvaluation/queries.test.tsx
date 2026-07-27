import { describe, expect, it } from 'vitest'
import { previewModelFamilies } from '../../mocks/fixtures/preview'

describe('model registry fixture', () => {
  it('contains seven selectable B02 preview families', () => {
    expect(previewModelFamilies).toHaveLength(7)
    expect(previewModelFamilies.every((family) => family.versions[0]?.selectable)).toBe(true)
  })
})
