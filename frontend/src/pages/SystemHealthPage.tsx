import { Stack, Typography } from '@mui/material'
import { ApiErrorPanel } from '../components/states/ApiErrorPanel'
import { PanelSkeleton } from '../components/states/PanelSkeleton'
import { PollingFailureNotice } from '../components/states/PollingFailureNotice'
import { ServiceStatusTable } from '../features/systemHealth/ServiceStatusTable'
import { StatusSnapshot } from '../features/systemHealth/StatusSnapshot'
import { useSystemStatusQuery } from '../features/systemHealth/query'

export function SystemHealthPage() {
  const status = useSystemStatusQuery()
  const displayedAt = status.dataUpdatedAt === 0
    ? undefined
    : new Date(status.dataUpdatedAt).toISOString()
  const pollAgeSeconds = Math.max(
    0,
    Math.floor(
      ((status.isRefetchError ? status.errorUpdatedAt : status.dataUpdatedAt) - status.dataUpdatedAt)
        / 1_000,
    ),
  )

  return (
    <Stack spacing={6}>
      <Stack spacing={0.5}>
        <Typography variant="h1">System Health</Typography>
        <Typography color="text.secondary" variant="body2" sx={{ maxWidth: '68ch' }}>
          Status komponen preview replay untuk B02F3872.
        </Typography>
        <Typography color="text.secondary" variant="body2" sx={{ maxWidth: '68ch' }}>
          Simulasi preview dipisahkan dari kesiapan artifact asli.
        </Typography>
      </Stack>

      {status.data === undefined || displayedAt === undefined ? (
        status.isError ? (
          <ApiErrorPanel error={status.error} onRetry={() => void status.refetch()} />
        ) : (
          <PanelSkeleton label="Loading system status" />
        )
      ) : (
        <>
          {status.isRefetchError ? (
            <Stack spacing={1}>
              <PollingFailureNotice
                resource="System status"
                lastUpdated={displayedAt}
                onRetry={() => void status.refetch()}
              />
              <Typography role="status" color="warning.main" variant="body2">
                Current reachability: Unknown
              </Typography>
            </Stack>
          ) : null}
          <StatusSnapshot
            snapshot={status.data}
            displayedAt={displayedAt}
            pollAgeSeconds={pollAgeSeconds}
          />
          <ServiceStatusTable services={status.data.services} />
        </>
      )}
    </Stack>
  )
}
