import '@testing-library/jest-dom/vitest'
import { describe, expect, it } from 'vitest'
import { screen, within } from '@testing-library/react'
import { renderApp } from '../test/renderApp'

const modelNames = [
  'Conv1D Autoencoder',
  'GRU Autoencoder',
  'LSTM Autoencoder',
  'RNN Autoencoder',
  'Transformer Autoencoder',
] as const

const modelFamilies = ['CONV1D', 'GRU', 'LSTM', 'RNN', 'TRANSFORMER'] as const

describe('ModelEvaluationPage', () => {
  it('renders five trained models in exactly two honest evidence sections', async () => {
    renderApp('/model-evaluation?__scenario=active-anomaly')

    expect(await screen.findByRole('heading', { name: 'Model Evaluation' })).toBeVisible()
    expect(
      screen.getByText(/metrik training yang dilaporkan dan evaluasi offline berlabel/i),
    ).toHaveTextContent('Conv1D, GRU, LSTM, RNN, dan Transformer')

    const registry = await screen.findByRole('region', {
      name: 'Model terdaftar (metrik dilaporkan dari training)',
    })
    const offline = await screen.findByRole('region', {
      name: 'Evaluasi offline (test-set injected berlabel)',
    })

    expect(screen.getAllByRole('region')).toHaveLength(2)
    expect(within(registry).getAllByRole('article')).toHaveLength(5)
    expect(within(offline).getAllByRole('article')).toHaveLength(5)

    for (const name of modelNames) {
      expect(within(registry).getByRole('heading', { name })).toBeVisible()
    }
    for (const family of modelFamilies) {
      expect(within(offline).getByRole('heading', { name: family })).toBeVisible()
    }

    expect(within(registry).getAllByText('b02f3872_ruang_produksi_v3_march07')).toHaveLength(5)
    expect(within(registry).getAllByText('10 langkah · suhu, rh')).toHaveLength(5)
    expect(within(registry).getByText(/latent_channels: 16/)).toBeVisible()
    expect(within(registry).getAllByText(/hidden_size: 32 · latent_size: 8/)).toHaveLength(3)
    expect(within(registry).getByText(/encoder_layers: 2 · decoder_layers: 2/)).toBeVisible()
    expect(
      within(registry).getByTitle(
        '85c901e8fed463207a44151adc14772d3660384ae88daf9fcc53431e6acc39c9',
      ),
    ).toHaveTextContent('85c901e8fed4…6acc39c9')

    const lstmHeading = within(offline).getByRole('heading', { name: 'LSTM' })
    const lstmArticle = lstmHeading.closest('article')
    expect(lstmArticle).not.toBeNull()
    const lstm = within(lstmArticle as HTMLElement)
    expect(lstm.getByText('Keluarga model: lstm')).toBeVisible()
    expect(lstm.getByText('46,15%')).toBeVisible()
    expect(lstm.getByText('83,81%')).toBeVisible()
    expect(lstm.getByText('59,53%')).toBeVisible()
    expect(lstm.getByText('92,86%')).toBeVisible()
    expect(lstm.getByText('50,00%')).toBeVisible()
    expect(lstm.getByText('1,38%')).toBeVisible()
    expect(lstm.getByText('61,66%')).toBeVisible()
    expect(lstm.getByText('4,63 /hari')).toBeVisible()
    expect(lstm.getByText('0.0004298445419408381')).toBeVisible()
    expect(lstm.getByText('clean_val_quantile · α=0.01 · strict_gt')).toBeVisible()
    expect(lstm.getByText('105.564')).toBeVisible()
    expect(lstm.getByText('28')).toBeVisible()
    expect(
      lstm.getByTitle(
        'f26a67d378c4b5a90e64f7dc3844d2971cb414d1bf60926fefa188b13df99212',
      ),
    ).toHaveTextContent('f26a67d378c4…3df99212')
    expect(lstm.getByText('b02f3872_ruang_produksi_v3_march07')).toBeVisible()
  })
})
