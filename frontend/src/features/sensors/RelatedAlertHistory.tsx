import { Box, Paper, Stack, Typography } from '@mui/material'
import { ApiErrorPanel } from '../../components/states/ApiErrorPanel'
import { EmptyState } from '../../components/states/EmptyState'
import { PanelSkeleton } from '../../components/states/PanelSkeleton'
import {
  sensorLabels,
  type AlertStatus,
  type SensorId,
} from '../../contracts/common'
import { ProvenanceBadge } from '../../components/data/ProvenanceBadge'
import { tokens } from '../../theme/tokens'
import { useAlertEventsQuery } from '../alerts/queries'

export interface RelatedAlertHistoryProps {
  sensorId: SensorId
  from: string
  to: string
}

const eventLabels: Record<AlertStatus, string> = {
  detected: 'Detected',
  acknowledged: 'Acknowledged',
  resolved: 'Resolved',
}

const technicalTextSx = {
  fontFamily: tokens.font.data,
  fontVariantNumeric: 'tabular-nums',
  overflowWrap: 'anywhere',
} as const

export function RelatedAlertHistory({ sensorId, from, to }: RelatedAlertHistoryProps) {
  const sensorLabel = sensorLabels[sensorId]
  const alerts = useAlertEventsQuery({
    deviceId: sensorId,
    limit: 200,
  })

  return (
    <Paper component="section" aria-label="Related alert history" variant="outlined" sx={{ p: 2 }}>
      <Stack spacing={2}>
        <Stack spacing={0.5}>
          <Typography variant="h2">Related alert history</Typography>
          <Typography variant="body2" color="text.secondary">
            Lifecycle terkait untuk {sensorLabel}; rentang episode terpilih {from}–{to} tidak
            menyembunyikan event operasional yang terjadi kemudian.
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Episode time WIB; lifecycle time UTC.
          </Typography>
        </Stack>
        {alerts.data === undefined ? (
          alerts.isError ? (
            <ApiErrorPanel error={alerts.error} onRetry={() => void alerts.refetch()} />
          ) : (
            <PanelSkeleton label="Loading related alert history" />
          )
        ) : alerts.data.events.length === 0 ? (
          <EmptyState
            title="No related alert history"
             detail="Tidak ada episode pada rentang WIB yang dipilih."
          />
        ) : (
          <Stack spacing={1}>
            <Typography variant="body2">
              {alerts.data.returned_count} bounded alert events
            </Typography>
            <Box
              sx={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(min(320px, 100%), 1fr))',
                gap: 1,
              }}
            >
              {alerts.data.events.map((event) => (
                <Paper
                  component="article"
                  key={event.event_id}
                  variant="outlined"
                  sx={{ minWidth: 0, p: 4 }}
                >
                  <Stack spacing={1}>
                    <Typography variant="h3">{eventLabels[event.event_type]}</Typography>
                    <Typography variant="body2">
                      Event time (UTC): <Box component="span" sx={technicalTextSx}>{event.event_at}</Box>
                    </Typography>
                    <Typography variant="body2">
                      Alert: <Box component="span" sx={technicalTextSx}>{event.alert_id}</Box>
                    </Typography>
                    <Typography variant="body2">
                      Actor: <Box component="span" sx={technicalTextSx}>{event.actor}</Box>
                    </Typography>
                    {event.note === null ? null : (
                      <Typography variant="body2">Note: {event.note}</Typography>
                    )}
                    <ProvenanceBadge provenance={event.detection_basis} />
                  </Stack>
                </Paper>
              ))}
            </Box>
          </Stack>
        )}
      </Stack>
    </Paper>
  )
}
