import '@testing-library/jest-dom/vitest'
import { describe, expect, it } from 'vitest'
import { screen } from '@testing-library/react'
import { renderApp } from '../test/renderApp'

describe('SensorDetailPage', () => {
  it('renders B02 history with data-driven score provenance', async () => {
    renderApp('/sensors/b02f3872-ruang-produksi')
    expect(await screen.findByText(/sesuai provenance API/)).toBeVisible()
    expect(await screen.findByText('Simulasi preview')).toBeVisible()
    expect(screen.getByRole('textbox', { name: 'From' })).toHaveValue('2026-02-01T00:00:00')
    expect(screen.getByRole('textbox', { name: 'To' })).toHaveValue('2026-06-01T00:00:00')
    expect(screen.getByRole('combobox', { name: 'Bucket' })).toHaveValue('1d')
    expect(await screen.findByText('120 bounded telemetry records')).toBeVisible()
    expect(screen.queryByText(/View truncated/)).not.toBeInTheDocument()
  })

  it('shows a bounded-data notice only when telemetry has a next cursor', async () => {
    renderApp('/sensors/b02f3872-ruang-produksi?bucket=15m')

    expect(await screen.findByText('2000 bounded telemetry records')).toBeVisible()
    expect(screen.getByRole('note')).toHaveTextContent(
      'View truncated. Pilih rentang lebih sempit atau bucket lebih kasar untuk melihat seluruh data.',
    )
  })
})
