import '@testing-library/jest-dom/vitest'
import { describe, expect, it } from 'vitest'
import { screen, within } from '@testing-library/react'
import { renderApp } from '../test/renderApp'

describe('ModelEvaluationPage', () => {
  it('renders reported training facts separately from the Dandy pilot', async () => {
    renderApp('/model-evaluation?__scenario=active-anomaly')
    expect(await screen.findByRole('heading', { name: 'Model registry' })).toBeVisible()
    const registry = await screen.findByRole('region', {
      name: 'Model terdaftar (metrik dilaporkan dari training)',
    })

    expect(within(registry).getAllByRole('article')).toHaveLength(3)
    expect(within(registry).getByRole('heading', { name: 'Transformer Autoencoder' })).toBeVisible()
    expect(within(registry).getByRole('heading', { name: 'Conv1D Autoencoder' })).toBeVisible()
    expect(within(registry).getByRole('heading', { name: 'LSTM Autoencoder' })).toBeVisible()
    expect(within(registry).getByText(/d_model: 32 · n_heads: 4/)).toBeVisible()
    expect(within(registry).getAllByText('b02f3872_ruang_produksi_v3_march07')).toHaveLength(3)
    expect(within(registry).getAllByText('30 langkah · suhu, rh')).toHaveLength(3)
    expect(within(registry).getByTitle('1'.repeat(64))).toHaveTextContent('111111111111…11111111')
    expect(within(registry).getByText(/bukan hasil komputasi platform/i)).toBeVisible()
    expect(within(registry).queryByText(/stuck: gagal/i)).not.toBeInTheDocument()
    expect(screen.getByText(/Snapshot ini berasal dari satu run/i)).toBeVisible()
  })
})
