import { createTheme } from '@mui/material/styles'
import { describe, expect, it } from 'vitest'
import { formatChartNumber, getChartColors } from './muiChartTheme'

describe('getChartColors', () => {
  it('maps chart roles to the active semantic palette', () => {
    const theme = createTheme({
      palette: {
        primary: { main: '#101010' },
        success: { main: '#202020' },
        warning: { main: '#303030' },
        error: { main: '#404040' },
        info: { main: '#505050' },
        text: { secondary: '#606060' },
      },
    })

    expect(getChartColors(theme)).toEqual({
      temperature: theme.palette.primary.main,
      humidity: theme.palette.success.main,
      anomalyScore: theme.palette.warning.main,
      outlier: theme.palette.error.main,
      threshold: theme.palette.text.secondary,
      normalPoint: theme.palette.info.main,
    })
  })
})

describe('formatChartNumber', () => {
  it('formats finite values with the requested precision', () => {
    expect(formatChartNumber(12.345, 2)).toBe('12.35')
    expect(formatChartNumber(4, 0)).toBe('4')
    expect(formatChartNumber(-0.5, 3)).toBe('-0.500')
  })

  it('returns an em dash for missing and non-finite values', () => {
    const unavailable = [null, undefined, Number.NaN, Number.POSITIVE_INFINITY, Number.NEGATIVE_INFINITY]

    expect(unavailable.map((value) => formatChartNumber(value, 2))).toEqual([
      '—',
      '—',
      '—',
      '—',
      '—',
    ])
  })
})
