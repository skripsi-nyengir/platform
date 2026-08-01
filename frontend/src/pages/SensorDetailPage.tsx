import { Box, Paper, Stack, Typography } from '@mui/material'
import { Navigate, useParams, useSearchParams } from 'react-router-dom'
import { TemporalFilterBar } from '../components/filters/TemporalFilterBar'
import { ApiErrorPanel } from '../components/states/ApiErrorPanel'
import { EmptyState } from '../components/states/EmptyState'
import { PanelSkeleton } from '../components/states/PanelSkeleton'
import { PollingFailureNotice } from '../components/states/PollingFailureNotice'
import { SensorStatus } from '../components/states/SensorStatus'
import { publicDeviceId, SensorIdSchema, sensorLabels, type SensorId } from '../contracts/common'
import {
  parseLiveUrlFilters,
  resolveLiveRange,
  updateLiveUrlFilters,
  type LiveUrlFilters,
} from '../features/filters/urlFilters'
import { ActiveAlertsSection } from '../features/sensors/ActiveAlertsSection'
import { RelatedAlertHistory } from '../features/sensors/RelatedAlertHistory'
import { SensorHistoryPanel } from '../features/sensors/SensorHistoryPanel'
import { StatusSnapshot } from '../features/systemHealth/StatusSnapshot'
import { useLiveTelemetryData } from '../features/useLiveTelemetryData'
import { tokens } from '../theme/tokens'

const technicalTextSx = {
  fontFamily: tokens.font.data,
  fontVariantNumeric: 'tabular-nums',
  overflowWrap: 'anywhere',
} as const

type LiveData = ReturnType<typeof useLiveTelemetryData>

function SensorSnapshot({
  sensorId,
  latest,
}: {
  sensorId: SensorId
  latest: LiveData['latestTelemetry']
}) {
  const sensorLabel = sensorLabels[sensorId]
  const sensor = latest.data?.sensors.find((item) => item.device_id === sensorId)

  return (
    <Paper
      component="section"
      aria-label={`Sensor ${sensorLabel} snapshot`}
      variant="outlined"
      sx={{ minWidth: 0, p: 4 }}
    >
      <Stack spacing={2}>
        <Typography variant="h2">Current snapshot</Typography>
        {latest.data === undefined ? (
          latest.isError ? (
            <ApiErrorPanel error={latest.error} onRetry={() => void latest.refetch()} />
          ) : (
            <PanelSkeleton label="Loading current sensor snapshot" />
          )
        ) : sensor === undefined ? (
          <EmptyState
            title="Current sensor snapshot unavailable"
            detail="No latest telemetry record was returned for the selected sensor."
          />
        ) : (
          <Stack spacing={2}>
            {latest.isRefetchError ? (
              <PollingFailureNotice
                resource="Current sensor snapshot"
                lastUpdated={latest.data.generated_at}
                onRetry={() => void latest.refetch()}
              />
            ) : null}
            <SensorStatus
              freshness={sensor.freshness}
              availability={sensor.availability}
              ageSeconds={sensor.age_seconds ?? undefined}
              timestamp={sensor.ts ?? undefined}
            />
            <Stack
              direction="row"
              spacing={3}
              useFlexGap
              sx={{ minWidth: 0, flexWrap: 'wrap' }}
            >
              <Typography variant="body2">
                Temperature:{' '}
                <Box component="span" sx={technicalTextSx}>
                  {sensor.temperature_c === null ? 'Unavailable' : `${sensor.temperature_c} °C`}
                </Box>
              </Typography>
              <Typography variant="body2">
                RH:{' '}
                <Box component="span" sx={technicalTextSx}>
                  {sensor.relative_humidity_pct === null ? 'Unavailable' : `${sensor.relative_humidity_pct} %`}
                </Box>
              </Typography>
            </Stack>
          </Stack>
        )}
      </Stack>
    </Paper>
  )
}

export function SensorDetailPage() {
  const { sensorId: rawSensorId } = useParams()
  const [params, setParams] = useSearchParams()
  const parsedSensorId = SensorIdSchema.safeParse(rawSensorId)
  const sensorId = parsedSensorId.success ? parsedSensorId.data : publicDeviceId
  const sensorLabel = sensorLabels[sensorId]
  const filters = parseLiveUrlFilters(params, sensorId)
  const live = useLiveTelemetryData(sensorId, filters)
  const displayedRange = live.telemetryHistory.data ?? resolveLiveRange(filters)
  const updateFilters = (patch: Partial<LiveUrlFilters>) =>
    setParams(updateLiveUrlFilters(params, patch))

  if (!parsedSensorId.success) return <Navigate to="/" replace />

  return (
    <Stack spacing={6}>
      <Stack spacing={0.5}>
        <Typography variant="h1">Sensor Detail &amp; History</Typography>
        <Typography color="text.secondary">
          Selected sensor: <Box component="span" sx={technicalTextSx}>{sensorLabel}</Box>
        </Typography>
        <Typography color="text.secondary" variant="body2">
          Telemetri live · Asia/Jakarta (WIB)
        </Typography>
        <Typography color="text.secondary" variant="body2">
          Skor berbadge sesuai provenance API; histori menampilkan satu versi model.
        </Typography>
      </Stack>
      <TemporalFilterBar
        value={filters}
        onChange={updateFilters}
      />
      <SensorSnapshot sensorId={sensorId} latest={live.latestTelemetry} />
      {live.health.data === undefined ? (
        live.health.isError ? (
          <ApiErrorPanel error={live.health.error} onRetry={() => void live.health.refetch()} />
        ) : (
          <PanelSkeleton label="Loading live system health" />
        )
      ) : (
        <StatusSnapshot
          snapshot={live.health.data}
          displayedAt={live.health.dataUpdatedAt === 0
            ? live.health.data.checked_at
            : new Date(live.health.dataUpdatedAt).toISOString()}
          pollAgeSeconds={0}
        />
      )}
      <SensorHistoryPanel
        sensorId={sensorId}
        filters={filters}
        telemetry={live.telemetryHistory}
        inference={live.inference}
        alertEvents={live.alertEvents}
        postInferenceBins={live.postInferenceBins}
      />
      {live.currentAlerts.data?.items.length
        ? <ActiveAlertsSection alerts={live.currentAlerts.data.items} />
        : null}
      <RelatedAlertHistory
        sensorId={sensorId}
        from={displayedRange.from}
        to={displayedRange.to}
        alerts={live.alertEvents}
      />
    </Stack>
  )
}
