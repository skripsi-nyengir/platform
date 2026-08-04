import type { Theme } from '@mui/material/styles'

export function getChartColors(theme: Theme) {
  return {
    temperature: theme.palette.primary.main,
    humidity: theme.palette.success.main,
    anomalyScore: theme.palette.warning.main,
    outlier: theme.palette.error.main,
    threshold: theme.palette.text.secondary,
    normalPoint: theme.palette.info.main,
    reconstructionError: theme.palette.app.reconstructionError,
  } as const
}

export function formatChartNumber(
  value: number | null | undefined,
  precision: number,
): string {
  return typeof value === 'number' && Number.isFinite(value)
    ? value.toFixed(precision)
    : '—'
}
