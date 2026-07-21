import { createTheme } from '@mui/material/styles'
import type {} from '@mui/x-charts/themeAugmentation'
import type {} from '@mui/x-data-grid/themeAugmentation'
import { tokens } from './tokens'

export const theme = createTheme({
  spacing: tokens.spacing.unit,
  shape: {
    borderRadius: tokens.radius.sm,
  },
  palette: {
    mode: 'dark',
    primary: {
      main: tokens.color.signal,
    },
    success: {
      main: tokens.color.success,
    },
    warning: {
      main: tokens.color.warning,
    },
    error: {
      main: tokens.color.alarm,
    },
    info: {
      main: tokens.color.offline,
      light: tokens.color.offlineSoft,
    },
    text: {
      primary: tokens.color.ink,
      secondary: tokens.color.inkMuted,
    },
    divider: tokens.color.rule,
    background: {
      default: tokens.color.paper,
      paper: tokens.color.surface,
    },
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
      styleOverrides: {
        html: {
          colorScheme: 'dark',
          backgroundColor: tokens.color.paper,
        },
        body: {
          margin: 0,
          color: tokens.color.ink,
          backgroundColor: tokens.color.paper,
        },
        '#root': {
          minWidth: 0,
          minHeight: '100vh',
        },
        '*, *::before, *::after': {
          boxSizing: 'border-box',
        },
        'a:focus-visible, button:focus-visible, [tabindex]:focus-visible': {
          outline: `${tokens.focus.width}px solid ${tokens.color.signal}`,
          outlineOffset: tokens.focus.offset,
        },
      },
    },
    MuiDrawer: {
      styleOverrides: {
        paper: {
          borderRight: 'none',
          backgroundColor: tokens.color.paper,
          color: tokens.color.ink,
        },
      },
    },
    MuiListItemButton: {
      styleOverrides: {
        root: {
          minHeight: tokens.size.control,
          borderLeft: `${tokens.size.activeRule}px solid transparent`,
          color: tokens.color.sidebarText,
          '&:hover': {
            backgroundColor: tokens.color.sidebarHover,
            color: tokens.color.ink,
          },
          '&.active': {
            borderLeftColor: tokens.color.signal,
            backgroundColor: tokens.color.sidebarActive,
            color: tokens.color.ink,
          },
          '&.Mui-focusVisible': {
            outline: `${tokens.focus.width}px solid ${tokens.color.signal}`,
            outlineOffset: -tokens.focus.width,
          },
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          backgroundImage: 'none',
          borderColor: tokens.color.rule,
        },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: {
          fontWeight: 600,
        },
        colorSuccess: {
          backgroundColor: tokens.color.successSoft,
          color: tokens.color.successText,
        },
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
        outlined: {
          borderColor: tokens.color.rule,
          boxShadow: 'none',
        },
      },
    },
    MuiDataGrid: {
      styleOverrides: {
        root: {
          borderColor: tokens.color.ruleStrong,
        },
        columnHeaderTitle: {
          fontWeight: 700,
        },
      },
    },
  },
})
