export interface AppPalette {
  signalSoft: string
  successSoft: string
  successText: string
  warningSoft: string
  offlineSoft: string
  strongDivider: string
  sidebarDivider: string
  sidebarText: string
  sidebarMuted: string
  sidebarHover: string
  sidebarActive: string
  reconstructionError: string
}

declare module '@mui/material/styles' {
  interface CssThemeVariables {
    enabled: true
  }

  interface Palette {
    app: AppPalette
  }

  interface PaletteOptions {
    app?: AppPalette
  }
}
