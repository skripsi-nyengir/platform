import { ThemeProvider } from '@mui/material/styles'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { theme } from '../../theme/theme'
import { CanvasHeatmap } from './CanvasHeatmap'

afterEach(() => {
  vi.restoreAllMocks()
})

describe('CanvasHeatmap', () => {
  it('draws every static cell and exposes complete source rows in the bounded dialog', async () => {
    const context = {
      clearRect: vi.fn(),
      fillRect: vi.fn(),
      fillStyle: '',
    }
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(
      context as unknown as CanvasRenderingContext2D,
    )
    const user = userEvent.setup()

    render(
      <ThemeProvider theme={theme}>
        <CanvasHeatmap
          title="Resolved raw — n=10"
          description="Matriks dua kali dua dengan satu skala bersama."
          temperatureEdges={[0, 30, 60]}
          humidityEdges={[0, 50, 100]}
          matrix={[[1, 2], [3, 4]]}
          maximumCount={4}
          colors={['#000000', '#111111', '#222222', '#333333']}
        />
      </ThemeProvider>,
    )

    expect(screen.getByRole('img', { name: 'Resolved raw — n=10' }).getAttribute('width')).toBe('2')
    expect(context.clearRect).toHaveBeenCalledWith(0, 0, 2, 2)
    expect(context.fillRect).toHaveBeenCalledTimes(4)
    expect(screen.getByRole('img', { name: 'Legenda jumlah pasangan skala logaritmik dari 0 sampai 4' })).not.toBeNull()

    await user.click(screen.getByRole('button', { name: 'Lihat data Resolved raw — n=10' }))
    expect(await screen.findByRole('dialog', { name: 'Resolved raw — n=10 — seluruh sel' })).not.toBeNull()
    expect(screen.getByText('4 bounded records returned')).not.toBeNull()
    expect(screen.getByRole('columnheader', { name: 'Jumlah pasangan' })).not.toBeNull()
  })
})
