import { DataGrid, type GridColDef } from '@mui/x-data-grid'
import type { CurrentAlert } from '../../contracts/alerts'
import { sensorLabels } from '../../contracts/common'
import { formatWibDateTime } from '../../lib/dateTime'
import { formatProvenance } from '../../components/data/provenance'
import { tokens } from '../../theme/tokens'
import { AlertLifecycleActions } from './AlertLifecycleActions'

export interface AttentionQueueGridProps {
  alerts: readonly CurrentAlert[]
}

const pageSizeOptions = [5, 10, 25, 50]

const columns: GridColDef<CurrentAlert>[] = [
  {
    field: 'device_id',
    headerName: 'Sensor',
    flex: 0.6,
    minWidth: 80,
    valueFormatter: (value) => sensorLabels[value as CurrentAlert['device_id']],
  },
  {
    field: 'status',
    headerName: 'Status',
    flex: 0.7,
    minWidth: 90,
    renderCell: ({ row }) => (row.status === 'detected' ? 'Active' : row.status),
  },
  {
    field: 'episode_start_ts',
    headerName: 'Episode start (WIB)',
    flex: 1.3,
    minWidth: 150,
    valueFormatter: (value) =>
      formatWibDateTime(value as CurrentAlert['episode_start_ts']),
  },
  {
    field: 'episode_end_ts',
    headerName: 'Episode end (WIB)',
    flex: 1.3,
    minWidth: 150,
    valueFormatter: (value) =>
      formatWibDateTime(value as CurrentAlert['episode_end_ts']),
  },
  {
    field: 'anomalous_window_count',
    headerName: 'Windows',
    flex: 0.5,
    minWidth: 90,
  },
  {
    field: 'peak_score',
    headerName: 'Peak score',
    flex: 0.7,
    minWidth: 110,
  },
  {
    field: 'detection_basis',
    headerName: 'Detection basis',
    flex: 1.1,
    minWidth: 140,
    sortable: false,
    valueFormatter: (value) =>
      formatProvenance(value as CurrentAlert['detection_basis']),
  },
  {
    field: 'actions',
    headerName: 'Action',
    flex: 1.4,
    minWidth: 200,
    sortable: false,
    filterable: false,
    renderCell: ({ row }) => <AlertLifecycleActions alert={row} />,
  },
]

export function AttentionQueueGrid({ alerts }: AttentionQueueGridProps) {
  return (
    <DataGrid<CurrentAlert>
      aria-label="Attention queue table"
      rows={alerts as CurrentAlert[]}
      columns={columns}
      getRowId={(row) => row.alert_id}
      getRowHeight={() => 'auto'}
      initialState={{
        pagination: { paginationModel: { page: 0, pageSize: 5 } },
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
        '& .MuiDataGrid-cell[data-field="actions"]': {
          alignItems: 'stretch',
          overflow: 'visible',
          py: 1,
        },
        '& .MuiDataGrid-cell[data-field="device_id"], & .MuiDataGrid-cell[data-field="episode_start_ts"], & .MuiDataGrid-cell[data-field="episode_end_ts"], & .MuiDataGrid-cell[data-field="anomalous_window_count"], & .MuiDataGrid-cell[data-field="peak_score"]': {
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
