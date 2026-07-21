import { Box, Button, Paper, Stack, Typography } from '@mui/material'
import { useTheme } from '@mui/material/styles'
import { LineChart } from '@mui/x-charts/LineChart'
import type { GridColDef } from '@mui/x-data-grid'
import { useState } from 'react'
import { getChartColors } from '../../components/charts/muiChartTheme'
import {
  buildTemporalChartData,
  buildTemporalSummary,
  type TemporalChartInput,
} from '../../components/charts/temporalOptions'
import { BoundedDataDialog } from '../../components/data/BoundedDataDialog'
import { ApiErrorPanel } from '../../components/states/ApiErrorPanel'
import { EmptyState } from '../../components/states/EmptyState'
import { PanelSkeleton } from '../../components/states/PanelSkeleton'
import type { SensorId } from '../../contracts/common'
import { useInferenceResultsQuery } from '../inference/queries'
import { useTelemetryHistoryQuery } from '../telemetry/queries'
import { tokens } from '../../theme/tokens'
import type { UrlFilters } from '../filters/urlFilters'

const technicalTextSx = {
  fontFamily: tokens.font.data,
  fontVariantNumeric: 'tabular-nums',
  overflowWrap: 'anywhere',
} as const

interface TemporalRow {
  id: string
  source: string
  timestamp: string
  temperature_c: number | null
  relative_humidity_pct: number | null
  score: number | null
}

const temporalColumns: readonly GridColDef<TemporalRow>[] = [
  { field: 'source', headerName: 'Source', flex: 1 },
  { field: 'timestamp', headerName: 'Timestamp', flex: 2 },
  { field: 'temperature_c', headerName: 'Temperature °C', flex: 1 },
  { field: 'relative_humidity_pct', headerName: 'RH %', flex: 1 },
  { field: 'score', headerName: 'Score', flex: 1 },
]

export function TemporalPatternsPanel({
  filters,
  sampleSize,
}: {
  filters: UrlFilters
  sampleSize: number
}) {
  return (
    <Paper
      component="section"
      aria-labelledby="temporal-patterns"
      variant="outlined"
      sx={{ minWidth: 0, p: 4 }}
    >
      <Stack spacing={2} sx={{ minWidth: 0 }}>
        <Typography id="temporal-patterns" variant="h2">Temporal patterns</Typography>
        {filters.sensor === undefined ? (
          <EmptyState
            title="Select a sensor for temporal patterns"
            detail="History and inference endpoints require one sensor while the other EDA panels support all sensors."
          />
        ) : (
          <TemporalPatternsData sensor={filters.sensor} filters={filters} sampleSize={sampleSize} />
        )}
      </Stack>
    </Paper>
  )
}

function TemporalPatternsData({
  sensor,
  filters,
  sampleSize,
}: {
  sensor: SensorId
  filters: UrlFilters
  sampleSize: number
}) {
  const [dialogOpen, setDialogOpen] = useState(false)
  const theme = useTheme()
  const limit = Math.min(sampleSize, filters.bucket === 'raw' ? 5_000 : 2_000)
  const telemetry = useTelemetryHistoryQuery({
    deviceId: sensor,
    from: filters.from,
    to: filters.to,
    bucket: filters.bucket,
    limit,
  })
  const inference = useInferenceResultsQuery({
    deviceId: sensor,
    from: filters.from,
    to: filters.to,
    bucket: filters.bucket,
    limit,
    modelVersion: filters.modelVersion,
  })
  const alerts: TemporalChartInput['alerts'] = []
  const chartInput: TemporalChartInput = {
    theme,
    sensorId: sensor,
    from: filters.from,
    to: filters.to,
    telemetry: telemetry.data?.points ?? [],
    inference: inference.data?.points ?? [],
    alerts,
  }
  const chartData = buildTemporalChartData(chartInput)
  const chartSummary = buildTemporalSummary(chartInput)
  const chartColors = getChartColors(theme)
  const anomalyEndTimes = new Set(
    chartData.anomalyIntervals.map((interval) => interval.end.getTime()),
  )
  const anomalyScores = chartData.scores.map((point) =>
    anomalyEndTimes.has(point.x.getTime()) ? point.y : null,
  )
  const rows: TemporalRow[] = [
    ...(telemetry.data?.points ?? []).map((point, index) => ({
      id: `telemetry-${point.ts}-${index}`,
      source: 'Telemetry',
      timestamp: point.ts,
      temperature_c: point.temperature_c,
      relative_humidity_pct: point.relative_humidity_pct,
      score: null,
    })),
    ...(inference.data?.points ?? []).map((point, index) => ({
      id: `inference-${point.window_end_ts}-${index}`,
      source: 'Inference',
      timestamp: point.window_end_ts,
      temperature_c: null,
      relative_humidity_pct: null,
      score: point.score,
    })),
  ]
  const gapCount = chartInput.telemetry.filter((point) => point.gap_before).length
  const threshold = chartInput.inference[0]?.threshold
  const anomalyCount = chartInput.inference.filter((point) => point.is_anomaly).length
  const alertCount = alerts.filter((event) => event.event_type === 'detected').length
  const hasData = rows.length > 0
  const pending = telemetry.data === undefined && !telemetry.isError && inference.data === undefined && !inference.isError
  const temperatureDescription = `Temperature in degrees Celsius. ${chartSummary}`
  const humidityDescription = `Relative humidity in percent. ${chartSummary}`
  const scoreDescription = `Anomaly score and threshold. Diamond marks identify anomalous window ends. ${chartSummary}`

  return (
    <Stack spacing={1} sx={{ minWidth: 0 }}>
      {telemetry.data === undefined ? (
        telemetry.isError ? (
          <ApiErrorPanel error={telemetry.error} onRetry={() => void telemetry.refetch()} />
        ) : null
      ) : (
        <Typography variant="body2">
          <Box component="span" sx={technicalTextSx}>{telemetry.data.returned_count}</Box> telemetry points returned
        </Typography>
      )}
      {inference.data === undefined ? (
        inference.isError ? (
          <ApiErrorPanel error={inference.error} onRetry={() => void inference.refetch()} />
        ) : null
      ) : (
        <Typography variant="body2">
          <Box component="span" sx={technicalTextSx}>{inference.data.returned_count}</Box> inference points returned
        </Typography>
      )}
      {pending ? <PanelSkeleton label="Loading temporal patterns" /> : null}
      {!pending && !hasData && !telemetry.isError && !inference.isError ? (
        <EmptyState
          title="No temporal points returned"
          detail="Adjust the selected time range or sensor."
        />
      ) : null}
      {hasData ? (
        <>
          <Typography variant="body2" color="text.secondary">
            Sensor <Box component="span" sx={technicalTextSx}>{sensor}</Box> from <Box component="span" sx={technicalTextSx}>{filters.from}</Box> to <Box component="span" sx={technicalTextSx}>{filters.to}</Box>.{' '}
            <Box component="span" sx={technicalTextSx}>{gapCount}</Box> documented gap{gapCount === 1 ? '' : 's'}.{' '}
            {threshold === undefined ? (
              'Score threshold unavailable.'
            ) : (
              <>Score threshold <Box component="span" sx={technicalTextSx}>{threshold}</Box>.</>
            )}{' '}
            <Box component="span" sx={technicalTextSx}>{anomalyCount}</Box> anomaly interval{anomalyCount === 1 ? '' : 's'}.{' '}
            <Box component="span" sx={technicalTextSx}>{alertCount}</Box> detected alert{alertCount === 1 ? '' : 's'}.
          </Typography>
          <Box
            role="group"
            aria-label={`Temporal charts for sensor ${sensor}`}
            sx={{
              display: 'grid',
              gap: 2,
              minWidth: 0,
            }}
          >
            <Paper component="article" variant="outlined" sx={{ minWidth: 0, p: 2 }}>
              <Stack spacing={1} sx={{ minWidth: 0 }}>
                <Typography variant="h3">Temperature</Typography>
                <Box
                  role="img"
                  aria-label={`Temperature chart for sensor ${sensor}`}
                  aria-description={temperatureDescription}
                  sx={{ minWidth: 0 }}
                >
                   <LineChart
                     id={`temperature-chart-${sensor}`}
                     title="Temperature"
                     desc={temperatureDescription}
                     disableKeyboardNavigation
                     height={tokens.size.control * 7}
                    hideLegend
                    skipAnimation
                    xAxis={[
                       {
                         id: 'temperature-x-axis',
                         data: chartData.temperature.map((point) => point.x),
                         label: 'Date',
                         scaleType: 'time',
                         min: new Date(filters.from),
                         max: new Date(filters.to),
                       },
                    ]}
                    yAxis={[{ id: 'temperature-y-axis', label: 'Temperature (°C)' }]}
                    series={[
                      {
                        id: 'temperature-series',
                        data: chartData.temperature.map((point) => point.y),
                        label: 'Temperature (°C)',
                        color: chartColors.temperature,
                        connectNulls: false,
                        curve: 'linear',
                        showMark: false,
                        valueFormatter: (value) => value === null ? null : `${value} °C`,
                        xAxisId: 'temperature-x-axis',
                        yAxisId: 'temperature-y-axis',
                      },
                    ]}
                  />
                </Box>
              </Stack>
            </Paper>

            <Paper component="article" variant="outlined" sx={{ minWidth: 0, p: 2 }}>
              <Stack spacing={1} sx={{ minWidth: 0 }}>
                <Typography variant="h3">Relative humidity</Typography>
                <Box
                  role="img"
                  aria-label={`Relative humidity chart for sensor ${sensor}`}
                  aria-description={humidityDescription}
                  sx={{ minWidth: 0 }}
                >
                   <LineChart
                     id={`humidity-chart-${sensor}`}
                     title="Relative humidity"
                     desc={humidityDescription}
                     disableKeyboardNavigation
                     height={tokens.size.control * 7}
                    hideLegend
                    skipAnimation
                    xAxis={[
                       {
                         id: 'humidity-x-axis',
                         data: chartData.humidity.map((point) => point.x),
                         label: 'Date',
                         scaleType: 'time',
                         min: new Date(filters.from),
                         max: new Date(filters.to),
                       },
                    ]}
                    yAxis={[{ id: 'humidity-y-axis', label: 'Relative humidity (%)' }]}
                    series={[
                      {
                        id: 'humidity-series',
                        data: chartData.humidity.map((point) => point.y),
                        label: 'Relative humidity (%)',
                        color: chartColors.humidity,
                        connectNulls: false,
                        curve: 'linear',
                        showMark: false,
                        valueFormatter: (value) => value === null ? null : `${value} %`,
                        xAxisId: 'humidity-x-axis',
                        yAxisId: 'humidity-y-axis',
                      },
                    ]}
                  />
                </Box>
              </Stack>
            </Paper>

            <Paper component="article" variant="outlined" sx={{ minWidth: 0, p: 2 }}>
              <Stack spacing={1} sx={{ minWidth: 0 }}>
                <Typography variant="h3">Anomaly score / threshold</Typography>
                <Box
                  role="img"
                  aria-label={`Anomaly score and threshold chart for sensor ${sensor}`}
                  aria-description={scoreDescription}
                  sx={{ minWidth: 0 }}
                >
                   <LineChart
                     id={`score-chart-${sensor}`}
                     title="Anomaly score and threshold"
                     desc={scoreDescription}
                     disableKeyboardNavigation
                     height={tokens.size.control * 7}
                    skipAnimation
                    xAxis={[
                       {
                         id: 'score-x-axis',
                         data: chartData.scores.map((point) => point.x),
                         label: 'Date',
                         scaleType: 'time',
                         min: new Date(filters.from),
                         max: new Date(filters.to),
                       },
                    ]}
                    yAxis={[{ id: 'score-y-axis', label: 'Score' }]}
                    series={[
                      {
                        id: 'score-series',
                        data: chartData.scores.map((point) => point.y),
                        label: 'Anomaly score',
                        color: chartColors.anomalyScore,
                        curve: 'linear',
                        showMark: false,
                        xAxisId: 'score-x-axis',
                        yAxisId: 'score-y-axis',
                      },
                      {
                        id: 'threshold-series',
                        data: chartData.scores.map(() => chartData.threshold ?? null),
                        label: 'Threshold',
                        color: chartColors.threshold,
                        connectNulls: false,
                        curve: 'linear',
                        disableHighlight: true,
                        showMark: false,
                        xAxisId: 'score-x-axis',
                        yAxisId: 'score-y-axis',
                      },
                      {
                        id: 'anomaly-series',
                        data: anomalyScores,
                        label: 'Anomaly window end',
                        color: chartColors.outlier,
                        connectNulls: false,
                        curve: 'linear',
                        shape: 'diamond',
                        showMark: true,
                        xAxisId: 'score-x-axis',
                        yAxisId: 'score-y-axis',
                      },
                    ]}
                  />
                </Box>
              </Stack>
            </Paper>
          </Box>
          <Button size="small" onClick={() => setDialogOpen(true)}>Lihat data</Button>
          <BoundedDataDialog<TemporalRow>
            open={dialogOpen}
            title={`Temporal data for sensor ${sensor}`}
            rows={rows}
            returnedCount={rows.length}
            columns={temporalColumns}
            onClose={() => setDialogOpen(false)}
          />
        </>
      ) : null}
    </Stack>
  )
}
