import { Alert, Card, CardContent, Grid, Stack, Typography } from '@mui/material'
import { useSearchParams } from 'react-router-dom'
import { TemporalFilterBar } from '../components/filters/TemporalFilterBar'
import { ApiErrorPanel } from '../components/states/ApiErrorPanel'
import { EmptyState } from '../components/states/EmptyState'
import { PanelSkeleton } from '../components/states/PanelSkeleton'
import { PollingFailureNotice } from '../components/states/PollingFailureNotice'
import { publicDeviceId, sensorIds, sensorLabels } from '../contracts/common'
import { AlertEpisodeContext } from '../features/alerts-ui/AlertEpisodeContext'
import { AttentionQueueGrid } from '../features/alerts-ui/AttentionQueueGrid'
import { SensorMatrix } from '../features/overview/SensorMatrix'
import {
  latestSensorScore,
  type LatestSensorScore,
} from '../features/overview/useOverviewData'
import { tokens } from '../theme/tokens'
import { useDevicesQuery } from '../features/preview/queries'
import { parseLiveUrlFilters, updateLiveUrlFilters } from '../features/filters/urlFilters'
import { useLiveTelemetryData } from '../features/useLiveTelemetryData'
import { StatusSnapshot } from '../features/systemHealth/StatusSnapshot'

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
    : `+${highest.value.toFixed(4)} · ${sensorLabels[highest.deviceId]}`
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
  const [params, setParams] = useSearchParams()
  const devices = useDevicesQuery()
  const filters = parseLiveUrlFilters(params, publicDeviceId)
  const live = useLiveTelemetryData(publicDeviceId, filters)
  const { latestTelemetry, currentAlerts, health } = live
  const latestScores = [latestSensorScore(publicDeviceId, live.inference.data)]
  const activeAlerts = currentAlerts.data?.items ?? []
  const telemetrySensors = latestTelemetry.data?.sensors
  const telemetryComplete = telemetrySensors !== undefined &&
    telemetrySensors.length === sensorIds.length &&
    sensorIds.every((sensorId) => telemetrySensors.some((sensor) => sensor.device_id === sensorId))
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
      <Stack spacing={0.5}>
        <Typography variant="h1">Overview</Typography>
        <Typography color="text.secondary">Telemetri live · Asia/Jakarta (WIB)</Typography>
        <Typography color="text.secondary">
          Provenance skor dan alert ditampilkan pada setiap hasil.
        </Typography>
      </Stack>

      <TemporalFilterBar
        value={filters}
        onChange={(patch) => setParams(updateLiveUrlFilters(params, patch))}
      />

      {devices.data?.items[0]?.import_readiness === 'ready' ? null : (
        <Alert severity={devices.isError ? 'error' : 'info'}>
          {devices.isError
            ? 'Status import telemetri tidak dapat dibaca.'
            : 'Corpus telemetri belum siap. Preview tidak menggunakan fallback fixture.'}
        </Alert>
      )}

      {health.data === undefined ? (
        health.isError ? (
          <ApiErrorPanel error={health.error} onRetry={() => void health.refetch()} />
        ) : (
          <PanelSkeleton label="Loading live system health" />
        )
      ) : (
        <StatusSnapshot
          snapshot={health.data}
          displayedAt={health.dataUpdatedAt === 0
            ? health.data.checked_at
            : new Date(health.dataUpdatedAt).toISOString()}
          pollAgeSeconds={0}
        />
      )}

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
              value={telemetryAvailable === undefined ? 'Unknown' : `${telemetryAvailable}/${sensorIds.length}`}
            />
          </Grid>
          <Grid size={{ xs: 12, md: 6, lg: 3 }}>
            <SummaryCard label="Score availability" value={`${scoreAvailability}/${sensorIds.length}`} />
          </Grid>
          <Grid size={{ xs: 12, md: 6, lg: 3 }}>
            <SummaryCard
              label="Highest preview score breach"
              value={highestBreachValue}
              error={highestBreachValue.startsWith('+')}
            />
          </Grid>
        </Grid>
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
          history={live.telemetryHistory.data}
          historyError={live.telemetryHistory.isError}
          filters={filters}
          scores={latestScores}
          alerts={activeAlerts}
        />
      </Stack>

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
                  <AttentionQueueGrid alerts={activeAlerts} />
                  <AlertEpisodeContext alertId={activeAlerts[0]!.alert_id} compact />
                </Stack>
              )}
            </>
          )}
        </Stack>
      </section>

    </Stack>
  )
}
