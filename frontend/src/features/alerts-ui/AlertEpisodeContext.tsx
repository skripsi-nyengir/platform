import { Box, Paper, Stack, Typography } from '@mui/material'
import { ApiErrorPanel } from '../../components/states/ApiErrorPanel'
import { PanelSkeleton } from '../../components/states/PanelSkeleton'
import { tokens } from '../../theme/tokens'
import { useAlertDetailQuery } from '../alerts/queries'

export interface AlertEpisodeContextProps {
  alertId: string
  compact?: boolean
}

const technicalTextSx = {
  fontFamily: tokens.font.data,
  fontVariantNumeric: 'tabular-nums',
} as const

export function AlertEpisodeContext({ alertId, compact = false }: AlertEpisodeContextProps) {
  const detail = useAlertDetailQuery(alertId)

  if (compact) {
    return (
      <Box component="section" aria-label="Episode context">
        <Stack spacing={1}>
          <Typography variant="h4">Episode context</Typography>
          {detail.data === undefined ? (
            detail.isError ? (
              <ApiErrorPanel error={detail.error} onRetry={() => void detail.refetch()} />
            ) : (
              <PanelSkeleton label="Loading episode context" />
            )
          ) : (
            <Box
              component="dl"
              sx={{
                display: 'grid',
                gap: 2,
                gridTemplateColumns: {
                  xs: 'minmax(0, 1fr)',
                  md: 'repeat(3, minmax(0, 1fr))',
                },
                m: 0,
              }}
            >
              <Box>
                <Typography component="dt" variant="caption" color="text.secondary">
                  Context before
                </Typography>
                <Typography component="dd" variant="body2" sx={{ m: 0 }}>
                  <Box component="span" sx={technicalTextSx}>{detail.data.context_before.length}</Box>
                  {' source readings before the episode'}
                </Typography>
              </Box>
              <Box>
                <Typography component="dt" variant="caption" color="text.secondary">
                  Episode points
                </Typography>
                <Typography component="dd" variant="body2" sx={{ m: 0 }}>
                  <Box component="span" sx={technicalTextSx}>{detail.data.episode_points.length}</Box>
                  {' anomalous episode windows'}
                </Typography>
              </Box>
              <Box>
                <Typography component="dt" variant="caption" color="text.secondary">
                  Recovery points
                </Typography>
                <Typography component="dd" variant="body2" sx={{ m: 0 }}>
                  <Box component="span" sx={technicalTextSx}>{detail.data.recovery_points.length}</Box>
                  {' persisted recovery windows'}
                </Typography>
              </Box>
            </Box>
          )}
        </Stack>
      </Box>
    )
  }

  return (
    <Paper component="section" aria-label="Episode context" variant="outlined" sx={{ p: 2 }}>
      <Stack spacing={1}>
        <Typography variant="h2">Episode context</Typography>
        {detail.data === undefined ? (
          detail.isError ? (
            <ApiErrorPanel error={detail.error} onRetry={() => void detail.refetch()} />
          ) : (
            <PanelSkeleton label="Loading episode context" />
          )
        ) : (
          <Stack spacing={0.5}>
            <Typography variant="body2">
              {detail.data.context_before.length} source readings before the episode
            </Typography>
            <Typography variant="body2">
              {detail.data.episode_points.length} anomalous episode windows
            </Typography>
            <Typography variant="body2">
              {detail.data.recovery_points.length} persisted recovery windows
            </Typography>
          </Stack>
        )}
      </Stack>
    </Paper>
  )
}
