import '@testing-library/jest-dom/vitest'
import { describe, expect, it } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderApp } from '../test/renderApp'

describe('SensorDetailPage', () => {
  it('restores custom live bounds and renders current Task 9 data', async () => {
    renderApp(
      '/sensors/b02f3872-ruang-produksi?range=custom&from=2026-07-31T06:00:00&to=2026-07-31T08:00:00',
    )
    expect(await screen.findByRole('combobox', { name: 'Range' })).toHaveValue('custom')
    expect(screen.getByRole('textbox', { name: 'From' })).toHaveValue('2026-07-31T06:00:00')
    expect(screen.getByRole('textbox', { name: 'To' })).toHaveValue('2026-07-31T08:00:00')
    expect(await screen.findByText('Latest score: 0.58')).toBeVisible()
    expect(screen.getByText('Severity: info')).toBeVisible()
    expect(screen.getByText('Live health: healthy')).toBeVisible()
    expect(await screen.findByText(/bounded telemetry records/)).toBeVisible()
  })

  it('supports manual acknowledge then resolve with episode context and history', async () => {
    const user = userEvent.setup()
    renderApp('/sensors/b02f3872-ruang-produksi?range=1h&__scenario=active-anomaly')

    expect(await screen.findByRole('heading', { name: 'Episode context' })).toBeVisible()
    expect(await screen.findByText('10 source readings before the episode')).toBeVisible()
    expect(screen.getByText('Detected')).toBeVisible()
    await user.click(screen.getByRole('button', { name: 'Acknowledge alert' }))
    await user.click(await screen.findByRole('button', { name: 'Resolve alert' }))
    expect(await screen.findByText('Resolved alert')).toBeVisible()
  })
})
