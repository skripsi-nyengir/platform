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

  it('keeps simulation out of the primary navigation', () => {
    expect(navigationItems.some((item) => item.path === '/simulation')).toBe(false)
  })

  it('exposes Slack settings in system navigation and at its authenticated route', async () => {
    expect(navigationItems).toContainEqual({
      path: '/settings/slack',
      label: 'Slack',
      group: 'system',
    })

    renderApp('/settings/slack')
    expect(await screen.findByRole('heading', { name: 'Slack' })).toBeVisible()
    expect(screen.getByRole('link', { name: 'Slack' })).toHaveAttribute('aria-current', 'page')
  })

  it('renders the B02 sensor detail route', async () => {
    renderApp('/sensors/b02f3872-ruang-produksi')
    expect(await screen.findByRole('heading', { name: 'Sensor Detail & History' })).toBeVisible()
    expect(screen.getByRole('combobox', { name: 'Range' })).toHaveValue('1h')
    expect(screen.queryByRole('textbox', { name: 'From' })).not.toBeInTheDocument()
    expect(screen.queryByRole('combobox', { name: 'Bucket' })).not.toBeInTheDocument()
  })
})
