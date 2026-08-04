import { LineChart } from '@mui/x-charts/LineChart'
import { render } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { AlertBinOverlay } from './AlertBinOverlay'
import type { AlertBinInterval } from './alertBinShapes'

const TEST_COLOR = '#ff00ff'

function interval(startMs: number, endMs: number, isAlert: boolean): AlertBinInterval {
  return { start: new Date(startMs), end: new Date(endMs), isAlert }
}

function renderOverlay(intervals: AlertBinInterval[]) {
  return render(
    <LineChart
      width={400}
      height={200}
      xAxis={[
        {
          id: 'x',
          scaleType: 'time',
          data: [new Date(0), new Date(100_000)],
          min: new Date(0),
          max: new Date(100_000),
        },
      ]}
      series={[{ data: [1, 2], xAxisId: 'x' }]}
    >
      <AlertBinOverlay intervals={intervals} xAxisId="x" color={TEST_COLOR} />
    </LineChart>,
  )
}

describe('AlertBinOverlay', () => {
  it('draws a pink band for each alert bin only', () => {
    const { container } = renderOverlay([
      interval(10_000, 20_000, true),
      interval(20_000, 30_000, false),
      interval(30_000, 40_000, true),
    ])
    expect(container.querySelectorAll(`rect[fill="${TEST_COLOR}"]`)).toHaveLength(2)
  })

  it('draws no band when no bin is an alert', () => {
    const { container } = renderOverlay([interval(10_000, 20_000, false)])
    expect(container.querySelectorAll(`rect[fill="${TEST_COLOR}"]`)).toHaveLength(0)
  })

  it('draws a band for every bin when all bins are alerts', () => {
    const { container } = renderOverlay([
      interval(10_000, 20_000, true),
      interval(20_000, 30_000, true),
      interval(30_000, 40_000, true),
    ])
    expect(container.querySelectorAll(`rect[fill="${TEST_COLOR}"]`)).toHaveLength(3)
  })
})
