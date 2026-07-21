import { Box, List, ListItem, Paper, Stack, Typography } from '@mui/material'
import type { AlertStatus, SensorId } from '../../contracts/common'
import { EmptyState } from '../../components/states/EmptyState'
import { ApiErrorPanel } from '../../components/states/ApiErrorPanel'
import { PanelSkeleton } from '../../components/states/PanelSkeleton'
import { tokens } from '../../theme/tokens'
import { useAlertEventsQuery } from '../alerts/queries'

export interface AlertEventHistoryProps {
  alertId?: string
  deviceId?: SensorId
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

export function AlertEventHistory({
  alertId,
  deviceId,
  from,
  to,
}: AlertEventHistoryProps) {
  const history = useAlertEventsQuery({ alertId, deviceId, from, to, limit: 200 })

  return (
    <Paper
      component="section"
      aria-label="Immutable alert event history"
      variant="outlined"
      sx={{ p: 2 }}
    >
      <Stack spacing={2}>
        <Stack spacing={0.5}>
          <Typography variant="h2">Alert event history</Typography>
          <Typography variant="body2" color="text.secondary">
            {alertId === undefined
              ? 'All matching immutable events'
              : <>Immutable events for <Box component="span" sx={technicalTextSx}>{alertId}</Box></>}
          </Typography>
        </Stack>
        {history.data === undefined ? (
          history.isError ? (
            <ApiErrorPanel error={history.error} onRetry={() => void history.refetch()} />
          ) : (
            <PanelSkeleton label="Loading alert event history" />
          )
        ) : history.data.events.length === 0 ? (
          <EmptyState
            title="No alert events returned"
            detail="Adjust the selected sensor or time range."
          />
        ) : (
          <>
            <List component="ol" disablePadding>
              {history.data.events.map((item) => (
                <ListItem
                  component="li"
                  divider
                  disableGutters
                  alignItems="flex-start"
                  key={item.event_id}
                >
                  <Stack spacing={0.5} sx={{ minWidth: 0 }}>
                    <Typography variant="h3">{eventLabels[item.event_type]}</Typography>
                    <Typography variant="body2" sx={technicalTextSx}>{item.event_ts}</Typography>
                    <Typography variant="caption" color="text.secondary">
                      Alert <Box component="span" sx={technicalTextSx}>{item.alert_id}</Box>
                      {' · Sensor '}
                      <Box component="span" sx={technicalTextSx}>{item.device_id}</Box>
                      {' · Actor '}
                      <Box component="span" sx={technicalTextSx}>{item.actor}</Box>
                    </Typography>
                    {item.note === null ? null : (
                      <Typography variant="body2">Note: {item.note}</Typography>
                    )}
                  </Stack>
                </ListItem>
              ))}
            </List>
            {history.data.next_cursor === null ? null : (
              <Typography variant="caption" color="text.secondary">
                Additional immutable events are available beyond this bounded result.
              </Typography>
            )}
          </>
        )}
      </Stack>
    </Paper>
  )
}
