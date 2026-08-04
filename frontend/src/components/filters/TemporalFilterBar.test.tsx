import '@testing-library/jest-dom/vitest'
import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { TemporalFilterBar } from './TemporalFilterBar'

describe('TemporalFilterBar', () => {
  it('offers only the B02 public sensor', () => {
    render(<TemporalFilterBar value={{
      sensor: 'b02f3872-ruang-produksi',
      range: '1h',
    }} onChange={vi.fn()} />)
    expect(screen.getByRole('option', { name: 'B02' })).toBeVisible()
    expect(screen.queryByText('talpha-1')).not.toBeInTheDocument()
  })

  it('offers the rolling live ranges as one labelled control', () => {
    render(<TemporalFilterBar value={{
      sensor: 'b02f3872-ruang-produksi',
      range: '6h',
    }} onChange={vi.fn()} />)

    expect(screen.getByRole('combobox', { name: 'Range' })).toHaveValue('6h')
    expect(screen.getAllByRole('option').map((option) => option.textContent)).toEqual([
      'B02',
      'Last 1 minute',
      'Last 5 minutes',
      'Last 10 minutes',
      'Last 15 minutes',
      'Last 30 minutes',
      'Last 1 hour',
      'Last 6 hours',
      'Last 12 hours',
      'Last 24 hours',
      'Custom',
    ])
    expect(screen.queryByRole('textbox', { name: 'From' })).not.toBeInTheDocument()
    expect(screen.queryByRole('textbox', { name: 'To' })).not.toBeInTheDocument()
  })

  it('uses dependency-free text inputs for custom live bounds', () => {
    render(<TemporalFilterBar value={{
      sensor: 'b02f3872-ruang-produksi',
      range: 'custom',
      from: '2026-07-31T06:00:00',
      to: '2026-07-31T08:00:00',
    }} onChange={vi.fn()} />)

    expect(screen.getByRole('textbox', { name: 'From' })).toHaveValue('2026-07-31T06:00:00')
    expect(screen.getByRole('textbox', { name: 'To' })).toHaveValue('2026-07-31T08:00:00')
  })
})
