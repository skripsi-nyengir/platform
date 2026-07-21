import { describe, expect, it } from 'vitest'
import { theme } from './theme'
import { tokens } from './tokens'

describe('visual foundation theme', () => {
  it('uses the approved dark palette and type scale on the 4px base', () => {
    expect(tokens.spacing.unit).toBe(4)
    expect(tokens.size.sidebarCompact).toBe(72)
    expect(theme.palette.mode).toBe('dark')
    expect(theme.palette.primary.main).toBe(tokens.color.signal)
    expect(theme.palette.success.main).toBe(tokens.color.success)
    expect(theme.palette.background).toMatchObject({
      default: tokens.color.paper,
      paper: tokens.color.surface,
    })
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

  it('does not impose or mask document-level horizontal overflow', () => {
    const baseline = theme.components?.MuiCssBaseline?.styleOverrides
    expect(baseline).toMatchObject({
      body: { margin: 0 },
      '#root': { minWidth: 0, minHeight: '100vh' },
    })
    expect(baseline).not.toHaveProperty('body.minWidth')
    expect(baseline).not.toHaveProperty('body.overflowX')
    expect(baseline).not.toHaveProperty('html.overflowX')
  })

  it('applies minimal shared MUI Card, Chip, Button, and Data Grid overrides', () => {
    expect(theme.components).toMatchObject({
      MuiChartsDataProvider: {
        defaultProps: { disableKeyboardNavigation: true },
      },
      MuiDrawer: {
        styleOverrides: {
          paper: { borderRight: 'none' },
        },
      },
      MuiCard: {
        styleOverrides: {
          root: { backgroundImage: 'none', borderColor: tokens.color.rule },
        },
      },
      MuiChip: {
        styleOverrides: {
          root: { fontWeight: 600 },
          colorSuccess: {
            backgroundColor: tokens.color.successSoft,
            color: tokens.color.successText,
          },
        },
      },
      MuiButton: {
        defaultProps: { disableElevation: true },
        styleOverrides: {
          root: { minHeight: tokens.size.control, fontWeight: 600, textTransform: 'none' },
        },
      },
      MuiPaper: {
        styleOverrides: {
          outlined: { borderColor: tokens.color.rule, boxShadow: 'none' },
        },
      },
      MuiDataGrid: {
        styleOverrides: {
          root: { borderColor: tokens.color.ruleStrong },
          columnHeaderTitle: { fontWeight: 700 },
        },
      },
    })
  })

  it('keeps selected navigation and keyboard focus visible without color alone', () => {
    expect(theme.components).toMatchObject({
      MuiListItemButton: {
        styleOverrides: {
          root: {
            borderLeft: `${tokens.size.activeRule}px solid transparent`,
            '&:hover': {
              backgroundColor: tokens.color.sidebarHover,
              color: tokens.color.ink,
            },
            '&.active': {
              borderLeftColor: tokens.color.signal,
              backgroundColor: tokens.color.sidebarActive,
            },
            '&.Mui-focusVisible': {
              outline: `${tokens.focus.width}px solid ${tokens.color.signal}`,
            },
          },
        },
      },
    })
  })
})
