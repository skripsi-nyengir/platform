import { Stack } from '@mui/material'
import { ThemeProvider } from '@mui/material/styles'
import { fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { ApiError } from '../../api/errors'
import type { UrlFilters } from '../../features/filters/urlFilters'
import { theme } from '../../theme/theme'
import { ApiErrorPanel } from '../states/ApiErrorPanel'
import { EmptyState } from '../states/EmptyState'
import { TemporalFilterBar } from './TemporalFilterBar'

const value: Pick<UrlFilters, 'sensor' | 'from' | 'to' | 'bucket'> = {
  sensor: 'n2',
  from: '2026-07-19T09:00:00+07:00',
  to: '2026-07-19T10:00:00+07:00',
  bucket: '15m',
}

function renderWithTheme(ui: ReactNode) {
  return render(<ThemeProvider theme={theme}>{ui}</ThemeProvider>)
}

describe('TemporalFilterBar', () => {
  it('renders compact labeled controls in keyboard order with text timestamp inputs', async () => {
    const user = userEvent.setup()
    renderWithTheme(<TemporalFilterBar value={value} onChange={vi.fn()} />)

    const filters = screen.getByRole('group', { name: 'Temporal filters' })
    const sensor = within(filters).getByRole('combobox', { name: 'Sensor' })
    const from = within(filters).getByRole('textbox', { name: 'From' })
    const to = within(filters).getByRole('textbox', { name: 'To' })
    const bucket = within(filters).getByRole('combobox', { name: 'Bucket' })

    expect(filters).toHaveStyle({ width: '100%', minWidth: '0px', flexWrap: 'wrap' })
    expect(sensor).toAppearBefore(from)
    expect(from).toAppearBefore(to)
    expect(to).toAppearBefore(bucket)
    expect(from).toHaveAttribute('type', 'text')
    expect(to).toHaveAttribute('type', 'text')
    expect(from).toHaveValue(value.from)
    expect(to).toHaveValue(value.to)
    for (const control of [sensor, from, to, bucket]) {
      expect(getComputedStyle(control).fontFamily).toContain('IBM Plex Mono')
      expect(getComputedStyle(control).fontVariantNumeric).toContain('tabular-nums')
    }

    await user.tab()
    expect(sensor).toHaveFocus()
    await user.tab()
    expect(from).toHaveFocus()
    await user.tab()
    expect(to).toHaveFocus()
    await user.tab()
    expect(bucket).toHaveFocus()
  })

  it('emits minimal offset-preserving From and To patches', () => {
    const onChange = vi.fn()
    renderWithTheme(<TemporalFilterBar value={value} onChange={onChange} />)

    fireEvent.change(screen.getByRole('textbox', { name: 'From' }), {
      target: { value: '2026-07-19T08:30:00+05:30' },
    })
    fireEvent.change(screen.getByRole('textbox', { name: 'To' }), {
      target: { value: '2026-07-19T11:30:00-04:00' },
    })

    expect(onChange).toHaveBeenNthCalledWith(1, { from: '2026-07-19T08:30:00+05:30' })
    expect(onChange).toHaveBeenNthCalledWith(2, { to: '2026-07-19T11:30:00-04:00' })
  })

  it('uses contract sensor and bucket options and conditionally clears the sensor', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    const { rerender } = renderWithTheme(
      <TemporalFilterBar value={value} onChange={onChange} />,
    )

    expect(screen.queryByRole('option', { name: 'All sensors' })).not.toBeInTheDocument()
    expect(screen.getAllByRole('option').map((option) => option.textContent)).toEqual([
      'n1',
      'n2',
      'n3',
      'n4',
      'n5',
      'n6',
      'raw',
      '1m',
      '5m',
      '15m',
      '1h',
      '1d',
    ])

    await user.selectOptions(screen.getByRole('combobox', { name: 'Sensor' }), 'n4')
    await user.selectOptions(screen.getByRole('combobox', { name: 'Bucket' }), '1h')
    expect(onChange).toHaveBeenNthCalledWith(1, { sensor: 'n4' })
    expect(onChange).toHaveBeenNthCalledWith(2, { bucket: '1h' })

    rerender(
      <ThemeProvider theme={theme}>
        <TemporalFilterBar value={value} onChange={onChange} allowAllSensors />
      </ThemeProvider>,
    )
    await user.selectOptions(screen.getByRole('combobox', { name: 'Sensor' }), '')
    expect(screen.getByRole('option', { name: 'All sensors' })).toBeInTheDocument()
    expect(onChange).toHaveBeenLastCalledWith({ sensor: undefined })
  })

  it('shows a disabled sensor placeholder when selection is required', () => {
    renderWithTheme(
      <TemporalFilterBar value={{ ...value, sensor: undefined }} onChange={vi.fn()} />,
    )

    expect(screen.getByRole('option', { name: 'Select sensor' })).toBeDisabled()
  })

  it('ignores invalid select values', () => {
    const onChange = vi.fn()
    renderWithTheme(<TemporalFilterBar value={value} onChange={onChange} />)

    fireEvent.change(screen.getByRole('combobox', { name: 'Sensor' }), {
      target: { value: 'n7' },
    })
    fireEvent.change(screen.getByRole('combobox', { name: 'Bucket' }), {
      target: { value: '2h' },
    })
    expect(onChange).not.toHaveBeenCalled()
  })

  it('remains independently composable beside empty and error states', () => {
    const error = new ApiError('network', 'Connection unavailable')
    renderWithTheme(
      <Stack direction="row" spacing={2}>
        <TemporalFilterBar value={value} onChange={vi.fn()} allowAllSensors />
        <EmptyState title="No records" detail="Adjust the temporal filters." />
        <ApiErrorPanel error={error} onRetry={vi.fn()} />
      </Stack>,
    )

    expect(screen.getByRole('group', { name: 'Temporal filters' })).toBeVisible()
    expect(screen.getByRole('status', { name: 'No records' })).toBeVisible()
    expect(screen.getByRole('alert')).toHaveTextContent('Connection unavailable')
  })
})
