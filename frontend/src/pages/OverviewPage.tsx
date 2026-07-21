import { Card, CardContent, Grid, Stack, Typography } from '@mui/material'
import { ApiErrorPanel } from '../components/states/ApiErrorPanel'
import { EmptyState } from '../components/states/EmptyState'
import { PanelSkeleton } from '../components/states/PanelSkeleton'
import { PollingFailureNotice } from '../components/states/PollingFailureNotice'
import { sensorIds } from '../contracts/common'
import { CurrentAlertCard } from '../features/overview/CurrentAlertCard'
import { SensorMatrix } from '../features/overview/SensorMatrix'
import {
  useOverviewData,
  type LatestSensorScore,
} from '../features/overview/useOverviewData'
import { tokens } from '../theme/tokens'

const technicalTextSx = {
  fontFamily: tokens.font.data,
  fontVariantNumeric: 'tabular-nums',
  overflowWrap: 'anywhere',
} as const

const summaryLabelSx = {
  fontWeight: 700,
  letterSpacing: '0.08em',
  textTransform: 'uppercase',
} as const

const summaryValueSx = {
  ...technicalTextSx,
  fontSize: tokens.font.size.summaryValue,
  lineHeight: tokens.font.lineHeight.summaryValue,
} as const

function highestBreach(scores: readonly LatestSensorScore[]): string {
  if (scores.some((item) => item.score === undefined || item.threshold === undefined)) {
    return 'Unknown'
  }

  let highest: { deviceId: LatestSensorScore['deviceId']; value: number } | undefined
  for (const item of scores) {
    if (item.score === undefined || item.threshold === undefined || item.isAnomaly !== true) continue
    const value = item.score - item.threshold
    if (highest === undefined || value > highest.value) highest = { deviceId: item.deviceId, value }
  }

  return highest === undefined || highest.value <= 0
    ? 'None'
    : `+${highest.value.toFixed(2)} · ${highest.deviceId}`
}

function SummaryCard({
  label,
  value,
  error = false,
}: {
  label: string
  value: string | number
  error?: boolean
}) {
  return (
    <Card variant="outlined" sx={{ height: '100%', minWidth: 0 }}>
      <CardContent>
        <Stack spacing={0.5}>
          <Typography variant="caption" color="text.secondary" sx={summaryLabelSx}>
            {label}
          </Typography>
          <Typography
            variant="h2"
            sx={{ ...summaryValueSx, color: error ? 'error.main' : 'text.primary' }}
          >
            {value}
          </Typography>
        </Stack>
      </CardContent>
    </Card>
  )
}

export function OverviewPage() {
  const { latestTelemetry, currentAlerts, latestScores } = useOverviewData()
  const activeAlerts = currentAlerts.data?.items ?? []
  const telemetrySensors = latestTelemetry.data?.sensors
  const telemetryComplete = telemetrySensors !== undefined && sensorIds.every((sensorId) =>
    telemetrySensors.some((sensor) => sensor.device_id === sensorId),
  )
  const telemetryAvailable = telemetryComplete
    ? sensorIds.filter((sensorId) => telemetrySensors.some((sensor) =>
        sensor.device_id === sensorId && sensor.availability === 'online' && sensor.ts !== null,
      )).length
    : undefined
  const scoreAvailability = latestScores.filter((score) => score.score !== undefined).length
  const alertCount = currentAlerts.data?.total
  const highestBreachValue = highestBreach(latestScores)

  return (
    <Stack spacing={5}>
      <Typography variant="h1">Overview</Typography>

      <section aria-label="Operational summary">
        <Grid container spacing={2}>
          <Grid size={{ xs: 12, md: 6, lg: 3 }}>
            <SummaryCard
              label="Active alerts"
              value={alertCount ?? 'Unknown'}
              error={alertCount !== undefined && alertCount > 0}
            />
          </Grid>
          <Grid size={{ xs: 12, md: 6, lg: 3 }}>
            <SummaryCard
              label={telemetryComplete ? 'Telemetry available' : 'Telemetry availability unknown'}
              value={telemetryAvailable === undefined ? 'Unknown' : `${telemetryAvailable}/6`}
            />
          </Grid>
          <Grid size={{ xs: 12, md: 6, lg: 3 }}>
            <SummaryCard label="Score availability" value={`${scoreAvailability}/6`} />
          </Grid>
          <Grid size={{ xs: 12, md: 6, lg: 3 }}>
            <SummaryCard
              label="Highest breach"
              value={highestBreachValue}
              error={highestBreachValue.startsWith('+')}
            />
          </Grid>
        </Grid>
      </section>

      <section aria-labelledby="attention-queue-heading">
        <Stack spacing={2}>
          <Typography id="attention-queue-heading" variant="h2">
            Attention queue
          </Typography>
          {currentAlerts.data === undefined ? (
            currentAlerts.isError ? (
              <ApiErrorPanel error={currentAlerts.error} onRetry={() => void currentAlerts.refetch()} />
            ) : (
              <PanelSkeleton label="Loading current alerts" />
            )
          ) : (
            <>
              {currentAlerts.isRefetchError ? (
                <PollingFailureNotice
                  resource="Current alerts"
                  lastUpdated={currentAlerts.data.generated_at}
                  onRetry={() => void currentAlerts.refetch()}
                />
              ) : null}
              {activeAlerts.length === 0 ? (
                <EmptyState
                  title="No active alerts"
                  detail="No detected alert currently requires acknowledgement."
                />
              ) : (
                <Stack spacing={2}>
                  {activeAlerts.map((alert) => (
                    <CurrentAlertCard alert={alert} key={alert.alert_id} />
                  ))}
                </Stack>
              )}
            </>
          )}
        </Stack>
      </section>

      <Stack spacing={2}>
        {latestTelemetry.data === undefined ? (
          latestTelemetry.isError ? (
            <ApiErrorPanel error={latestTelemetry.error} onRetry={() => void latestTelemetry.refetch()} />
          ) : (
            <PanelSkeleton label="Loading latest telemetry" />
          )
        ) : latestTelemetry.isRefetchError ? (
          <PollingFailureNotice
            resource="Latest telemetry"
            lastUpdated={latestTelemetry.data.generated_at}
            onRetry={() => void latestTelemetry.refetch()}
          />
        ) : null}
        <SensorMatrix
          telemetry={latestTelemetry.data}
          scores={latestScores}
          alerts={activeAlerts}
        />
      </Stack>
    </Stack>
  )
}
