import { getValueToPositionMapper } from '@mui/x-charts/hooks'
import { useDrawingArea, useXScale } from '@mui/x-charts/hooks'
import { buildAlertBinShapes, type AlertBinInterval } from './alertBinShapes'

export interface AlertBinOverlayProps {
  intervals: readonly AlertBinInterval[]
  xAxisId: string
  color: string
}

export function AlertBinOverlay({ intervals, xAxisId, color }: AlertBinOverlayProps) {
  const { top, height, left, width } = useDrawingArea()
  const scale = useXScale(xAxisId)
  const project = getValueToPositionMapper(scale)
  const { bands, boundaries } = buildAlertBinShapes(
    intervals,
    (value) => project(value),
    { left, right: left + width },
  )
  return (
    <g aria-hidden="true">
      {bands.map((band) => (
        <rect
          key={`alert-band-${band.x}-${band.width}`}
          x={band.x}
          y={top}
          width={band.width}
          height={height}
          fill={color}
          fillOpacity={0.16}
        />
      ))}
      {boundaries.map((x, index) => (
        <line
          key={`alert-edge-${x}-${index}`}
          x1={x}
          x2={x}
          y1={top}
          y2={top + height}
          stroke={color}
          strokeOpacity={0.45}
          strokeDasharray="3 3"
        />
      ))}
    </g>
  )
}
