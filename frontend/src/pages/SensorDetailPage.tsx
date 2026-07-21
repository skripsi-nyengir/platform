import { Box, Paper, Stack, Typography } from '@mui/material'
import { Navigate, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { TemporalFilterBar } from '../components/filters/TemporalFilterBar'
import { ApiErrorPanel } from '../components/states/ApiErrorPanel'
import { EmptyState } from '../components/states/EmptyState'
import { PanelSkeleton } from '../components/states/PanelSkeleton'
import { PollingFailureNotice } from '../components/states/PollingFailureNotice'
import { SensorStatus } from '../components/states/SensorStatus'
import { SensorIdSchema, type SensorId } from '../contracts/common'
import {
  parseUrlFilters,
  updateUrlFilters,
  type UrlFilters,
} from '../features/filters/urlFilters'
import { useLatestTelemetryQuery } from '../features/telemetry/queries'
import { RelatedAlertHistory } from '../features/sensors/RelatedAlertHistory'
import { SensorHistoryPanel } from '../features/sensors/SensorHistoryPanel'
import { tokens } from '../theme/tokens'

const technicalTextSx = {
  fontFamily: tokens.font.data,
  fontVariantNumeric: 'tabular-nums',
  overflowWrap: 'anywhere',
} as const

function SensorSnapshot({ sensorId }: { sensorId: SensorId }) {
  const latest = useLatestTelemetryQuery(sensorId)
  const sensor = latest.data?.sensors.find((item) => item.device_id === sensorId)

  return (
    <Paper
      component="section"
      aria-label={`Sensor ${sensorId} snapshot`}
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
  const navigate = useNavigate()
  const parsedSensorId = SensorIdSchema.safeParse(rawSensorId)

  if (!parsedSensorId.success) return <Navigate to="/" replace />

  const sensorId = parsedSensorId.data
  const filters = parseUrlFilters(params, sensorId)
  const updateFilters = (patch: Partial<UrlFilters>) => {
    const next = updateUrlFilters(params, patch)
    if (patch.sensor !== undefined && patch.sensor !== sensorId) {
      void navigate({
        pathname: `/sensors/${patch.sensor}`,
        search: next.toString(),
      })
      return
    }
    setParams(next)
  }

  return (
    <Stack spacing={6}>
      <Stack spacing={0.5}>
        <Typography variant="h1">Sensor Detail &amp; History</Typography>
        <Typography color="text.secondary">
          Selected sensor: <Box component="span" sx={technicalTextSx}>{sensorId}</Box>
        </Typography>
      </Stack>
      <TemporalFilterBar
        value={{ ...filters, sensor: sensorId }}
        onChange={updateFilters}
      />
      <SensorSnapshot sensorId={sensorId} />
      <SensorHistoryPanel sensorId={sensorId} filters={filters} />
      <RelatedAlertHistory sensorId={sensorId} from={filters.from} to={filters.to} />
    </Stack>
  )
}
