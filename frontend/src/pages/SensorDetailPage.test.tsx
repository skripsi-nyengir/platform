import { describe, expect, it } from 'vitest'
import { screen } from '@testing-library/react'
import { renderApp } from '../test/renderApp'

describe('SensorDetailPage', () => {
  it('renders B02 history with data-driven score provenance', async () => {
    renderApp('/sensors/b02f3872-ruang-produksi')
    expect(await screen.findByText(/sesuai provenance API/)).toBeVisible()
    expect(await screen.findByText('Simulasi preview')).toBeVisible()
  })
})
