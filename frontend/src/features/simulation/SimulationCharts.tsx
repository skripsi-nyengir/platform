import { Box, Card, CardContent, Grid, Paper, Stack, Typography, useMediaQuery } from '@mui/material'
import { useTheme } from '@mui/material/styles'
import { LineChart } from '@mui/x-charts/LineChart'
import { useMemo } from 'react'
import { getChartColors } from '../../components/charts/muiChartTheme'
import {
  historicalDateTimeToDate,
  type HistoricalDateTime,
} from '../../contracts/common'
import type { InferencePoint } from '../../contracts/inference'
import type { SimInjectionEvent } from '../../contracts/injection'
import type { TelemetryPoint } from '../../contracts/telemetry'
import { tokens } from '../../theme/tokens'
import { classifyDetectionWindows } from './classification'

export interface SimulationChartsProps {
  from: HistoricalDateTime
  to: HistoricalDateTime
  telemetry: readonly TelemetryPoint[]
  inference: readonly InferencePoint[]
  injections: readonly SimInjectionEvent[]
}

const technicalTextSx = {
  fontFamily: tokens.font.data,
  fontVariantNumeric: 'tabular-nums',
} as const

function formatPercent(value: number): string {
  return value.toLocaleString('id-ID', {
    style: 'percent',
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  })
}

function formatTime(value: Date): string {
  return value.toLocaleTimeString('id-ID', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
}

function extrema(values: readonly (number | null)[]): readonly [number, number] | undefined {
  const finite = values.filter((value): value is number => value !== null && Number.isFinite(value))
  return finite.length === 0 ? undefined : [Math.min(...finite), Math.max(...finite)]
}

function LegendItem({ color, label }: { color: string; label: string }) {
  return (
    <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
      <Box
        aria-hidden="true"
        sx={{
          width: tokens.size.control / 2,
          height: tokens.size.activeRule,
          borderRadius: tokens.radius.sm,
          backgroundColor: color,
        }}
      />
      <Typography variant="caption" color="text.secondary">{label}</Typography>
    </Stack>
  )
}

export function SimulationCharts({
  from,
  to,
  telemetry,
  inference,
  injections,
}: SimulationChartsProps) {
  const theme = useTheme()
  const compactChart = useMediaQuery(theme.breakpoints.down('sm'))
  const colors = getChartColors(theme)
  const data = useMemo(() => {
    const visibleInjections = injections.filter((event) => event.start_ts <= to && event.end_ts >= from)
    const classification = classifyDetectionWindows(visibleInjections, inference)
    const timelineKeys = [...new Set([
      from,
      to,
      ...telemetry.map((point) => point.ts),
      ...inference.flatMap((point) => [
        point.window_start_ts,
        point.window_end_ts,
        point.score_ts,
      ]),
      ...visibleInjections.flatMap((event) => [event.start_ts, event.end_ts]),
    ])].toSorted()
    const telemetryByTs = new Map(telemetry.map((point) => [point.ts, point]))
    const inferenceByTs = new Map(inference.map((point) => [point.score_ts, point]))

    return {
      classification,
      timeline: timelineKeys.map(historicalDateTimeToDate),
      temperature: timelineKeys.map((ts) => telemetryByTs.get(ts)?.temperature_c ?? null),
      humidity: timelineKeys.map((ts) => telemetryByTs.get(ts)?.relative_humidity_pct ?? null),
      scores: timelineKeys.map((ts) => inferenceByTs.get(ts)?.score ?? null),
      thresholds: timelineKeys.map((ts) => inferenceByTs.get(ts)?.threshold ?? null),
      anomalyScores: timelineKeys.map((ts) => {
        const point = inferenceByTs.get(ts)
        return point?.is_anomaly === true ? point.score : null
      }),
      injectionTp: timelineKeys.map((ts) => classification.injections.some((item) =>
        item.classification === 'tp' && item.event.start_ts <= ts && item.event.end_ts >= ts,
      ) ? 1 : null),
      injectionFn: timelineKeys.map((ts) => classification.injections.some((item) =>
        item.classification === 'fn' && item.event.start_ts <= ts && item.event.end_ts >= ts,
      ) ? 1 : null),
      detectionTp: timelineKeys.map((ts) => classification.detections.some((item) =>
        item.classification === 'tp' &&
        item.point.window_start_ts <= ts &&
        item.point.window_end_ts >= ts,
      ) ? 0 : null),
      detectionFp: timelineKeys.map((ts) => classification.detections.some((item) =>
        item.classification === 'fp' &&
        item.point.window_start_ts <= ts &&
        item.point.window_end_ts >= ts,
      ) ? 0 : null),
    }
  }, [from, inference, injections, telemetry, to])
  const axisFrom = historicalDateTimeToDate(from)
  const axisTo = historicalDateTimeToDate(to)
  const sharedXAxis = (id: string) => [{
    id,
    data: data.timeline,
    scaleType: 'time' as const,
    min: axisFrom,
    max: axisTo,
    label: compactChart ? undefined : 'Replay time · Asia/Jakarta (WIB)',
    tickNumber: compactChart ? 3 : undefined,
    valueFormatter: formatTime,
  }]
  const chartHeight = tokens.size.control * 7
  const scoreFormatter = (value: number | null) => value === null ? '—' : value.toExponential(4)
  const temperatureRange = extrema(data.temperature)
  const humidityRange = extrema(data.humidity)
  const scoreRange = extrema(data.scores)
  const telemetryDescription = `${telemetry.length} telemetry samples across the one-hour replay. Temperature ranges from ${temperatureRange?.[0].toFixed(2) ?? 'unavailable'} to ${temperatureRange?.[1].toFixed(2) ?? 'unavailable'} degrees Celsius; relative humidity ranges from ${humidityRange?.[0].toFixed(2) ?? 'unavailable'} to ${humidityRange?.[1].toFixed(2) ?? 'unavailable'} percent.`
  const scoreDescription = `${inference.length} inference windows; ${data.classification.counts.tp + data.classification.counts.fp} are above threshold. Scores range from ${scoreFormatter(scoreRange?.[0] ?? null)} to ${scoreFormatter(scoreRange?.[1] ?? null)}; the plotted threshold is ${scoreFormatter(inference[0]?.threshold ?? null)}.`
  const ribbonDescription = `${data.classification.counts.totalEvents} injected intervals: ${data.classification.counts.caughtEvents} caught and ${data.classification.counts.totalEvents - data.classification.counts.caughtEvents} missed. Model windows include ${data.classification.counts.tp} true positives and ${data.classification.counts.fp} false-alarm windows. Green indicates caught overlap, red missed injection, and amber false alarm.`
  const metricCards = [
    ['Event-hit rate', data.classification.metrics.eventHitRate, `${data.classification.counts.caughtEvents}/${data.classification.counts.totalEvents} injected events caught`],
    ['Precision', data.classification.metrics.precision, `${data.classification.counts.tp} TP / ${data.classification.counts.fp} FP windows`],
    ['Recall', data.classification.metrics.recall, `${data.classification.counts.tp} TP / ${data.classification.counts.fn} FN windows`],
    ['FPR', data.classification.metrics.falsePositiveRate, `${data.classification.counts.fp} FP / ${data.classification.counts.tn} TN windows`],
  ] as const

  return (
    <Stack spacing={3}>
      <Paper component="section" aria-labelledby="telemetry-chart-heading" variant="outlined" sx={{ p: 4, minWidth: 0 }}>
        <Stack spacing={2}>
          <Stack spacing={0.5}>
            <Typography id="telemetry-chart-heading" variant="h2" sx={{ textWrap: 'balance' }}>
              Injected telemetry
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ textWrap: 'pretty' }}>
              Physical-unit replay values from the injected corpus.
            </Typography>
          </Stack>
          <Box role="img" aria-label="Injected temperature and relative humidity chart" aria-description={telemetryDescription} sx={{ minWidth: 0 }}>
            <LineChart
              id="simulation-telemetry"
              title="Injected temperature and relative humidity"
              desc={telemetryDescription}
              height={chartHeight}
              skipAnimation
              xAxis={sharedXAxis('simulation-shared-time-telemetry')}
              yAxis={[
                { id: 'temperature', label: compactChart ? undefined : 'Temperature (°C)', width: compactChart ? tokens.size.control : 'auto' },
                { id: 'humidity', label: compactChart ? undefined : 'Relative humidity (%)', position: 'right', width: compactChart ? tokens.size.control : 'auto' },
              ]}
              series={[
                {
                  id: 'temperature',
                  label: 'Temperature (°C)',
                  data: data.temperature,
                  color: colors.temperature,
                  connectNulls: true,
                  curve: 'linear',
                  showMark: false,
                  yAxisId: 'temperature',
                },
                {
                  id: 'humidity',
                  label: 'Relative humidity (%)',
                  data: data.humidity,
                  color: colors.humidity,
                  connectNulls: true,
                  curve: 'linear',
                  showMark: false,
                  yAxisId: 'humidity',
                },
              ]}
            />
          </Box>
        </Stack>
      </Paper>

      <Paper component="section" aria-labelledby="score-chart-heading" variant="outlined" sx={{ p: 4, minWidth: 0 }}>
        <Stack spacing={2}>
          <Stack spacing={0.5}>
            <Typography id="score-chart-heading" variant="h2" sx={{ textWrap: 'balance' }}>
              Score vs threshold
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ textWrap: 'pretty' }}>
              Anomaly marks show windows where the artifact score exceeds its stored threshold.
            </Typography>
          </Stack>
          <Box role="img" aria-label="Artifact score and threshold chart" aria-description={scoreDescription} sx={{ minWidth: 0 }}>
            <LineChart
              id="simulation-score"
              title="Artifact score versus threshold"
              desc={scoreDescription}
              height={chartHeight}
              skipAnimation
              xAxis={sharedXAxis('simulation-shared-time-score')}
              yAxis={[{ id: 'score', label: compactChart ? undefined : 'Artifact score', width: compactChart ? tokens.size.sidebarCompact : 'auto', valueFormatter: scoreFormatter }]}
              series={[
                {
                  id: 'score',
                  label: 'Score',
                  data: data.scores,
                  color: colors.anomalyScore,
                  connectNulls: true,
                  curve: 'linear',
                  showMark: false,
                  valueFormatter: scoreFormatter,
                },
                {
                  id: 'threshold',
                  label: 'Threshold',
                  data: data.thresholds,
                  color: colors.threshold,
                  connectNulls: true,
                  curve: 'linear',
                  showMark: false,
                  valueFormatter: scoreFormatter,
                },
                {
                  id: 'anomaly',
                  label: 'Above threshold',
                  data: data.anomalyScores,
                  color: theme.palette.error.main,
                  connectNulls: false,
                  curve: 'linear',
                  showMark: true,
                  valueFormatter: scoreFormatter,
                },
              ]}
            />
          </Box>
        </Stack>
      </Paper>

      <Paper component="section" aria-labelledby="ribbon-chart-heading" variant="outlined" sx={{ p: 4, minWidth: 0 }}>
        <Stack spacing={2}>
          <Stack spacing={0.5}>
            <Typography id="ribbon-chart-heading" variant="h2" sx={{ textWrap: 'balance' }}>
              Detection ribbon
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ textWrap: 'pretty' }}>
              Ground truth marks injected intervals; model detections mark anomaly windows that overlap or miss them.
            </Typography>
          </Stack>
          <Stack direction="row" spacing={2} useFlexGap sx={{ flexWrap: 'wrap' }}>
            <LegendItem color={theme.palette.success.main} label="TP · caught" />
            <LegendItem color={theme.palette.error.main} label="FN · missed" />
            <LegendItem color={theme.palette.warning.main} label="FP · false alarm" />
          </Stack>
          <Box role="img" aria-label="Ground truth and model detection ribbon" aria-description={ribbonDescription} sx={{ minWidth: 0 }}>
            <LineChart
              id="simulation-ribbon"
              title="Ground truth and model detection ribbon"
              desc={ribbonDescription}
              height={chartHeight}
              skipAnimation
              xAxis={sharedXAxis('simulation-shared-time-ribbon')}
              yAxis={[{
                id: 'ribbon',
                min: -0.25,
                max: 1.25,
                tickNumber: 2,
                width: 'auto',
                valueFormatter: (value: number) => value >= 0.5 ? 'Injected' : 'Detected',
              }]}
              series={[
                { id: 'injection-tp', label: 'Injected · caught (TP)', data: data.injectionTp, color: theme.palette.success.main, connectNulls: false, curve: 'linear', showMark: false },
                { id: 'injection-fn', label: 'Injected · missed (FN)', data: data.injectionFn, color: theme.palette.error.main, connectNulls: false, curve: 'linear', showMark: false },
                { id: 'detection-tp', label: 'Detected · overlap (TP)', data: data.detectionTp, color: theme.palette.success.main, connectNulls: false, curve: 'linear', showMark: false },
                { id: 'detection-fp', label: 'Detected · false alarm (FP)', data: data.detectionFp, color: theme.palette.warning.main, connectNulls: false, curve: 'linear', showMark: false },
              ]}
              sx={{ '& .MuiLineElement-root': { strokeWidth: tokens.size.activeRule * 2 } }}
            />
          </Box>
        </Stack>
      </Paper>

      <Paper component="section" aria-labelledby="simulation-summary-heading" variant="outlined" sx={{ p: 4 }}>
        <Stack spacing={2}>
          <Stack spacing={0.5}>
            <Typography id="simulation-summary-heading" variant="h2" sx={{ textWrap: 'balance' }}>
              Summary figures
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Event-hit is interval-level; precision, recall, and FPR are computed across replay windows.
            </Typography>
          </Stack>
          <Grid container spacing={2}>
            {metricCards.map(([label, value, detail]) => (
              <Grid key={label} size={{ xs: 12, sm: 6, lg: 3 }}>
                <Card variant="outlined" sx={{ height: '100%' }}>
                  <CardContent>
                    <Stack spacing={0.5}>
                      <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                        {label}
                      </Typography>
                      <Typography variant="h2" sx={{ ...technicalTextSx, fontSize: tokens.font.size.summaryValue, lineHeight: tokens.font.lineHeight.summaryValue }}>
                        {formatPercent(value)}
                      </Typography>
                      <Typography variant="body2" color="text.secondary" sx={technicalTextSx}>
                        {detail}
                      </Typography>
                    </Stack>
                  </CardContent>
                </Card>
              </Grid>
            ))}
          </Grid>
        </Stack>
      </Paper>
    </Stack>
  )
}
