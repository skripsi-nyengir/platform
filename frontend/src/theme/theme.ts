import { createTheme } from '@mui/material/styles'
import type {} from '@mui/x-charts/themeAugmentation'
import type {} from '@mui/x-data-grid/themeAugmentation'
import type { AppPalette } from './mui'
import { tokens } from './tokens'

export const THEME_MODE_STORAGE_KEY = 'adp-theme-mode'
export const THEME_COLOR_SCHEME_STORAGE_KEY = 'adp-theme-scheme'

type SchemeColors = typeof tokens.color.dark | typeof tokens.color.light

function appPalette(colors: SchemeColors): AppPalette {
  return {
    signalSoft: colors.signalSoft,
    successSoft: colors.successSoft,
    successText: colors.successText,
    warningSoft: colors.warningSoft,
    offlineSoft: colors.offlineSoft,
    strongDivider: colors.ruleStrong,
    sidebarDivider: colors.ruleStrong,
    sidebarText: colors.sidebarText,
    sidebarMuted: colors.sidebarMuted,
    sidebarHover: colors.sidebarHover,
    sidebarActive: colors.sidebarActive,
    reconstructionError: colors.reconstructionError,
  }
}

function palette(colors: SchemeColors) {
  return {
    primary: { main: colors.signal },
    success: { main: colors.success },
    warning: { main: colors.warning },
    error: { main: colors.alarm },
    info: { main: colors.offline, light: colors.offlineSoft },
    text: { primary: colors.ink, secondary: colors.inkMuted },
    divider: colors.rule,
    background: { default: colors.paper, paper: colors.surface },
    app: appPalette(colors),
  }
}

export const theme = createTheme({
  cssVariables: {
    colorSchemeSelector: 'data',
  },
  colorSchemes: {
    light: { palette: palette(tokens.color.light) },
    dark: { palette: palette(tokens.color.dark) },
  },
  spacing: tokens.spacing.unit,
  shape: {
    borderRadius: tokens.radius.sm,
  },
  typography: {
    fontFamily: tokens.font.ui,
    fontSize: tokens.font.base,
    h1: {
      fontSize: tokens.font.size.pageTitle,
      fontWeight: 700,
      lineHeight: tokens.font.lineHeight.pageTitle,
    },
    h2: {
      fontSize: tokens.font.size.sectionTitle,
      fontWeight: 700,
      lineHeight: tokens.font.lineHeight.sectionTitle,
    },
    h3: {
      fontSize: tokens.font.size.panelTitle,
      fontWeight: 700,
      lineHeight: tokens.font.lineHeight.panelTitle,
    },
    h4: {
      fontSize: tokens.font.size.panelTitle,
      fontWeight: 700,
      lineHeight: tokens.font.lineHeight.panelTitle,
    },
    body1: {
      fontSize: tokens.font.size.body,
      lineHeight: tokens.font.lineHeight.body,
    },
    body2: {
      fontSize: tokens.font.size.supporting,
      lineHeight: tokens.font.lineHeight.supporting,
    },
    caption: {
      fontSize: tokens.font.size.caption,
      lineHeight: tokens.font.lineHeight.caption,
    },
  },
  components: {
    MuiChartsDataProvider: {
      defaultProps: {
        disableKeyboardNavigation: true,
      },
    },
    MuiCssBaseline: {
      styleOverrides: (activeTheme) => ({
        html: {
          backgroundColor: activeTheme.vars.palette.background.default,
        },
        body: {
          margin: 0,
          color: activeTheme.vars.palette.text.primary,
          backgroundColor: activeTheme.vars.palette.background.default,
        },
        '#root': {
          minWidth: 0,
          minHeight: '100vh',
        },
        '*, *::before, *::after': {
          boxSizing: 'border-box',
        },
        'a:focus-visible, button:focus-visible, [tabindex]:focus-visible': {
          outline: `${tokens.focus.width}px solid ${activeTheme.vars.palette.primary.main}`,
          outlineOffset: tokens.focus.offset,
        },
      }),
    },
    MuiDrawer: {
      styleOverrides: {
        paper: ({ theme: activeTheme }) => ({
          borderRight: 'none',
          backgroundColor: activeTheme.vars.palette.background.default,
          color: activeTheme.vars.palette.text.primary,
        }),
      },
    },
    MuiListItemButton: {
      styleOverrides: {
        root: ({ theme: activeTheme }) => ({
          minHeight: tokens.size.control,
          borderLeft: `${tokens.size.activeRule}px solid transparent`,
          color: activeTheme.vars.palette.app.sidebarText,
          '&:hover': {
            backgroundColor: activeTheme.vars.palette.app.sidebarHover,
            color: activeTheme.vars.palette.text.primary,
          },
          '&.active': {
            borderLeftColor: activeTheme.vars.palette.primary.main,
            backgroundColor: activeTheme.vars.palette.app.sidebarActive,
            color: activeTheme.vars.palette.text.primary,
          },
          '&.Mui-focusVisible': {
            outline: `${tokens.focus.width}px solid ${activeTheme.vars.palette.primary.main}`,
            outlineOffset: -tokens.focus.width,
          },
        }),
      },
    },
    MuiCard: {
      styleOverrides: {
        root: ({ theme: activeTheme }) => ({
          backgroundImage: 'none',
          borderColor: activeTheme.vars.palette.divider,
        }),
      },
    },
    MuiChip: {
      styleOverrides: {
        root: {
          fontWeight: 600,
        },
        colorSuccess: ({ theme: activeTheme }) => ({
          backgroundColor: activeTheme.vars.palette.app.successSoft,
          color: activeTheme.vars.palette.app.successText,
        }),
      },
    },
    MuiButton: {
      defaultProps: {
        disableElevation: true,
      },
      styleOverrides: {
        root: {
          minHeight: tokens.size.control,
          fontWeight: 600,
          textTransform: 'none',
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        outlined: ({ theme: activeTheme }) => ({
          borderColor: activeTheme.vars.palette.divider,
          boxShadow: 'none',
        }),
      },
    },
    MuiDataGrid: {
      styleOverrides: {
        root: ({ theme: activeTheme }) => ({
          borderColor: activeTheme.vars.palette.app.strongDivider,
        }),
        columnHeaderTitle: {
          fontWeight: 700,
        },
      },
    },
  },
})
