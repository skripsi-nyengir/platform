import {
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Typography,
} from '@mui/material'
import {
  DataGrid,
  useGridApiRef,
  type GridColDef,
  type GridRowId,
  type GridValidRowModel,
} from '@mui/x-data-grid'
import { useId } from 'react'
import { tokens } from '../../theme/tokens'

function csvFileName(title: string): string {
  const slug = title
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
  const stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-')
  return `${slug || 'data'}-${stamp}`
}

export interface BoundedDataDialogProps<
  Row extends GridValidRowModel & { id: GridRowId },
> {
  open: boolean
  title: string
  rows: readonly Row[]
  returnedCount: number
  columns: readonly GridColDef<Row>[]
  onClose: () => void
}

export function BoundedDataDialog<
  Row extends GridValidRowModel & { id: GridRowId },
>({
  open,
  title,
  rows,
  returnedCount,
  columns,
  onClose,
}: BoundedDataDialogProps<Row>) {
  const titleId = useId()
  const countId = useId()
  const apiRef = useGridApiRef()

  return (
    <Dialog
      open={open}
      onClose={onClose}
      aria-labelledby={titleId}
      aria-describedby={countId}
      fullWidth
      maxWidth="lg"
    >
      <DialogTitle id={titleId}>{title}</DialogTitle>
      <DialogContent>
        <Typography id={countId} variant="body2">
          {returnedCount} bounded records returned
        </Typography>
        <DataGrid<Row>
          apiRef={apiRef}
          rows={rows}
          columns={columns}
          isCellEditable={() => false}
          rowSelection={false}
          disableRowSelectionOnClick
          pagination
          autoHeight
          columnHeaderHeight={64}
          getRowHeight={() => 'auto'}
          sx={{
            minWidth: 0,
            '& .MuiDataGrid-cell': {
              fontFamily: tokens.font.data,
              fontVariantNumeric: 'tabular-nums',
              alignItems: 'center',
              lineHeight: 1.3,
              py: 0.5,
              whiteSpace: 'normal',
            },
            '& .MuiDataGrid-columnHeaderTitle': {
              lineHeight: 1.15,
              overflow: 'visible',
              textOverflow: 'clip',
              whiteSpace: 'normal',
            },
          }}
        />
      </DialogContent>
      <DialogActions>
        <Button
          variant="outlined"
          disabled={rows.length === 0}
          onClick={() =>
            apiRef.current?.exportDataAsCsv({
              fileName: csvFileName(title),
              utf8WithBom: true,
            })
          }
        >
          Export CSV
        </Button>
        <Button onClick={onClose}>Close</Button>
      </DialogActions>
    </Dialog>
  )
}
