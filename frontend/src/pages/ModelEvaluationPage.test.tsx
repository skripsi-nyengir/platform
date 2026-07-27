import { describe, expect, it } from 'vitest'
import { screen } from '@testing-library/react'
import { renderApp } from '../test/renderApp'

describe('ModelEvaluationPage', () => {
  it('renders the seven-family registry and pilot disclaimer', async () => {
    renderApp('/model-evaluation')
    expect(await screen.findByRole('heading', { name: 'Model registry' })).toBeVisible()
    expect(screen.getByText(/satu run/i)).toBeVisible()
  })
})
