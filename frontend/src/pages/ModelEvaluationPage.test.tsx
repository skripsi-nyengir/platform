import { CssBaseline } from '@mui/material'
import { getContrastRatio, ThemeProvider } from '@mui/material/styles'
import { lineClasses, type LineChartProps } from '@mui/x-charts/LineChart'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { HttpResponse, http } from 'msw'
import type { ReactNode } from 'react'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type {
  ModelEvaluationDetail,
  ModelEvaluationSummary,
} from '../contracts/modelEvaluation'
import { LabeledMetricsPanels } from '../features/modelEvaluation/LabeledMetricsPanels'
import { MetricsPanel } from '../features/modelEvaluation/MetricsPanel'
import {
  modelEvaluationDetails,
  modelEvaluationSummaries,
} from '../mocks/fixtures/modelEvaluations'
import { server } from '../mocks/node'
import {
  createQueryTestHarness,
  type QueryTestHarness,
} from '../test/queryTestUtils'
import { theme } from '../theme/theme'
import { ModelEvaluationPage } from './ModelEvaluationPage'

const lineChartSpy = vi.hoisted(() => vi.fn())

vi.mock('@mui/x-charts/LineChart', async (importOriginal) => {
  const original = await importOriginal<typeof import('@mui/x-charts/LineChart')>()
  return {
    ...original,
    LineChart: (props: LineChartProps) => {
      lineChartSpy(props)
      return <div id={props.id} />
    },
  }
})

const origin = window.location.origin

const unlabeledSummary = {
  version: 'model-unlabeled',
  created_at: '2026-07-19T09:00:00Z',
  evaluation_period: '2026-07-18 to 2026-07-19',
  has_labeled_ground_truth: false,
  available_metrics: ['mean_score'],
  summary: 'Unlabeled score summary',
} satisfies ModelEvaluationSummary

const unlabeledArtifact = {
  request_id: 'req_model_unlabeled',
  version: unlabeledSummary.version,
  created_at: unlabeledSummary.created_at,
  evaluation_period: unlabeledSummary.evaluation_period,
  model_hash: null,
  preprocessing_hash: null,
  threshold_hash: null,
  has_labeled_ground_truth: false,
  available_metrics: unlabeledSummary.available_metrics,
  metrics: { mean_score: 0.42 },
  notes: null,
} satisfies ModelEvaluationDetail

let harness: QueryTestHarness

function LocationProbe() {
  const location = useLocation()
  return <output aria-label="Current location">{`${location.pathname}${location.search}`}</output>
}

function Providers({ children, route }: { children: ReactNode; route: string }) {
  const QueryProvider = harness.wrapper
  return (
    <QueryProvider>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <MemoryRouter initialEntries={[route]}>
          {children}
          <LocationProbe />
        </MemoryRouter>
      </ThemeProvider>
    </QueryProvider>
  )
}

function renderPage(route = '/model-evaluation') {
  return render(
    <Providers route={route}>
      <ModelEvaluationPage />
    </Providers>,
  )
}

function listing(items: readonly ModelEvaluationSummary[]) {
  return {
    request_id: 'req_model_evaluations_test',
    items: structuredClone(items),
    page: 1,
    page_size: 25,
    total: items.length,
  }
}

function problem(requestId: string, instance: string) {
  return {
    type: `https://example.invalid/problems/${requestId}`,
    title: 'Evaluation request failed',
    status: 503,
    detail: 'The evaluation artifact service is temporarily unavailable',
    instance,
    request_id: requestId,
  }
}

beforeEach(() => {
  harness = createQueryTestHarness()
  lineChartSpy.mockClear()
})

afterEach(() => {
  harness.restore()
  vi.restoreAllMocks()
})

describe('ModelEvaluationPage', () => {
  it('keeps the page identity visible while the artifact list loads', async () => {
    let release: () => void = () => undefined
    const gate = new Promise<void>((resolve) => {
      release = resolve
    })
    server.use(
      http.get(`${origin}/api/model-evaluations`, async () => {
        await gate
        return HttpResponse.json(listing(modelEvaluationSummaries))
      }),
    )

    renderPage()

    expect(screen.getByRole('heading', { level: 1, name: 'Model Evaluation' })).toBeVisible()
    expect(screen.getByRole('status', { name: 'Loading evaluation artifacts' })).toBeVisible()
    release()
    expect(await screen.findByRole('combobox', { name: 'Model version' })).toBeVisible()
  })

  it('shows a retryable list error with its request ID', async () => {
    server.use(
      http.get(`${origin}/api/model-evaluations`, () =>
        HttpResponse.json(problem('req_model_list_error', '/api/model-evaluations'), {
          status: 503,
        }),
      ),
    )

    renderPage()

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('req_model_list_error')
    expect(within(alert).getByRole('button', { name: 'Retry' })).toBeEnabled()
    expect(screen.getByRole('heading', { level: 1, name: 'Model Evaluation' })).toBeVisible()
  })

  it('shows an explicit empty artifact state without a quality verdict', async () => {
    server.use(
      http.get(`${origin}/api/model-evaluations`, () => HttpResponse.json(listing([]))),
    )

    renderPage()

    expect(await screen.findByText('No evaluation artifact exists')).toBeVisible()
    expect(screen.getByText('Live scores do not establish model quality.')).toBeVisible()
    expect(screen.queryByRole('heading', { level: 2, name: 'Artifact metrics' })).not.toBeInTheDocument()
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
  })

  it.each([
    ['restores', '/model-evaluation?model_version=model-v1', 'model-v1'],
    ['persists a default for', '/model-evaluation', 'model-v2'],
    ['normalizes', '/model-evaluation?model_version=missing', 'model-v2'],
  ])('%s the selected model_version', async (_label, route, expectedVersion) => {
    renderPage(route)

    const select = await screen.findByRole('combobox', { name: 'Model version' })
    await waitFor(() => expect(select).toHaveValue(expectedVersion))
    await waitFor(() =>
      expect(screen.getByLabelText('Current location')).toHaveTextContent(
        `model_version=${expectedVersion}`,
      ),
    )
    const metadata = await screen.findByRole('region', {
      name: 'Artifact identity and metadata',
    })
    expect(within(metadata).getByText('Model hash:')).toHaveProperty('tagName', 'DT')
    expect(within(metadata).getByText(`sha256:${expectedVersion}`)).toHaveProperty(
      'tagName',
      'DD',
    )
  })

  it('updates the URL and detail artifact when the version changes', async () => {
    renderPage('/model-evaluation?model_version=model-v2')
    const select = await screen.findByRole('combobox', { name: 'Model version' })
    const initialMetadata = await screen.findByRole('region', {
      name: 'Artifact identity and metadata',
    })
    expect(within(initialMetadata).getByText('sha256:model-v2')).toBeVisible()

    await userEvent.selectOptions(select, 'model-v1')

    await waitFor(() => expect(select).toHaveValue('model-v1'))
    await waitFor(() =>
      expect(screen.getByLabelText('Current location')).toHaveTextContent('model_version=model-v1'),
    )
    expect(await screen.findByText('sha256:model-v1')).toBeVisible()
    const updatedMetadata = screen.getByRole('region', {
      name: 'Artifact identity and metadata',
    })
    expect(within(updatedMetadata).getByText('Model hash:')).toHaveProperty('tagName', 'DT')
    expect(within(updatedMetadata).getByText('sha256:model-v1')).toHaveProperty('tagName', 'DD')
  })

  it('shows evaluation scope, supplied hashes, declared metrics, and all matching labeled panels', async () => {
    renderPage('/model-evaluation?model_version=model-v2')

    const metadata = await screen.findByRole('region', {
      name: 'Artifact identity and metadata',
    })
    expect(within(metadata).getByText('Selected version:')).toHaveProperty('tagName', 'DT')
    expect(within(metadata).getByText('model-v2')).toHaveProperty('tagName', 'DD')
    expect(within(metadata).getByText('Evaluation period:')).toHaveProperty('tagName', 'DT')
    expect(within(metadata).getByText('2026-07-12 to 2026-07-18')).toHaveProperty(
      'tagName',
      'DD',
    )
    expect(within(metadata).getByText('Model hash:')).toHaveProperty('tagName', 'DT')
    expect(within(metadata).getByText('sha256:model-v2')).toHaveProperty('tagName', 'DD')
    expect(within(metadata).getByText('Preprocessing hash:')).toHaveProperty('tagName', 'DT')
    expect(within(metadata).getByText('sha256:preprocessing-v1')).toHaveProperty(
      'tagName',
      'DD',
    )
    expect(within(metadata).getByText('Threshold hash:')).toHaveProperty('tagName', 'DT')
    expect(within(metadata).getByText('sha256:threshold-v1')).toHaveProperty('tagName', 'DD')
    const metrics = screen.getByRole('region', { name: 'Artifact metrics' })
    const scalarMetrics = within(metrics).getByRole('list', { name: 'Scalar metrics' })
    expect(within(scalarMetrics).getAllByRole('listitem')).toHaveLength(2)
    expect(within(metrics).getByText('accuracy: 0.96')).toBeVisible()
    expect(within(metrics).getByText('f1: 0.91')).toBeVisible()
    expect(within(metrics).queryByText(/confusion_matrix:/)).not.toBeInTheDocument()
    expect(within(metrics).queryByText(/precision_recall:/)).not.toBeInTheDocument()
    const charts = screen.getByRole('group', { name: 'Labeled evaluation charts' })
    const confusionPanel = within(charts).getByRole('article', { name: 'Confusion matrix' })
    expect(
      within(confusionPanel).getByRole('heading', { level: 3, name: 'Confusion matrix' }),
    ).toBeVisible()
    expect(within(confusionPanel).getByRole('table', { name: 'Confusion matrix' })).toBeVisible()
    const rocPanel = within(charts).getByRole('article', { name: 'ROC curve' })
    expect(within(rocPanel).getByRole('heading', { level: 3, name: 'ROC curve' })).toBeVisible()
    expect(within(rocPanel).getByRole('img', { name: 'ROC curve' })).toHaveAttribute(
      'aria-description',
      'ROC curve with AUC 0.97.',
    )
    expect(within(rocPanel).getByText('AUC: 0.97')).toBeVisible()
    const precisionRecallPanel = within(charts).getByRole('article', {
      name: 'Precision recall curve',
    })
    expect(
      within(precisionRecallPanel).getByRole('heading', {
        level: 3,
        name: 'Precision recall curve',
      }),
    ).toBeVisible()
    expect(
      within(precisionRecallPanel).getByRole('img', { name: 'Precision-recall curve' }),
    ).toHaveAttribute(
      'aria-description',
      'Precision-recall curve with average precision 0.93.',
    )
    expect(within(precisionRecallPanel).getByText('Average precision: 0.93')).toBeVisible()
    expect(screen.getByRole('button', { name: 'Lihat data Confusion matrix' })).toBeVisible()
    expect(screen.getByRole('button', { name: 'Lihat data ROC curve' })).toBeVisible()
    expect(
      screen.getByRole('button', { name: 'Lihat data Precision recall curve' }),
    ).toBeVisible()
  })

  it('renders an unlabeled scalar artifact without absent hashes or classification panels', async () => {
    server.use(
      http.get(`${origin}/api/model-evaluations`, () =>
        HttpResponse.json(listing([unlabeledSummary])),
      ),
      http.get(`${origin}/api/model-evaluations/:version`, () =>
        HttpResponse.json(structuredClone(unlabeledArtifact)),
      ),
    )

    renderPage('/model-evaluation?model_version=model-unlabeled')

    expect(await screen.findByText('mean_score: 0.42')).toBeVisible()
    const metadata = screen.getByRole('region', { name: 'Artifact identity and metadata' })
    expect(within(metadata).queryByText('Model hash:')).not.toBeInTheDocument()
    expect(within(metadata).queryByText('Preprocessing hash:')).not.toBeInTheDocument()
    expect(within(metadata).queryByText('Threshold hash:')).not.toBeInTheDocument()
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
  })

  it('keeps the selector visible when the selected detail fails', async () => {
    server.use(
      http.get(`${origin}/api/model-evaluations/:version`, ({ params }) =>
        HttpResponse.json(
          problem('req_model_detail_error', `/api/model-evaluations/${String(params.version)}`),
          { status: 503 },
        ),
      ),
    )

    renderPage('/model-evaluation?model_version=model-v1')

    expect(await screen.findByRole('combobox', { name: 'Model version' })).toHaveValue('model-v1')
    expect(await screen.findByRole('alert')).toHaveTextContent('req_model_detail_error')
  })
})

describe('model evaluation panels', () => {
  it('renders only scalar metrics that are both declared and present', () => {
    render(
      <ThemeProvider theme={theme}>
        <MetricsPanel
          availableMetrics={['accuracy', 'roc', 'missing_scalar']}
          metrics={{ accuracy: 0.96, internal_metric: 123 }}
        />
      </ThemeProvider>,
    )

    const metrics = screen.getByRole('region', { name: 'Artifact metrics' })
    expect(within(metrics).getByText('accuracy: 0.96')).toBeVisible()
    expect(within(metrics).queryByText(/internal_metric/)).not.toBeInTheDocument()
    expect(within(metrics).queryByText(/roc:/)).not.toBeInTheDocument()
    expect(within(metrics).queryByText(/missing_scalar:/)).not.toBeInTheDocument()
  })

  it('renders a labeled matrix and mapped, non-animated 0–1 evaluation curves', () => {
    const complete = structuredClone(modelEvaluationDetails['model-v2'])

    render(
      <ThemeProvider theme={theme}>
        <LabeledMetricsPanels artifact={complete} />
      </ThemeProvider>,
    )

    const matrix = screen.getByRole('table', { name: 'Confusion matrix' })
    expect(within(matrix).getByRole('columnheader', { name: 'Actual' })).toBeVisible()
    expect(within(matrix).getByRole('columnheader', { name: 'Predicted' })).toBeVisible()
    expect(within(matrix).getByRole('columnheader', { name: 'normal' })).toBeVisible()
    expect(within(matrix).getByRole('columnheader', { name: 'anomaly' })).toBeVisible()
    expect(within(matrix).getByRole('rowheader', { name: 'normal' })).toBeVisible()
    expect(within(matrix).getByRole('rowheader', { name: 'anomaly' })).toBeVisible()
    const maximumCountCell = within(matrix).getByRole('cell', {
      name: 'Actual normal, predicted normal: 92',
    })
    expect(maximumCountCell).toBeVisible()
    const maximumCountStyle = window.getComputedStyle(maximumCountCell)
    expect(
      getContrastRatio(maximumCountStyle.backgroundColor, maximumCountStyle.color),
    ).toBeGreaterThanOrEqual(4.5)
    expect(
      within(matrix).getByRole('cell', {
        name: 'Actual anomaly, predicted anomaly: 13',
      }),
    ).toBeVisible()

    const charts = lineChartSpy.mock.calls.map(([props]) => props as LineChartProps)
    const roc = charts.find((props) => props.id === 'roc-curve-chart')
    expect(roc).not.toHaveProperty('role')
    expect(roc).not.toHaveProperty('aria-label')
     expect(roc).toMatchObject({
       title: 'ROC curve',
       desc: 'ROC curve with AUC 0.97.',
       disableKeyboardNavigation: true,
       height: 320,
      hideLegend: true,
      skipAnimation: true,
      xAxis: [
        {
          id: 'roc-x-axis',
          data: [0, 0.08, 1],
          label: 'False positive rate',
          scaleType: 'linear',
          min: 0,
          max: 1,
        },
      ],
      yAxis: [
        {
          id: 'roc-y-axis',
          label: 'True positive rate',
          scaleType: 'linear',
          min: 0,
          max: 1,
        },
      ],
     series: [
        {
          id: 'roc-series',
          data: [0, 0.9, 1],
          curve: 'linear',
          showMark: false,
          xAxisId: 'roc-x-axis',
          yAxisId: 'roc-y-axis',
        },
        {
          id: 'roc-reference-series',
          data: [0, 0.08, 1],
          curve: 'linear',
          label: 'Reference diagonal',
          showMark: false,
          xAxisId: 'roc-x-axis',
          yAxisId: 'roc-y-axis',
        },
       ],
     })
    expect(roc?.sx).toEqual({
      [`& .${lineClasses.line}[data-series="roc-reference-series"]`]: {
        strokeDasharray: '5 5',
      },
    })

    const precisionRecall = charts.find((props) => props.id === 'precision-recall-curve-chart')
    expect(precisionRecall).not.toHaveProperty('role')
    expect(precisionRecall).not.toHaveProperty('aria-label')
     expect(precisionRecall).toMatchObject({
       title: 'Precision-recall curve',
       desc: 'Precision-recall curve with average precision 0.93.',
       disableKeyboardNavigation: true,
       height: 320,
      hideLegend: true,
      skipAnimation: true,
      xAxis: [
        {
          id: 'precision-recall-x-axis',
          data: [0, 0.9, 1],
          label: 'Recall',
          scaleType: 'linear',
          min: 0,
          max: 1,
        },
      ],
      yAxis: [
        {
          id: 'precision-recall-y-axis',
          label: 'Precision',
          scaleType: 'linear',
          min: 0,
          max: 1,
        },
      ],
      series: [
        {
          id: 'precision-recall-series',
          data: [1, 0.88, 0.5],
          curve: 'linear',
          showMark: false,
          xAxisId: 'precision-recall-x-axis',
          yAxisId: 'precision-recall-y-axis',
        },
      ],
    })
  })

  it('opens and closes bounded data dialogs for every labeled chart', async () => {
    const user = userEvent.setup()
    const complete = structuredClone(modelEvaluationDetails['model-v2'])

    render(
      <ThemeProvider theme={theme}>
        <LabeledMetricsPanels artifact={complete} />
      </ThemeProvider>,
    )

    const confusionTrigger = screen.getByRole('button', { name: 'Lihat data Confusion matrix' })
    await user.click(confusionTrigger)
    const confusionDialog = screen.getByRole('dialog', { name: 'Confusion matrix data' })
    expect(within(confusionDialog).getByRole('heading', { name: 'Confusion matrix data' })).toBeVisible()
    expect(within(confusionDialog).getAllByRole('row').slice(1)).toHaveLength(4)
    expect(within(confusionDialog).getByRole('columnheader', { name: 'Actual class' })).toBeVisible()
    expect(within(confusionDialog).getByRole('columnheader', { name: 'Predicted class' })).toBeVisible()
    expect(within(confusionDialog).getByRole('columnheader', { name: 'Count' })).toBeVisible()
    expect(within(confusionDialog).getByText('92')).toBeVisible()
    expect(within(confusionDialog).getByText('13')).toBeVisible()
    await user.keyboard('{Escape}')
    await waitFor(() =>
      expect(screen.queryByRole('dialog', { name: 'Confusion matrix data' })).not.toBeInTheDocument(),
    )
    expect(confusionTrigger).toHaveFocus()

    const rocTrigger = screen.getByRole('button', { name: 'Lihat data ROC curve' })
    await user.click(rocTrigger)
    const rocDialog = screen.getByRole('dialog', { name: /ROC curve data.*AUC.*0\.97/i })
    expect(within(rocDialog).getByRole('heading', { name: /ROC curve data.*AUC.*0\.97/i })).toBeVisible()
    expect(within(rocDialog).getAllByRole('row').slice(1)).toHaveLength(3)
    expect(within(rocDialog).getByRole('columnheader', { name: 'False positive rate' })).toBeVisible()
    expect(within(rocDialog).getByRole('columnheader', { name: 'True positive rate' })).toBeVisible()
    expect(within(rocDialog).getByText('0.08')).toBeVisible()
    expect(within(rocDialog).getByText('0.9')).toBeVisible()
    await user.keyboard('{Escape}')
    await waitFor(() =>
      expect(screen.queryByRole('dialog', { name: /ROC curve data.*AUC.*0\.97/i })).not.toBeInTheDocument(),
    )
    expect(rocTrigger).toHaveFocus()

    const precisionRecallTrigger = screen.getByRole('button', {
      name: 'Lihat data Precision recall curve',
    })
    await user.click(precisionRecallTrigger)
    const precisionRecallDialog = screen.getByRole('dialog', {
      name: /Precision recall curve data.*average precision.*0\.93/i,
    })
    expect(
      within(precisionRecallDialog).getByRole('heading', {
        name: /Precision recall curve data.*average precision.*0\.93/i,
      }),
    ).toBeVisible()
    expect(within(precisionRecallDialog).getAllByRole('row').slice(1)).toHaveLength(3)
    expect(within(precisionRecallDialog).getByRole('columnheader', { name: 'Recall' })).toBeVisible()
    expect(within(precisionRecallDialog).getByRole('columnheader', { name: 'Precision' })).toBeVisible()
    expect(within(precisionRecallDialog).getByText('0.9')).toBeVisible()
    expect(within(precisionRecallDialog).getByText('0.88')).toBeVisible()
    await user.keyboard('{Escape}')
    await waitFor(() =>
      expect(
        screen.queryByRole('dialog', {
          name: /Precision recall curve data.*average precision.*0\.93/i,
        }),
      ).not.toBeInTheDocument(),
    )
    expect(precisionRecallTrigger).toHaveFocus()
  })

  it('requires labeled ground truth, declaration, and matching data for every chart', () => {
    const complete = structuredClone(modelEvaluationDetails['model-v2'])
    const undeclaredPrecisionRecall: ModelEvaluationDetail = {
      ...complete,
      available_metrics: complete.available_metrics.filter(
        (name) => name !== 'precision_recall',
      ),
    }
    const missingPrecisionRecallData: ModelEvaluationDetail = structuredClone(complete)
    delete missingPrecisionRecallData.precision_recall

    const view = render(
      <ThemeProvider theme={theme}>
        <LabeledMetricsPanels artifact={{ ...complete, has_labeled_ground_truth: false }} />
      </ThemeProvider>,
    )
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
    expect(screen.queryByRole('table', { name: 'Confusion matrix' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Lihat data Confusion matrix' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Lihat data ROC curve' })).not.toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: 'Lihat data Precision recall curve' }),
    ).not.toBeInTheDocument()

    view.rerender(
      <ThemeProvider theme={theme}>
        <LabeledMetricsPanels artifact={undeclaredPrecisionRecall} />
      </ThemeProvider>,
    )
    expect(screen.getByRole('table', { name: 'Confusion matrix' })).toBeVisible()
    expect(screen.getByRole('img', { name: 'ROC curve' })).toBeVisible()
    expect(screen.queryByRole('img', { name: 'Precision-recall curve' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Lihat data Confusion matrix' })).toBeVisible()
    expect(screen.getByRole('button', { name: 'Lihat data ROC curve' })).toBeVisible()
    expect(
      screen.queryByRole('button', { name: 'Lihat data Precision recall curve' }),
    ).not.toBeInTheDocument()

    view.rerender(
      <ThemeProvider theme={theme}>
        <LabeledMetricsPanels artifact={missingPrecisionRecallData} />
      </ThemeProvider>,
    )
    expect(screen.queryByRole('img', { name: 'Precision-recall curve' })).not.toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: 'Lihat data Precision recall curve' }),
    ).not.toBeInTheDocument()
  })
})
