import { getContrastRatio } from '@mui/material/styles'
import { describe, expect, it } from 'vitest'
import {
  THEME_COLOR_SCHEME_STORAGE_KEY,
  THEME_MODE_STORAGE_KEY,
  theme,
} from './theme'
import { tokens } from './tokens'

const expectedDark = {
  primary: '#4C8DFF',
  success: '#4EC7A5',
  warning: '#F2B84B',
  error: '#FF6B6B',
  info: '#9AA7B2',
  text: { primary: '#F3F6F8', secondary: '#9BA8B4' },
  background: { default: '#090D12', paper: '#111820' },
  divider: '#26323D',
  app: {
    signalSoft: '#172A47',
    successSoft: '#123A32',
    successText: '#A7E8D5',
    warningSoft: '#332716',
    offlineSoft: '#202A33',
    strongDivider: '#3C4A57',
    sidebarDivider: '#3C4A57',
    sidebarText: '#CBD4DC',
    sidebarMuted: '#81909D',
    sidebarHover: '#151F29',
    sidebarActive: '#192A3F',
    reconstructionError: '#F06292',
  },
} as const

const expectedLight = {
  primary: '#2563EB',
  success: '#147D64',
  warning: '#9A6700',
  error: '#C9374C',
  info: '#52606D',
  text: { primary: '#17202A', secondary: '#52606D' },
  background: { default: '#F6F8FA', paper: '#FFFFFF' },
  divider: '#D8E0E7',
  app: {
    signalSoft: '#E7EFFF',
    successSoft: '#E2F4ED',
    successText: '#17202A',
    warningSoft: '#FFF1CC',
    offlineSoft: '#E9EEF2',
    strongDivider: '#B8C4CE',
    sidebarDivider: '#B8C4CE',
    sidebarText: '#334155',
    sidebarMuted: '#64748B',
    sidebarHover: '#EDF2F7',
    sidebarActive: '#E7EFFF',
    reconstructionError: '#AD1457',
  },
} as const

function expectPalette(
  palette: (typeof theme.colorSchemes)['light']['palette'],
  expected: typeof expectedLight | typeof expectedDark,
) {
  expect(palette.primary.main).toBe(expected.primary)
  expect(palette.success.main).toBe(expected.success)
  expect(palette.warning.main).toBe(expected.warning)
  expect(palette.error.main).toBe(expected.error)
  expect(palette.info.main).toBe(expected.info)
  expect(palette.text).toMatchObject(expected.text)
  expect(palette.background).toMatchObject(expected.background)
  expect(palette.divider).toBe(expected.divider)
  expect(palette.app).toEqual(expected.app)
}

function resolveStyle(override: unknown, argument: never) {
  expect(typeof override).toBe('function')
  return (override as (input: never) => Record<string, unknown>)(argument)
}

describe('visual foundation theme', () => {
  it('defines the complete approved light and unchanged dark palettes', () => {
    expectPalette(theme.colorSchemes.dark.palette, expectedDark)
    expectPalette(theme.colorSchemes.light.palette, expectedLight)
    expect(theme.colorSchemes.dark.palette.mode).toBe('dark')
    expect(theme.colorSchemes.light.palette.mode).toBe('light')
    expect(theme.colorSchemeSelector).toBe('data')
    expect(THEME_MODE_STORAGE_KEY).toBe('adp-theme-mode')
    expect(THEME_COLOR_SCHEME_STORAGE_KEY).toBe('adp-theme-scheme')
  })

  it('preserves typography, shape, and layout tokens on the 4px base', () => {
    expect(tokens.spacing.unit).toBe(4)
    expect(tokens.size).toMatchObject({ sidebar: 264, sidebarCompact: 72, routeCanvas: 1600 })
    expect(theme.shape.borderRadius).toBe(4)
    expect(theme.typography.fontFamily).toBe(tokens.font.ui)
    expect(theme.typography.h1).toMatchObject({ fontSize: '1.75rem', lineHeight: '2rem' })
    expect(theme.typography.h2).toMatchObject({ fontSize: '1.125rem', lineHeight: '1.5rem' })
    expect(theme.typography.h3).toMatchObject({ fontSize: '0.9375rem', lineHeight: '1.25rem' })
    expect(theme.typography.body1).toMatchObject({ fontSize: '0.875rem', lineHeight: '1.25rem' })
    expect(theme.typography.body2).toMatchObject({ fontSize: '0.8125rem', lineHeight: '1.125rem' })
    expect(theme.typography.caption).toMatchObject({ fontSize: '0.75rem', lineHeight: '1rem' })
    expect(tokens).not.toHaveProperty('shadow')
    expect(tokens).not.toHaveProperty('motion')
  })

  it('meets key WCAG AA contrast ratios in both schemes', () => {
    for (const palette of [expectedLight, expectedDark]) {
      expect(getContrastRatio(palette.text.primary, palette.background.default)).toBeGreaterThanOrEqual(4.5)
      expect(getContrastRatio(palette.text.primary, palette.background.paper)).toBeGreaterThanOrEqual(4.5)
      expect(getContrastRatio(palette.text.secondary, palette.background.paper)).toBeGreaterThanOrEqual(4.5)
      expect(getContrastRatio(palette.app.sidebarText, palette.background.default)).toBeGreaterThanOrEqual(4.5)
      expect(getContrastRatio(palette.app.successText, palette.app.successSoft)).toBeGreaterThanOrEqual(4.5)
      expect(getContrastRatio(palette.primary, palette.background.paper)).toBeGreaterThanOrEqual(3)
      expect(getContrastRatio(palette.error, palette.background.paper)).toBeGreaterThanOrEqual(3)
    }
  })

  it('uses active CSS-variable palette roles in component overrides', () => {
    const drawerPaper = theme.components?.MuiDrawer?.styleOverrides?.paper
    const listItemRoot = theme.components?.MuiListItemButton?.styleOverrides?.root
    const cardRoot = theme.components?.MuiCard?.styleOverrides?.root
    const successChip = theme.components?.MuiChip?.styleOverrides?.colorSuccess
    const gridRoot = theme.components?.MuiDataGrid?.styleOverrides?.root

    expect(typeof drawerPaper).toBe('function')
    expect(typeof listItemRoot).toBe('function')
    expect(typeof cardRoot).toBe('function')
    expect(typeof successChip).toBe('function')
    expect(typeof gridRoot).toBe('function')

    const componentArgs = { theme, ownerState: {} } as never
    expect(resolveStyle(drawerPaper, componentArgs)).toMatchObject({
      backgroundColor: theme.vars.palette.background.default,
      color: theme.vars.palette.text.primary,
    })
    expect(resolveStyle(listItemRoot, componentArgs)).toMatchObject({
      color: theme.vars.palette.app.sidebarText,
      '&:hover': { backgroundColor: theme.vars.palette.app.sidebarHover },
      '&.active': { backgroundColor: theme.vars.palette.app.sidebarActive },
    })
    expect(resolveStyle(cardRoot, componentArgs)).toMatchObject({
      borderColor: theme.vars.palette.divider,
    })
    expect(resolveStyle(successChip, componentArgs)).toMatchObject({
      backgroundColor: theme.vars.palette.app.successSoft,
      color: theme.vars.palette.app.successText,
    })
    expect(resolveStyle(gridRoot, componentArgs)).toMatchObject({
      borderColor: theme.vars.palette.app.strongDivider,
    })
  })

  it('does not impose or mask document-level horizontal overflow', () => {
    const baseline = theme.components?.MuiCssBaseline?.styleOverrides
    expect(typeof baseline).toBe('function')
    const styles = resolveStyle(baseline, theme as never)
    expect(styles).toMatchObject({
      body: { margin: 0 },
      '#root': { minWidth: 0, minHeight: '100vh' },
    })
    expect(styles.body).not.toHaveProperty('minWidth')
    expect(styles.body).not.toHaveProperty('overflowX')
    expect(styles.html).not.toHaveProperty('overflowX')
  })
})
