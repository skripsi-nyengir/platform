import { Alert, Box, Button, Paper, Stack, Typography } from '@mui/material'
import { useTheme } from '@mui/material/styles'
import { LineChart } from '@mui/x-charts/LineChart'
import type { GridColDef, GridValidRowModel } from '@mui/x-data-grid'
import type { UseQueryResult } from '@tanstack/react-query'
import { useState } from 'react'
import type { ApiError } from '../../api/errors'
import { getChartColors } from '../../components/charts/muiChartTheme'
import {
  buildTemporalChartData,
  buildTemporalSummary,
} from '../../components/charts/temporalOptions'
import { BoundedDataDialog } from '../../components/data/BoundedDataDialog'
import { ProvenanceBadge } from '../../components/data/ProvenanceBadge'
import { formatProvenance } from '../../components/data/provenance'
import { ApiErrorPanel } from '../../components/states/ApiErrorPanel'
import { EmptyState } from '../../components/states/EmptyState'
import { PanelSkeleton } from '../../components/states/PanelSkeleton'
import {
  historicalDateTimeToDate,
  sensorLabels,
  type SensorId,
} from '../../contracts/common'
import type { AlertEventsResponse } from '../../contracts/alerts'
import type { InferenceResultsResponse } from '../../contracts/inference'
import type { PostInferenceBinsResponse } from '../../contracts/postInferenceBins'
import type { TelemetryHistoryResponse } from '../../contracts/telemetry'
import { resolveLiveRange, type LiveUrlFilters } from '../filters/urlFilters'
import { tokens } from '../../theme/tokens'
import { AlertBinOverlay } from './AlertBinOverlay'
import { toAlertBinIntervals } from './alertBinShapes'
import { ReconstructionChart } from './ReconstructionChart'

export interface SensorHistoryPanelProps {
  sensorId: SensorId
  filters: LiveUrlFilters
  telemetry: UseQueryResult<TelemetryHistoryResponse, ApiError>
  inference: UseQueryResult<InferenceResultsResponse, ApiError>
  alertEvents: UseQueryResult<AlertEventsResponse, ApiError>
  postInferenceBins: UseQueryResult<PostInferenceBinsResponse, ApiError>
}

interface HistoryTableRow extends GridValidRowModel {
  id: string
  record_type: 'Telemetry' | 'Inference'
  timestamp: string
  temperature_c?: number | null
  relative_humidity_pct?: number | null
  sample_count?: number
  gap_before?: 'Yes' | 'No'
  score?: number
  threshold?: number
  is_anomaly?: 'Yes' | 'No'
  model_version?: string
  score_provenance?: string
}

const historyColumns: readonly GridColDef<HistoryTableRow>[] = [
  { field: 'record_type', headerName: 'Record type', flex: 1 },
  { field: 'timestamp', headerName: 'Timestamp / window', flex: 2 },
  { field: 'temperature_c', headerName: 'Temperature °C', flex: 1 },
  { field: 'relative_humidity_pct', headerName: 'RH %', flex: 1 },
  { field: 'sample_count', headerName: 'Samples', flex: 1 },
  { field: 'gap_before', headerName: 'Gap before', flex: 1 },
  { field: 'score', headerName: 'Score', flex: 1 },
  { field: 'threshold', headerName: 'Threshold', flex: 1 },
  { field: 'is_anomaly', headerName: 'Anomaly', flex: 1 },
  { field: 'model_version', headerName: 'Model', flex: 1 },
  { field: 'score_provenance', headerName: 'Provenance', flex: 1 },
]

const technicalTextSx = {
  fontFamily: tokens.font.data,
  fontVariantNumeric: 'tabular-nums',
  overflowWrap: 'anywhere',
} as const

const chartHeight = tokens.size.control * 7

export function SensorHistoryPanel({
  sensorId,
  filters,
  telemetry,
  inference,
  alertEvents,
  postInferenceBins,
}: SensorHistoryPanelProps) {
  const [dialogOpen, setDialogOpen] = useState(false)
  const theme = useTheme()
  const sensorLabel = sensorLabels[sensorId]
  const displayedRange = telemetry.data ?? inference.data ?? resolveLiveRange(filters)
  const telemetryPoints = telemetry.data?.points ?? []
  const inferencePoints = inference.data?.points ?? []
  const binIntervals = toAlertBinIntervals(postInferenceBins.data?.bins ?? [])
  const completeBinCount = postInferenceBins.data?.bins.length ?? 0
  const binsUnavailable = postInferenceBins.isError
  const rows: readonly HistoryTableRow[] = [
    ...telemetryPoints.map((point) => ({
      id: `telemetry:${point.ts}`,
      record_type: 'Telemetry' as const,
      timestamp: point.ts,
      temperature_c: point.temperature_c,
      relative_humidity_pct: point.relative_humidity_pct,
      sample_count: point.sample_count,
      gap_before: point.gap_before ? 'Yes' as const : 'No' as const,
    })),
    ...inferencePoints.map((point) => ({
      id: `inference:${point.window_start_ts}:${point.window_end_ts}`,
      record_type: 'Inference' as const,
      timestamp: point.score_ts,
      score: point.latest_score ?? point.score,
      threshold: point.threshold,
      is_anomaly: point.is_anomaly ? 'Yes' as const : 'No' as const,
      model_version: point.model_version,
      score_provenance: formatProvenance(point.score_provenance),
    })),
  ]
  const chartInput = {
    theme,
    sensorId,
    from: displayedRange.from,
    to: displayedRange.to,
    telemetry: telemetryPoints,
    inference: inferencePoints,
    alerts: alertEvents.data?.events ?? [],
  }
  const chartData = buildTemporalChartData(chartInput)
  const chartSummary = buildTemporalSummary(chartInput)
  const temperatureDescription = `Temperature in degrees Celsius. ${chartSummary}`
  const humidityDescription = `Relative humidity in percent. ${chartSummary}`
  const scoreDescription = `Anomaly score and threshold. Diamond marks identify anomalous window ends. ${chartSummary}`
  const chartColors = getChartColors(theme)
  const anomalyEndTimes = new Set(
    chartData.anomalyIntervals.map((interval) => interval.end.getTime()),
  )
  const anomalyScores = chartData.scores.map((point) =>
    anomalyEndTimes.has(point.x.getTime()) ? point.y : null,
  )
  const hasChartData = telemetryPoints.length > 0 || inferencePoints.length > 0
  // ponytail: disclose the API cap here; add cursor pagination only if full fine-bucket browsing becomes required.
  const telemetryIsTruncated = telemetry.data?.next_cursor !== undefined && telemetry.data.next_cursor !== null

  return (
    <Paper
      component="section"
      aria-label="Telemetry and inference history"
      variant="outlined"
      sx={{ p: 2 }}
    >
      <Stack spacing={2}>
        <Typography variant="h2">Telemetry and inference history</Typography>
        <Typography variant="body2" color="text.secondary">
          Score timestamp dan provenance dipertahankan pada tabel hasil · Asia/Jakarta (WIB)
        </Typography>
        {inferencePoints.at(-1) === undefined ? null : (
          <Stack direction="row" spacing={3} useFlexGap sx={{ flexWrap: 'wrap' }}>
            <Typography variant="body2" sx={technicalTextSx}>
              Latest score: {inferencePoints.at(-1)?.latest_score ?? inferencePoints.at(-1)?.score}
            </Typography>
            <Typography variant="body2" sx={technicalTextSx}>
              Severity: {inferencePoints.at(-1)?.severity ?? 'unclassified'}
            </Typography>
          </Stack>
        )}
        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: 'repeat(2, minmax(0, 1fr))',
            gap: 2,
          }}
        >
          <Paper
            component="section"
            aria-label="Telemetry history"
            variant="outlined"
            sx={{ minWidth: 0, p: 4 }}
          >
            <Stack spacing={1}>
              <Typography variant="h3">Telemetry history</Typography>
              {telemetry.data === undefined ? (
                telemetry.isError ? (
                  <ApiErrorPanel error={telemetry.error} onRetry={() => void telemetry.refetch()} />
                ) : (
                  <PanelSkeleton label="Loading telemetry history" />
                )
              ) : telemetry.data.points.length === 0 ? (
                <EmptyState
                  title="No telemetry history"
                  detail="Tidak ada sampel corpus historis pada rentang WIB yang dipilih."
                />
              ) : (
                <Typography variant="body2" sx={technicalTextSx}>
                  {telemetry.data.returned_count} bounded telemetry records
                </Typography>
              )}
            </Stack>
          </Paper>

          <Paper
            component="section"
            aria-label="Inference history"
            variant="outlined"
            sx={{ minWidth: 0, p: 4 }}
          >
            <Stack spacing={1}>
              <Typography variant="h3">Inference history</Typography>
              {inference.data === undefined ? (
                inference.isError ? (
                  <ApiErrorPanel error={inference.error} onRetry={() => void inference.refetch()} />
                ) : (
                  <PanelSkeleton label="Loading inference history" />
                )
              ) : inference.data.points.length === 0 ? (
                <EmptyState
                  title="No inference history"
                  detail="Belum ada hasil replay untuk versi model dan rentang WIB yang dipilih."
                />
              ) : (
                <Typography variant="body2" sx={technicalTextSx}>
                  {inference.data.returned_count} bounded inference records
                </Typography>
              )}
            </Stack>
          </Paper>
        </Box>

        {hasChartData ? (
          <Stack spacing={1}>
            {telemetryIsTruncated ? (
              <Alert severity="warning" role="note">
                View truncated. Pilih rentang lebih sempit atau bucket lebih kasar untuk melihat seluruh data.
              </Alert>
            ) : null}
            <Typography variant="body2" color="text.secondary">
              {chartSummary}
            </Typography>
            <Box
              role="group"
              aria-label={`Temporal charts for sensor ${sensorLabel}`}
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
                    aria-label={`Temperature chart for sensor ${sensorLabel}`}
                    aria-description={temperatureDescription}
                  >
                     <LineChart
                       id={`temperature-chart-${sensorId}`}
                       title="Temperature"
                       desc={temperatureDescription}
                       disableKeyboardNavigation
                       height={chartHeight}
                      hideLegend
                      skipAnimation
                      xAxis={[
                         {
                           id: 'temperature-x-axis',
                           data: chartData.temperature.map((point) => point.x),
                           label: 'Date',
                           scaleType: 'time',
                             min: historicalDateTimeToDate(displayedRange.from),
                             max: historicalDateTimeToDate(displayedRange.to),
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
                    >
                      <AlertBinOverlay
                        intervals={binIntervals}
                        xAxisId="temperature-x-axis"
                        color={chartColors.reconstructionError}
                      />
                    </LineChart>
                  </Box>
                </Stack>
              </Paper>

              <Paper component="article" variant="outlined" sx={{ minWidth: 0, p: 2 }}>
                <Stack spacing={1} sx={{ minWidth: 0 }}>
                  <Typography variant="h3">Relative humidity</Typography>
                  <Box
                    role="img"
                    aria-label={`Relative humidity chart for sensor ${sensorLabel}`}
                    aria-description={humidityDescription}
                  >
                     <LineChart
                       id={`humidity-chart-${sensorId}`}
                       title="Relative humidity"
                       desc={humidityDescription}
                       disableKeyboardNavigation
                       height={chartHeight}
                      hideLegend
                      skipAnimation
                      xAxis={[
                         {
                           id: 'humidity-x-axis',
                           data: chartData.humidity.map((point) => point.x),
                           label: 'Date',
                           scaleType: 'time',
                             min: historicalDateTimeToDate(displayedRange.from),
                             max: historicalDateTimeToDate(displayedRange.to),
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
                    >
                      <AlertBinOverlay
                        intervals={binIntervals}
                        xAxisId="humidity-x-axis"
                        color={chartColors.reconstructionError}
                      />
                    </LineChart>
                  </Box>
                </Stack>
              </Paper>

              <Paper component="article" variant="outlined" sx={{ minWidth: 0, p: 2 }}>
                <Stack spacing={1} sx={{ minWidth: 0 }}>
                  <Stack direction="row" spacing={1} useFlexGap sx={{ alignItems: 'center', flexWrap: 'wrap' }}>
                    <Typography variant="h3">Anomaly score / threshold</Typography>
                    {inference.data?.points[0] === undefined ? null : (
                      <ProvenanceBadge provenance={inference.data.points[0].score_provenance} />
                    )}
                  </Stack>
                  <Box
                    role="img"
                    aria-label={`Anomaly score and threshold chart for sensor ${sensorLabel}`}
                    aria-description={scoreDescription}
                  >
                     <LineChart
                       id={`score-chart-${sensorId}`}
                       title="Anomaly score and threshold"
                       desc={scoreDescription}
                       disableKeyboardNavigation
                       height={chartHeight}
                      skipAnimation
                      xAxis={[
                         {
                           id: 'score-x-axis',
                           data: chartData.scores.map((point) => point.x),
                           label: 'Date',
                           scaleType: 'time',
                             min: historicalDateTimeToDate(displayedRange.from),
                             max: historicalDateTimeToDate(displayedRange.to),
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

              {binsUnavailable ? (
                <Alert severity="warning" variant="outlined" sx={{ minWidth: 0 }}>
                  Overlay bin alert tidak tersedia (endpoint gagal). Chart tetap
                  ditampilkan; skor dan alert lama tidak berubah.
                </Alert>
              ) : completeBinCount < 3 ? (
                <Alert severity="info" variant="outlined" sx={{ minWidth: 0 }}>
                  Konteks bin belum lengkap: {completeBinCount}/3 bin lengkap. Butuh
                  {' '}~{(3 - completeBinCount) * 51} timestamp-score lagi.
                </Alert>
              ) : null}
              <ReconstructionChart
                sensorId={sensorId}
                channel="temperature"
                telemetry={telemetryPoints}
                inference={inferencePoints}
                binIntervals={binIntervals}
                windowCount={153}
              />
              <ReconstructionChart
                sensorId={sensorId}
                channel="humidity"
                telemetry={telemetryPoints}
                inference={inferencePoints}
                binIntervals={binIntervals}
                windowCount={153}
              />
            </Box>
            <Button variant="outlined" onClick={() => setDialogOpen(true)} sx={{ alignSelf: 'flex-start' }}>
              Lihat data
            </Button>
            <BoundedDataDialog
              open={dialogOpen}
              title={`History data for ${sensorLabel}`}
              rows={rows}
              returnedCount={rows.length}
              columns={historyColumns}
              onClose={() => setDialogOpen(false)}
            />
          </Stack>
        ) : null}
      </Stack>
    </Paper>
  )
}
