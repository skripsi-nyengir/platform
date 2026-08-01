import { Box, Paper, Stack, Typography } from '@mui/material'
import { useTheme } from '@mui/material/styles'
import { LineChart } from '@mui/x-charts/LineChart'
import { getChartColors } from '../../components/charts/muiChartTheme'
import { buildReconstructionBand, buildReconstructionSlice } from '../../components/charts/temporalOptions'
import { EmptyState } from '../../components/states/EmptyState'
import { sensorLabels, type SensorId } from '../../contracts/common'
import type { InferencePoint } from '../../contracts/inference'
import type { TelemetryPoint } from '../../contracts/telemetry'
import { tokens } from '../../theme/tokens'
import { AlertBinOverlay } from './AlertBinOverlay'
import type { AlertBinInterval } from './alertBinShapes'

export interface ReconstructionChartProps {
  sensorId: SensorId
  telemetry: readonly TelemetryPoint[]
  inference: readonly InferencePoint[]
  binIntervals?: readonly AlertBinInterval[]
  windowCount?: number
}

const chartHeight = tokens.size.control * 5

export function ReconstructionChart({
  sensorId,
  telemetry,
  inference,
  binIntervals = [],
  windowCount = 10,
}: ReconstructionChartProps) {
  const theme = useTheme()
  const colors = getChartColors(theme)
  const sensorLabel = sensorLabels[sensorId]
  const slice = buildReconstructionSlice(telemetry, inference, windowCount)
  const description =
    `Actual versus reconstructed temperature for the last ${windowCount} inferred ` +
    'windows (about one minute). The pink band is the reconstruction error.'

  const values = slice.flatMap((point) =>
    [point.actualTemperature, point.reconTemperature].filter(
      (value): value is number => value !== null,
    ),
  )
  const dataMin = values.length > 0 ? Math.min(...values) : 0
  const dataMax = values.length > 0 ? Math.max(...values) : 1
  const margin = (dataMax - dataMin) * 0.15 || 1

  const { baseline: bandBaseline, error: bandError } = buildReconstructionBand(slice)

  return (
    <Paper component="article" variant="outlined" sx={{ minWidth: 0, p: 2 }}>
      <Stack spacing={1} sx={{ minWidth: 0 }}>
        <Typography variant="h3">
          Reconstruction · last {windowCount} windows
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Data asli vs reconstruction; selisih (error) diarsir pink · Asia/Jakarta (WIB)
        </Typography>
        {slice.length === 0 ? (
          <EmptyState
            title="No reconstruction yet"
            detail="Belum ada hasil inferensi untuk rentang WIB yang dipilih."
          />
        ) : (
          <Box
            role="img"
            aria-label={`Reconstruction chart for sensor ${sensorLabel}`}
            aria-description={description}
          >
            <LineChart
              id={`reconstruction-chart-${sensorId}`}
              title="Reconstruction"
              desc={description}
              disableKeyboardNavigation
              height={chartHeight}
              skipAnimation
              xAxis={[
                {
                  id: 'reconstruction-x-axis',
                  data: slice.map((point) => point.x),
                  scaleType: 'time',
                  label: 'Window end (WIB)',
                },
              ]}
              yAxis={[
                {
                  id: 'reconstruction-y-axis',
                  label: 'Temperature (°C)',
                  min: dataMin - margin,
                  max: dataMax + margin,
                },
              ]}
              series={[
                {
                  id: 'reconstruction-band-baseline',
                  data: bandBaseline,
                  area: true,
                  stack: 'reconstruction-band',
                  color: 'transparent',
                  showMark: false,
                  disableHighlight: true,
                  curve: 'linear',
                  xAxisId: 'reconstruction-x-axis',
                  yAxisId: 'reconstruction-y-axis',
                },
                {
                  id: 'reconstruction-band-error',
                  data: bandError,
                  label: 'Reconstruction error',
                  area: true,
                  stack: 'reconstruction-band',
                  color: colors.reconstructionError,
                  showMark: false,
                  disableHighlight: true,
                  curve: 'linear',
                  xAxisId: 'reconstruction-x-axis',
                  yAxisId: 'reconstruction-y-axis',
                },
                {
                  id: 'reconstruction-actual',
                  data: slice.map((point) => point.actualTemperature),
                  label: 'Actual (°C)',
                  color: colors.temperature,
                  curve: 'linear',
                  connectNulls: false,
                  showMark: true,
                  valueFormatter: (value) => (value === null ? null : `${value} °C`),
                  xAxisId: 'reconstruction-x-axis',
                  yAxisId: 'reconstruction-y-axis',
                },
                {
                  id: 'reconstruction-recon',
                  data: slice.map((point) => point.reconTemperature),
                  label: 'Reconstruction (°C)',
                  color: colors.threshold,
                  curve: 'linear',
                  connectNulls: false,
                  showMark: true,
                  valueFormatter: (value) => (value === null ? null : `${value} °C`),
                  xAxisId: 'reconstruction-x-axis',
                  yAxisId: 'reconstruction-y-axis',
                },
              ]}
            >
              <AlertBinOverlay
                intervals={binIntervals}
                xAxisId="reconstruction-x-axis"
                color={colors.reconstructionError}
              />
            </LineChart>
          </Box>
        )}
      </Stack>
    </Paper>
  )
}
