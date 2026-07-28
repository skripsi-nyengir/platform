import '@testing-library/jest-dom/vitest'
import { describe, expect, it } from 'vitest'
import { screen, within } from '@testing-library/react'
import { renderApp } from '../test/renderApp'

describe('ModelEvaluationPage', () => {
  it('renders training, offline, and Dandy evidence as separate sections', async () => {
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

    const offline = await screen.findByRole('region', {
      name: 'Evaluasi offline (test-set injected berlabel)',
    })
    expect(within(offline).getAllByRole('article')).toHaveLength(1)
    expect(within(offline).getByRole('heading', { name: 'LSTM' })).toBeVisible()
    expect(within(offline).getByText('Keluarga model: lstm')).toBeVisible()
    expect(within(offline).getByText('Window precision')).toBeVisible()
    expect(within(offline).getByText('46,15%')).toBeVisible()
    expect(within(offline).getByText('Window recall')).toBeVisible()
    expect(within(offline).getByText('83,81%')).toBeVisible()
    expect(within(offline).getByText('Window F1')).toBeVisible()
    expect(within(offline).getByText('59,53%')).toBeVisible()
    expect(within(offline).getByText('Event hit rate')).toBeVisible()
    expect(within(offline).getByText('92,86%')).toBeVisible()
    expect(within(offline).getByText('Event hit · coe')).toBeVisible()
    expect(within(offline).getByText('50,00%')).toBeVisible()
    expect(within(offline).getByText('Clean test FPR')).toBeVisible()
    expect(within(offline).getByText('1,38%')).toBeVisible()
    expect(within(offline).getByText('Composite Fc1')).toBeVisible()
    expect(within(offline).getByText('61,66%')).toBeVisible()
    expect(within(offline).getByText('Alert rate')).toBeVisible()
    expect(within(offline).getByText('4,63 /hari')).toBeVisible()
    expect(within(offline).getByText('0.0004298445419408381')).toBeVisible()
    expect(within(offline).getByText('clean_val_quantile · α=0.01 · strict_gt')).toBeVisible()
    expect(within(offline).getByText('105.564')).toBeVisible()
    expect(within(offline).getByText('28')).toBeVisible()
    expect(
      within(offline).getByTitle(
        'f26a67d378c4b5a90e64f7dc3844d2971cb414d1bf60926fefa188b13df99212',
      ),
    ).toHaveTextContent('f26a67d378c4…3df99212')
    expect(within(offline).getByText('b02f3872_ruang_produksi_v3_march07')).toBeVisible()
    expect(within(offline).getByText(/bukan inferensi live platform/i)).toBeVisible()
    expect(within(offline).queryByText(/Best val MSE/i)).not.toBeInTheDocument()
    expect(within(offline).queryByText(/stuck: gagal/i)).not.toBeInTheDocument()
    expect(screen.getByText(/Snapshot ini berasal dari satu run/i)).toBeVisible()
  })
})
