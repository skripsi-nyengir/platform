import '@testing-library/jest-dom/vitest'
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { queryClient } from '../app/queryClient'
import { modelRegistryResponse } from '../mocks/fixtures/modelRegistry'
import { offlineEvaluationsResponse } from '../mocks/fixtures/offlineEvaluations'
import { server } from '../mocks/node'
import { renderApp } from '../test/renderApp'

const { barChartPropsSpy } = vi.hoisted(() => ({ barChartPropsSpy: vi.fn() }))

vi.mock('@mui/x-charts/BarChart', () => ({
  BarChart: (props: Record<string, unknown>) => {
    barChartPropsSpy(props)
    return <div data-testid="offline-bar-chart" />
  },
}))

const modelNames = [
  'Conv1D Autoencoder',
  'GRU Autoencoder',
  'LSTM Autoencoder',
  'RNN Autoencoder',
  'Transformer Autoencoder',
] as const

beforeEach(() => {
  barChartPropsSpy.mockClear()
  queryClient.clear()
  queryClient.setDefaultOptions({ queries: { retry: false } })
})
afterEach(() => queryClient.setDefaultOptions({ queries: { retry: undefined } }))

describe('ModelEvaluationPage', () => {
  it('renders the registry as five core-fact cards and discloses separate technical provenance in a dialog', async () => {
    const user = userEvent.setup()
    renderApp('/model-evaluation')

    const registry = await screen.findByRole('region', {
      name: 'Model terdaftar (metrik dilaporkan dari training)',
    })
    expect(await within(registry).findAllByRole('article')).toHaveLength(5)
    for (const name of modelNames) {
      expect(within(registry).getByRole('heading', { name })).toBeVisible()
    }
    expect(within(registry).getByText('16 latent channels')).toBeVisible()
    expect(within(registry).queryByText('latent_channels: 16')).not.toBeInTheDocument()
    expect(within(registry).queryByText('b02f3872_ruang_produksi_v3_march07')).not.toBeInTheDocument()

    const trigger = within(registry).getByRole('button', {
      name: 'Detail teknis Conv1D Autoencoder',
    })
    await user.click(trigger)
    const dialog = screen.getByRole('dialog', { name: 'Detail teknis registry · Conv1D Autoencoder' })
    expect(within(dialog).getByText('b02f3872_ruang_produksi_v3_march07')).toBeVisible()
    expect(within(dialog).getByText('10 langkah')).toBeVisible()
    expect(within(dialog).getByText('suhu, rh')).toBeVisible()
    expect(within(dialog).getByText(modelRegistryResponse.items[0].model_sha256)).toBeVisible()
    expect(within(dialog).getByText('reported_model_registry')).toBeVisible()
    expect(within(dialog).getByText('latent_channels: 16')).toBeVisible()

    await user.click(within(dialog).getByRole('button', { name: 'Tutup' }))
    expect(trigger).toHaveFocus()
  })

  it('exposes fixed chart order, domain, series, description, and exact raw values without ranking claims', async () => {
    const user = userEvent.setup()
    renderApp('/model-evaluation')

    const chart = await screen.findByRole('img', {
      name: 'Perbandingan precision recall dan F1 lima model',
    })
    expect(chart).toHaveAccessibleDescription(/skala tetap 0–100% dari baseline nol/i)
    expect(barChartPropsSpy).toHaveBeenCalled()
    const chartProps = barChartPropsSpy.mock.lastCall?.[0] as {
      layout: string
      xAxis: Array<{ min: number; max: number }>
      yAxis: Array<{ data: string[]; width: 'auto' }>
      series: Array<{ label: string; color: string; data: number[] }>
    }
    expect(chartProps.layout).toBe('horizontal')
    expect(chartProps.xAxis[0]).toMatchObject({ min: 0, max: 100 })
    expect(chartProps.yAxis[0]?.data).toEqual([
      'Conv1D', 'GRU', 'LSTM', 'RNN', 'Transformer',
    ])
    expect(chartProps.yAxis[0]?.width).toBe('auto')
    expect(chartProps.series.map((series) => series.label)).toEqual([
      'Precision', 'Recall', 'F1',
    ])
    expect(chartProps.series.map((series) => series.color)).toEqual([
      '#2563EB', '#147D64', '#9A6700',
    ])
    expect(chartProps.series[0]?.data).toEqual([49, 44, 46.15384615384615, 47, 52])
    expect(screen.queryByText(/winner|pemenang|peringkat|terbaik/i)).not.toBeInTheDocument()

    const trigger = screen.getByRole('button', { name: 'Lihat data eksak' })
    await user.click(trigger)
    const table = screen.getByRole('table', { name: 'Data eksak precision recall dan F1' })
    const rows = within(table).getAllByRole('row')
    expect(rows).toHaveLength(6)
    expect(within(rows[1]!).getAllByRole('cell').map((cell) => cell.textContent)).toEqual([
      'Conv1D', '0.49', '0.81', '0.61',
    ])
    expect(within(rows[3]!).getByText('0.46153846153846156')).toBeVisible()

    await user.click(screen.getByRole('button', { name: 'Tutup' }))
    expect(trigger).toHaveFocus()
  })

  it('uses native pressed buttons, defaults to Conv1D, and updates neutral KPIs and dynamic event families from the selected model', async () => {
    const response = structuredClone(offlineEvaluationsResponse)
    response.items[1]!.metrics.event_hit_by_family = { rare_family: 0.25 }
    server.use(http.get('/api/offline-evaluations', () => HttpResponse.json(response)))
    const user = userEvent.setup()
    renderApp('/model-evaluation')

    const conv1d = await screen.findByRole('button', { name: 'Conv1D', pressed: true })
    expect(conv1d).toBeVisible()
    expect(screen.getByText('63,00%')).toBeVisible()

    const gru = screen.getByRole('button', { name: 'GRU', pressed: false })
    gru.focus()
    await user.keyboard('{Enter}')
    expect(gru).toHaveAttribute('aria-pressed', 'true')
    expect(conv1d).toHaveAttribute('aria-pressed', 'false')
    expect(screen.getByText('60,00%')).toBeVisible()
    expect(screen.getByRole('heading', { name: 'Event-family hit rate · GRU' })).toBeVisible()
    expect(screen.getByText('rare family')).toBeVisible()
    expect(screen.getByText('25,00%')).toBeVisible()
    expect(screen.getByRole('progressbar', { name: 'Event hit rare family' })).toHaveAttribute('aria-valuenow', '25')
    expect(screen.queryByText(/\d+\s*\/\s*\d+/)).not.toBeInTheDocument()
  })

  it('keeps thresholds, counts, SHA, forward validation, and offline provenance collapsed by default', async () => {
    const user = userEvent.setup()
    renderApp('/model-evaluation')

    const summary = await screen.findByRole('button', { name: 'Detail teknis evaluasi Conv1D' })
    expect(screen.queryByText(offlineEvaluationsResponse.items[0].model_sha256)).not.toBeVisible()
    await user.click(summary)
    expect(screen.getByText(offlineEvaluationsResponse.items[0].model_sha256)).toBeVisible()
    expect(screen.getByText('105.338')).toBeVisible()
    expect(screen.getByText(/clean_val_quantile · α=0.01 · strict_gt/)).toBeVisible()
    expect(screen.getByText(/reverse-engineered from state-dict/)).toBeVisible()
    expect(screen.getByText(/Lulus · recon max abs diff/)).toBeVisible()
  })

  it('keeps offline evaluation visible when the registry endpoint fails', async () => {
    server.use(http.get('/api/model-registry', () => HttpResponse.json({}, { status: 503 })))
    renderApp('/model-evaluation')

    const registry = await screen.findByRole('region', {
      name: 'Model terdaftar (metrik dilaporkan dari training)',
    })
    expect(await within(registry).findByRole('alert')).toHaveTextContent('HTTP 503')
    expect(await screen.findByRole('img', { name: 'Perbandingan precision recall dan F1 lima model' })).toBeVisible()
    expect(screen.getByRole('button', { name: 'Conv1D', pressed: true })).toBeVisible()
  })

  it('keeps the registry visible when the offline evaluation endpoint fails', async () => {
    server.use(http.get('/api/offline-evaluations', () => HttpResponse.json({}, { status: 503 })))
    renderApp('/model-evaluation')

    const offline = await screen.findByRole('region', {
      name: 'Evaluasi offline (test-set injected berlabel)',
    })
    expect(await within(offline).findByRole('alert')).toHaveTextContent('HTTP 503')
    const registry = await screen.findByRole('region', {
      name: 'Model terdaftar (metrik dilaporkan dari training)',
    })
    expect(await within(registry).findAllByRole('article')).toHaveLength(5)
    expect(within(registry).getByRole('heading', { name: 'Transformer Autoencoder' })).toBeVisible()
  })
})
