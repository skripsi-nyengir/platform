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
    const assignedFillStyles: string[] = []
    const context = {
      clearRect: vi.fn(),
      fillRect: vi.fn(),
    }
    Object.defineProperty(context, 'fillStyle', {
      get: () => assignedFillStyles.at(-1) ?? '',
      set: (value: string) => assignedFillStyles.push(value),
    })
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(
      context as unknown as CanvasRenderingContext2D,
    )
    const user = userEvent.setup()
    const matrix = [[1, 2], [3, 4]] as const
    const initialColors = ['#000000', '#111111', '#222222', '#333333'] as const
    const initialColorSet = new Set<string>(initialColors)

    const { rerender } = render(
      <ThemeProvider theme={theme}>
        <CanvasHeatmap
          title="Resolved raw — n=10"
          description="Matriks dua kali dua dengan satu skala bersama."
          temperatureEdges={[0, 30, 60]}
          humidityEdges={[0, 50, 100]}
          matrix={matrix}
          maximumCount={4}
          colors={initialColors}
        />
      </ThemeProvider>,
    )

    expect(screen.getByRole('img', { name: 'Resolved raw — n=10' }).getAttribute('width')).toBe('2')
    expect(context.clearRect).toHaveBeenCalledWith(0, 0, 2, 2)
    expect(context.fillRect).toHaveBeenCalledTimes(4)
    expect(assignedFillStyles).toHaveLength(4)
    expect(assignedFillStyles.every((color) => initialColorSet.has(color))).toBe(true)
    expect(screen.getByRole('img', { name: 'Legenda jumlah pasangan skala logaritmik dari 0 sampai 4' })).not.toBeNull()

    const lightColors = ['#E9EEF2', '#E7EFFF', '#2563EB', '#17202A'] as const
    const lightColorSet = new Set<string>(lightColors)
    rerender(
      <ThemeProvider theme={theme}>
        <CanvasHeatmap
          title="Resolved raw — n=10"
          description="Matriks dua kali dua dengan satu skala bersama."
          temperatureEdges={[0, 30, 60]}
          humidityEdges={[0, 50, 100]}
          matrix={matrix}
          maximumCount={4}
          colors={lightColors}
        />
      </ThemeProvider>,
    )

    expect(context.clearRect).toHaveBeenCalledTimes(2)
    expect(context.fillRect).toHaveBeenCalledTimes(8)
    expect(assignedFillStyles.slice(4)).toHaveLength(4)
    expect(assignedFillStyles.slice(4).every((color) => lightColorSet.has(color))).toBe(true)

    await user.click(screen.getByRole('button', { name: 'Lihat data Resolved raw — n=10' }))
    expect(await screen.findByRole('dialog', { name: 'Resolved raw — n=10 — seluruh sel' })).not.toBeNull()
    expect(screen.getByText('4 bounded records returned')).not.toBeNull()
    expect(screen.getByRole('columnheader', { name: 'Jumlah pasangan' })).not.toBeNull()
  })
})
