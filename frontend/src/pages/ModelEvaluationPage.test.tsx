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
    expect(
      within(registry).queryByText('b02f3872_ruang_produksi_v3_march07'),
    ).not.toBeInTheDocument()

    const trigger = within(registry).getByRole('button', {
      name: 'Detail teknis Conv1D Autoencoder',
    })
    await user.click(trigger)
    const dialog = screen.getByRole('dialog', {
      name: 'Detail teknis registry · Conv1D Autoencoder',
    })
    expect(within(dialog).getByText('b02f3872_ruang_produksi_v3_march07')).toBeVisible()
    expect(within(dialog).getByText('10 langkah')).toBeVisible()
    expect(within(dialog).getByText('suhu, rh')).toBeVisible()
    expect(within(dialog).getByText(modelRegistryResponse.items[0].model_sha256)).toBeVisible()
    expect(within(dialog).getByText('reported_model_registry')).toBeVisible()
    expect(within(dialog).getByText('latent_channels: 16')).toBeVisible()

    await user.click(within(dialog).getByRole('button', { name: 'Tutup' }))
    expect(trigger).toHaveFocus()
  })

  it('uses the Step 7 non-overlapping-bin metrics for the chart and exact table', async () => {
    const user = userEvent.setup()
    renderApp('/model-evaluation')

    const chart = await screen.findByRole('img', {
      name: 'Perbandingan precision recall dan F1 lima model pada bin evaluasi',
    })
    expect(chart).toHaveAccessibleDescription(/scope utama output Step 7/i)
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
      'Conv1D',
      'GRU',
      'LSTM',
      'RNN',
      'Transformer',
    ])
    expect(chartProps.yAxis[0]?.width).toBe('auto')
    expect(chartProps.series.map((series) => series.label)).toEqual([
      'Precision',
      'Recall',
      'F1',
    ])
    expect(chartProps.series.map((series) => series.color)).toEqual([
      '#2563EB',
      '#147D64',
      '#9A6700',
    ])
    expect(chartProps.series[0]?.data).toEqual([
      82.8169014084507,
      Number('83.65122615803815'),
      87.88927335640139,
      85,
      Number('81.14143920595533'),
    ])
    expect(chartProps.series[1]?.data).toEqual([
      72.5925925925926,
      75.80246913580247,
      62.71604938271606,
      71.35802469135803,
      80.74074074074075,
    ])
    expect(chartProps.series[2]?.data).toEqual([
      77.36842105263158,
      79.53367875647669,
      73.19884726224784,
      77.58389261744966,
      80.94059405940595,
    ])
    expect(screen.queryByText(/winner|pemenang|peringkat|terbaik/i)).not.toBeInTheDocument()

    const trigger = screen.getByRole('button', { name: 'Lihat data eksak' })
    await user.click(trigger)
    const table = screen.getByRole('table', {
      name: 'Data eksak precision recall F1 dan confusion matrix',
    })
    const rows = within(table).getAllByRole('row')
    expect(rows).toHaveLength(6)
    expect(
      within(rows[1]!)
        .getAllByRole('cell')
        .map((cell) => cell.textContent),
    ).toEqual([
      'Conv1D',
      '0.828169014084507',
      '0.725925925925926',
      '0.7736842105263158',
      '1605',
      '61',
      '111',
      '294',
    ])
    expect(within(rows[3]!).getByText('0.7319884726224783')).toBeVisible()

    await user.click(screen.getByRole('button', { name: 'Tutup' }))
    expect(trigger).toHaveFocus()
  })

  it('defaults to Conv1D and updates the notebook-backed KPIs and all three scopes', async () => {
    const user = userEvent.setup()
    renderApp('/model-evaluation')

    const conv1d = await screen.findByRole('button', { name: 'Conv1D', pressed: true })
    expect(conv1d).toBeVisible()
    const conv1dSummary = screen.getByRole('region', { name: 'Ringkasan Step 7 Conv1D' })
    expect(within(conv1dSummary).getByText('0.0003201981883103135')).toBeVisible()
    expect(within(conv1dSummary).getByText('79,33%')).toBeVisible()
    expect(
      screen.getByRole('heading', { name: 'Tiga scope evaluasi · Conv1D' }),
    ).toBeVisible()

    const scopeTable = screen.getByRole('table', { name: 'Metrik tiga scope Conv1D' })
    expect(within(scopeTable).getByText('105.408')).toBeVisible()
    expect(within(scopeTable).getByText('2.071')).toBeVisible()
    expect(within(scopeTable).getByText('77,37%')).toBeVisible()

    const gru = screen.getByRole('button', { name: 'GRU', pressed: false })
    gru.focus()
    await user.keyboard('{Enter}')
    expect(gru).toHaveAttribute('aria-pressed', 'true')
    expect(conv1d).toHaveAttribute('aria-pressed', 'false')
    const gruSummary = screen.getByRole('region', { name: 'Ringkasan Step 7 GRU' })
    expect(within(gruSummary).getByText('0.0005618056084495022')).toBeVisible()
    expect(
      screen.getByRole('heading', { name: 'Tiga scope evaluasi · GRU' }),
    ).toBeVisible()
    expect(screen.getByRole('table', { name: 'Metrik tiga scope GRU' })).toBeVisible()
  })

  it('keeps notebook hashes and artifact conflicts collapsed, then discloses them', async () => {
    const user = userEvent.setup()
    renderApp('/model-evaluation')

    const summary = await screen.findByRole('button', {
      name: 'Detail teknis evaluasi Conv1D',
    })
    expect(
      screen.queryByText(offlineEvaluationsResponse.items[0]!.model_sha256),
    ).not.toBeVisible()
    await user.click(summary)
    expect(
      screen.getByText(offlineEvaluationsResponse.items[0]!.model_sha256),
    ).toBeVisible()
    expect(screen.getByText('val_injected')).toBeVisible()
    expect(screen.getByText('Tidak digunakan')).toBeVisible()
    expect(
      screen.getByText(
        'conv1d_autoencoder_b02f3872_ruang_produksi_v3_march07_step7.ipynb',
      ),
    ).toBeVisible()

    await user.click(screen.getByRole('button', { name: 'Transformer', pressed: false }))
    const transformerSummary = screen.getByRole('button', {
      name: 'Detail teknis evaluasi Transformer',
    })
    await user.click(transformerSummary)
    expect(
      screen.getByText('Konflik dikarantina · transformer_step7_artifacts.zip'),
    ).toBeVisible()
    expect(screen.getByText(/stale selected_operating_threshold\.json/i)).toBeVisible()
  })

  it('keeps Step 7 evaluation visible when the registry endpoint fails', async () => {
    server.use(
      http.get('/api/model-registry', () => HttpResponse.json({}, { status: 503 })),
    )
    renderApp('/model-evaluation')

    const registry = await screen.findByRole('region', {
      name: 'Model terdaftar (metrik dilaporkan dari training)',
    })
    expect(await within(registry).findByRole('alert')).toHaveTextContent('HTTP 503')
    expect(
      await screen.findByRole('img', {
        name: 'Perbandingan precision recall dan F1 lima model pada bin evaluasi',
      }),
    ).toBeVisible()
    expect(screen.getByRole('button', { name: 'Conv1D', pressed: true })).toBeVisible()
  })

  it('keeps the registry visible when the Step 7 endpoint fails', async () => {
    server.use(
      http.get('/api/offline-evaluations', () =>
        HttpResponse.json({}, { status: 503 }),
      ),
    )
    renderApp('/model-evaluation')

    const offline = await screen.findByRole('region', {
      name: 'Evaluasi Step 7 (validation-injected berlabel)',
    })
    expect(await within(offline).findByRole('alert')).toHaveTextContent('HTTP 503')
    const registry = await screen.findByRole('region', {
      name: 'Model terdaftar (metrik dilaporkan dari training)',
    })
    expect(await within(registry).findAllByRole('article')).toHaveLength(5)
    expect(
      within(registry).getByRole('heading', { name: 'Transformer Autoencoder' }),
    ).toBeVisible()
  })
})
