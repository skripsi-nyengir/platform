import { CssBaseline } from '@mui/material'
import { ThemeProvider } from '@mui/material/styles'
import { QueryClientProvider } from '@tanstack/react-query'
import type { PropsWithChildren } from 'react'
import {
  THEME_COLOR_SCHEME_STORAGE_KEY,
  THEME_MODE_STORAGE_KEY,
  theme,
} from '../theme/theme'
import { queryClient } from './queryClient'

export function AppProviders({ children }: PropsWithChildren) {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider
        theme={theme}
        defaultMode="system"
        modeStorageKey={THEME_MODE_STORAGE_KEY}
        colorSchemeStorageKey={THEME_COLOR_SCHEME_STORAGE_KEY}
        noSsr
        disableTransitionOnChange
        forceThemeRerender
      >
        <CssBaseline enableColorScheme />
        {children}
      </ThemeProvider>
    </QueryClientProvider>
  )
}
