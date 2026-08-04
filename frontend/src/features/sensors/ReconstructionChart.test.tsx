import { ThemeProvider } from '@mui/material/styles'
import { render, screen } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { publicDeviceId } from '../../contracts/common'
import type { InferencePoint } from '../../contracts/inference'
import type { TelemetryPoint } from '../../contracts/telemetry'
import { getChartColors } from '../../components/charts/muiChartTheme'
import type { ReconstructionChannel } from '../../components/charts/temporalOptions'
import { theme } from '../../theme/theme'
import { ReconstructionChart } from './ReconstructionChart'

interface CapturedSeries {
  color?: string
  data?: readonly (number | null)[]
  label?: string
}

interface CapturedAxis {
  id?: string
  label?: string
}

interface CapturedLineChartProps {
  children?: ReactNode
  id?: string
  series?: readonly CapturedSeries[]
  title?: string
  yAxis?: readonly CapturedAxis[]
}

const { lineChartPropsSpy } = vi.hoisted(() => ({ lineChartPropsSpy: vi.fn() }))

vi.mock('@mui/x-charts/LineChart', () => ({
  LineChart: (props: CapturedLineChartProps) => {
    lineChartPropsSpy(props)
    return <div data-testid={props.id}>{props.children}</div>
  },
}))

vi.mock('./AlertBinOverlay', () => ({
  AlertBinOverlay: ({ xAxisId }: { xAxisId: string }) => (
    <span data-testid="alert-bin-overlay" data-x-axis-id={xAxisId} />
  ),
}))

const scoreTs = '2026-05-31T23:48:00'

const telemetry: TelemetryPoint = {
  ts: scoreTs,
  temperature_c: 25,
  relative_humidity_pct: 60,
  temperature_c_min: 25,
  temperature_c_max: 25,
  relative_humidity_pct_min: 60,
  relative_humidity_pct_max: 60,
  sample_count: 1,
  gap_before: false,
}

const inference: InferencePoint = {
  window_start_ts: '2026-05-31T23:47:30',
  window_end_ts: scoreTs,
  score_ts: scoreTs,
  score: 0.5,
  threshold: 1,
  is_anomaly: false,
  severity: 'info',
  latest_score: 0.5,
  sample_count: 1,
  model_version: 'test',
  score_provenance: 'artifact_backed',
  recon_temperature_c: 24.5,
  recon_relative_humidity_pct: 59,
  band_half_temperature_c: null,
  band_half_relative_humidity_pct: null,
}

function renderChart(channel: ReconstructionChannel) {
  render(
    <ThemeProvider theme={theme}>
      <ReconstructionChart
        sensorId={publicDeviceId}
        channel={channel}
        telemetry={[telemetry]}
        inference={[inference]}
        windowCount={153}
      />
    </ThemeProvider>,
  )
  return lineChartPropsSpy.mock.lastCall?.[0] as CapturedLineChartProps
}

afterEach(() => {
  lineChartPropsSpy.mockClear()
})

describe('ReconstructionChart', () => {
  it('preserves the temperature chart contract', () => {
    const props = renderChart('temperature')

    expect(screen.getByRole('heading', {
      name: 'Temperature reconstruction · last 153 windows',
    })).toBeVisible()
    expect(props.id).toBe(`reconstruction-chart-${publicDeviceId}`)
    expect(props.title).toBe('Temperature reconstruction')
    expect(props.yAxis?.[0]).toMatchObject({
      id: 'reconstruction-y-axis',
      label: 'Temperature (°C)',
    })
    expect(props.series?.map((series) => series.data)).toEqual([
      [24.5],
      [0.5],
      [25],
      [24.5],
    ])
    expect(screen.getByTestId('alert-bin-overlay')).toHaveAttribute(
      'data-x-axis-id',
      'reconstruction-x-axis',
    )
  })

  it('renders RH values, units, colors, and channel-scoped identifiers', () => {
    const props = renderChart('humidity')
    const colors = getChartColors(theme)

    expect(screen.getByRole('heading', {
      name: 'RH reconstruction · last 153 windows',
    })).toBeVisible()
    expect(props.id).toBe(`rh-reconstruction-chart-${publicDeviceId}`)
    expect(props.title).toBe('RH reconstruction')
    expect(props.yAxis?.[0]).toMatchObject({
      id: 'rh-reconstruction-y-axis',
      label: 'Relative humidity (%)',
    })
    expect(props.series?.map((series) => series.data)).toEqual([
      [59],
      [1],
      [60],
      [59],
    ])
    expect(props.series?.[2]).toMatchObject({
      color: colors.humidity,
      label: 'Actual RH (%)',
    })
    expect(props.series?.[3]?.label).toBe('Reconstruction RH (%)')
    expect(screen.getByTestId('alert-bin-overlay')).toHaveAttribute(
      'data-x-axis-id',
      'rh-reconstruction-x-axis',
    )
  })
})
