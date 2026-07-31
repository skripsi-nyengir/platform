import { Paper, Stack, Typography } from '@mui/material'
import { ApiErrorPanel } from '../../components/states/ApiErrorPanel'
import { PanelSkeleton } from '../../components/states/PanelSkeleton'
import { useAlertDetailQuery } from '../alerts/queries'

export function AlertEpisodeContext({ alertId }: { alertId: string }) {
  const detail = useAlertDetailQuery(alertId)

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
