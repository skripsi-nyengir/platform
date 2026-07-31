import { DataGrid, type GridColDef } from '@mui/x-data-grid'
import type { CurrentAlert, CurrentAlertsResponse } from '../../contracts/alerts'
import { sensorLabels } from '../../contracts/common'
import { formatWibDateTime } from '../../lib/dateTime'
import { tokens } from '../../theme/tokens'
import { AlertLifecycleActions } from './AlertLifecycleActions'
import { formatProvenance } from '../../components/data/provenance'

export interface AlertsGridProps {
  response: CurrentAlertsResponse
  page: number
  onPageChange: (page: number) => void
  onSelectAlert: (alertId: string) => void
  onPageSizeChange?: (pageSize: number) => void
}

const pageSizeOptions = [10, 25, 50, 100]

const columnWidths = {
  alert_id: { flex: 1.25, minWidth: 130 },
  device_id: { flex: 0.7, minWidth: 80 },
  status: { flex: 0.9, minWidth: 95 },
  latest_event_ts: { flex: 1.5, minWidth: 150 },
  detection_basis: { flex: 1.5, minWidth: 180 },
  actions: { flex: 1.65, minWidth: 240 },
} as const

const columns: GridColDef<CurrentAlert>[] = [
  { field: 'alert_id', headerName: 'Alert ID', ...columnWidths.alert_id },
  {
    field: 'device_id',
    headerName: 'Sensor',
    ...columnWidths.device_id,
    valueFormatter: (value) => sensorLabels[value as CurrentAlert['device_id']],
  },
  {
    field: 'status',
    headerName: 'Status',
    ...columnWidths.status,
    renderCell: ({ row }) => row.status === 'detected' ? 'Active' : row.status,
  },
  {
    field: 'episode_start_ts',
    headerName: 'Episode start (WIB)',
    ...columnWidths.latest_event_ts,
    valueFormatter: (value) => formatWibDateTime(value as CurrentAlert['episode_start_ts']),
  },
  {
    field: 'episode_end_ts',
    headerName: 'Episode end (WIB)',
    ...columnWidths.latest_event_ts,
    valueFormatter: (value) => formatWibDateTime(value as CurrentAlert['episode_end_ts']),
  },
  { field: 'anomalous_window_count', headerName: 'Windows', minWidth: 90 },
  {
    field: 'detection_basis',
    headerName: 'Detection basis',
    ...columnWidths.detection_basis,
    sortable: false,
    valueFormatter: (value) => formatProvenance(value as CurrentAlert['detection_basis']),
  },
  {
    field: 'actions',
    headerName: 'Action',
    ...columnWidths.actions,
    sortable: false,
    filterable: false,
    renderCell: ({ row }) => <AlertLifecycleActions alert={row} />,
  },
]

export function AlertsGrid({
  response,
  page,
  onPageChange,
  onSelectAlert,
  onPageSizeChange,
}: AlertsGridProps) {
  return (
    <DataGrid<CurrentAlert>
      aria-label="Current alerts"
      rows={response.items}
      columns={columns}
      getRowId={(row) => row.alert_id}
      getRowHeight={() => 'auto'}
      rowCount={response.total}
      pagination
      paginationMode="server"
      paginationModel={{ page: page - 1, pageSize: response.page_size }}
      pageSizeOptions={pageSizeOptions}
      onPaginationModelChange={(model) => {
        if (model.pageSize !== response.page_size) {
          if (model.pageSize <= 100) onPageSizeChange?.(model.pageSize)
          return
        }
        const nextPage = model.page + 1
        if (nextPage !== page) onPageChange(nextPage)
      }}
      onRowClick={({ row }) => onSelectAlert(row.alert_id)}
      onRowSelectionModelChange={(model) => {
        if (model.type !== 'include') return
        const selectedId = model.ids.values().next().value
        if (selectedId !== undefined) onSelectAlert(String(selectedId))
      }}
      onCellKeyDown={(params, event) => {
        if (params.field === 'actions' || (event.key !== 'Enter' && event.key !== ' ')) return
        event.preventDefault()
        onSelectAlert(params.row.alert_id)
      }}
      disableMultipleRowSelection
      disableRowSelectionOnClick
      autoHeight
      columnHeaderHeight={64}
      sx={{
        width: '100%',
        maxWidth: '100%',
        minWidth: 0,
        '& .MuiDataGrid-cell': {
          alignItems: 'center',
          lineHeight: 1.3,
          py: 0.5,
          overflowWrap: 'anywhere',
          whiteSpace: 'normal',
        },
        '& .MuiDataGrid-cell[data-field="actions"]': {
          alignItems: 'stretch',
          overflow: 'visible',
          py: 1,
        },
        '& .MuiDataGrid-cell[data-field="alert_id"], & .MuiDataGrid-cell[data-field="device_id"], & .MuiDataGrid-cell[data-field="episode_start_ts"], & .MuiDataGrid-cell[data-field="episode_end_ts"]': {
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
  )
}
