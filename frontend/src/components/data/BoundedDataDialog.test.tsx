import { Button } from '@mui/material'
import { ThemeProvider } from '@mui/material/styles'
import type { GridColDef, GridRowId, GridValidRowModel } from '@mui/x-data-grid'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { theme } from '../../theme/theme'
import { tokens } from '../../theme/tokens'
import { BoundedDataDialog } from './BoundedDataDialog'

interface TestRow extends GridValidRowModel {
  id: GridRowId
  label: string
}

const rows: readonly TestRow[] = Object.freeze(
  Array.from({ length: 101 }, (_, index) => ({
    id: index + 1,
    label: `Record ${index + 1}`,
  })),
)
const columns: readonly GridColDef<TestRow>[] = Object.freeze([
  { field: 'label', headerName: 'Record' },
])

function DialogHarness({
  onClose = () => undefined,
  data = rows,
}: {
  onClose?: () => void
  data?: readonly TestRow[]
}) {
  const [open, setOpen] = useState(false)

  return (
    <ThemeProvider theme={theme}>
      <Button onClick={() => setOpen(true)}>Lihat data</Button>
      <BoundedDataDialog
        open={open}
        title="Bounded telemetry data"
        rows={data}
        returnedCount={data.length}
        columns={columns}
        onClose={() => {
          onClose()
          setOpen(false)
        }}
      />
    </ThemeProvider>
  )
}

describe('BoundedDataDialog', () => {
  it('is opened only by the caller and exposes a named display-only data dialog', async () => {
    const user = userEvent.setup()
    render(<DialogHarness />)

    const trigger = screen.getByRole('button', { name: 'Lihat data' })
    expect(screen.getAllByRole('button', { name: 'Lihat data' })).toHaveLength(1)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()

    await user.click(trigger)

    const dialog = screen.getByRole('dialog', { name: 'Bounded telemetry data' })
    expect(dialog).toHaveTextContent('101 bounded records returned')
    const grid = screen.getByRole('grid')
    expect(grid).toBeVisible()
    const gridRoot = grid.closest('.MuiDataGrid-root')
    if (!(gridRoot instanceof HTMLElement)) throw new Error('Data Grid root was not rendered')
    expect(gridRoot).toHaveStyle({ minWidth: '0px', '--DataGrid-headerHeight': '64px' })
    const columnHeader = screen.getByRole('columnheader', { name: 'Record' })
    expect(columnHeader).toBeVisible()
    const columnHeaderTitle = columnHeader.querySelector('.MuiDataGrid-columnHeaderTitle')
    if (!(columnHeaderTitle instanceof HTMLElement)) {
      throw new Error('Data Grid column header title was not rendered')
    }
    expect(columnHeaderTitle).toHaveStyle({
      lineHeight: '1.15',
      overflow: 'visible',
      textOverflow: 'clip',
      whiteSpace: 'normal',
    })
    const firstCell = screen.getByRole('gridcell', { name: 'Record 1' })
    expect(firstCell).toHaveStyle({
      fontFamily: tokens.font.data,
      fontVariantNumeric: 'tabular-nums',
      whiteSpace: 'normal',
    })
    expect(firstCell.closest('.MuiDataGrid-row')).toHaveStyle({ '--height': 'auto' })
    await user.dblClick(firstCell)
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
  })

  it('keeps Community pagination visible and makes the 101st row reachable', async () => {
    const user = userEvent.setup()
    render(<DialogHarness />)
    await user.click(screen.getByRole('button', { name: 'Lihat data' }))

    const nextPage = screen.getByRole('button', { name: /next page/i })
    expect(nextPage).toBeVisible()
    await user.click(nextPage)
    expect(await screen.findByRole('gridcell', { name: 'Record 101' })).toBeVisible()
  })

  it('exports the displayed rows as a downloadable CSV', async () => {
    const user = userEvent.setup()
    const createObjectURL = vi.fn(() => 'blob:csv')
    const revokeObjectURL = vi.fn()
    vi.stubGlobal('URL', { ...URL, createObjectURL, revokeObjectURL })
    render(<DialogHarness />)
    await user.click(screen.getByRole('button', { name: 'Lihat data' }))

    await user.click(screen.getByRole('button', { name: 'Export CSV' }))

    expect(createObjectURL).toHaveBeenCalledOnce()
    const blob = createObjectURL.mock.calls[0]?.[0] as unknown as Blob
    expect(blob).toBeInstanceOf(Blob)
    expect(blob.type).toContain('text/csv')
    vi.unstubAllGlobals()
  })

  it('disables CSV export when there is nothing to export', async () => {
    const user = userEvent.setup()
    render(<DialogHarness data={[]} />)
    await user.click(screen.getByRole('button', { name: 'Lihat data' }))

    expect(screen.getByRole('button', { name: 'Export CSV' })).toBeDisabled()
  })

  it('closes from the Close button and restores focus to the caller trigger', async () => {
    const user = userEvent.setup()
    const onClose = vi.fn()
    render(<DialogHarness onClose={onClose} />)
    const trigger = screen.getByRole('button', { name: 'Lihat data' })

    await user.click(trigger)
    await user.click(screen.getByRole('button', { name: 'Close' }))

    expect(onClose).toHaveBeenCalledOnce()
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(trigger).toHaveFocus()
  })

  it('contains focus and closes on Escape with focus restoration', async () => {
    const user = userEvent.setup()
    const onClose = vi.fn()
    render(<DialogHarness onClose={onClose} />)
    const trigger = screen.getByRole('button', { name: 'Lihat data' })

    await user.click(trigger)
    const dialog = screen.getByRole('dialog', { name: 'Bounded telemetry data' })
    expect(dialog.contains(document.activeElement)).toBe(true)

    screen.getByRole('button', { name: 'Close' }).focus()
    await user.tab()
    expect(dialog.contains(document.activeElement)).toBe(true)

    await user.keyboard('{Escape}')
    expect(onClose).toHaveBeenCalledOnce()
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(trigger).toHaveFocus()
  })
})
