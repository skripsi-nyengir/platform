import '@testing-library/jest-dom/vitest'
import { describe, expect, it } from 'vitest'
import { screen } from '@testing-library/react'
import { renderApp } from '../test/renderApp'

describe('OverviewPage', () => {
  it('renders the single public B02 sensor', async () => {
    renderApp('/')
    expect(await screen.findByRole('article', { name: 'Sensor B02' })).toBeVisible()
    expect(screen.queryByText(/talpha-1/i)).not.toBeInTheDocument()
  })
})
