import type { Theme } from '@mui/material/styles'
import { describe, expect, it } from 'vitest'
import { theme } from '../../theme/theme'
import { formatChartNumber, getChartColors } from './muiChartTheme'

function themeFor(scheme: 'light' | 'dark'): Theme {
  const colorSystem = theme.colorSchemes[scheme]
  if (colorSystem === undefined) throw new Error(`Missing ${scheme} color scheme`)
  return { ...theme, ...colorSystem }
}

describe('getChartColors', () => {
  it('maps chart roles to distinct active light and dark semantic palettes', () => {
    const darkColors = getChartColors(themeFor('dark'))
    const lightColors = getChartColors(themeFor('light'))

    expect(darkColors).toEqual({
      temperature: '#4C8DFF',
      humidity: '#4EC7A5',
      anomalyScore: '#F2B84B',
      outlier: '#FF6B6B',
      threshold: '#9BA8B4',
      normalPoint: '#9AA7B2',
      reconstructionError: '#F06292',
    })
    expect(lightColors).toEqual({
      temperature: '#2563EB',
      humidity: '#147D64',
      anomalyScore: '#9A6700',
      outlier: '#C9374C',
      threshold: '#52606D',
      normalPoint: '#52606D',
      reconstructionError: '#AD1457',
    })
    expect(lightColors).not.toEqual(darkColors)
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
