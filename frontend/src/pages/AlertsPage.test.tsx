import { describe, expect, it } from 'vitest'
import { screen } from '@testing-library/react'
import { renderApp } from '../test/renderApp'

describe('AlertsPage', () => {
  it('renders B02 episode and lifecycle semantics', async () => {
    renderApp('/alerts?__scenario=active-anomaly')
    expect(await screen.findByRole('heading', { name: 'Current alerts' })).toBeVisible()
    expect(screen.getByText(/lifecycle adalah UTC/)).toBeVisible()
  })
})
