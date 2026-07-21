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
  type GridColDef,
  type GridRowId,
  type GridValidRowModel,
} from '@mui/x-data-grid'
import { useId } from 'react'
import { tokens } from '../../theme/tokens'

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
        <Button onClick={onClose}>Close</Button>
      </DialogActions>
    </Dialog>
  )
}
