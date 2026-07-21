import {
  Box,
  Button,
  Card,
  CardActions,
  CardContent,
  Chip,
  Grid,
  Skeleton,
  Stack,
  Typography,
} from '@mui/material'
import { useTheme } from '@mui/material/styles'
import { SparkLineChart } from '@mui/x-charts/SparkLineChart'
import { useState } from 'react'
import { Link as RouterLink } from 'react-router-dom'
import { getChartColors } from '../../components/charts/muiChartTheme'
import { buildOverviewSparklineData } from '../../components/charts/temporalOptions'
import { SensorStatus } from '../../components/states/SensorStatus'
import type { CurrentAlert } from '../../contracts/alerts'
import { sensorIds, type SensorId } from '../../contracts/common'
import type { LatestTelemetryResponse, LatestTelemetrySensor } from '../../contracts/telemetry'
import { tokens } from '../../theme/tokens'
import { useTelemetryHistoryQuery } from '../telemetry/queries'
import type { LatestSensorScore } from './useOverviewData'

export interface SensorMatrixProps {
  telemetry?: LatestTelemetryResponse
  scores: readonly LatestSensorScore[]
  alerts: readonly CurrentAlert[]
}

const technicalTextSx = {
  fontFamily: tokens.font.data,
  fontVariantNumeric: 'tabular-nums',
  overflowWrap: 'anywhere',
} as const

const definitionLabelSx = {
  fontFamily: tokens.font.ui,
  fontWeight: 600,
  m: 0,
  overflowWrap: 'anywhere',
} as const

const metricLabelSx = {
  ...definitionLabelSx,
  fontSize: tokens.font.size.caption,
  textTransform: 'uppercase',
} as const

const definitionValueSx = {
  ...technicalTextSx,
  m: 0,
} as const

const metricValueSx = {
  ...definitionValueSx,
  fontSize: tokens.font.size.sectionTitle,
  lineHeight: tokens.font.lineHeight.sectionTitle,
  fontWeight: 700,
} as const

const metadataRowSx = {
  alignItems: 'baseline',
  columnGap: 1,
  display: 'grid',
  gridTemplateColumns: 'auto minmax(0, 1fr)',
} as const

function sparklineValues(points: readonly { y: number | null }[]): number[] {
  const values = new Array<number>(points.length)
  points.forEach((point, index) => {
    if (point.y !== null) values[index] = point.y
  })
  return values
}

function SensorCard({
  sensorId,
  sensor,
  score,
  hasDetectedAlert,
}: {
  sensorId: SensorId
  sensor?: LatestTelemetrySensor
  score?: LatestSensorScore
  hasDetectedAlert: boolean
}) {
  const theme = useTheme()
  const [range] = useState(() => {
    const to = Date.now()
    return {
      from: new Date(to - 30 * 60 * 1_000).toISOString(),
      to: new Date(to).toISOString(),
    }
  })
  const history = useTelemetryHistoryQuery({
    deviceId: sensorId,
    ...range,
    bucket: 'raw',
    limit: 500,
  })
  const historyPoints = history.data?.points ?? []
  const chartColors = getChartColors(theme)
  const sparklineData = buildOverviewSparklineData({
    theme,
    sensorId,
    ...range,
    telemetry: historyPoints,
  })
  const priority = score?.isAnomaly === true || hasDetectedAlert
  const temperature = sensor?.temperature_c
  const humidity = sensor?.relative_humidity_pct
  const timestamp = sensor?.ts
  const age = sensor?.age_seconds

  return (
    <Card
      component="article"
      aria-label={`Sensor ${sensorId}`}
      variant="outlined"
      sx={{
        borderLeftColor: priority ? 'error.main' : 'divider',
        borderLeftStyle: 'solid',
        borderLeftWidth: tokens.size.activeRule,
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        minWidth: 0,
      }}
    >
      <CardContent sx={{ flexGrow: 1, minWidth: 0 }}>
        <Stack spacing={2}>
          <Stack
            direction="row"
            spacing={1}
            useFlexGap
            sx={{ alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap' }}
          >
            <Typography variant="h3">Sensor {sensorId}</Typography>
            <Stack
              direction="row"
              spacing={1}
              useFlexGap
              sx={{ alignItems: 'center', justifyContent: 'flex-end', flexWrap: 'wrap' }}
            >
              <SensorStatus
                freshness={sensor?.freshness ?? 'unknown'}
                availability={sensor?.availability ?? 'unknown'}
                statusOnly
              />
              {priority ? <Chip label="Active anomaly" color="error" size="small" /> : null}
            </Stack>
          </Stack>

          <Box
            component="dl"
            sx={{
              display: 'grid',
              gap: 2,
              gridTemplateColumns: 'repeat(2, minmax(0, 1fr))',
              m: 0,
              minWidth: 0,
            }}
          >
            <Box component="div" sx={{ minWidth: 0 }}>
              <Box component="dt" sx={{ ...metricLabelSx, color: 'primary.main' }}>Temperature</Box>
              <Box component="dd" sx={metricValueSx}>
                {temperature === null || temperature === undefined
                  ? 'Unavailable'
                  : `${temperature} °C`}
              </Box>
            </Box>
            <Box component="div" sx={{ minWidth: 0 }}>
              <Box component="dt" sx={{ ...metricLabelSx, color: 'success.main' }}>RH</Box>
              <Box component="dd" sx={metricValueSx}>
                {humidity === null || humidity === undefined ? 'Unavailable' : `${humidity} %`}
              </Box>
            </Box>
          </Box>

          <Box sx={{ height: tokens.size.sparkline, minWidth: 0 }}>
            {history.data === undefined ? (
              history.isError ? (
                <Stack
                  role="status"
                  aria-label={`Recent history unavailable for sensor ${sensorId}`}
                  sx={{ height: '100%', justifyContent: 'center' }}
                >
                  <Typography color="text.secondary" variant="body2">
                    Recent history unavailable
                  </Typography>
                </Stack>
              ) : (
                <Box
                  role="status"
                  aria-busy="true"
                  aria-label={`Loading recent history for sensor ${sensorId}`}
                  sx={{ height: '100%' }}
                >
                  <Skeleton animation={false} height="100%" variant="rounded" />
                </Box>
              )
            ) : historyPoints.length === 0 ? (
              <Stack
                role="status"
                aria-label={`No recent history available for sensor ${sensorId}`}
                sx={{ height: '100%', justifyContent: 'center' }}
              >
                <Typography color="text.secondary" variant="body2">
                  No recent history available
                </Typography>
              </Stack>
            ) : (
              <Box
                sx={{
                  display: 'grid',
                  gap: 2,
                  gridTemplateColumns: 'repeat(2, minmax(0, 1fr))',
                  height: '100%',
                  minWidth: 0,
                }}
              >
                <Box
                  role="img"
                  aria-label={`Recent Temperature history for sensor ${sensorId}`}
                  aria-description={`Recent temperature history for sensor ${sensorId}.`}
                  sx={{ height: tokens.size.sparkline, width: tokens.size.sparkline }}
                >
                  <SparkLineChart
                    color={chartColors.temperature}
                    data={sparklineValues(sparklineData.temperature)}
                    height={tokens.size.sparkline}
                    width={tokens.size.sparkline}
                    xAxis={{
                      scaleType: 'time',
                      data: sparklineData.temperature.map((point) => point.x),
                    }}
                  />
                </Box>
                <Box
                  role="img"
                  aria-label={`Recent RH history for sensor ${sensorId}`}
                  aria-description={`Recent relative humidity history for sensor ${sensorId}.`}
                  sx={{ height: tokens.size.sparkline, width: tokens.size.sparkline }}
                >
                  <SparkLineChart
                    color={chartColors.humidity}
                    data={sparklineValues(sparklineData.humidity)}
                    height={tokens.size.sparkline}
                    width={tokens.size.sparkline}
                    xAxis={{
                      scaleType: 'time',
                      data: sparklineData.humidity.map((point) => point.x),
                    }}
                  />
                </Box>
              </Box>
            )}
          </Box>

          <Box component="dl" sx={{ display: 'grid', gap: 0.5, m: 0 }}>
            <Box component="div" sx={metadataRowSx}>
              <Box component="dt" sx={definitionLabelSx}>Timestamp</Box>
              <Box component="dd" sx={definitionValueSx}>{timestamp ?? 'Unavailable'}</Box>
            </Box>
            <Box component="div" sx={metadataRowSx}>
              <Box component="dt" sx={definitionLabelSx}>Age</Box>
              <Box component="dd" sx={definitionValueSx}>
                {age === null || age === undefined ? 'Unavailable' : `${age} seconds`}
              </Box>
            </Box>
          </Box>

          <Box component="dl" sx={{ display: 'grid', gap: 0.5, m: 0 }}>
            <Box component="div" sx={metadataRowSx}>
              <Box component="dt" sx={definitionLabelSx}>State</Box>
              <Box
                component="dd"
                sx={{
                  ...definitionValueSx,
                  color: score?.isAnomaly === true ? 'error.main' : 'text.primary',
                }}
              >
                {score?.score === undefined
                  ? 'Inference unavailable'
                  : score.isAnomaly === true
                    ? 'Anomalous inference'
                    : 'Normal inference'}
              </Box>
            </Box>
            <Box component="div" sx={metadataRowSx}>
              <Box component="dt" sx={definitionLabelSx}>Score</Box>
              <Box component="dd" sx={definitionValueSx}>
                {score?.score === undefined ? (
                  <Box component="span" sx={{ fontFamily: tokens.font.ui }}>
                    No score available
                  </Box>
                ) : score.score}
              </Box>
            </Box>
            {score?.threshold === undefined ? null : (
              <Box component="div" sx={metadataRowSx}>
                <Box component="dt" sx={definitionLabelSx}>Threshold</Box>
                <Box component="dd" sx={definitionValueSx}>{score.threshold}</Box>
              </Box>
            )}
          </Box>
        </Stack>
      </CardContent>

      <CardActions sx={{ flexWrap: 'wrap', px: 2, pb: 2, pt: 0 }}>
        <Button
          component={RouterLink}
          to={`/sensors/${sensorId}?sensor=${sensorId}`}
          fullWidth={!hasDetectedAlert}
          variant="outlined"
        >
          Inspect sensor history
        </Button>
        {hasDetectedAlert ? (
          <Button component={RouterLink} to={`/alerts?sensor=${sensorId}`} variant="text">
            Review active alert
          </Button>
        ) : null}
      </CardActions>
    </Card>
  )
}

export function SensorMatrix({ telemetry, scores, alerts }: SensorMatrixProps) {
  return (
    <section aria-labelledby="sensor-matrix-heading">
      <Stack spacing={2}>
        <Typography id="sensor-matrix-heading" variant="h2">
          Sensor matrix
        </Typography>
        <Grid container spacing={2}>
          {sensorIds.map((sensorId) => (
            <Grid key={sensorId} size={{ xs: 12, md: 6, lg: 4 }} sx={{ minWidth: 0 }}>
              <SensorCard
                sensorId={sensorId}
                sensor={telemetry?.sensors.find((item) => item.device_id === sensorId)}
                score={scores.find((item) => item.deviceId === sensorId)}
                hasDetectedAlert={alerts.some((alert) => alert.device_id === sensorId)}
              />
            </Grid>
          ))}
        </Grid>
      </Stack>
    </section>
  )
}
