import '@testing-library/jest-dom/vitest'
import { afterEach, describe, expect, it } from 'vitest'
import { screen, within } from '@testing-library/react'
import { queryClient } from '../app/queryClient'
import { renderApp } from '../test/renderApp'

afterEach(() => {
  queryClient.clear()
})

describe('OverviewPage', () => {
  it('renders the single public B02 sensor', async () => {
    renderApp('/')
    expect(await screen.findByRole('article', { name: 'Sensor B02' })).toBeVisible()
    expect(screen.queryByText(/talpha-1/i)).not.toBeInTheDocument()
  })

  it('shows the default live range, freshness, latest score, severity, and health', async () => {
    renderApp('/?__scenario=active-anomaly')

    expect(await screen.findByRole('combobox', { name: 'Range' })).toHaveValue('1h')
    const sensor = await screen.findByRole('article', { name: 'Sensor B02' })
    expect(within(sensor).getByRole('status', { name: 'Fresh telemetry' })).toBeVisible()
    expect(await within(sensor).findByText('1.31')).toBeVisible()
    expect(within(sensor).getByText('critical')).toBeVisible()
    expect(await screen.findByText('Live health: healthy')).toBeVisible()
    expect(await screen.findByRole('heading', { name: 'Episode context' })).toBeVisible()
    expect(screen.getByText('10 source readings before the episode')).toBeVisible()
    expect(screen.getByText('31 May 2026, 23:51:30')).toBeVisible()
    expect(screen.getByText('31 May 2026, 23:52:30')).toBeVisible()
  })
})
