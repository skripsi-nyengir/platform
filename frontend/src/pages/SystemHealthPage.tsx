import { Stack, Typography } from '@mui/material'
import { ApiErrorPanel } from '../components/states/ApiErrorPanel'
import { PanelSkeleton } from '../components/states/PanelSkeleton'
import { resolveStatusDisplayMeta } from '../features/systemHealth/displayMeta'
import { SystemHealthDashboard } from '../features/systemHealth/SystemHealthDashboard'
import { useSystemStatusQuery } from '../features/systemHealth/query'

export function SystemHealthPage() {
  const status = useSystemStatusQuery()
  return (
    <Stack spacing={6}>
      <Stack spacing={0.5}>
        <Typography variant="h1">System Health</Typography>
        <Typography color="text.secondary" variant="body2" sx={{ maxWidth: '68ch' }}>
          Status layanan runtime dan aliran live telemetry untuk B02F3872.
        </Typography>
      </Stack>

      {status.data === undefined ? (
        status.isError ? (
          <ApiErrorPanel error={status.error} onRetry={() => void status.refetch()} />
        ) : (
          <PanelSkeleton label="Loading system status" />
        )
      ) : (
        <SystemHealthDashboard
          snapshot={status.data}
          display={resolveStatusDisplayMeta(status.data, status.dataUpdatedAt, status.isRefetchError)}
          onRetry={() => void status.refetch()}
        />
      )}
    </Stack>
  )
}
