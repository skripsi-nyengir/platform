import '@testing-library/jest-dom/vitest'
import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { TemporalFilterBar } from './TemporalFilterBar'

describe('TemporalFilterBar', () => {
  it('offers only the B02 public sensor', () => {
    render(<TemporalFilterBar value={{
      sensor: 'b02f3872-ruang-produksi',
      from: '2026-02-01T00:00:00',
      to: '2026-03-01T00:00:00',
      bucket: '15m',
    }} onChange={vi.fn()} />)
    expect(screen.getByRole('option', { name: 'B02' })).toBeVisible()
    expect(screen.queryByText('talpha-1')).not.toBeInTheDocument()
  })
})
