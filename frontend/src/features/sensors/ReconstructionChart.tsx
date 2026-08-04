import { Box, Paper, Stack, Typography } from '@mui/material'
import { useTheme } from '@mui/material/styles'
import { LineChart } from '@mui/x-charts/LineChart'
import { getChartColors } from '../../components/charts/muiChartTheme'
import {
  buildReconstructionBand,
  buildReconstructionSlice,
  type ReconstructionChannel,
} from '../../components/charts/temporalOptions'
import { EmptyState } from '../../components/states/EmptyState'
import { sensorLabels, type SensorId } from '../../contracts/common'
import type { InferencePoint } from '../../contracts/inference'
import type { TelemetryPoint } from '../../contracts/telemetry'
import { tokens } from '../../theme/tokens'
import { AlertBinOverlay } from './AlertBinOverlay'
import type { AlertBinInterval } from './alertBinShapes'

export interface ReconstructionChartProps {
  sensorId: SensorId
  channel: ReconstructionChannel
  telemetry: readonly TelemetryPoint[]
  inference: readonly InferencePoint[]
  binIntervals?: readonly AlertBinInterval[]
  windowCount?: number
}

const chartHeight = tokens.size.control * 5

export function ReconstructionChart({
  sensorId,
  channel,
  telemetry,
  inference,
  binIntervals = [],
  windowCount = 10,
}: ReconstructionChartProps) {
  const theme = useTheme()
  const colors = getChartColors(theme)
  const sensorLabel = sensorLabels[sensorId]
  const slice = buildReconstructionSlice(telemetry, inference, windowCount)
  const isTemperature = channel === 'temperature'
  const channelTitle = isTemperature ? 'Temperature reconstruction' : 'RH reconstruction'
  const metricName = isTemperature ? 'temperature' : 'relative humidity'
  const unit = isTemperature ? '°C' : '%'
  const yAxisLabel = isTemperature ? 'Temperature (°C)' : 'Relative humidity (%)'
  const idPrefix = isTemperature ? 'reconstruction' : 'rh-reconstruction'
  const xAxisId = `${idPrefix}-x-axis`
  const yAxisId = `${idPrefix}-y-axis`
  const actualValues = slice.map((point) =>
    isTemperature ? point.actualTemperature : point.actualHumidity,
  )
  const reconstructedValues = slice.map((point) =>
    isTemperature ? point.reconTemperature : point.reconHumidity,
  )
  const description =
    `Actual versus reconstructed ${metricName} for the last ${windowCount} inferred windows. ` +
    'The pink band is the absolute reconstruction error.'

  const values = actualValues.flatMap((actual, index) =>
    [actual, reconstructedValues[index]].filter(
      (value): value is number => value !== null,
    ),
  )
  const dataMin = values.length > 0 ? Math.min(...values) : 0
  const dataMax = values.length > 0 ? Math.max(...values) : 1
  const margin = (dataMax - dataMin) * 0.15 || 1

  const { baseline: bandBaseline, error: bandError } = buildReconstructionBand(slice, channel)
  const valueFormatter = (value: number | null) =>
    value === null ? null : `${value} ${unit}`

  return (
    <Paper component="article" variant="outlined" sx={{ minWidth: 0, p: 2 }}>
      <Stack spacing={1} sx={{ minWidth: 0 }}>
        <Typography variant="h3">
          {channelTitle} · last {windowCount} windows
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Data {isTemperature ? 'suhu' : 'RH'} asli vs reconstruction; selisih (error)
          {' '}diarsir pink · Asia/Jakarta (WIB)
        </Typography>
        {slice.length === 0 ? (
          <EmptyState
            title="No reconstruction yet"
            detail="Belum ada hasil inferensi untuk rentang WIB yang dipilih."
          />
        ) : (
          <Box
            role="img"
            aria-label={`${channelTitle} chart for sensor ${sensorLabel}`}
            aria-description={description}
          >
            <LineChart
              id={`${idPrefix}-chart-${sensorId}`}
              title={channelTitle}
              desc={description}
              disableKeyboardNavigation
              height={chartHeight}
              skipAnimation
              xAxis={[
                {
                  id: xAxisId,
                  data: slice.map((point) => point.x),
                  scaleType: 'time',
                  label: 'Window end (WIB)',
                },
              ]}
              yAxis={[
                {
                  id: yAxisId,
                  label: yAxisLabel,
                  min: dataMin - margin,
                  max: dataMax + margin,
                },
              ]}
              series={[
                {
                  id: `${idPrefix}-band-baseline`,
                  data: bandBaseline,
                  area: true,
                  stack: `${idPrefix}-band`,
                  color: 'transparent',
                  showMark: false,
                  disableHighlight: true,
                  curve: 'linear',
                  xAxisId,
                  yAxisId,
                },
                {
                  id: `${idPrefix}-band-error`,
                  data: bandError,
                  label: 'Reconstruction error',
                  area: true,
                  stack: `${idPrefix}-band`,
                  color: colors.reconstructionError,
                  showMark: false,
                  disableHighlight: true,
                  curve: 'linear',
                  xAxisId,
                  yAxisId,
                },
                {
                  id: `${idPrefix}-actual`,
                  data: actualValues,
                  label: isTemperature ? 'Actual (°C)' : 'Actual RH (%)',
                  color: isTemperature ? colors.temperature : colors.humidity,
                  curve: 'linear',
                  connectNulls: false,
                  showMark: true,
                  valueFormatter,
                  xAxisId,
                  yAxisId,
                },
                {
                  id: `${idPrefix}-recon`,
                  data: reconstructedValues,
                  label: isTemperature ? 'Reconstruction (°C)' : 'Reconstruction RH (%)',
                  color: colors.threshold,
                  curve: 'linear',
                  connectNulls: false,
                  showMark: true,
                  valueFormatter,
                  xAxisId,
                  yAxisId,
                },
              ]}
            >
              <AlertBinOverlay
                intervals={binIntervals}
                xAxisId={xAxisId}
                color={colors.reconstructionError}
              />
            </LineChart>
          </Box>
        )}
      </Stack>
    </Paper>
  )
}
