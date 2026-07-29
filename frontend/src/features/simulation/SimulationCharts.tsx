import { Box, Card, CardContent, Grid, Paper, Stack, Typography, useMediaQuery } from '@mui/material'
import { alpha, useTheme } from '@mui/material/styles'
import { LineChart } from '@mui/x-charts/LineChart'
import { useMemo } from 'react'
import { getChartColors } from '../../components/charts/muiChartTheme'
import {
  historicalDateTimeToDate,
  type HistoricalDateTime,
} from '../../contracts/common'
import type { InferencePoint } from '../../contracts/inference'
import type { SimInjectionEvent } from '../../contracts/injection'
import type { SimModel } from '../../contracts/simulation'
import type { TelemetryPoint } from '../../contracts/telemetry'
import { tokens } from '../../theme/tokens'
import { classifyDetectionWindows } from './classification'

export interface SimulationModelResult {
  model: SimModel
  inference: readonly InferencePoint[]
}

export interface SimulationChartsProps {
  from: HistoricalDateTime
  to: HistoricalDateTime
  telemetry: readonly TelemetryPoint[]
  modelResults: readonly SimulationModelResult[]
  activeModelVersion: string
  injections: readonly SimInjectionEvent[]
}

interface SignalChartData {
  timeline: Date[]
  actual: (number | null)[]
  normal: (number | null)[]
  anomaly: (number | null)[]
  bandBase: (number | null)[]
  bandWidth: (number | null)[]
  bandUpper: (number | null)[]
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

function interpolate(samples: readonly (readonly [number, number])[], target: number): number | null {
  if (samples.length === 0 || target < samples[0][0] || target > samples[samples.length - 1][0]) return null
  const upperIndex = samples.findIndex(([timestamp]) => timestamp >= target)
  const upper = samples[upperIndex]
  if (upper === undefined) return null
  if (upper[0] === target || upperIndex === 0) return upper[1]
  const lower = samples[upperIndex - 1]
  const ratio = (target - lower[0]) / (upper[0] - lower[0])
  return lower[1] + (upper[1] - lower[1]) * ratio
}

function signalChartData(
  from: HistoricalDateTime,
  to: HistoricalDateTime,
  telemetry: readonly TelemetryPoint[],
  inference: readonly InferencePoint[],
): SignalChartData {
  const timelineKeys = [...new Set([
    from,
    to,
    ...telemetry.map((point) => point.ts),
    ...inference.flatMap((point) => [point.window_start_ts, point.window_end_ts, point.score_ts]),
  ])].toSorted()
  const telemetrySamples = telemetry
    .flatMap((point) => point.temperature_c === null
      ? []
      : [[historicalDateTimeToDate(point.ts).getTime(), point.temperature_c] as const])
    .toSorted((left, right) => left[0] - right[0])
  const reconstructionSamples = inference.flatMap((point) =>
    point.recon_temperature_c === null || point.recon_temperature_c === undefined
      ? []
      : [[historicalDateTimeToDate(point.score_ts).getTime(), point.recon_temperature_c] as const],
  ).toSorted((left, right) => left[0] - right[0])
  const bandSamples = inference.flatMap((point) =>
    point.band_half_temperature_c === null || point.band_half_temperature_c === undefined
      ? []
      : [[historicalDateTimeToDate(point.score_ts).getTime(), point.band_half_temperature_c] as const],
  ).toSorted((left, right) => left[0] - right[0])
  const actual = timelineKeys.map((timestamp) => interpolate(
    telemetrySamples,
    historicalDateTimeToDate(timestamp).getTime(),
  ))
  const bandBase = timelineKeys.map((timestamp) => {
    const target = historicalDateTimeToDate(timestamp).getTime()
    const reconstruction = interpolate(reconstructionSamples, target)
    const halfBand = interpolate(bandSamples, target)
    return reconstruction === null || halfBand === null ? null : reconstruction - halfBand
  })
  const bandWidth = timelineKeys.map((timestamp) => {
    const halfBand = interpolate(bandSamples, historicalDateTimeToDate(timestamp).getTime())
    return halfBand === null ? null : halfBand * 2
  })
  const anomalousAt = (timestamp: HistoricalDateTime) => inference.some((point) =>
    point.is_anomaly && point.window_start_ts <= timestamp && point.window_end_ts >= timestamp,
  )

  return {
    timeline: timelineKeys.map(historicalDateTimeToDate),
    actual,
    normal: actual.map((value, index) => anomalousAt(timelineKeys[index]) ? null : value),
    anomaly: actual.map((value, index) => anomalousAt(timelineKeys[index]) ? value : null),
    bandBase,
    bandWidth,
    bandUpper: bandBase.map((value, index) => value === null ? null : value + (bandWidth[index] ?? 0)),
  }
}

function LegendItem({ color, label, band = false }: { color: string; label: string; band?: boolean }) {
  return (
    <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
      <Box
        aria-hidden="true"
        sx={{
          width: tokens.size.control / 2,
          height: band ? tokens.size.control / 4 : tokens.size.activeRule,
          borderRadius: tokens.radius.sm,
          backgroundColor: color,
        }}
      />
      <Typography variant="caption" color="text.secondary">{label}</Typography>
    </Stack>
  )
}

function SignalBandChart({
  id,
  data,
  from,
  to,
  height,
  yRange,
  compact,
  showXAxisLabel,
}: {
  id: string
  data: SignalChartData
  from: HistoricalDateTime
  to: HistoricalDateTime
  height: number
  yRange: readonly [number, number]
  compact: boolean
  showXAxisLabel: boolean
}) {
  const theme = useTheme()
  const colors = getChartColors(theme)
  const description = `Temperature signal from ${from} through ${to}. Blue indicates normal observations, red indicates observations inside anomalous model windows, and the gray area is the model reconstruction band.`

  return (
    <Box role="img" aria-label="Temperature signal and reconstruction band" aria-description={description} sx={{ minWidth: 0 }}>
      <LineChart
        id={id}
        title="Temperature signal and reconstruction band"
        desc={description}
        height={height}
        hideLegend
        skipAnimation
        xAxis={[{
          id: `${id}-time`,
          data: data.timeline,
          scaleType: 'time',
          min: historicalDateTimeToDate(from),
          max: historicalDateTimeToDate(to),
          label: showXAxisLabel && !compact ? 'Replay time · Asia/Jakarta (WIB)' : undefined,
          tickNumber: compact ? 3 : undefined,
          valueFormatter: formatTime,
        }]}
        yAxis={[{
          id: `${id}-temperature`,
          min: yRange[0],
          max: yRange[1],
          label: compact ? undefined : 'Temperature (°C)',
          width: compact ? tokens.size.sidebarCompact : 'auto',
          valueFormatter: (value: number) => `${value.toFixed(1)} °C`,
        }]}
        series={[
          {
            id: `${id}-band-base`,
            label: 'Expected lower bound',
            data: data.bandBase,
            area: true,
            stack: `${id}-expected-band`,
            color: 'transparent',
            connectNulls: true,
            curve: 'linear',
            showMark: false,
            disableHighlight: true,
          },
          {
            id: `${id}-band-width`,
            label: 'Expected range',
            data: data.bandWidth,
            area: true,
            stack: `${id}-expected-band`,
            color: alpha(theme.palette.text.secondary, 0.2),
            connectNulls: true,
            curve: 'linear',
            showMark: false,
            disableHighlight: true,
          },
          {
            id: `${id}-normal`,
            label: 'Actual temperature',
            data: data.normal,
            color: colors.temperature,
            connectNulls: false,
            curve: 'linear',
            showMark: false,
          },
          {
            id: `${id}-anomaly`,
            label: 'Anomalous segment',
            data: data.anomaly,
            color: theme.palette.error.main,
            connectNulls: false,
            curve: 'linear',
            showMark: true,
          },
        ]}
        sx={{
          [`& .MuiLineElement-series-${id}-band-base, & .MuiLineElement-series-${id}-band-width`]: {
            stroke: 'transparent',
          },
          [`& .MuiAreaElement-series-${id}-band-base`]: { fill: 'transparent' },
          [`& .MuiAreaElement-series-${id}-band-width`]: {
            fill: alpha(theme.palette.text.secondary, 0.16),
          },
          [`& .MuiLineElement-series-${id}-normal, & .MuiLineElement-series-${id}-anomaly`]: {
            strokeWidth: tokens.size.activeRule,
          },
        }}
      />
    </Box>
  )
}

export function SimulationCharts({
  from,
  to,
  telemetry,
  modelResults,
  activeModelVersion,
  injections,
}: SimulationChartsProps) {
  const theme = useTheme()
  const compactChart = useMediaQuery(theme.breakpoints.down('sm'))
  const colors = getChartColors(theme)
  const results = useMemo(() => modelResults.map((result) => ({
    ...result,
    chart: signalChartData(from, to, telemetry, result.inference),
  })), [from, modelResults, telemetry, to])
  const activeResult = results.find((result) => result.model.version === activeModelVersion) ?? results[0]
  const classification = useMemo(() => activeResult === undefined
    ? undefined
    : classifyDetectionWindows(
      injections.filter((event) => event.start_ts <= to && event.end_ts >= from),
      activeResult.inference,
    ), [activeResult, from, injections, to])
  const yRange = useMemo(() => {
    const values = results.flatMap((result) => [
      ...result.chart.actual,
      ...result.chart.bandBase,
      ...result.chart.bandUpper,
    ]).filter((value): value is number => value !== null && Number.isFinite(value))
    const minimum = values.length === 0 ? 0 : Math.min(...values)
    const maximum = values.length === 0 ? 1 : Math.max(...values)
    const padding = Math.max((maximum - minimum) * 0.08, 0.1)
    return [minimum - padding, maximum + padding] as const
  }, [results])

  if (activeResult === undefined || classification === undefined) return null

  const metricCards = [
    ['Event-hit rate', classification.metrics.eventHitRate, `${classification.counts.caughtEvents}/${classification.counts.totalEvents} injected events caught`],
    ['Precision', classification.metrics.precision, `${classification.counts.tp} TP / ${classification.counts.fp} FP windows`],
    ['Recall', classification.metrics.recall, `${classification.counts.tp} TP / ${classification.counts.fn} FN windows`],
    ['FPR', classification.metrics.falsePositiveRate, `${classification.counts.fp} FP / ${classification.counts.tn} TN windows`],
  ] as const

  return (
    <Stack spacing={3}>
      <Paper component="section" aria-labelledby="active-signal-heading" variant="outlined" sx={{ p: { xs: 2, sm: 4 }, minWidth: 0 }}>
        <Stack spacing={2}>
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} sx={{ justifyContent: 'space-between' }}>
            <Stack spacing={0.5}>
              <Typography id="active-signal-heading" variant="h2" sx={{ textWrap: 'balance' }}>
                Active model · {activeResult.model.display_name}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Actual temperature against the model&apos;s expected reconstruction range.
              </Typography>
            </Stack>
            <Stack direction="row" spacing={2} useFlexGap sx={{ flexWrap: 'wrap', alignItems: 'center' }}>
              <LegendItem color={colors.temperature} label="Actual" />
              <LegendItem color={theme.palette.error.main} label="Anomalous" />
              <LegendItem color={alpha(theme.palette.text.secondary, 0.2)} label="Expected range" band />
            </Stack>
          </Stack>
          <SignalBandChart
            id="simulation-active-signal"
            data={activeResult.chart}
            from={from}
            to={to}
            height={tokens.size.control * 8}
            yRange={yRange}
            compact={compactChart}
            showXAxisLabel
          />
        </Stack>
      </Paper>

      <Stack component="section" aria-labelledby="model-comparison-heading" spacing={2}>
        <Stack spacing={0.5}>
          <Typography id="model-comparison-heading" variant="h2">Model comparison</Typography>
          <Typography variant="body2" color="text.secondary">
            Identical replay window and temperature scale across all artifact models.
          </Typography>
        </Stack>
        <Grid container spacing={2}>
          {results.map((result) => (
            <Grid key={result.model.version} size={{ xs: 12, lg: 4 }}>
              <Card component="article" variant="outlined" sx={{ height: '100%', minWidth: 0 }}>
                <CardContent sx={{ p: { xs: 2, sm: 3 }, '&:last-child': { pb: { xs: 2, sm: 3 } } }}>
                  <Stack spacing={1}>
                    <Typography variant="h3">{result.model.display_name}</Typography>
                    <SignalBandChart
                      id={`simulation-${result.model.model_key}`}
                      data={result.chart}
                      from={from}
                      to={to}
                      height={tokens.size.control * 5}
                      yRange={yRange}
                      compact
                      showXAxisLabel={false}
                    />
                  </Stack>
                </CardContent>
              </Card>
            </Grid>
          ))}
        </Grid>
      </Stack>

      <Paper component="section" aria-labelledby="simulation-summary-heading" variant="outlined" sx={{ p: { xs: 2, sm: 4 } }}>
        <Stack spacing={2}>
          <Stack spacing={0.5}>
            <Typography id="simulation-summary-heading" variant="h2">Active-model summary</Typography>
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
