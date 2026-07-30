import '@testing-library/jest-dom/vitest'
import { fireEvent, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import { simulationMetricsResponse } from '../mocks/fixtures/simulation'
import { server } from '../mocks/node'
import { renderApp } from '../test/renderApp'

describe('SimulationPage', () => {
  it('renders five artifact models, server metrics, and the full injection corpus navigator', async () => {
    renderApp('/simulation')

    expect(await screen.findByRole('heading', { name: 'Anomaly simulation' })).toBeVisible()
    expect(await screen.findByRole('heading', { name: 'LSTM-AE' })).toBeVisible()
    expect(screen.getByRole('heading', { name: 'Conv1D Autoencoder' })).toBeVisible()
    expect(screen.getByRole('heading', { name: 'Transformer Autoencoder' })).toBeVisible()
    expect(screen.getByRole('heading', { name: 'GRU-AE' })).toBeVisible()
    expect(screen.getByRole('heading', { name: 'RNN-AE' })).toBeVisible()
    expect(screen.getAllByText('Window size')).toHaveLength(5)

    expect(await screen.findByRole('heading', { name: 'Research scoreboard' })).toBeVisible()
    expect(screen.getByRole('heading', { name: 'Timestamp scope' })).toBeVisible()
    expect(screen.getByRole('heading', { name: 'Overlapping model windows' })).toBeVisible()
    expect(screen.getByRole('heading', { name: 'Non-overlapping evaluation bins' })).toBeVisible()
    expect(screen.getByText('Primary thesis metric')).toBeVisible()
    expect(screen.getByRole('heading', { name: 'Operational alerts' })).toBeVisible()
    expect(screen.getByRole('table', { name: 'Operational alert events' })).toBeVisible()
    expect(screen.getByText('Replay already computed — showing stored results.')).toBeVisible()
    expect(screen.queryByRole('button', { name: 'Run injected replay' })).not.toBeInTheDocument()

    expect(await screen.findByText('210 injected events')).toBeVisible()
    expect(screen.getByRole('list', { name: 'Injection events by corpus day' })).toBeVisible()
    expect(screen.getByRole('button', { name: /19 Apr, \d+ injection events/ })).toHaveAttribute('aria-current', 'date')
    const slider = screen.getByRole('slider', { name: 'Injection event' })
    expect(slider).toHaveAttribute('aria-valuemax', '210')
    expect(screen.getByRole('heading', { name: 'Event 1 of 210' })).toBeVisible()
    expect(await screen.findByRole('img', { name: 'Temperature signal and reconstruction band' })).toBeVisible()

    fireEvent.change(slider, { target: { value: '210' } })
    expect(await screen.findByRole('heading', { name: 'Event 210 of 210' })).toBeVisible()
  })

  it('renders a clear empty state when the selected model has no replay results', async () => {
    const user = userEvent.setup()
    renderApp('/simulation')

    await user.click(await screen.findByRole('button', { name: 'GRU-AE, select model' }))

    expect(await screen.findByRole('heading', { name: 'No replay data for this model yet' })).toBeVisible()
    expect(screen.getByText(/GRU-AE has no inference results/)).toBeVisible()
    expect(screen.getByRole('button', { name: 'Run injected replay' })).toBeVisible()
  })

  it('falls back to stored results when replay population overlaps an existing job', async () => {
    let replayConflict = false
    server.use(
      http.get('/api/simulation/metrics', ({ request }) => {
        const modelVersion = new URL(request.url).searchParams.get('model_version')
        if (modelVersion !== 'artifact-gru-v3') return undefined
        if (replayConflict) return HttpResponse.json(simulationMetricsResponse('artifact-gru-v3'))
        return HttpResponse.json({
          type: 'https://example.invalid/problems/replay-results-not-found',
          title: 'Replay results not found',
          status: 404,
          detail: 'No replay results exist for this model on the simulation device',
          instance: '/api/simulation/metrics',
          request_id: 'req_simulation_metrics_missing',
        }, { status: 404 })
      }),
      http.post('/api/replay-jobs', () => {
        replayConflict = true
        return HttpResponse.json({
          type: 'https://example.invalid/problems/replay-overlap',
          title: 'Conflict',
          status: 409,
          detail: 'Replay interval overlaps existing job job_existing',
          instance: '/api/replay-jobs',
          request_id: 'req_replay_conflict',
        }, { status: 409 })
      }),
    )
    const user = userEvent.setup()
    renderApp('/simulation')

    await user.click(await screen.findByRole('button', { name: 'GRU-AE, select model' }))
    await user.click(await screen.findByRole('button', { name: 'Run injected replay' }))

    expect(await screen.findByText('A replay already exists for this model; showing stored results.')).toBeVisible()
    expect(await screen.findByRole('heading', { name: 'Research scoreboard' })).toBeVisible()
    expect(screen.queryByText(/Replay interval overlaps existing job/)).not.toBeInTheDocument()
  })
})
