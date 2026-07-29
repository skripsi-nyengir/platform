import '@testing-library/jest-dom/vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { renderApp } from '../test/renderApp'

describe('SimulationPage', () => {
  it('renders the model calibration cards and completed replay results', async () => {
    const user = userEvent.setup()
    renderApp('/simulation')

    expect(await screen.findByRole('heading', { name: 'Anomaly simulation' })).toBeVisible()
    expect(await screen.findByRole('heading', { name: 'LSTM-AE' })).toBeVisible()
    expect(screen.getByRole('heading', { name: 'Conv1D Autoencoder' })).toBeVisible()
    expect(screen.getByRole('heading', { name: 'Transformer Autoencoder' })).toBeVisible()
    expect(screen.getByText('0.0006799018211313575')).toBeVisible()
    expect(screen.getAllByText('global_mse')).toHaveLength(3)

    await user.click(screen.getByRole('button', { name: 'Run injected replay' }))

    expect(await screen.findByRole('heading', { name: 'Active model · LSTM-AE' })).toBeVisible()
    expect(screen.getByRole('heading', { name: 'Model comparison' })).toBeVisible()
    expect(screen.getAllByRole('img', { name: 'Temperature signal and reconstruction band' })).toHaveLength(4)
    expect(screen.getByRole('heading', { name: 'Active-model summary' })).toBeVisible()
  })
})
