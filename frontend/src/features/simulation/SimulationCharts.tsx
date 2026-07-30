import { Box, Paper, Stack, Typography } from '@mui/material'
import { alpha, useTheme } from '@mui/material/styles'
import { LineChart } from '@mui/x-charts/LineChart'
import { useMemo } from 'react'
import { getChartColors } from '../../components/charts/muiChartTheme'
import {
  historicalDateTimeToDate,
  type HistoricalDateTime,
} from '../../contracts/common'
import type { InferencePoint } from '../../contracts/inference'
import type { SimModel } from '../../contracts/simulation'
import type { TelemetryPoint } from '../../contracts/telemetry'
import { tokens } from '../../theme/tokens'

export interface SimulationChartsProps {
  from: HistoricalDateTime
  to: HistoricalDateTime
  telemetry: readonly TelemetryPoint[]
  inference: readonly InferencePoint[]
  model: SimModel
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

export function SimulationCharts({ from, to, telemetry, inference, model }: SimulationChartsProps) {
  const theme = useTheme()
  const colors = getChartColors(theme)
  const data = useMemo(
    () => signalChartData(from, to, telemetry, inference),
    [from, inference, telemetry, to],
  )
  const yRange = useMemo(() => {
    const values = [
      ...data.actual,
      ...data.bandBase,
      ...data.bandUpper,
    ].filter((value): value is number => value !== null && Number.isFinite(value))
    const minimum = values.length === 0 ? 0 : Math.min(...values)
    const maximum = values.length === 0 ? 1 : Math.max(...values)
    const padding = Math.max((maximum - minimum) * 0.08, 0.1)
    return [minimum - padding, maximum + padding] as const
  }, [data])
  const description = `Temperature signal from ${from} through ${to}. Blue indicates normal observations, red indicates observations inside anomalous model windows, and the gray area is the model reconstruction band.`

  return (
    <Paper component="section" aria-labelledby="active-signal-heading" variant="outlined" sx={{ p: 4, minWidth: 0 }}>
      <Stack spacing={2}>
        <Stack direction="row" spacing={2} useFlexGap sx={{ justifyContent: 'space-between', flexWrap: 'wrap' }}>
          <Stack spacing={0.5}>
            <Typography id="active-signal-heading" variant="h2" sx={{ textWrap: 'balance' }}>
              Event detail · {model.display_name}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Raw telemetry with the model&apos;s expected reconstruction range for the selected injection event.
            </Typography>
          </Stack>
          <Stack direction="row" spacing={2} useFlexGap sx={{ flexWrap: 'wrap', alignItems: 'center' }}>
            <LegendItem color={colors.temperature} label="Actual" />
            <LegendItem color={theme.palette.error.main} label="Anomalous" />
            <LegendItem color={alpha(theme.palette.text.secondary, 0.2)} label="Expected range" band />
          </Stack>
        </Stack>
        <Box role="img" aria-label="Temperature signal and reconstruction band" aria-description={description} sx={{ minWidth: 0 }}>
          <LineChart
            id="simulation-active-signal"
            title="Temperature signal and reconstruction band"
            desc={description}
            height={tokens.size.control * 8}
            hideLegend
            skipAnimation
            xAxis={[{
              id: 'simulation-time',
              data: data.timeline,
              scaleType: 'time',
              min: historicalDateTimeToDate(from),
              max: historicalDateTimeToDate(to),
              label: 'Replay time · Asia/Jakarta (WIB)',
              valueFormatter: formatTime,
            }]}
            yAxis={[{
              id: 'simulation-temperature',
              min: yRange[0],
              max: yRange[1],
              label: 'Temperature (°C)',
              width: 'auto',
              valueFormatter: (value: number) => `${value.toFixed(1)} °C`,
            }]}
            series={[
              {
                id: 'simulation-band-base',
                label: 'Expected lower bound',
                data: data.bandBase,
                area: true,
                stack: 'simulation-expected-band',
                color: 'transparent',
                connectNulls: true,
                curve: 'linear',
                showMark: false,
                disableHighlight: true,
              },
              {
                id: 'simulation-band-width',
                label: 'Expected range',
                data: data.bandWidth,
                area: true,
                stack: 'simulation-expected-band',
                color: alpha(theme.palette.text.secondary, 0.2),
                connectNulls: true,
                curve: 'linear',
                showMark: false,
                disableHighlight: true,
              },
              {
                id: 'simulation-normal',
                label: 'Actual temperature',
                data: data.normal,
                color: colors.temperature,
                connectNulls: false,
                curve: 'linear',
                showMark: false,
              },
              {
                id: 'simulation-anomaly',
                label: 'Anomalous segment',
                data: data.anomaly,
                color: theme.palette.error.main,
                connectNulls: false,
                curve: 'linear',
                showMark: ({ index }) => index % 20 === 0,
              },
            ]}
            sx={{
              '& .MuiLineElement-series-simulation-band-base, & .MuiLineElement-series-simulation-band-width': {
                stroke: 'transparent',
              },
              '& .MuiAreaElement-series-simulation-band-base': { fill: 'transparent' },
              '& .MuiAreaElement-series-simulation-band-width': {
                fill: alpha(theme.palette.text.secondary, 0.16),
              },
              '& .MuiLineElement-series-simulation-normal, & .MuiLineElement-series-simulation-anomaly': {
                strokeWidth: tokens.size.activeRule,
              },
            }}
          />
        </Box>
      </Stack>
    </Paper>
  )
}
