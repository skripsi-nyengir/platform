import { DataGrid, type GridColDef } from '@mui/x-data-grid'
import type { CurrentAlert, CurrentAlertsResponse } from '../../contracts/alerts'
import { tokens } from '../../theme/tokens'
import { AlertLifecycleActions } from './AlertLifecycleActions'

export interface AlertsGridProps {
  response: CurrentAlertsResponse
  page: number
  onPageChange: (page: number) => void
  onSelectAlert: (alertId: string) => void
  onPageSizeChange?: (pageSize: number) => void
}

const pageSizeOptions = [10, 25, 50, 100]

const columnWidths = {
  alert_id: { flex: 1.25, minWidth: 150 },
  device_id: { flex: 0.7, minWidth: 80 },
  status: { flex: 0.9, minWidth: 105 },
  latest_event_ts: { flex: 1.5, minWidth: 190 },
  actions: { flex: 1.65, minWidth: 230 },
} as const

const columns: GridColDef<CurrentAlert>[] = [
  { field: 'alert_id', headerName: 'Alert ID', ...columnWidths.alert_id },
  { field: 'device_id', headerName: 'Sensor', ...columnWidths.device_id },
  {
    field: 'status',
    headerName: 'Status',
    ...columnWidths.status,
    renderCell: ({ row }) => row.status === 'detected' ? 'Active' : row.status,
  },
  { field: 'latest_event_ts', headerName: 'Last event', ...columnWidths.latest_event_ts },
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
        '& .MuiDataGrid-cell[data-field="alert_id"], & .MuiDataGrid-cell[data-field="device_id"], & .MuiDataGrid-cell[data-field="latest_event_ts"]': {
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
