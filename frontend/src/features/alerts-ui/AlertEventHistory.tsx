import { Box, Paper, Stack, Typography } from '@mui/material'
import { DataGrid, type GridColDef } from '@mui/x-data-grid'
import {
  sensorLabels,
  type AlertStatus,
  type SensorId,
} from '../../contracts/common'
import type { AlertEvent } from '../../contracts/alerts'
import { formatProvenance } from '../../components/data/provenance'
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

const pageSizeOptions = [10, 25, 50, 100]

const technicalTextSx = {
  fontFamily: tokens.font.data,
  fontVariantNumeric: 'tabular-nums',
  overflowWrap: 'anywhere',
} as const

const columns: GridColDef<AlertEvent>[] = [
  {
    field: 'event_type',
    headerName: 'Event',
    flex: 0.8,
    minWidth: 120,
    valueFormatter: (value) => eventLabels[value as AlertStatus],
  },
  {
    field: 'event_at',
    headerName: 'Event at (UTC)',
    flex: 1.3,
    minWidth: 170,
  },
  { field: 'alert_id', headerName: 'Alert ID', flex: 1.4, minWidth: 150 },
  {
    field: 'device_id',
    headerName: 'Sensor',
    flex: 0.6,
    minWidth: 80,
    valueFormatter: (value) => sensorLabels[value as SensorId],
  },
  { field: 'actor', headerName: 'Actor', flex: 1, minWidth: 130 },
  {
    field: 'detection_basis',
    headerName: 'Detection basis',
    flex: 1.2,
    minWidth: 150,
    sortable: false,
    valueFormatter: (value) =>
      formatProvenance(value as AlertEvent['detection_basis']),
  },
  {
    field: 'note',
    headerName: 'Note',
    flex: 1,
    minWidth: 120,
    sortable: false,
    valueFormatter: (value) => (value === null ? '—' : String(value)),
  },
]

export function AlertEventHistory({
  alertId,
  deviceId,
  from,
  to,
}: AlertEventHistoryProps) {
  const history = useAlertEventsQuery({
    alertId,
    ...(alertId === undefined ? { deviceId } : {}),
    limit: 200,
  })

  return (
    <Paper
      component="section"
      aria-label="Alert event history"
      variant="outlined"
      sx={{ p: 2 }}
    >
      <Stack spacing={2}>
        <Stack spacing={0.5}>
          <Typography variant="h2">Alert event history</Typography>
          <Typography variant="body2" color="text.secondary">
            {alertId === undefined
               ? 'Semua event lifecycle yang cocok.'
               : <>Event lifecycle untuk <Box component="span" sx={technicalTextSx}>{alertId}</Box>.</>}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Timestamp event dan penerimaan ditampilkan sebagai UTC.
          </Typography>
          <Typography variant="caption" color="text.secondary">
            Lifecycle tidak dibatasi oleh rentang waktu episode {from}–{to}.
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
            <DataGrid<AlertEvent>
              aria-label="Alert event history table"
              rows={history.data.events}
              columns={columns}
              getRowId={(row) => row.event_id}
              getRowHeight={() => 'auto'}
              initialState={{
                pagination: { paginationModel: { page: 0, pageSize: 10 } },
              }}
              pageSizeOptions={pageSizeOptions}
              disableRowSelectionOnClick
              autoHeight
              columnHeaderHeight={56}
              sx={{
                width: '100%',
                maxWidth: '100%',
                minWidth: 0,
                '& .MuiDataGrid-cell': {
                  alignItems: 'center',
                  lineHeight: 1.3,
                  py: 0.75,
                  overflowWrap: 'anywhere',
                  whiteSpace: 'normal',
                },
                '& .MuiDataGrid-cell[data-field="event_at"], & .MuiDataGrid-cell[data-field="alert_id"], & .MuiDataGrid-cell[data-field="device_id"], & .MuiDataGrid-cell[data-field="actor"]': {
                  fontFamily: tokens.font.data,
                  fontVariantNumeric: 'tabular-nums',
                },
                '& .MuiDataGrid-columnHeaderTitle': {
                  lineHeight: 1.15,
                  overflow: 'visible',
                  textOverflow: 'clip',
                  whiteSpace: 'normal',
                },
              }}
            />
            {history.data.next_cursor === null ? null : (
              <Typography variant="caption" color="text.secondary">
                 Event tambahan tersedia di luar hasil terbatas ini.
              </Typography>
            )}
          </>
        )}
      </Stack>
    </Paper>
  )
}
