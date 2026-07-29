import '@testing-library/jest-dom/vitest'
import { describe, expect, it } from 'vitest'
import { screen } from '@testing-library/react'
import { renderApp } from '../test/renderApp'
import { navigationItems } from './navigation'

describe('B02 routes', () => {
  it('uses the single public sensor route', () => {
    expect(navigationItems.find((item) => item.label === 'Sensor')?.path)
      .toBe('/sensors/b02f3872-ruang-produksi')
  })

  it('renders the B02 sensor detail route', async () => {
    renderApp('/sensors/b02f3872-ruang-produksi')
    expect(await screen.findByRole('heading', { name: 'Sensor Detail & History' })).toBeVisible()
    expect(screen.getByRole('textbox', { name: 'From' })).toHaveValue('2026-02-01T00:00:00')
    expect(screen.getByRole('textbox', { name: 'To' })).toHaveValue('2026-06-01T00:00:00')
    expect(screen.getByRole('combobox', { name: 'Bucket' })).toHaveValue('1d')
  })
})
